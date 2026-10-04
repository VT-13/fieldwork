"""Explicit, expiring staging-only validation scope for the existing Gmail paths.

No scope-creation HTTP endpoint, company sender, queue or alternate transport.
Normal self-tests remain own-account only. The operator provisions this scope in
isolated staging; packet hashes and the durable ledger fence every mutation.
"""
import os
import hashlib
from datetime import datetime,timedelta,timezone
from email.utils import getaddresses
from sqlalchemy import select
from .config import settings
from .core import Blocked,aware,profile_fingerprint
from .models import State,Profile,Company,Operation,Event,now
from .services import ledger

KEY='gmail_validation'
PREFIX='[Fieldwork staging test] '

def context(db,id=None,*,writing=False):
    row=db.get(State,KEY)
    if not row or (id and id not in (row.value.get('send_packet_id'),row.value.get('draft_packet_id'))):return None
    v=row.value
    if not settings().live_gmail_validation_enabled or os.environ.get('RAILWAY_ENVIRONMENT_NAME')!='staging':
        if id is None:return None
        raise Blocked('Live Gmail validation is disabled outside isolated staging')
    from email_validator import validate_email,EmailNotValidError
    try:
        if validate_email(v.get('account_b',''),check_deliverability=False).normalized.lower()!=v.get('account_b'):raise ValueError()
    except (EmailNotValidError,ValueError):raise Blocked('Invalid staging validation recipient') from None
    profile=db.get(Profile,1);company=db.get(Company,v.get('audit_company_id'))
    if (v.get('version')!=1 or not profile or not profile.data.get('verified')
        or v.get('account_a')!=profile.data.get('email','').lower()
        or v.get('account_a')==v.get('account_b') or not v.get('account_b')
        or not v.get('send_packet_id') or v.get('send_packet_id')==v.get('draft_packet_id')
        or not settings().dry_run or not settings().manual_mode or settings().response_poll_enabled
        or not company or not company.demo):raise Blocked('Invalid staging validation scope')
    try:
        created=aware(datetime.fromisoformat(v['created_at']));expires=aware(datetime.fromisoformat(v['expires_at']))
        if created>now()+timedelta(minutes=1) or expires-created>timedelta(hours=24) or expires<=created or (writing and now()>=expires):raise ValueError()
    except (KeyError,ValueError,TypeError):raise Blocked('Staging validation scope expired or invalid') from None
    return v

def spec(db,id,purpose):
    v=context(db,id,writing=True)
    if not v:return None
    if purpose not in ('send','draft') or id!=v[purpose+'_packet_id']:raise Blocked('Validation packet purpose mismatch')
    packet=db.get(State,'desk:'+id)
    if (not packet or packet.value.get('draft_hash')!=v[purpose+'_hash']
        or packet.value['subject']!=PREFIX+('Gmail live verification' if purpose=='send' else 'Gmail draft verification')
        or packet.value['body']!='Fieldwork staging synthetic '+purpose+' verification. No company outreach.'
        or packet.value.get('company') or packet.value.get('fictional')):raise Blocked('Validation packet changed')
    return {'to':v['account_b'] if purpose=='send' else v['account_a'],
            'subject':packet.value['subject'],'body':packet.value['body'],
            'scope_hash':profile_fingerprint({k:v[k] for k in ('account_a','account_b','send_packet_id','draft_packet_id','send_hash','draft_hash','created_at','expires_at')})}

def send_state(db,v):
    key='self-test:'+v['send_packet_id']+':'+v['send_hash']
    return db.get(State,'self-test:'+hashlib.sha256(key.encode()).hexdigest())

