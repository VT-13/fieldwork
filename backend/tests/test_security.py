from datetime import timedelta
from urllib.parse import urlsplit,parse_qs
import json
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
from sqlalchemy import select
from app.main import app
from app.db import session
from app.auth import password_hash,digest,Operator,require_operator,COOKIE
from app.config import settings
from app.core import Blocked
from app.models import OperatorSession,Integration,OAuthGrant,State,Outreach,Job,ActionAttempt,now
from app import gmail_oauth as oauth,credentials,privacy

@pytest.fixture
def secure(db,monkeypatch):
    monkeypatch.setenv('API_KEY','module2-private-test-api-key-with-more-than-32-characters')
    monkeypatch.setenv('OPERATOR_PASSWORD_HASH',password_hash('a-unique-long-test-passphrase'))
    monkeypatch.setenv('CREDENTIAL_KEYS',Fernet.generate_key().decode())
    monkeypatch.setenv('OAUTH_CLIENT_ID','fake-client')
    monkeypatch.setenv('OAUTH_CLIENT_SECRET','fake-secret')
    settings.cache_clear()
    app.dependency_overrides[session]=lambda:db
    yield
    app.dependency_overrides.clear()


def login(client):
    return client.post('/auth/login',headers={'Origin':settings().app_origin},json={'password':'a-unique-long-test-passphrase'})


def test_sessions_require_server_auth_expire_and_logout(db,secure):
    with TestClient(app) as client:
        assert client.get('/profile').status_code==401
        assert client.get('/outreach/other-id').status_code==405  # PATCH-only path exposes no GET data
        bad=client.post('/auth/login',headers={'Origin':settings().app_origin},json={'password':'wrong'})
        assert bad.status_code==401
        result=login(client);assert result.status_code==200
        cookie=result.headers['set-cookie'];assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie
        token=client.cookies.get(COOKIE);assert token not in json.dumps(result.json())
        stored=db.get(OperatorSession,digest(token));assert stored and stored.token_hash!=token
        assert client.get('/profile').status_code==200
        assert client.put('/profile',json={}).status_code==403
        assert client.put('/profile',headers={'Origin':'https://evil.example'},json={}).status_code==403
        assert client.post('/auth/logout',headers={'Origin':settings().app_origin}).status_code==200
        client.cookies.set(COOKIE,token);assert client.get('/profile').status_code==401
        client.cookies.clear();assert login(client).status_code==200
        stored=db.get(OperatorSession,digest(client.cookies.get(COOKIE)));stored.expires_at=now()-timedelta(seconds=1);db.commit()
        assert client.get('/profile').status_code==401


def test_rotation_invalidates_sessions_and_object_access(db,secure,ready,monkeypatch):
    with TestClient(app) as client:
        login(client)
        assert client.get('/companies/'+ready[0].id).status_code==200
        client.cookies.set(COOKIE,'forged-session');assert client.get('/companies/'+ready[0].id).status_code==401
        client.cookies.clear();login(client)
        monkeypatch.setenv('OPERATOR_PASSWORD_HASH',password_hash('another-long-test-passphrase'));settings.cache_clear()
        assert client.get('/profile').status_code==401
    with pytest.raises(HTTPException):require_operator(Operator(id='another-operator'))


def test_login_rate_body_host_content_and_validation(db,secure):
    with TestClient(app) as client:
        assert client.get('/profile',headers={'Host':'evil.example'}).status_code==400
        assert client.post('/auth/login',content='x'*100001).status_code==413
        assert client.post('/auth/login',content='{}',headers={'Content-Type':'text/plain'}).status_code==415
        assert client.post('/auth/login',json={},headers={'Origin':settings().app_origin}).status_code==422
        r=client.post('/auth/login',json={'password':'sensitive-value'*100},headers={'Origin':settings().app_origin})
        assert r.status_code==422 and 'sensitive-value' not in r.text
        for _ in range(4):client.post('/auth/login',json={'password':'bad'},headers={'Origin':settings().app_origin})
        assert login(client).status_code==429
        assert client.get('/profile').headers['cache-control']=='no-store'


