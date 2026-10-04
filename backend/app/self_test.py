"""Explicit operator self-test, sharing the delivery ledger and account quota."""
import base64
import hashlib
from email.message import EmailMessage
from . import desk
from .mail import Mailbox
from .models import State,now
from .core import Blocked
from .services import ledger,policy

async def send(db,id,box=None):
    packet=desk.get_packet(db,id).value;address=desk.mailbox_address(db)
    fingerprint=packet['draft_hash'];key='self-test:'+id+':'+fingerprint
    state_key='self-test:'+hashlib.sha256(key.encode()).hexdigest()
    # Preserve historical exact-key tests; new state IDs fit PostgreSQL's
    # legacy varchar(100) bound without changing operation idempotency.
    old=db.get(State,state_key) or db.get(State,key)
    if old:
        if old.value['status']=='sent':return old.value
        raise Blocked('Previous test delivery is uncertain. Check Gmail before trying another version.')
    box=box or Mailbox();await box.connect()
    if box.cfg.mail_provider!='gmail':raise Blocked('Self-tests require Gmail in this release')
    def authorize():
        if hasattr(box,'ensure_authorized'):box.ensure_authorized(db)
        if desk.get_packet(db,id).value['draft_hash']!=fingerprint:raise Blocked('Draft changed; save current version')
        return policy.own_mailbox(db,desk.mailbox_address(db),box.cfg.sender_email,'self_test')
    def reserve(attempt):
        db.add(State(key=state_key,value={'status':'sending','to':address,'at':attempt.started_at.isoformat()}))
    attempt,replay=ledger.claim(db,key,'self_test',box.cfg.mail_provider,authorize,entity_id=id,reserve=reserve)
    if replay:return {**attempt.receipt,'status':'sent','to':address}
    msg=EmailMessage();msg['From']=address;msg['To']=address;msg['Subject']='[DRY RUN] '+packet['subject']
    msg['Message-ID']='<fieldwork-test-'+attempt.operation_id+'@gmail.com>'
    msg.set_content('TEST COPY TO YOURSELF — no company was contacted.\n\n'+packet['body'])
    try:
        with ledger.permit(attempt):
            result=await box.call('POST','https://gmail.googleapis.com/gmail/v1/users/me/messages/send',json={'raw':base64.urlsafe_b64encode(msg.as_bytes()).decode()})
        receipt={'gmail_id':result['id'],'thread_id':result.get('threadId',''),'at':now().isoformat()}
    except Exception:
        db.rollback();row=db.get(State,state_key);row.value={**row.value,'status':'unknown'}
        ledger.finish(db,attempt,'unknown',reason='delivery_uncertain')
        raise Blocked('Test delivery is uncertain. Check Gmail; this version will not be resent automatically.')
    row=db.get(State,state_key);row.value={**row.value,**receipt,'status':'sent'}
    ledger.finish(db,attempt,'succeeded',receipt=receipt,reason='provider_accepted')
    return row.value
