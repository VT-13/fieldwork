"""Single PostgreSQL advisory-lock leader. All paid and mail actions run here."""
import asyncio
import logging
from contextlib import contextmanager
from datetime import timedelta
from sqlalchemy import select, text
from .db import Session, engine
from .models import Company, Contact, Job, Outreach, State, now
from .domain.states import transition
from .services import ledger, policy
from .config import settings
from .core import Blocked, public_url, aware, STOP_STAGES
from .providers import verify
from .services.intelligence import ConfiguredProspects
discover=ConfiguredProspects().discover
from .pipeline import research, generate
from .mail import send_one, sync_mailbox

log = logging.getLogger("worker")

@contextmanager
def leadership():
    if engine.dialect.name=="postgresql":
        with engine.connect() as conn:
            acquired = conn.scalar(text("SELECT pg_try_advisory_lock(198640921)"))
            try:
                yield acquired
            finally:
                if acquired:
                    conn.execute(text("SELECT pg_advisory_unlock(198640921)"))
    else:
        # OS lock prevents multiple local demo workers as well.
        import fcntl
        with open(".worker.lock","w") as handle:
            try:
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(handle,fcntl.LOCK_UN)

def enqueue(db,kind,payload,key):
    existing = db.scalar(select(Job).where(Job.dedupe_key==key))
    if existing:
        return existing
    job=Job(kind=kind,payload=payload,dedupe_key=key)
    db.add(job)
    db.commit()
    return job

async def _execute(db,job):
    policy.background(db,job.kind)
    p=job.payload
    if settings().manual_mode and job.kind in {"discover","research","pipeline","generate","regenerate","verify","send"}:
        raise Blocked("Manual mode: use the personal review desk; paid calls and live sends are disabled")
    if job.kind=="discover":
        async with asyncio.timeout(60):
            rows=await discover(db,p)
        inserted=0
        for data in rows:
            try:
                domain=public_url(data["website"])
            except Blocked:
                continue
            if not db.scalar(select(Company).where(Company.domain==domain)):
                c=Company(domain=domain,**data)
                db.add(c)
                db.flush()
                inserted+=1
        db.commit()
        return {"discovered":inserted,"candidates":len(rows)}
    if job.kind=="mailbox_draft":
        from .draft_mail import save_mailbox_draft
        return await save_mailbox_draft(db,p["id"],p["draft_hash"])
    if job.kind=="sync":
        return {"messages":await sync_mailbox(db)}
    if job.kind=="regenerate":
        row=db.get(Outreach,p["id"])
        if not row or row.status not in {"draft","approved","rejected"}:
            raise Blocked("Draft cannot be regenerated")
        company=db.get(Company,row.company_id)
        seq=row.sequence
        generated=await generate(db,company,seq,replace=True)
        return {"draft_id":generated.id}
    if job.kind=="send":
        await send_one(db,db.get(Outreach,p["id"]))
        return {"sent":True}
    if job.kind=="verify":
        return {"validation":await verify(db,db.get(Contact,p["id"]))}
    company=db.get(Company,p["id"])
    if not company:
        raise Blocked("Company no longer exists")
    if job.kind in {"research","pipeline"}:
        await research(db,company)
    if job.kind in {"generate","pipeline"}:
        row=await generate(db,company,p.get("sequence",0))
        contact=db.get(Contact,row.contact_id)
        if settings().hunter_api_key and contact.validation!="valid":
            await verify(db,contact)
        return {"draft_id":row.id,"status":row.status}
    return {"stage":company.stage}

async def execute(db,job):
    if not job.id:  # Unsaved callers can validate, but cannot create a durable job execution.
        return await _execute(db,job)
    def authorize():
        if settings().manual_mode and job.kind in {"discover","research","pipeline","generate","regenerate","verify","send"}:
            raise Blocked("Manual mode: paid calls and live sends are disabled")
        return policy.background(db,job.kind)
    attempt,replay=ledger.claim(db,'job:'+job.id,'job:'+job.kind,'local',authorize,entity_id=job.id,job_id=job.id,retry=True)
    if replay:return attempt.receipt
    try:
        result=await _execute(db,job)
    except Exception as exc:
        db.rollback();ledger.finish(db,attempt,'failed',reason='job_blocked' if isinstance(exc,Blocked) else 'job_failed')
        raise
    ledger.finish(db,attempt,'succeeded',receipt=result or {})
    return result

