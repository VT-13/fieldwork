"""Only company delivery entry point. UI, worker and CLI converge here."""
from sqlalchemy import select
from ..models import Outreach,Operation,Evidence,now
from ..core import Blocked,profile_fingerprint
from ..domain.states import transition
from . import ledger,policy
from .email_provider import MailboxProvider


def content_fingerprint(db,row,contact,profile):
    facts=list(db.scalars(select(Evidence).where(Evidence.id.in_(row.evidence_ids)).order_by(Evidence.id)))
    return profile_fingerprint({'subject':row.subject,'body':row.body,'contact_id':row.contact_id,
        'email':contact.email,'name':contact.name,'review':row.review,'profile':profile.data,
        'evidence':[(e.id,e.fact,e.quote,e.url) for e in facts]})

async def send_company(db,id,*,mode='scheduled',provider=None):
    from ..mail import Mailbox
    row=db.get(Outreach,id)
    key='send:'+id
    # First evaluation fails before connecting to any provider; denial is queryable.
    try:
        company,contact,profile,original=policy.company(db,row,now(),mode)
    except Blocked:
        ledger.claim(db,key,'company_send','gmail',lambda: policy.company(db,db.get(Outreach,id),now(),mode),outreach_id=id if row else None,entity_id=id)
        raise
    provider=provider or MailboxProvider(Mailbox())
    fingerprint=content_fingerprint(db,row,contact,profile)
    from uuid import uuid4
    check,_=ledger.claim(db,'preflight:'+id+':'+str(uuid4()),'delivery_preflight',provider.name,
                         lambda:policy.snapshot(db,'read_only'),outreach_id=id,entity_id=id)
    try:
        await provider.connect()
        if provider.sender.lower()!=profile.data.get('email','').lower():raise Blocked('Sender/profile mismatch')
        await provider.check_conversation(db,row,contact,original)
    except Exception as exc:
        db.rollback();ledger.finish(db,check,'blocked' if isinstance(exc,Blocked) else 'failed',reason='preflight_blocked' if isinstance(exc,Blocked) else 'provider_check_failed')
        raise
    ledger.finish(db,check,'succeeded',reason='conversation_checked')
    def authorize():
        nonlocal row,company,contact,profile,original
        row=db.get(Outreach,id)
        company,contact,profile,original=policy.company(db,row,now(),mode)
        if provider.sender.lower()!=profile.data.get('email','').lower():raise Blocked('Sender/profile mismatch')
        if hasattr(provider,'authorize'):provider.authorize(db)
        if content_fingerprint(db,row,contact,profile)!=fingerprint:raise Blocked('Message or evidence changed during preflight; review again')
        return {**policy.snapshot(db,mode),'content_hash':fingerprint}
    def reserve(attempt):
        transition(db,row,'sending',reason='attempt_reserved')
        row.attempts+=1;row.sent_at=attempt.started_at
        row.message_id=f'<fieldwork-{row.id}@gmail.com>'
    attempt,replay=ledger.claim(db,key,'company_send',provider.name,authorize,outreach_id=id,entity_id=id,reserve=reserve)
    if replay:return attempt.receipt
    try:
        with ledger.permit(attempt):
            receipt=await provider.deliver(db,row,contact,original)
        if not receipt.provider_id:raise ValueError('Missing provider receipt')
    except Exception:
        db.rollback();row=db.get(Outreach,id)
        transition(db,row,'unknown',reason='delivery_uncertain')
        # Fail closed for any ambiguous provider error. No blind 429 replay.
        ledger.finish(db,attempt,'unknown',reason='delivery_uncertain')
        raise Blocked('Delivery uncertain; reconcile Sent before further communication')
    row.provider_id=receipt.provider_id;row.thread_id=receipt.thread_id
    transition(db,row,'sent',reason='provider_accepted');company.stage='contacted'
    result={'outreach_id':id,'provider_id':receipt.provider_id,'thread_id':receipt.thread_id,'at':row.sent_at.isoformat(),'sent_verified':receipt.sent_verified,'confirmation_pending':True}
    ledger.finish(db,attempt,'succeeded',receipt=result,reason='provider_accepted')
    # Acceptance is durable even if confirmation fails; confirmation never resends.
    try:
        verified=await provider.confirm(receipt)
        result={**result,'sent_verified':verified,'confirmation_pending':verified is not True}
    except Exception: result={**result,'confirmation_pending':True}
    attempt=db.get(type(attempt),attempt.id);attempt.receipt=result;db.commit()
    return result
