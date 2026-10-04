"""Authenticated status from database evidence; no provider checks on page reads."""

from datetime import datetime
from sqlalchemy import select, func, inspect, text
from ..models import State, Integration, Operation, Job, Outreach, Event, now
from ..core import aware, day_start
from ..config import settings


def status(db):
    db.execute(text("SELECT 1"))
    schema = (
        db.scalar(text("SELECT version_num FROM alembic_version"))
        if inspect(db.bind).has_table("alembic_version")
        else "unknown"
    )

    def pulse(key):
        row = db.get(State, key)
        value = row.value if row else {}
        timestamp = value.get("at")
        try:
            age = (now() - aware(datetime.fromisoformat(timestamp))).total_seconds()
        except (ValueError, TypeError):
            age = float("inf")
        healthy = (
            age <= settings().worker_lease_seconds and value.get("status") != "stopped"
        )
        return (
            "processing" if value.get("status") == "processing" else "available"
        ) if healthy else "offline", timestamp

    worker, wat = pulse("worker_heartbeat")
    scheduler, sat = pulse("scheduler_heartbeat")
    if worker == "processing" and scheduler == "offline":
        scheduler = "waiting_for_current_job"
    integration = db.get(Integration, "gmail")
    sync = db.get(State, "response_sync")
    policy = db.get(State, "outreach_policy")
    try:
        stale = (
            not sync
            or (
                now() - aware(datetime.fromisoformat(sync.value["last_success"]))
            ).total_seconds()
            > settings().mailbox_poll_seconds * 2
        )
    except (ValueError, KeyError):
        stale = True
    unresolved = db.scalar(
        select(func.count())
        .select_from(Operation)
        .where(
            Operation.kind.in_(["company_send", "self_test", "mailbox_draft"]),
            Operation.status.in_(["running", "unknown"]),
        )
    )
    unresolved += db.scalar(
        select(func.count())
        .select_from(Outreach)
        .where(
            Outreach.status.in_(["unknown", "sending"]),
            ~select(Operation.id)
            .where(
                Operation.outreach_id == Outreach.id, Operation.kind == "company_send"
            )
            .exists(),
        )
    )
    from . import ledger, jobs, policy as communication_policy
    limits=communication_policy.snapshot(db,'read_only')
    bounces=len(set(db.scalars(select(Event.company_id).where(Event.kind=='bounce',Event.created_at>=day_start()))))

    if ledger.unresolved(db) and unresolved == 0:
        unresolved = 1
    communication = list(
        db.scalars(
            select(Job)
            .where(Job.kind.in_(["send", "sync", "reconcile", "followup_prepare"]))
            .order_by(Job.created_at.desc())
            .limit(25)
        )
    )
    return {
        "database": "reachable",
        "schema_version": schema,
        "worker": worker,
        "worker_at": wat,
        "scheduler": scheduler,
        "scheduler_at": sat,
        "gmail": integration.status if integration else "disconnected",
        "unresolved": unresolved,
        "sync_stale": stale,
        "recurring_paused": not policy or not policy.value.get("enabled"),
        "daily_attempts": communication_policy.send_usage(db,day_start()),
        "daily_limit": limits['daily_cap'],
        "daily_bounces": bounces,
        "bounce_stop": bounces>=min(2,(policy.value if policy else {}).get('stop_after_bounces_per_day',2)),
        "communication_jobs": [jobs.view(db, j) for j in communication],
    }


def require_schema(db):
    """Production startup gate; diagnostics contain no SQL or connection secrets."""
    try:
        if (
            not inspect(db.bind).has_table("alembic_version")
            or db.scalar(text("SELECT version_num FROM alembic_version")) != "006"
        ):
            raise RuntimeError()
    except Exception:
        raise RuntimeError(
            "Production database/schema unavailable; verify stopped-sender migration to schema006"
        ) from None
