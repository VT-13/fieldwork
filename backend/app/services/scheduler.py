"""Bounded intent creation; never transmits or grants delivery authorization."""

from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select, or_, func
from sqlalchemy.orm import aliased
from ..models import (
    State,
    Job,
    Integration,
    Outreach,
    Company,
    Operation,
    ActionAttempt,
    now,
)
from ..config import settings
from ..core import aware, STOP_STAGES, Blocked
from . import ledger, jobs


def tick(db, at=None):
    at = at or now()
    cfg = settings()
    ledger.lock(db)
    db.merge(
        State(key="scheduler_heartbeat", value={"at": at.isoformat(), "status": "ok"})
    )
    integration = db.get(Integration, "gmail")
    connected = integration and integration.status == "connected"
    bucket = str(int(at.timestamp()) // cfg.mailbox_poll_seconds)
    sync = db.get(State, "response_sync")
    retry_at = sync.value.get("next_retry_at") if sync else None
    can_poll = not retry_at or aware(datetime.fromisoformat(retry_at)) <= at
    if connected and cfg.response_poll_enabled and can_poll:
        jobs.enqueue(db, "sync", {}, "scheduled-sync:" + bucket, commit=False)
    if connected:
        pending = list(
            db.scalars(
                select(Operation)
                .where(
                    Operation.kind == "company_send",
                    or_(
                        Operation.status.in_(["running", "unknown"]),
                        select(ActionAttempt.id)
                        .where(
                            ActionAttempt.operation_id == Operation.id,
                            ActionAttempt.receipt["confirmation_pending"].as_boolean()
                            == True,
                        )
                        .exists(),
                    ),
                )
                .order_by(Operation.created_at)
                .limit(100)
            )
        )
        # Rotate a bounded batch so a held oldest operation cannot starve later ones.
        cursor = db.get(State, "reconciliation_schedule_cursor")
        last_id = cursor.value.get("last_id") if cursor else None
        ids = [op.id for op in pending]
        offset = (ids.index(last_id) + 1) % len(ids) if last_id in ids else 0
        pending = pending[offset:] + pending[:offset]
        queued = 0
        for op in pending:
            attempt = ledger.latest(db, op)
            if op.status in ("running", "unknown") or (
                attempt and attempt.receipt.get("confirmation_pending")
            ):
                jobs.enqueue(
                    db,
                    "reconcile",
                    {"id": op.outreach_id},
                    "reconcile:" + op.id + ":" + bucket,
                    commit=False,
                )
                db.merge(
                    State(
                        key="reconciliation_schedule_cursor", value={"last_id": op.id}
                    )
                )
                queued += 1
                if queued == 5:
                    break
    automation = db.get(State, "automation")
    enabled = automation and automation.value.get("enabled")
    if not enabled:
        db.commit()
        return
    policy = db.get(State, "outreach_policy")
    p = policy.value if policy else {}
    from ..intelligence.capabilities import capabilities

    caps = {r["id"]: r for r in capabilities(db)["providers"]}
    from . import autopilot
    if autopilot.configuration(db)['autopilot_enabled']:
        autopilot.plan(db, at, caps)
    else:
        if not cfg.manual_mode and not p.get("stop_requested"):
            spec = automation.value.get("discovery")
            if spec and caps.get(spec.get("provider", "maps"), {}).get("available"):
                day = at.astimezone(ZoneInfo(cfg.timezone)).date().isoformat()
                jobs.enqueue(
                    db, "discover", spec, "scheduled-discovery:" + day, commit=False
                )
            if caps["research"]["available"] and caps["generate"]["available"]:
                company = db.scalar(
                    select(Company)
                    .where(Company.stage == "discovered", Company.demo == False)
                    .order_by(Company.score.desc())
                    .limit(1)
                )
                if company:
                    jobs.enqueue(
                        db,
                        "pipeline",
                        {"id": company.id},
                        "pipeline:" + company.id,
                        commit=False,
                    )
    if p.get("enabled") and not p.get("stop_requested"):
        # One final follow-up intent per original; due time never slides with polling.
        follow = aliased(Outreach)
        for original in db.scalars(
            select(Outreach)
            .join(Company, Company.id == Outreach.company_id)
            .where(
                Outreach.sequence == 0,
                Outreach.status == "sent",
                Outreach.sent_at.is_not(None),
                Company.stage.not_in(STOP_STAGES),
                Company.demo == False,
                Company.research["followups"].as_boolean().is_not(False),
                ~select(follow.id)
                .where(follow.company_id == Outreach.company_id, follow.sequence == 1)
                .exists(),
                ~select(Job.id)
                .where(Job.dedupe_key == "followup-prepare:" + Outreach.id)
                .exists(),
            )
            .order_by(Outreach.sent_at)
            .limit(100)
        ):
            company = db.get(Company, original.company_id)
            existing = db.scalar(
                select(Outreach.id).where(
                    Outreach.company_id == original.company_id, Outreach.sequence == 1
                )
            )
            if (
                original.sent_at
                and p.get("max_followups_per_company") == 1
                and not existing
                and company.stage not in STOP_STAGES
                and company.research.get("followups") is not False
            ):
                due = aware(original.sent_at) + timedelta(hours=168)
                jobs.enqueue(
                    db,
                    "followup_prepare",
                    {"id": original.id, "company_id": original.company_id},
                    "followup-prepare:" + original.id,
                    due,
                    commit=False,
                )
        local = at.astimezone(ZoneInfo(cfg.timezone))
        if (
            not cfg.dry_run
            and not cfg.manual_mode
            and local.weekday() < 5
            and 9 <= local.hour < 17
        ):
            pending_send = db.scalar(select(Job.id).where(Job.kind == 'send', Job.status.in_(['queued', 'running'])).limit(1))
            from .policy import send_usage, snapshot
            start = local.replace(hour=0, minute=0, second=0, microsecond=0)
            last = db.scalar(select(func.max(Outreach.sent_at)))
            can_send = (not pending_send and not ledger.unresolved(db)
                        and send_usage(db, start) < snapshot(db, 'scheduled')['daily_cap']
                        and (not last or (at - aware(last)).total_seconds() >= max(60, cfg.send_interval_seconds, p.get('send_interval_seconds', 60))))
            for row in db.scalars(
                select(Outreach)
                .where(
                    Outreach.status == "approved",
                    Outreach.attempts == 0,
                    Outreach.due_at <= at,
                    ~select(Job.id)
                    .where(Job.dedupe_key == "send:" + Outreach.id + ":0")
                    .exists(),
                )
                .order_by(Outreach.sequence.desc(), Outreach.due_at)
                .limit(25)
            ):
                if not can_send:
                    break
                try:
                    if row.review.get('autopilot_approval'):
                        autopilot.approval_current(db, row, at)
                    if not row.sequence and autopilot.remaining(db, at) <= 0:
                        continue
                except Blocked:
                    continue
                jobs.enqueue(
                    db,
                    "send",
                    {"id": row.id, "sequence": row.sequence},
                    "send:" + row.id + ":0",
                    max(aware(row.due_at), at),
                    commit=False,
                )
                break
    db.commit()