def test_chunked_oversize_cannot_bypass_limit(db,secure):
    import asyncio
    from app.ingress import Ingress
    calls=[];sent=[];parts=iter([{'type':'http.request','body':b'x'*60000,'more_body':True},{'type':'http.request','body':b'x'*60000,'more_body':False}])
    async def target(*args):calls.append(True)
    async def receive():return next(parts)
    async def send(v):sent.append(v)
    asyncio.run(Ingress(target)({'type':'http','method':'POST','path':'/auth/login','query_string':b'','headers':[(b'content-type',b'application/json')],'client':('chunk-client',1)},receive,send))
    assert sent[0]['status']==413 and not calls


def operator(db):
    row=OperatorSession(token_hash=digest('session'),auth_version=digest(settings().operator_password_hash),expires_at=now()+timedelta(hours=1))
    db.add(row);db.commit();return Operator(session_hash=row.token_hash,mechanism='session')


def start(db):
    op=operator(db);query=parse_qs(urlsplit(oauth.start(db,op)['url']).query)
    return op,query['state'][0],query


async def fake_google(method,url,**kwargs):
    if url==oauth.TOKEN:return {'refresh_token':'private-refresh','access_token':'private-access','expires_in':3600,'scope':oauth.SEND+' '+oauth.READ}
    if url==oauth.PROFILE:return {'emailAddress':'student@example.com'}
    return {}


async def test_oauth_state_pkce_scope_encryption_and_replay(db,secure,ready):
    op,state,q=start(db)
    assert q['code_challenge_method']==['S256'] and q['scope']==[oauth.SEND+' '+oauth.READ]
    assert oauth.COMPOSE not in q['scope'][0]
    grant=db.get(OAuthGrant,digest(state));assert state not in grant.verifier_ciphertext
    with pytest.raises(HTTPException):await oauth.callback(db,op,'wrong','code',request=fake_google)
    with pytest.raises(HTTPException):await oauth.callback(db,Operator(session_hash='other'),'state','code',request=fake_google)
    result=await oauth.callback(db,op,state,'code',request=fake_google)
    assert result['connected'] and 'token' not in json.dumps(result)
    connection=db.get(Integration,'gmail');assert 'private-' not in connection.encrypted_tokens
    assert credentials.decrypt(connection.encrypted_tokens)['refresh_token']=='private-refresh'
    assert db.get(OAuthGrant,digest(state)).verifier_ciphertext==''
    with pytest.raises(HTTPException):await oauth.callback(db,op,state,'code',request=fake_google)


async def test_expired_oauth_and_identity_mismatch_fail_closed(db,secure,ready):
    op,state,_=start(db);grant=db.get(OAuthGrant,digest(state));grant.expires_at=now()-timedelta(seconds=1);db.commit()
    with pytest.raises(HTTPException):await oauth.callback(db,op,state,'code',request=fake_google)
    q=parse_qs(urlsplit(oauth.start(db,op)['url']).query);state=q['state'][0]
    async def mismatch(method,url,**kw):return {'emailAddress':'other@example.com'} if url==oauth.PROFILE else await fake_google(method,url,**kw)
    with pytest.raises(Blocked):await oauth.callback(db,op,state,'code',request=mismatch)
    row=db.get(Integration,'gmail');assert row.status=='identity_mismatch' and not row.encrypted_tokens
    assert db.get(State,'outreach_policy').value['enabled'] is False


async def connected(db):
    op,state,_=start(db);await oauth.callback(db,op,state,'code',request=fake_google)


