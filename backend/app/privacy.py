"""Explicit personal-data minimization; delivery evidence and stop state survive deletion."""
from sqlalchemy import select,delete
from .core import Blocked,profile_fingerprint
from .models import Profile,Outreach,State,Cache,Event,Job,DomainTransition,Operation,ActionAttempt,OperatorSession,OAuthGrant,now
from .services import ledger
from .domain.states import transition


def export(db):
    # No sessions, OAuth verifier/tokens, credentials or security rate state.
    from .models import Company,Contact,Evidence,Suppression,Usage
    output={}
    for model in (Profile,Company,Contact,Evidence,Outreach,Event,Job,Operation,ActionAttempt,DomainTransition,Suppression,Usage):
        output[model.__tablename__]=[{c.name:getattr(r,c.name) for c in model.__table__.columns} for r in db.scalars(select(model))]
    output['state']=[{'key':r.key,'value':r.value} for r in db.scalars(select(State)) if r.key in ('outreach_policy','manual_batch','manual_batch_progress','automation') or r.key.startswith(('desk:','response:','self-test:'))]
    return output


def pause(db):
    p=db.get(State,'outreach_policy')
    if p:p.value={**p.value,'enabled':False}
    batch=db.get(State,'manual_batch')
    if batch:batch.value={**batch.value,'enabled':False,'stop_requested':True}
    automation=db.get(State,'automation')
    if automation:automation.value={**automation.value,'enabled':False}


def invalidate_messages(db,erase=False):
    for row in db.scalars(select(Outreach)):
        if row.status in ('draft','approved','rejected'):
            transition(db,row,'cancelled',reason='privacy_delete')
        if erase:
            row.review={'content_erased':True,'original_content_hash':profile_fingerprint({'subject':row.subject,'body':row.body})}
            row.subject='';row.body=''


def remove(db,scope,confirmation):
    required={'resume':'DELETE RESUME','generated':'DELETE GENERATED DATA','personal':'DELETE PERSONAL CONTENT'}
    if scope not in required or confirmation!=required[scope]:raise Blocked('Exact deletion confirmation is required')
    ledger.lock(db)
    # Never erase data that may still be transmitting or needed to resolve uncertainty.
    if ledger.unresolved(db) or db.scalar(select(Outreach.id).where(Outreach.status.in_(['sending','unknown'])).limit(1)):
        db.rollback();raise Blocked('Resolve in-flight or uncertain delivery before deleting content')
    pause(db);profile=db.get(Profile,1)
    if scope=='resume':
        if profile:profile.data={**profile.data,'resume':'','cover_letter_snippets':[],'verified':False}
        invalidate_messages(db)
    else:
        invalidate_messages(db,erase=scope=='personal')
        if scope=='generated':
            for r in db.scalars(select(Outreach).where(Outreach.attempts==0)):
                r.subject='';r.body='';r.review={'content_erased':True}
        # Remove derived content/cached student context, never receipt linkage.
        db.execute(delete(Cache))
        for state in list(db.scalars(select(State))):
            if state.key.startswith('desk:'):db.delete(state)
            elif scope=='personal' and state.key.startswith('response:'):
                state.value={**state.value,'preview':'','subject':'','sender':'','company':'','gmail_url':'','handled':True}
            elif scope=='personal' and state.key.startswith('self-test:'):
                state.value={**state.value,'to':''}
        if scope=='personal':
            db.execute(delete(OAuthGrant))
            for s in db.scalars(select(OperatorSession)):s.revoked_at=now()
            if profile:profile.data={'verified':False};profile.updated_at=now()
            for event in db.scalars(select(Event)):event.detail=''
    for job in db.scalars(select(Job).where(Job.status=='queued')):
        transition(db,job,'running',domain='job',reason='privacy_cancel')
        transition(db,job,'blocked',domain='job',reason='privacy_cancel')
        job.error='Cancelled by personal data deletion';job.payload={};job.result={};job.finished_at=now()
    db.add(DomainTransition(domain='privacy',entity_id='personal',from_state='retained',to_state=scope+'_erased',reason='operator_explicit_deletion'))
    db.commit()
    return {'scope':scope,'deleted':True,'outreach_paused':True,'retained':'Receipt IDs, attempt history, contact suppression and minimal operational linkage'}


def prune(db):
    """Periodic minimization; never deletes receipt or suppression evidence."""
    from datetime import datetime,timedelta
    from .core import aware
    from .config import settings
    ledger.lock(db);at=now()
    db.execute(delete(Cache).where(Cache.expires_at<at).execution_options(synchronize_session=False))
    db.execute(delete(OAuthGrant).where(OAuthGrant.expires_at<at).execution_options(synchronize_session=False))
    cutoff=at-timedelta(days=settings().response_preview_retention_days)
    for state in db.scalars(select(State).where(State.key.like('response:%'))):
        try:old=aware(datetime.fromisoformat(state.value['received_at']))<cutoff
        except (ValueError,KeyError,TypeError):old=False
        if old:state.value={**state.value,'preview':'','subject':''}
    # Expired session hashes are non-secret but no longer needed; OAuth grants were pruned first.
    active_grants=select(OAuthGrant.session_hash)
    db.execute(delete(OperatorSession).where(OperatorSession.expires_at<at,OperatorSession.token_hash.not_in(active_grants)).execution_options(synchronize_session=False))
    db.commit()


async def retention_loop():
    import asyncio,logging
    from .db import Session
    while True:
        try:
            with Session() as db:prune(db)
        except Exception:logging.getLogger(__name__).error('Privacy maintenance failed; retrying in one hour')
        await asyncio.sleep(3600)