async def reconcile(db,id,box):
    from .responses import verify_identity
    from .services.reconciliation import matches_envelope,headers,BASE
    v=context(db,id)
    if not v or id!=v['send_packet_id']:raise Blocked('Reserved message identity required')
    state=send_state(db,v);op=ledger.operation(db,'self-test:'+id+':'+v['send_hash'])
    attempt=ledger.latest(db,op) if op else None
    if not state or not op or not attempt:raise Blocked('Reserved validation attempt required')
    saved=state.value;reserved_mid='<fieldwork-test-'+op.id+'@gmail.com>';mid=saved.get('message_id',reserved_mid)
    account,_=await verify_identity(db,box)
    if account!=v['account_a']:raise Blocked('Validation account mismatch')
    packet=db.get(State,'desk:'+id).value
    if saved.get('gmail_id'):
        # Gmail may rewrite RFC Message-ID. Only its accepted immutable API ID
        # can establish that alias; an uncertain send without a receipt cannot.
        msg=await box.call('GET',BASE+'messages/'+saved['gmail_id'],params={'format':'full'})
        import re
        actual=headers(msg).get('message-id','')
        if (msg.get('id')!=saved['gmail_id'] or not saved.get('thread_id')
            or msg.get('threadId')!=saved['thread_id'] or len(actual)>255
            or not re.fullmatch(r'<[^<>\s@]+@[^<>\s@]+>',actual)
            or (saved.get('sent_verified') and actual!=mid)
            or not matches_envelope(msg,account,v['account_b'],actual,packet['subject'],packet['body'],datetime.fromisoformat(saved['at']))):
            raise Blocked('Accepted validation receipt conflicts with Sent evidence')
        mid=actual
    found=await box.call('GET',BASE+'messages',params={'q':'in:sent rfc822msgid:'+mid.strip('<>'),'maxResults':5})
    matches=[]
    for item in found.get('messages',[])[:5]:
        msg=await box.call('GET',BASE+'messages/'+item['id'],params={'format':'full'})
        if matches_envelope(msg,account,v['account_b'],mid,packet['subject'],packet['body'],datetime.fromisoformat(saved['at'])):matches.append(msg)
    if len(matches)!=1 or found.get('nextPageToken'):return {'status':'held','reason':'No unique matching Sent evidence; never resend'}
    msg=matches[0]
    if (saved.get('gmail_id') and saved['gmail_id']!=msg['id']) or (saved.get('thread_id') and saved['thread_id']!=msg.get('threadId')):raise Blocked('Validation receipt conflicts with Sent evidence')
    ledger.lock(db);state=send_state(db,v);op=ledger.operation(db,op.idempotency_key);attempt=ledger.latest(db,op)
    proof={**attempt.receipt,'gmail_id':msg['id'],'thread_id':msg.get('threadId',''),'message_id':mid,'reserved_message_id':reserved_mid,'sent_verified':True,'confirmation_pending':False}
    if op.status in ('running','unknown'):
        from .domain.states import transition
        transition(db,op,'succeeded',domain='operation',reason='sent_reconciled')
        attempt.status='succeeded';attempt.finished_at=now()
    elif op.status!='succeeded':raise Blocked('Validation operation cannot be reconciled')
    attempt.receipt=proof;state.value={**state.value,**proof,'status':'sent'};db.commit()
    return {'status':'confirmed','provider_id':msg['id'],'test_packet_id':id}

def related(v,receipt,msg):
    from .services.reconciliation import headers
    h=headers(msg);senders={a.lower() for _,a in getaddresses([h.get('from','')])}
    targets={a.lower() for _,a in getaddresses([h.get('to','')])}
    mid=receipt.get('message_id','')
    return bool(senders in ({v['account_a']},{v['account_b']}) and targets in ({v['account_a']},{v['account_b']}) and
        ((receipt.get('thread_id') and msg.get('threadId')==receipt['thread_id']) or (mid and mid in h.get('references','')+' '+h.get('in-reply-to','')) or msg.get('id')==receipt.get('gmail_id')))

def ingest(db,msg):
    from .responses import text_body
    from .services.reconciliation import headers
    v=context(db)
    if not v:return None
    sent=send_state(db,v)
    if not sent or sent.value.get('status')!='sent' or not related(v,sent.value,msg):return None
    h=headers(msg)
    sender={a.lower() for _,a in getaddresses([h.get('from','')])}
    targets={a.lower() for _,a in getaddresses([h.get('to','')])}
    if sender!={v['account_b']} or targets!={v['account_a']} or 'SENT' in msg.get('labelIds',[]) or h.get('cc') or h.get('bcc'):return None
    try:received=datetime.fromtimestamp(int(msg['internalDate'])/1000,timezone.utc)
    except (KeyError,ValueError,OverflowError):return None
    if not aware(datetime.fromisoformat(sent.value['at']))-timedelta(minutes=1)<=received<=now()+timedelta(minutes=5):return None
    body=text_body(msg.get('payload',{})).strip()
    if not body.startswith('Fieldwork staging controlled reply test.'):return None
    ledger.lock(db);source='gmail-validation:'+msg['id']
    event=db.scalar(select(Event).where(Event.source_id==source))
    if not event:
        db.add(Event(company_id=v['audit_company_id'],campaign_id='gmail-validation',kind='test_reply',source_id=source,detail='Controlled staging reply linked to test packet '+v['send_packet_id'],created_at=received))
        row=db.get(State,KEY);row.value={**row.value,'reply_provider_id':msg['id'],'reply_thread_id':msg.get('threadId',''),'reply_packet_id':v['send_packet_id'],'followup_status':'cancelled'}
    db.commit()
    return {'kind':'test_reply','test_packet_id':v['send_packet_id']}