async def test_expired_access_refresh_revocation_and_disconnect(db,secure,ready):
    await connected(db);row=db.get(Integration,'gmail');tokens=credentials.decrypt(row.encrypted_tokens)
    row.encrypted_tokens=credentials.encrypt({**tokens,'expires_at':(now()-timedelta(hours=1)).isoformat()});db.commit()
    seen=[]
    async def refresh(method,url,**kw):seen.append(url);return await fake_google(method,url,**kw)
    token,email,generation=await oauth.access(request=refresh)
    assert token=='private-access' and email=='student@example.com' and oauth.TOKEN in seen
    db.expire_all();row=db.get(Integration,'gmail')
    row.encrypted_tokens=credentials.encrypt({**tokens,'expires_at':(now()-timedelta(hours=1)).isoformat()});db.commit()
    async def revoked(*a,**k):raise oauth.OAuthFailure('revoked')
    with pytest.raises(Blocked):await oauth.access(request=revoked)
    db.expire_all();assert db.get(Integration,'gmail').status=='reconnect_required'
    with pytest.raises(Blocked):oauth.require_connection(db,generation)
    # Reconnect never resumes campaign authorization.
    op=Operator(session_hash=digest('session'),mechanism='session');state=parse_qs(urlsplit(oauth.start(db,op)['url']).query)['state'][0]
    await oauth.callback(db,op,state,'code',request=fake_google)
    ready[2].provider_id='retained-id';ready[2].status='sent';db.commit()
    result=await oauth.disconnect(db,request=revoked)
    assert result['local_credentials_removed'] and result['upstream_revoked'] is False
    assert ready[2].provider_id=='retained-id'
    assert not db.get(Integration,'gmail').encrypted_tokens
    with pytest.raises(Blocked):await oauth.access(request=fake_google)


async def test_disconnect_during_oauth_and_cached_connection(db,secure,ready):
    await connected(db);row=db.get(Integration,'gmail');generation=row.generation
    op=Operator(session_hash=digest('session'),mechanism='session');state=parse_qs(urlsplit(oauth.start(db,op)['url']).query)['state'][0]
    async def race(method,url,**kw):
        if url==oauth.TOKEN:await oauth.disconnect(db,revoke=False)
        return await fake_google(method,url,**kw)
    with pytest.raises(Blocked):await oauth.callback(db,op,state,'code',request=race)
    with pytest.raises(Blocked):oauth.require_connection(db,generation)


async def test_missing_and_corrupt_credentials_block(db,secure,ready):
    from app.mail import Mailbox
    with pytest.raises(Blocked):await Mailbox().connect()
    await connected(db);row=db.get(Integration,'gmail');row.encrypted_tokens='tampered';db.commit()
    with pytest.raises(Blocked):await oauth.access(request=fake_google)
    db.expire_all();assert db.get(Integration,'gmail').status=='reconnect_required'


def test_key_rotation_and_secret_redaction(db,secure,monkeypatch):
    old=settings().credential_keys;encrypted=credentials.encrypt({'refresh_token':'keep-private'})
    new=Fernet.generate_key().decode();monkeypatch.setenv('CREDENTIAL_KEYS',new+','+old);settings.cache_clear()
    rotated=credentials.rotate(encrypted);monkeypatch.setenv('CREDENTIAL_KEYS',new);settings.cache_clear()
    assert credentials.decrypt(rotated)['refresh_token']=='keep-private'
    with pytest.raises(Blocked):credentials.decrypt(encrypted)
    from app.redaction import redact
    assert redact({'Authorization':'secret','resume':'student facts','receipt':{'provider_id':'id'}})=={'Authorization':'[REDACTED]','resume':'[REDACTED]','receipt':{'provider_id':'id'}}
    text=redact('Bearer private-access api_key=hidden password=hidden '+settings().oauth_client_secret)
    assert 'private-access' not in text and 'hidden' not in text and 'fake-secret' not in text


def test_resume_and_generated_delete_export_preserves_evidence(db,secure,ready):
    from app.models import Profile
    profile=db.get(Profile,1);profile.data={**profile.data,'resume':'private resume','cover_letter_snippets':['derived']};db.commit()
    with pytest.raises(Blocked):privacy.remove(db,'resume','wrong')
    assert privacy.remove(db,'resume','DELETE RESUME')['deleted']
    assert db.get(Profile,1).data['resume']=='' and ready[2].status=='cancelled'
    sent=ready[2];sent.status='sent';sent.provider_id='provider-evidence';sent.body='private sent content';db.commit()
    privacy.remove(db,'personal','DELETE PERSONAL CONTENT')
    assert sent.provider_id=='provider-evidence' and sent.body=='' and db.get(Profile,1).data=={'verified':False}
    data=privacy.export(db);assert 'integrations' not in data and 'operator_sessions' not in data
    assert data['outreach'][0]['provider_id']=='provider-evidence'


