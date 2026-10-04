"""Durable idempotency and attempt history. Claims serialize in the database.

No external I/O inside a claim transaction. A running/unknown communication holds
other communications until completion or explicit reconciliation.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import logging
from sqlalchemy import select, text, func
from ..models import Operation, ActionAttempt, now
from ..core import Blocked
from ..domain.states import transition

active_delivery = ContextVar('active_delivery', default=None)
COMMUNICATIONS = ('company_send','self_test','mailbox_draft')

def log_status(op,status):
    logging.getLogger('uvicorn.error').info(json.dumps({'event':'operation','operation_id':op.id,'job_id':op.job_id,'outreach_id':op.outreach_id,'provider':op.provider,'status':status}))

def lock(db):
    db.flush()
    db.execute(text('INSERT INTO execution_lock (id, version) VALUES (1, 0) ON CONFLICT (id) DO NOTHING'))
    db.execute(text('UPDATE execution_lock SET version = version + 1 WHERE id = 1'))
    db.expire_all()

def latest(db, operation):
    return db.scalar(select(ActionAttempt).where(ActionAttempt.operation_id==operation.id).order_by(ActionAttempt.number.desc()).limit(1))

def operation(db, key):
    return db.scalar(select(Operation).where(Operation.idempotency_key==key))

def claim(db, key, kind, provider, authorize, *, outreach_id=None, entity_id='', job_id=None, retry=False, reserve=None):
    """authorize runs under the same lock as quota/claim; it must do no I/O/commit.
    Returns (attempt, replay). Successful operations replay only saved receipts.
    Blocked decisions are durable but never consume network quota.
    """
    lock(db)
    op = operation(db,key)
    if op and (op.kind!=kind or op.entity_id!=entity_id or op.outreach_id!=outreach_id):
        db.rollback();raise Blocked('Idempotency key cannot be reused for a different operation')
    if op and op.status=='succeeded':
        result=latest(db,op);db.commit();return result,True
    if op and op.status in {'running','unknown','skipped'}:
        db.rollback();raise Blocked('Operation is in progress or uncertain; reconcile before retrying')
    if op and op.status=='failed' and not retry:
        db.rollback();raise Blocked('Failed operation requires an explicit retry')
    if not op:
        op=Operation(idempotency_key=key,kind=kind,provider=provider,outreach_id=outreach_id,entity_id=entity_id,job_id=job_id,status='pending')
        db.add(op);db.flush()
    elif op.kind!=kind or op.entity_id!=entity_id or op.outreach_id!=outreach_id:
        db.rollback();raise Blocked('Idempotency key cannot be reused for a different operation')
    prior=latest(db,op)
    attempt=ActionAttempt(operation_id=op.id,number=(prior.number+1 if prior else 1),retry_of=prior.id if prior else None,status='running')
    db.add(attempt)
    try:
        policy=authorize()
    except Blocked as exc:
        # Reason is a bounded application error code/message, never a provider exception.
        attempt.status='blocked';attempt.reason=__import__('app.redaction',fromlist=['redact']).redact(str(exc))[:160];attempt.finished_at=now()
        if op.status=='failed':
            transition(db,op,'running',domain='operation',reason='retry_evaluation')
        transition(db,op,'blocked',domain='operation',reason='policy_denied')
        db.commit();log_status(op,'blocked');raise
    transition(db,op,'running',domain='operation',reason='authorized')
    attempt.authorized=True;attempt.network_units=1;attempt.policy=policy;db.flush()
    if reserve:
        reserve(attempt)
    db.commit()
    log_status(op,'reserved')
    return attempt,False

def finish(db, attempt, status, *, receipt=None, reason=''):
    lock(db)
    attempt=db.get(ActionAttempt,attempt.id)
    op=db.get(Operation,attempt.operation_id)
    if attempt.status!='running':
        db.rollback();raise Blocked('Attempt is already terminal; use explicit reconciliation')
    transition(db,op,status,domain='operation',reason=reason or status)
    attempt.status=status;attempt.reason=reason[:160];attempt.receipt=receipt or {};attempt.finished_at=now()
    db.commit()
    log_status(op,status)
    return attempt

@contextmanager
def permit(attempt):
    if not attempt.authorized or attempt.status!='running':
        raise Blocked('Delivery requires an active authorized attempt')
    token=active_delivery.set(attempt.id)
    try:yield
    finally:active_delivery.reset(token)

def unresolved(db):
    active=db.scalar(select(Operation.id).where(Operation.kind.in_(COMMUNICATIONS),Operation.status.in_(['running','unknown'])).limit(1))
    pending=db.scalar(select(ActionAttempt.id).join(Operation).where(Operation.kind=='company_send',ActionAttempt.receipt['confirmation_pending'].as_boolean()==True).limit(1))
    return active is not None or pending is not None

def usage(db, since, kind=None):
    q=select(func.coalesce(func.sum(ActionAttempt.network_units),0)).join(Operation).where(ActionAttempt.started_at>=since)
    q=q.where(Operation.kind==kind) if kind else q.where(Operation.kind.in_(['company_send','self_test']))
    return db.scalar(q)


def reconcile_sent(db,row,provider_id,thread_id,message_id,*,account=None,reserved_message_id=None):
    """Only use after exact Sent evidence; aliases additionally require a durable API receipt."""
    if not provider_id or not message_id or message_id!=row.message_id and reserved_message_id!=row.message_id:
        raise Blocked('Reconciliation requires matching provider Sent evidence')
    lock(db)
    from ..models import Outreach
    row=db.get(Outreach,row.id)
    if (row.provider_id and row.provider_id!=provider_id) or (row.thread_id and row.thread_id!=thread_id):
        db.rollback();raise Blocked('Sent evidence conflicts with recorded provider receipt; investigate')
    op=operation(db,'send:'+row.id)
    if reserved_message_id is not None and row.message_id!=reserved_message_id:
        db.rollback();raise Blocked('Reserved RFC identity changed during reconciliation')
    alias=message_id!=row.message_id
    attempt=latest(db,op) if op else None
    if alias and (not op or op.status!='succeeded' or attempt.status!='succeeded'
        or attempt.receipt.get('provider_id')!=provider_id or attempt.receipt.get('thread_id')!=thread_id
        or row.provider_id!=provider_id or row.thread_id!=thread_id):
        db.rollback();raise Blocked('Durable accepted receipt required for RFC normalization')
    if alias:
        attempt.receipt={**attempt.receipt,'reserved_message_id':attempt.receipt.get('reserved_message_id',row.message_id)}
        row.message_id=message_id
    if op and op.status in {'running','unknown','succeeded'}:
        attempt=latest(db,op)
        if op.status!='succeeded':transition(db,op,'succeeded',domain='operation',reason='sent_reconciled')
        attempt.status='succeeded';attempt.finished_at=now()
        attempt.receipt={**attempt.receipt,'provider_id':provider_id,'thread_id':thread_id,'message_id':message_id,'sent_verified':True,'confirmation_pending':False,'operation_id':op.id,'outreach_id':row.id,'reconciled_at':now().isoformat()}
        if account:attempt.receipt={**attempt.receipt,'account':account.lower()}
    if row.status in {'sending','unknown'}:transition(db,row,'sent',reason='sent_reconciled')
    row.provider_id=provider_id;row.thread_id=thread_id
    from ..models import Company
    from ..core import STOP_STAGES
    company=db.get(Company,row.company_id)
    if company and company.stage not in STOP_STAGES:company.stage='contacted'
    db.commit()
