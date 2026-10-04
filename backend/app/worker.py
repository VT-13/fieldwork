"""Deterministic scheduler and durable executor; current policy owns external work."""

import asyncio
import logging
from contextlib import contextmanager
from sqlalchemy import select, text
from .db import Session, engine
from .models import Company, Contact, Outreach, State, now
from .domain.states import transition
from .services import ledger, policy
from .config import settings
from .core import Blocked, STOP_STAGES
from .providers import verify
from .services.intelligence import ConfiguredProspects

discover = ConfiguredProspects().discover
from .pipeline import research, generate
from .mail import sync_mailbox
from .services.jobs import enqueue

from uuid import uuid4

INSTANCE_ID = str(uuid4())
log = logging.getLogger("worker")


@contextmanager
def leadership():
    if engine.dialect.name == "postgresql":
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

        with open(".worker.lock", "w") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


async def _execute(db, job):
    policy.background(db, job.kind)
    p = job.payload
    if settings().manual_mode and job.kind in {
        "discover",
        "research",
        "pipeline",
        "generate",
        "regenerate",
        "verify",
        "send",
        "followup_prepare",
    }:
        raise Blocked(
            "Manual mode: use the personal review desk; paid calls and live sends are disabled"
        )
    if job.kind == "discover":
        async with asyncio.timeout(settings().discovery_seconds):
            rows = await discover(db, p)
        from .intelligence.discovery import ingest_candidates

        return ingest_candidates(
            db, rows, p.get("context", "Personal internship search")
        )
    if job.kind == "candidate_import":
        from .intelligence.discovery import ingest_candidates

        return ingest_candidates(
            db, p["companies"], p.get("context", "Personal internship search")
        )
    if job.kind == "mailbox_draft":
        from .draft_mail import save_mailbox_draft

        return await save_mailbox_draft(db, p["id"], p["draft_hash"])
    if job.kind == "sync":
        return {"messages": await sync_mailbox(db)}
    if job.kind == "reconcile":
        from .services.reconciliation import reconcile

        return await reconcile(db, p["id"])
    if job.kind == "followup_prepare":
        from .services.email_provider import MailboxProvider
        from .mail import Mailbox

        original = db.get(Outreach, p["id"])
        company, contact = policy.followup(db, original, now())
        provider = MailboxProvider(Mailbox())
        await provider.connect()
        await provider.check_conversation(db, original, contact, original)
        ledger.lock(db)
        company, contact = policy.followup(db, db.get(Outreach, p["id"]), now())
        db.commit()
        row = await generate(db, company, 1, job_id=job.id)
        return {
            "draft_id": row.id,
            "status": row.status,
            "requires_operator_review": True,
        }
    if job.kind == "regenerate":
        row = db.get(Outreach, p["id"])
        if not row or row.status not in {"draft", "approved", "rejected"}:
            raise Blocked("Draft cannot be regenerated")
        company = db.get(Company, row.company_id)
        seq = row.sequence
        generated = await generate(db, company, seq, replace=True, job_id=job.id)
        return {"draft_id": generated.id}
    if job.kind == "send":
        from .services.delivery import send_company

        return await send_company(db, p["id"], mode="scheduled")
    if job.kind == "verify":
        return {"validation": await verify(db, db.get(Contact, p["id"]))}
    company = db.get(Company, p["id"])
    if not company:
        raise Blocked("Company no longer exists")
    if job.kind in {"research", "pipeline"}:
        research_result = await research(db, company)
    if job.kind in {"generate", "pipeline"}:
        row = await generate(db, company, p.get("sequence", 0), job_id=job.id)
        contact = db.get(Contact, row.contact_id)
        if settings().hunter_api_key and contact.validation != "valid":
            await verify(db, contact)
        return {"draft_id": row.id, "status": row.status}
    return {
        "stage": company.stage,
        **(research_result if job.kind == "research" else {}),
    }


async def execute(db, job):
    if (
        not job.id
    ):  # Unsaved callers can validate, but cannot create a durable job execution.
        return await _execute(db, job)

    def authorize():
        if job.owner_token:
            from .services.jobs import require_owner

            require_owner(db, job.id, job.owner_token)
        if settings().manual_mode and job.kind in {
            "discover",
            "research",
            "pipeline",
            "generate",
            "regenerate",
            "verify",
            "send",
            "followup_prepare",
        }:
            raise Blocked("Manual mode: paid calls and live sends are disabled")
        return policy.background(db, job.kind)

    attempt, replay = ledger.claim(
        db,
        "job:" + job.id,
        "job:" + job.kind,
        "local",
        authorize,
        entity_id=job.id,
        job_id=job.id,
        retry=True,
    )
    if replay:
        return attempt.receipt
    try:
        from .intelligence.bounds import scope

        with scope(db, job.id) as bounds:
            result = await _execute(db, job)
            if job.kind in (
                "discover",
                "candidate_import",
                "research",
                "pipeline",
                "generate",
                "regenerate",
                "verify",
            ):
                result = {**job.result, **(result or {}), **bounds.summary()}
                attempt.network_units = bounds.requests
    except Exception as exc:
        db.rollback()
        if "bounds" in locals():
            attempt.network_units = bounds.requests
            job.result = {**job.result, **bounds.summary()}
            from .intelligence.bounds import IntelligenceFailure

            if isinstance(exc, IntelligenceFailure):
                job.result = {
                    **job.result,
                    "failure": {"code": exc.code, "retryable": exc.retryable},
                }
        ledger.finish(
            db,
            attempt,
            "failed",
            reason="job_blocked" if isinstance(exc, Blocked) else "job_failed",
            receipt=bounds.summary() if "bounds" in locals() else {},
        )
        raise
    ledger.finish(db, attempt, "succeeded", receipt=result or {})
    return result