def test_privacy_blocks_uncertainty_and_file_upload_unavailable(db,secure,ready):
    ready[2].status='unknown';db.commit()
    with pytest.raises(Blocked):privacy.remove(db,'personal','DELETE PERSONAL CONTENT')
    with TestClient(app) as c:
        assert c.post('/resume/upload',files={'file':('../../escape.pdf',b'%PDF-test','application/pdf')}).status_code==415
        assert c.put('/profile',json={'resume':'x'*20001},headers={'Authorization':'Bearer '+settings().api_key}).status_code==422


async def test_unsafe_urls_and_direct_provider_bypass(db,secure):
    from app.url_safety import research_url
    from app.providers import request
    from app.mail import Mailbox
    for url in ('http://example.com','https://127.0.0.1','https://169.254.169.254/latest/meta-data','https://user:pass@example.com'):
        with pytest.raises(Blocked):research_url(url)
    def resolver(*a,**kw):return [(0,0,0,'',('10.0.0.1',443))]
    with pytest.raises(Blocked):research_url('https://public.example.com',resolver)
    with pytest.raises(Blocked):await request('GET','https://evil.example.com')
    with pytest.raises(Blocked):await Mailbox().call('POST','https://gmail.googleapis.com/gmail/v1/users/me/messages/send',json={})
    with pytest.raises(Blocked):await Mailbox().call('GET','https://evil.example.com')


def test_production_configuration_fails_closed(monkeypatch):
    from app.config import Settings
    from pydantic import ValidationError
    with pytest.raises(ValidationError):Settings(environment='production',_env_file=None)
    cfg=Settings(environment='production',database_url='postgresql+psycopg://test@localhost/test',api_key='x'*48,operator_password_hash=password_hash('production-test-passphrase'),credential_keys=Fernet.generate_key().decode(),app_origin='https://fieldwork.example.com',trusted_hosts=['fieldwork.example.com'],data_directory='/private/fieldwork-test',_env_file=None)
    assert cfg.environment=='production'

async def test_queued_jobs_recheck_pause_and_reply(db,secure,ready,monkeypatch):
    from app import worker,mail
    from app.core import record_event
    monkeypatch.setenv('DRY_RUN','false');monkeypatch.setenv('MANUAL_MODE','false');settings.cache_clear()
    job=Job(kind='send',payload={'id':ready[2].id},dedupe_key='queued-send')
    db.add(job);db.commit()
    from app.services.policy import set_paused
    set_paused(db,False)
    with pytest.raises(Blocked):await worker.execute(db,job)
    assert not list(db.scalars(select(ActionAttempt).where(ActionAttempt.operation_id.in_(select(__import__('app.models',fromlist=['Operation']).Operation.id).where(__import__('app.models',fromlist=['Operation']).Operation.kind=='company_send')),ActionAttempt.authorized==True)))
    set_paused(db,True)
    record_event(db,ready[0],'reply','unthreaded-reply')
    another=Job(kind='send',payload={'id':ready[2].id},dedupe_key='after-reply');db.add(another);db.commit()
    with pytest.raises(Blocked):await worker.execute(db,another)
    assert ready[2].status=='cancelled'

async def test_alternative_gmail_send_paths_are_prohibited(db,secure):
    from app.mail import Mailbox
    for path in ('drafts/abc/send','messages/send?alt=json','messages/batchModify'):
        with pytest.raises(Blocked):await Mailbox().call('POST','https://gmail.googleapis.com/gmail/v1/users/me/'+path,json={})


def test_production_cookie_and_browser_bearer_origin(db,secure,monkeypatch):
    from app import auth
    from fastapi.responses import JSONResponse
    cfg=settings().model_copy(update={'environment':'production'})
    monkeypatch.setattr(auth,'settings',lambda:cfg)
    response=JSONResponse({});auth.set_cookie(response,'fake-token')
    assert 'Secure' in response.headers['set-cookie'] and 'HttpOnly' in response.headers['set-cookie']
    with TestClient(app) as c:
        assert c.get('/profile',headers={'Authorization':'Bearer '+cfg.api_key,'Origin':'https://evil.example'}).status_code==403

