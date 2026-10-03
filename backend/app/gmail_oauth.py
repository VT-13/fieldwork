"""Gmail OAuth lifecycle; fixed endpoints, session-bound state and encrypted tokens."""
import base64
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode,urlsplit
import httpx
from fastapi import HTTPException
from sqlalchemy import delete
from . import credentials
from .auth import digest
from .config import settings
from .core import Blocked,aware
from .db import Session
from .models import Integration,OAuthGrant,Profile,State,DomainTransition,now
from .services import ledger
TOKEN='https://oauth2.googleapis.com/token'
PROFILE='https://gmail.googleapis.com/gmail/v1/users/me/profile'
SEND='https://www.googleapis.com/auth/gmail.send'
READ='https://www.googleapis.com/auth/gmail.readonly'
COMPOSE='https://www.googleapis.com/auth/gmail.compose'


class OAuthFailure(Exception):
    def __init__(self,reason):self.reason=reason


async def google_request(method,url,**kwargs):
    if url not in (TOKEN,PROFILE,'https://oauth2.googleapis.com/revoke'):
        raise Blocked('Unsupported OAuth endpoint')
    try:
        async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:
            r=await client.request(method,url,**kwargs)
    except httpx.HTTPError:
        raise OAuthFailure('provider_unavailable') from None
    try:payload=r.json() if r.content and url!='https://oauth2.googleapis.com/revoke' else {}
    except ValueError:raise OAuthFailure('invalid_response') from None
    if not isinstance(payload,dict):raise OAuthFailure('invalid_response')
    if r.status_code>=400:
        code=payload.get('error','')
        raise OAuthFailure('revoked' if code=='invalid_grant' or r.status_code==401 else 'provider_rejected')
    return payload


def expected_identity(db):
    profile=db.get(Profile,1)
    email=(profile.data.get('email','') if profile else '').strip().lower()
    configured=settings().sender_email.strip().lower()
    row=db.get(Integration,'gmail')
    if not profile or not profile.data.get('verified') or '@' not in email:
        raise Blocked('Verify the student profile email before connecting Gmail')
    if configured and email!=configured:raise Blocked('Profile and configured mailbox identity differ')
    if row and row.email and row.email.lower()!=email:raise Blocked('Existing Gmail identity differs; account transfer is unsupported')
    return email


def status(db):
    row=db.get(Integration,'gmail')
    mismatch=False
    if row and row.status=='connected':
        try:expected_identity(db)
        except Blocked:mismatch=True
    return {'provider':'gmail','status':'identity_mismatch' if mismatch else row.status if row else 'disconnected','email':row.email if row else '',
            'connected':bool(row and row.status=='connected' and row.encrypted_tokens and not mismatch),
            'drafts_enabled':bool(row and COMPOSE in row.scopes)}


def change(db,row,status,reason,clear=False):
    before=row.status
    if before!=status:db.add(DomainTransition(domain='integration',entity_id='gmail',from_state=before,to_state=status,reason=reason))
    row.status=status;row.updated_at=now()
    if clear:row.encrypted_tokens='';row.generation+=1
    # Credential loss never enables any communication, including scoped manual batches.
    if status!='connected':
        p=db.get(State,'outreach_policy')
        if p:p.value={**p.value,'enabled':False}
        batch=db.get(State,'manual_batch')
        if batch:batch.value={**batch.value,'enabled':False,'stop_requested':True}