async def tick():
    from .services import jobs, scheduler

    with leadership() as acquired:
        if not acquired:
            return False
        with Session() as db:
            jobs.recover(db, now())
            scheduler.tick(db)
            db.merge(
                State(
                    key="worker_heartbeat",
                    value={
                        "at": now().isoformat(),
                        "status": "idle",
                        "instance_id": INSTANCE_ID,
                    },
                )
            )
            db.commit()
            job = jobs.claim_next(db)
            if not job:
                return False
            token = job.owner_token
            db.merge(
                State(
                    key="worker_heartbeat",
                    value={
                        "at": now().isoformat(),
                        "status": "processing",
                        "instance_id": INSTANCE_ID,
                        "job_id": job.id,
                    },
                )
            )
            db.commit()

            async def heartbeat():
                while True:
                    await asyncio.sleep(settings().worker_lease_seconds / 3)
                    with Session() as current:
                        jobs.renew(current, job.id, token, INSTANCE_ID)

            pulse = asyncio.create_task(heartbeat())
            try:
                async with asyncio.timeout(settings().job_timeout_seconds):
                    with jobs.owned(job):
                        result = await execute(db, job)
                db.rollback()
                ledger.lock(db)
                current = db.get(type(job), job.id)
                if current.status == "running" and current.owner_token == token:
                    current.result = result or {}
                    transition(db, current, "done", domain="job", reason="completed")
            except BaseException as exc:
                db.rollback()
                ledger.lock(db)
                current = db.get(type(job), job.id)
                if current.status == "running" and current.owner_token == token:
                    state = (
                        "interrupted"
                        if isinstance(exc, asyncio.CancelledError)
                        else "blocked"
                        if isinstance(exc, Blocked)
                        else "failed"
                    )
                    transition(
                        db, current, state, domain="job", reason="execution_" + state
                    )
                    current.error = (
                        __import__("app.redaction", fromlist=["redact"]).redact(
                            str(exc)
                        )[:300]
                        if isinstance(exc, Blocked)
                        else "Worker interrupted"
                        if isinstance(exc, asyncio.CancelledError)
                        else "Integration/job failure; inspect configuration"
                    )
                    if job.kind in {"research", "pipeline", "generate"}:
                        company = db.get(Company, job.payload.get("id"))
                        if company and company.stage not in STOP_STAGES:
                            company.stage = "needs_attention"
                    log.warning(
                        "job_id=%s kind=%s status=%s category=%s",
                        job.id,
                        job.kind,
                        state,
                        type(exc).__name__,
                    )
                if isinstance(exc, asyncio.CancelledError):
                    op = ledger.operation(db, "job:" + job.id)
                    if op and op.status == "running":
                        ledger.finish(
                            db,
                            ledger.latest(db, op),
                            "unknown"
                            if job.kind in ("send", "mailbox_draft")
                            else "failed",
                            reason="worker_cancelled",
                        )
                    if job.kind == "send":
                        row = db.get(Outreach, job.payload.get("id"))
                        send = ledger.operation(db, "send:" + row.id) if row else None
                        if row and row.status == "sending":
                            transition(db, row, "unknown", reason="worker_cancelled")
                            if send and send.status == "running":
                                ledger.finish(
                                    db,
                                    ledger.latest(db, send),
                                    "unknown",
                                    reason="worker_cancelled",
                                )
                    # No resend. Reserved communications stay held for positive reconciliation.
                    db.commit()
                    raise
            finally:
                pulse.cancel()
                from contextlib import suppress

                with suppress(asyncio.CancelledError):
                    await pulse
                current = db.get(type(job), job.id)
                if current.owner_token == token:
                    current.lease_until = None
                    current.owner_token = ""
                    current.finished_at = now()
                    db.commit()
            return True


async def main():
    import signal
    from .redaction import install_logging

    logging.basicConfig(level=logging.INFO)
    install_logging()
    with Session() as db:
        from sqlalchemy import inspect

        if (
            not inspect(db.bind).has_table("alembic_version")
            or db.scalar(text("SELECT version_num FROM alembic_version")) != "005"
        ):
            raise SystemExit(
                "Worker requires schema005; run migration on the intended staged database first"
            )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    # Graceful signals finish the bounded in-flight job, then prevent new claims.
    while not stop.is_set():
        try:
            await tick()
        except Exception as exc:
            log.error("Worker tick failed category=%s", type(exc).__name__)
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings().worker_poll_seconds)
        except TimeoutError:
            pass
    with Session() as db:
        heartbeat = db.get(State, "worker_heartbeat")
        if heartbeat and heartbeat.value.get("instance_id") == INSTANCE_ID:
            heartbeat.value = {
                **heartbeat.value,
                "at": now().isoformat(),
                "status": "stopped",
            }
            db.commit()


if __name__ == "__main__":
    import sys, json

    if sys.argv[1:] == ["--health"]:
        from .services.runtime import status

        with Session() as db:
            value = status(db)
            print(
                json.dumps(
                    {
                        k: value[k]
                        for k in (
                            "database",
                            "schema_version",
                            "worker",
                            "scheduler",
                            "gmail",
                            "unresolved",
                            "sync_stale",
                            "recurring_paused",
                        )
                    }
                )
            )
            raise SystemExit(
                0
                if value["schema_version"] == "005"
                and value["worker"] in ("available", "processing")
                else 1
            )
    if sys.argv[1:]:
        raise SystemExit("Usage: python -m app.worker [--health]")
    asyncio.run(main())