async def test_profile_identity_change_revokes_existing_connection(db,secure,ready):
    await connected(db)
    with TestClient(app) as c:
        r=c.put('/profile',json={'name':'Student','email':'other@example.com','verified':True},headers={'Authorization':'Bearer '+settings().api_key})
        assert r.status_code==200
    row=db.get(Integration,'gmail');assert row.status=='identity_mismatch' and not row.encrypted_tokens
    assert db.get(State,'outreach_policy').value['enabled'] is False


def test_settings_repr_and_validation_do_not_expose_secrets(secure):
    from app.config import Settings
    from pydantic import ValidationError
    secret='super-private-database-password'
    assert secret not in repr(Settings(database_url='postgresql://user:'+secret+'@localhost/db',_env_file=None))
    with pytest.raises(ValidationError) as error:Settings(environment='production',database_url='sqlite:///'+secret,_env_file=None)
    assert secret not in str(error.value)


def test_retention_clears_previews_and_cache_but_keeps_receipts(db,secure):
    from app.models import Cache
    db.add(State(key='response:old',value={'received_at':(now()-timedelta(days=31)).isoformat(),'preview':'private old reply','subject':'private subject','thread_id':'kept-thread','kind':'reply'}))
    db.add(Cache(key='expired',value={'text':'private cached text'},expires_at=now()-timedelta(days=1)))
    db.commit();privacy.prune(db)
    row=db.get(State,'response:old');assert row.value['preview']=='' and row.value['thread_id']=='kept-thread'
    assert db.get(Cache,'expired') is None


def test_url_validation_resolves_actual_www_host():
    from app.url_safety import research_url
    seen=[]
    def resolver(host,*a,**k):seen.append(host);return [(0,0,0,'',('127.0.0.1',443))]
    with pytest.raises(Blocked):research_url('https://www.example.com',resolver)
    assert seen==['www.example.com']

async def test_sync_uses_verified_provider_identity_not_optional_env(db,secure,ready,monkeypatch):
    from app.mail import sync_mailbox
    from types import SimpleNamespace
    from test_workflow import FakeMailbox
    monkeypatch.setenv('SENDER_EMAIL','');settings.cache_clear()
    row=ready[2];row.status='unknown';row.message_id='<canonical>';db.commit()
    box=FakeMailbox(messages=[{'id':'verified-sent','thread':'thread-kept','headers':{'from':'student@example.com','message-id':'<canonical>'},'body':'','sent_verified':True}]);box.cfg=SimpleNamespace(sender_email='student@example.com')
    await sync_mailbox(db,box)
    assert row.status=='sent' and row.provider_id=='verified-sent'


def test_operator_setup_rejects_development_bearer_shortcut(secure):
    from app.config import Settings
    from pydantic import ValidationError
    with pytest.raises(ValidationError):Settings(api_key='local-development-key-change-me',_env_file=None)


def test_structured_log_filter_removes_body_arguments(secure):
    import logging
    from app.redaction import SafeLogFilter,install_logging
    record=logging.LogRecord('app.test',logging.INFO,'test',1,'details %s',({'resume':'private resume','body':'private message','provider_id':'kept'},),None)
    assert SafeLogFilter().filter(record)
    assert 'private resume' not in record.getMessage() and 'private message' not in record.getMessage() and 'kept' in record.getMessage()
    install_logging()
    assert logging.getLogger('openai').disabled and not logging.getLogger('openai').propagate

async def test_missing_old_key_fences_access_without_destroying_ciphertext(db,secure,ready,monkeypatch):
    await connected(db);row=db.get(Integration,'gmail');saved=row.encrypted_tokens;old=settings().credential_keys;generation=row.generation
    monkeypatch.setenv('CREDENTIAL_KEYS',Fernet.generate_key().decode());settings.cache_clear()
    with pytest.raises(Blocked):await oauth.access(request=fake_google)
    db.expire_all();row=db.get(Integration,'gmail')
    assert row.encrypted_tokens==saved and row.status=='reconnect_required' and row.generation>generation
    monkeypatch.setenv('CREDENTIAL_KEYS',old);settings.cache_clear()
    assert credentials.decrypt(row.encrypted_tokens)['refresh_token']=='private-refresh'