async def tick():
    with leadership() as acquired:
        if not acquired:
            return
        with Session() as db:
            # Crash recovery never blindly replays a potentially external mutation.
            for job in db.scalars(select(Job).where(Job.status=="running")):
                transition(db,job,"interrupted",domain="job",reason="worker_interrupted")
                op=ledger.operation(db,"job:"+job.id)
                if op and op.status=="running":
                    attempt=ledger.latest(db,op)
                    ledger.finish(db,attempt,"unknown",reason="worker_interrupted")
                job.error="Worker interrupted. Inspect results before explicitly retrying."
                job.finished_at=now()
            for row in db.scalars(select(Outreach).where(Outreach.status=="sending")):
                op=ledger.operation(db,"send:"+row.id)
                if not op or op.provider=="legacy":transition(db,row,"unknown",reason="legacy_crash_recovery")
            db.commit()
            job=db.scalar(select(Job).where(Job.status=="queued").order_by(Job.created_at).limit(1))
            if job:
                transition(db,job,"running",domain="job",reason="worker_claim")
                job.started_at=now()
                db.commit()
                try:
                    job.result=await execute(db,job)
                    transition(db,job,"done",domain="job",reason="completed")
                except Exception as exc:
                    db.rollback()
                    job=db.get(Job,job.id)
                    transition(db,job,"blocked" if isinstance(exc,Blocked) else "failed",domain="job",reason="execution_failed")
                    # Never persist exception URLs, request headers, or API keys.
                    job.error=__import__('app.redaction',fromlist=['redact']).redact(str(exc))[:500] if isinstance(exc,Blocked) else type(exc).__name__+": integration/job failure; inspect configuration or provider console"
                    if job.kind in {"research","pipeline","generate"}:
                        company=db.get(Company,job.payload.get("id"))
                        if company and company.stage not in STOP_STAGES:
                            company.stage="needs_attention"
                    log.warning("Job %s ended with %s",job.id,type(exc).__name__)
                job.finished_at=now()
                db.commit()
                return
            state=db.get(State,"automation")
            if not state or not state.value.get("enabled"):
                return
            if settings().manual_mode:
                return
            # Poll even when no drafts remain, so late replies still update the CRM.
            sync=db.get(State,"mail_sync")
            if settings().oauth_refresh_token and (not sync or (now()-aware(__import__('datetime').datetime.fromisoformat(sync.value["at"]))).total_seconds()>300):
                enqueue(db,"sync",{},"scheduled-sync:"+str(int(now().timestamp())//300))
            # Bounded scheduled discovery once daily; the search cache avoids rescanning.
            spec=state.value.get("discovery")
            if spec:
                enqueue(db,"discover",spec,"scheduled-discovery:"+now().strftime("%Y-%m-%d"))
            company=db.scalar(select(Company).where(Company.stage=="discovered",Company.demo==False).order_by(Company.score.desc()).limit(1))
            if company:
                enqueue(db,"pipeline",{"id":company.id},"pipeline:"+company.id)
            # Initial approved messages and follow-ups share one total sending limit.
            if not settings().dry_run:
                for row in db.scalars(select(Outreach).where(Outreach.status=="approved",Outreach.due_at<=now()).order_by(Outreach.due_at).limit(5)):
                    try:
                        await send_one(db,row)
                        break
                    except Blocked as exc:
                        row.review={**row.review,"send_block_reason":__import__('app.redaction',fromlist=['redact']).redact(str(exc))}
                        db.commit()
            for initial in db.scalars(select(Outreach).where(Outreach.sequence==0,Outreach.status=="sent")):
                company=db.get(Company,initial.company_id)
                if company.research.get("followups") is False or company.stage in STOP_STAGES or not initial.sent_at:
                    continue
                policy_row=db.get(State,"outreach_policy")
                if not policy_row or not policy_row.value.get("enabled") or policy_row.value.get("max_followups_per_company")!=1:continue
                for seq,days in [(1,7)]:
                    due=aware(initial.sent_at)+timedelta(days=days)
                    previous=db.scalar(select(Outreach).where(Outreach.company_id==company.id,Outreach.sequence==seq-1))
                    existing=db.scalar(select(Outreach).where(Outreach.company_id==company.id,Outreach.sequence==seq))
                    if due<=now() and previous and previous.status=="sent" and not existing and now()-aware(previous.sent_at)>=timedelta(days=6):
                        enqueue(db,"generate",{"id":company.id,"sequence":seq},f"followup:{company.id}:{seq}")
                        break
            db.merge(State(key="heartbeat",value={"at":now().isoformat()}))
            db.commit()

async def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            await tick()
        except Exception as exc:
            log.error("Worker tick: %s",type(exc).__name__)
        await asyncio.sleep(15)

if __name__=="__main__":
    asyncio.run(main())
