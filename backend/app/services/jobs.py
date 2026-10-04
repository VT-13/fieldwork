"""Database job ownership, leases and recovery. No provider I/O or send authority."""

from datetime import timedelta
from contextvars import ContextVar
from contextlib import contextmanager
from uuid import uuid4
from sqlalchemy import select, or_, case
from ..models import Job, State, Outreach, ActionAttempt, now
from ..core import aware, Blocked
from ..config import settings
from ..domain.states import transition
from . import ledger

active_job = ContextVar("active_job", default=None)


@contextmanager
def owned(job):
    token = active_job.set((job.id, job.owner_token))
    try:
        yield
    finally:
        active_job.reset(token)


SAFE_RETRY = {"sync", "reconcile"}
COMMUNICATION_JOBS = {"send", "followup_prepare"}


def enqueue(db, kind, payload, key, available_at=None, *, commit=True):
    ledger.lock(db)
    job = db.scalar(select(Job).where(Job.dedupe_key == key))
    if not job:
        job = Job(kind=kind, payload=payload, dedupe_key=key, available_at=available_at)
        db.add(job)
        db.flush()
    if commit:
        db.commit()
    return job


def cancel_company(db, company_id, reason):
    for job in db.scalars(
        select(Job).where(Job.status.in_(["queued", "running", "blocked"]))
    ):
        row = db.get(Outreach, job.payload.get("id")) if job.kind == "send" else None
        related = row.company_id if row else job.payload.get("company_id")
        if job.kind in ("generate", "regenerate") and job.payload.get("sequence") == 1:
            related = job.payload.get("id")
        if related == company_id and job.kind in COMMUNICATION_JOBS | {
            "generate",
            "regenerate",
        }:
            transition(db, job, "cancelled", domain="job", reason=reason)
            job.error = "Conversation stopped; future communication cancelled"
            job.finished_at = now()


def recover(db, at):
    ledger.lock(db)
    expired = list(
        db.scalars(
            select(Job).where(
                Job.status == "running",
                or_(Job.lease_until == None, Job.lease_until <= at),
            )
        )
    )
    for job in expired:
        transition(db, job, "interrupted", domain="job", reason="lease_expired")
        job.owner_token = ""
        job.lease_until = None
        job.finished_at = at
        job.error = "Worker interrupted; inspect saved outcome before retrying"
        op = ledger.operation(db, "job:" + job.id)
        if op and op.status == "running":
            ledger.finish(
                db,
                ledger.latest(db, op),
                "unknown" if job.kind in ("send", "mailbox_draft") else "failed",
                reason="lease_expired",
            )
        # A send reservation may outlive its worker even before the first socket write.
        if job.kind == "send":
            row = db.get(Outreach, job.payload.get("id"))
            send = ledger.operation(db, "send:" + row.id) if row else None
            if row and row.status == "sending":
                transition(db, row, "unknown", reason="worker_interrupted")
                if send and send.status == "running":
                    ledger.finish(
                        db,
                        ledger.latest(db, send),
                        "unknown",
                        reason="worker_interrupted",
                    )
        if (
            job.kind in SAFE_RETRY
            and job.payload.get("recovery_count", 0) < settings().max_job_retries
        ):
            job.payload = {
                **job.payload,
                "recovery_count": job.payload.get("recovery_count", 0) + 1,
            }
            transition(db, job, "queued", domain="job", reason="safe_read_recovery")
            job.available_at = at + timedelta(
                seconds=30 * job.payload["recovery_count"]
            )
    # Historical running company reservations also fail closed, even without a Job.
    for row in db.scalars(select(Outreach).where(Outreach.status == "sending")):
        send = ledger.operation(db, "send:" + row.id)
        if not send or aware(ledger.latest(db, send).started_at) < at - timedelta(
            seconds=settings().job_timeout_seconds + settings().worker_lease_seconds
        ):
            transition(db, row, "unknown", reason="orphaned_reservation")
            if send and send.status == "running":
                ledger.finish(
                    db,
                    ledger.latest(db, send),
                    "unknown",
                    reason="orphaned_reservation",
                )
    db.commit()
    return len(expired)


def claim_next(db, at=None):
    at = at or now()
    ledger.lock(db)
    job = db.scalar(
        select(Job)
        .where(
            Job.status == "queued",
            or_(Job.available_at == None, Job.available_at <= at),
        )
        .order_by(
            case(
                (Job.kind.in_(["sync", "reconcile"]), 0),
                (Job.kind == "followup_prepare", 1),
                (Job.kind == "send", 2),
                else_=3,
            ),
            Job.available_at.asc().nullsfirst(),
            Job.created_at,
        )
        .limit(1)
    )
    if job:
        transition(db, job, "running", domain="job", reason="worker_claim")
        job.owner_token = str(uuid4())
        job.lease_until = at + timedelta(seconds=settings().worker_lease_seconds)
        job.started_at = at
        job.finished_at = None
        job.error = ""
    db.commit()
    return job


def require_owner(db, id, token):
    job = db.get(Job, id)
    if (
        not job
        or job.status != "running"
        or job.owner_token != token
        or not job.lease_until
        or aware(job.lease_until) <= now()
    ):
        raise Blocked("Job ownership expired or work stopped")
    return job


def renew(db, id, token, instance_id=None):
    ledger.lock(db)
    job = require_owner(db, id, token)
    job.lease_until = now() + timedelta(seconds=settings().worker_lease_seconds)
    db.merge(
        State(
            key="worker_heartbeat",
            value={
                "at": now().isoformat(),
                "job_id": id,
                "status": "processing",
                "instance_id": instance_id,
            },
        )
    )
    db.commit()


def retry_allowed(db, job):
    if job.payload.get("stop_requested") or job.status not in {
        "failed",
        "blocked",
        "interrupted",
    }:
        return False
    if job.kind == "send":
        row = db.get(Outreach, job.payload.get("id"))
        op = ledger.operation(db, "send:" + row.id) if row else None
        if (
            not row
            or row.status != "approved"
            or row.attempts
            or job.status != "blocked"
            or (op and op.status in {"running", "unknown", "succeeded", "failed"})
        ):
            return False
    op = ledger.operation(db, "job:" + job.id)
    if op and op.status in {"running", "unknown", "succeeded"}:
        return False
    attempts = (
        len(
            list(
                db.scalars(
                    select(ActionAttempt).where(ActionAttempt.operation_id == op.id)
                )
            )
        )
        if op
        else 0
    )
    return attempts <= settings().max_job_retries


def view(db, job):
    return {
        **{
            c.name: getattr(job, c.name)
            for c in job.__table__.columns
            if c.name != "owner_token"
        },
        "can_retry": retry_allowed(db, job),
    }