def start(db,operator):
    cfg=settings();credentials.cipher()
    if not cfg.oauth_client_id:raise Blocked('Configure OAuth client credentials first')
    uri=urlsplit(cfg.oauth_redirect_uri);origin=urlsplit(cfg.app_origin)
    if (uri.scheme,uri.netloc)!=(origin.scheme,origin.netloc) or uri.path!='/api/integrations/gmail/callback' or uri.query or uri.fragment:
        raise Blocked('OAuth redirect must match the configured application origin and callback')
    ledger.lock(db);email=expected_identity(db);row=db.get(Integration,'gmail')
    if not row:row=Integration(id='gmail',email=email);db.add(row);db.flush()
    # Each new connect invalidates earlier connect attempts, not the existing working token.
    state=secrets.token_urlsafe(48);verifier=secrets.token_urlsafe(64)
    requested=[SEND,READ]+([COMPOSE] if cfg.gmail_drafts_enabled else [])
    db.execute(delete(OAuthGrant).where(OAuthGrant.expires_at<now()).execution_options(synchronize_session=False))
    db.execute(delete(OAuthGrant).where(OAuthGrant.session_hash==operator.session_hash))
    grant=OAuthGrant(state_hash=digest(state),session_hash=operator.session_hash,verifier_ciphertext=credentials.encrypt({'verifier':verifier}),expected_email=email,generation=row.generation,requested_scopes=requested,expires_at=now()+timedelta(minutes=10))
    db.add(grant);db.commit()
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    return {'url':'https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({'client_id':cfg.oauth_client_id,'redirect_uri':cfg.oauth_redirect_uri,'response_type':'code','scope':' '.join(requested),'state':state,'code_challenge':challenge,'code_challenge_method':'S256','access_type':'offline','prompt':'consent'})}


async def callback(db,operator,state,code,error='',request=google_request):
    ledger.lock(db);grant=db.get(OAuthGrant,digest(state))
    if not grant or grant.session_hash!=operator.session_hash or grant.consumed_at or aware(grant.expires_at)<=now():
        db.rollback();raise HTTPException(400,'Invalid or expired OAuth state')
    row=db.get(Integration,'gmail')
    if not row or row.generation!=grant.generation:db.rollback();raise HTTPException(400,'OAuth connection changed; start again')
    verifier=credentials.decrypt(grant.verifier_ciphertext)['verifier']
    expected=grant.expected_email;generation=grant.generation;scopes=grant.requested_scopes
    grant.consumed_at=now();grant.verifier_ciphertext='';db.commit()
    if error or not code:raise HTTPException(400,'Gmail authorization was not completed')
    try:
        tokens=await request('POST',TOKEN,data={'grant_type':'authorization_code','code':code,'client_id':settings().oauth_client_id,'client_secret':settings().oauth_client_secret,'redirect_uri':settings().oauth_redirect_uri,'code_verifier':verifier})
        if not tokens.get('refresh_token') or not tokens.get('access_token'):raise OAuthFailure('missing_offline_access')
        granted=tokens.get('scope','').split()
        if not all(s in granted for s in scopes):raise OAuthFailure('missing_scopes')
        who=await request('GET',PROFILE,headers={'Authorization':'Bearer '+tokens['access_token']})
        if str(who.get('emailAddress') or '').lower()!=expected:raise OAuthFailure('identity_mismatch')
    except OAuthFailure as exc:
        ledger.lock(db);row=db.get(Integration,'gmail')
        if row.generation==generation:change(db,row,'identity_mismatch' if exc.reason=='identity_mismatch' else 'reconnect_required',exc.reason,clear=True)
        db.commit();raise Blocked('Gmail authorization failed; reconnect with the verified account') from None
    ledger.lock(db);row=db.get(Integration,'gmail')
    if row.generation!=generation or expected_identity(db)!=expected:db.rollback();raise Blocked('Gmail authorization changed during connection')
    row.encrypted_tokens=credentials.encrypt({'refresh_token':tokens['refresh_token'],'access_token':tokens['access_token'],'expires_at':(now()+timedelta(seconds=min(int(tokens.get('expires_in',3600)),3600))).isoformat()})
    row.scopes=granted;row.email=expected;row.generation+=1;change(db,row,'connected','oauth_connected');db.commit()
    return status(db)


def require_connection(db,generation=None):
    row=db.get(Integration,'gmail')
    if not row or row.status!='connected' or not row.encrypted_tokens or not all(s in row.scopes for s in (SEND,READ)):
        raise Blocked('Gmail disconnected or needs reconnect')
    if generation is not None and row.generation!=generation:raise Blocked('Gmail authorization changed; reconnect before continuing')
    if expected_identity(db)!=row.email.lower():raise Blocked('Gmail identity mismatch')
    return row


def invalidate(reason):
    with Session() as db:
        ledger.lock(db);row=db.get(Integration,'gmail')
        if row:change(db,row,'identity_mismatch' if reason=='identity_mismatch' else 'reconnect_required',reason,clear=True)
        db.commit()


async def access(request=google_request):
    with Session() as db:
        row=require_connection(db);generation=row.generation;email=row.email
        try:tokens=credentials.decrypt(row.encrypted_tokens)
        except Blocked:
            row.generation+=1
            change(db,row,'reconnect_required','decrypt_failed',clear=False);db.commit();raise
    try:
        expires=__import__('datetime').datetime.fromisoformat(tokens.get('expires_at','1970-01-01T00:00:00+00:00'))
        if aware(expires)<=now()+timedelta(seconds=60):
            renewed=await request('POST',TOKEN,data={'grant_type':'refresh_token','client_id':settings().oauth_client_id,'client_secret':settings().oauth_client_secret,'refresh_token':tokens['refresh_token']})
            if not renewed.get('access_token'):raise OAuthFailure('invalid_refresh')
            tokens={**tokens,**{k:renewed[k] for k in ('refresh_token','access_token') if renewed.get(k)},'expires_at':(now()+timedelta(seconds=min(int(renewed.get('expires_in',3600)),3600))).isoformat()}
        # Verify actual account every connection, even when using an unexpired cached token.
        who=await request('GET',PROFILE,headers={'Authorization':'Bearer '+tokens['access_token']})
        if str(who.get('emailAddress') or '').lower()!=email.lower():raise OAuthFailure('identity_mismatch')
    except OAuthFailure as exc:
        if exc.reason in ('revoked','identity_mismatch','invalid_refresh'):invalidate(exc.reason)
        raise Blocked('Gmail access unavailable; inspect connection or reconnect') from None
    with Session() as db:
        ledger.lock(db);row=require_connection(db,generation);row.encrypted_tokens=credentials.encrypt(tokens);row.updated_at=now();db.commit()
    return tokens['access_token'],email,generation


async def disconnect(db,revoke=True,request=google_request):
    token=''
    ledger.lock(db);row=db.get(Integration,'gmail')
    if not row:row=Integration(id='gmail');db.add(row);db.flush()
    try:token=credentials.decrypt(row.encrypted_tokens).get('refresh_token','') if row.encrypted_tokens else ''
    except Blocked:pass
    change(db,row,'disconnected','operator_disconnect',clear=True)
    db.execute(delete(OAuthGrant));db.commit()
    revoked=False
    if revoke and token:
        try:await request('POST','https://oauth2.googleapis.com/revoke',data={'token':token});revoked=True
        except OAuthFailure:pass
    return {**status(db),'upstream_revoked':revoked,'local_credentials_removed':True}
