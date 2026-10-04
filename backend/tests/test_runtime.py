"""Module5 communication runtime: disposable data and controlled provider evidence only."""

import asyncio
import base64
from datetime import timedelta
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from types import SimpleNamespace
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import sessionmaker
from app.models import (
    Company,
    Contact,
    Profile,
    State,
    Outreach,
    Evidence,
    ContactObservation,
    Job,
    Event,
    Operation,
    ActionAttempt,
    now,
)
from app.core import Blocked, record_event
from app.services import jobs, ledger, policy, scheduler
from app.services.delivery import send_company
from app.services.contracts import DeliveryReceipt, MailboxFailure
from app.services.reconciliation import reconcile
from app.responses import sync_session, ingest
from app import worker
from test_postgres_security import pg as pg, upgrade


class Provider:
    name = "gmail"
    sender = "student@example.com"

    def __init__(self, error=None):
        self.sent = 0
        self.error = error

    async def connect(self):
        pass

    async def check_conversation(self, *a):
        pass

    async def deliver(self, db, row, ct, original):
        self.sent += 1
        if self.error:
            raise self.error
        return DeliveryReceipt("accepted-id", "accepted-thread")

    async def confirm(self, *a):
        return True


class Box:
    token = "fake"
    cfg = SimpleNamespace(sender_email="student@example.com", mail_provider="gmail")

    def __init__(self, messages=None, *, account="student@example.com", expire=False):
        self.items = {m["id"]: m for m in messages or []}
        self.calls = []
        self.account = account
        self.expire = expire

    async def call(self, method, url, **kwargs):
        assert method == "GET"
        path = url.rsplit("/", 1)[-1]
        p = kwargs.get("params") or {}
        self.calls.append((path, p))
        if path == "profile":
            return {"emailAddress": self.account, "historyId": "100"}
        if path == "history":
            if self.expire:
                self.expire = False
                raise MailboxFailure("cursor_invalid", definite=True)
            return {
                "historyId": "101",
                "history": [
                    {"messagesAdded": [{"message": {"id": id}}]} for id in self.items
                ],
            }
        if path == "messages":
            return {"messages": [{"id": id} for id in self.items]}
        return self.items[path]


def msg(
    row,
    ct,
    id="inbound",
    *,
    sender=None,
    to="student@example.com",
    text="Could you share your portfolio?",
    sent=False,
    thread=None,
    refs=None,
    auto=False,
):
    headers = {
        "from": sender or ct.email,
        "to": to,
        "subject": row.subject,
        "message-id": row.message_id if sent else "<" + id + "@example.net>",
    }
    if refs:
        headers["references"] = refs
    if auto:
        headers["auto-submitted"] = "auto-replied"
    return {
        "id": id,
        "threadId": thread if thread is not None else row.thread_id,
        "internalDate": str(int(now().timestamp() * 1000)),
        "labelIds": ["SENT"] if sent else ["INBOX", "UNREAD"],
        "payload": {
            "mimeType": "text/plain",
            "headers": [{"name": k, "value": v} for k, v in headers.items()],
            "body": {"data": base64.urlsafe_b64encode(text.encode()).decode()},
        },
    }


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("MANUAL_MODE", "false")


def confirmed(db, ready):
    c, ct, row = ready
    row.status = "sent"
    row.provider_id = "original-id"
    row.thread_id = "original-thread"
    row.message_id = "<original@example.com>"
    row.sent_at = now() - timedelta(days=8)
    c.stage = "contacted"
    db.commit()
    return c, ct, row


async def test_success_receipt_replay_does_not_connect_or_send_again(
    db, ready, enabled
):
    p = Provider()
    first = await send_company(db, ready[2].id, mode="worker", provider=p)
    assert (
        first["account"] == "student@example.com"
        and first["message_id"] == ready[2].message_id
        and first["operation_id"]
    )
    assert not first["confirmation_pending"] and first["sent_verified"]
    policy.set_paused(db, False)
    assert (
        await send_company(db, ready[2].id, mode="worker", provider=p) == first
        and p.sent == 1
    )


@pytest.mark.parametrize(
    "code", ["rate_limited", "authorization_rejected", "provider_rejected"]
)
async def test_definite_rejection_is_terminal_no_blind_retry(db, ready, enabled, code):
    p = Provider(MailboxFailure(code, definite=True, retryable=code == "rate_limited"))
    with pytest.raises(Blocked, match="rejected"):
        await send_company(db, ready[2].id, mode="worker", provider=p)
    assert ready[2].status == "failed" and ready[2].attempts == 1
    with pytest.raises(Blocked):
        await send_company(db, ready[2].id, mode="worker", provider=p)
    assert p.sent == 1


async def test_crash_before_reservation_rolls_back_without_transmission(
    db, ready, enabled, monkeypatch
):
    import app.services.delivery as delivery

    real = delivery.transition

    def fail(db, row, to, **kw):
        if to == "sending":
            raise RuntimeError("Simulated commit preparation failure")
        return real(db, row, to, **kw)

    monkeypatch.setattr(delivery, "transition", fail)
    p = Provider()
    with pytest.raises(RuntimeError):
        await send_company(db, ready[2].id, mode="worker", provider=p)
    db.rollback()
    assert p.sent == 0 and ready[2].attempts == 0 and ready[2].status == "approved"
    assert not ledger.operation(db, "send:" + ready[2].id)


async def test_crash_after_reservation_before_socket_remains_held(db, ready, enabled):
    p = Provider(KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        await send_company(db, ready[2].id, mode="worker", provider=p)
    db.rollback()
    row = db.get(Outreach, ready[2].id)
    assert row.status == "sending" and row.attempts == 1 and ledger.unresolved(db)
    jobs.recover(db, now() + timedelta(hours=1))
    assert row.status == "unknown"
    assert (await reconcile(db, row.id, Box()))["status"] == "held"
    with pytest.raises(Blocked):
        await send_company(db, row.id, mode="worker", provider=p)
    assert p.sent == 1


async def test_provider_success_local_commit_crash_recovers_positive_exact_evidence(
    db, ready, enabled, monkeypatch
):
    real = ledger.finish

    def fail_once(db, attempt, status, **kw):
        if kw.get("reason") == "provider_accepted":
            raise RuntimeError("Simulated DB outage")
        return real(db, attempt, status, **kw)

    p = Provider()
    monkeypatch.setattr(ledger, "finish", fail_once)
    with pytest.raises(RuntimeError):
        await send_company(db, ready[2].id, mode="worker", provider=p)
    db.rollback()
    row = db.get(Outreach, ready[2].id)
    assert row.status == "sending" and ledger.unresolved(db)
    sent = msg(
        row,
        ready[1],
        sent=True,
        sender="student@example.com",
        to=ready[1].email,
        text=row.body,
        id="accepted-id",
        thread="accepted-thread",
    )
    assert (await reconcile(db, row.id, Box([sent])))["status"] == "confirmed"
    assert row.status == "sent" and not ledger.unresolved(db)
    assert (await send_company(db, row.id, mode="worker", provider=p))[
        "provider_id"
    ] == "accepted-id" and p.sent == 1


@pytest.mark.parametrize(
    "change",
    [
        "wrong_account",
        "wrong_recipient",
        "extra_recipient",
        "wrong_body",
        "wrong_rfc",
        "two_matches",
    ],
)
async def test_ambiguous_sent_evidence_cannot_resolve_uncertainty(db, ready, change):
    row = ready[2]
    row.status = "unknown"
    row.message_id = "<reserved>"
    row.sent_at = now()
    row.attempts = 1
    db.commit()
    sent = msg(
        row,
        ready[1],
        sent=True,
        sender="student@example.com",
        to=ready[1].email,
        text=row.body,
    )
    if change == "wrong_recipient":
        sent["payload"]["headers"][1]["value"] = "other@example.com"
    if change == "extra_recipient":
        sent["payload"]["headers"][1]["value"] += ", other@example.com"
    if change == "wrong_body":
        sent["payload"]["body"]["data"] = base64.urlsafe_b64encode(b"Changed").decode()
    if change == "wrong_rfc":
        sent["payload"]["headers"][3]["value"] = "<other>"
    box = Box(
        [sent],
        account="other@example.com"
        if change == "wrong_account"
        else "student@example.com",
    )
    if change == "two_matches":
        box.items["second"] = {**sent, "id": "second"}
    if change == "wrong_account":
        with pytest.raises(Blocked):
            await reconcile(db, row.id, box)
    else:
        assert (await reconcile(db, row.id, box))["status"] == "held"
    assert row.status == "unknown"


async def test_bounded_history_pagination_preserves_cursor_and_replay_idempotency(
    db, ready, monkeypatch
):
    _, ct, row = confirmed(db, ready)
    monkeypatch.setenv("MAILBOX_MAX_MESSAGES", "5")
    box = Box([msg(row, ct, id=str(i)) for i in range(8)])
    r = await sync_session(db, box)
    assert (
        r["status"] == "partial"
        and db.get(State, "response_sync").value.get("history_id") is None
    )
    assert len(db.get(State, "response_sync").value["pending_ids"]) == 3
    r = await sync_session(db, box)
    assert (
        r["status"] == "ok"
        and db.get(State, "response_sync").value["history_id"] == "100"
    )
    assert db.scalar(select(func.count()).select_from(Event)) == 8
    await sync_session(db, box)
    assert db.scalar(select(func.count()).select_from(Event)) == 8
    assert any(path == "history" for path, p in box.calls)
    assert all(path != "modify" for path, p in box.calls)


async def test_expired_cursor_bounded_recovery_and_wrong_account_fail_closed(db, ready):
    _, ct, row = confirmed(db, ready)
    db.add(
        State(
            key="response_sync",
            value={"history_id": "expired", "account": "student@example.com"},
        )
    )
    db.commit()
    box = Box([msg(row, ct)], expire=True)
    assert (await sync_session(db, box))["status"] == "ok"
    assert db.get(State, "response_sync").value["cursor_recovered"]
    assert any(p.get("q", "").startswith("after:") for path, p in box.calls)
    assert (await sync_session(db, Box(account="attacker@example.com")))[
        "status"
    ] == "error"
    assert db.get(State, "response_sync").value["history_id"] == "100"


def test_ambiguous_unthreaded_unknown_reference_wrong_recipient_and_old_mail_ignored(
    db, ready
):
    _, ct, row = confirmed(db, ready)
    for m in [
        msg(row, ct, to="elsewhere@example.com", thread="new"),
        msg(row, ct, thread="new", refs="<unrelated>"),
    ]:
        assert ingest(db, m, [row], {ct.id: ct}, "student@example.com") is None
    row.sent_at = now() - timedelta(days=40)
    assert (
        ingest(
            db, msg(row, ct, thread="new"), [row], {ct.id: ct}, "student@example.com"
        )
        is None
    )


@pytest.mark.parametrize(
    "kind,text,auto",
    [
        ("reply", "Happy to talk", False),
        ("auto_reply", "We received your note", True),
        ("opt_out", "Please stop emailing", False),
        ("bounce", "Final-Recipient: rfc822; founder@example.com", False),
    ],
)
def test_response_linkage_and_durable_followup_cancellation(
    db, ready, kind, text, auto
):
    c, ct, row = confirmed(db, ready)
    follow = Outreach(company_id=c.id, contact_id=ct.id, sequence=1, status="approved")
    db.add(follow)
    db.commit()
    intent = jobs.enqueue(
        db, "followup_prepare", {"id": row.id, "company_id": c.id}, "followup"
    )
    delivery = jobs.enqueue(db, "send", {"id": follow.id}, "delivery")
    m = msg(
        row,
        ct,
        text=text,
        auto=auto,
        sender="mailer-daemon@example.com" if kind == "bounce" else ct.email,
    )
    result = ingest(db, m, [row], {ct.id: ct}, "student@example.com")
    assert (
        result["kind"] == kind
        and result["outreach_id"] == row.id
        and result["contact_id"] == ct.id
    )
    assert (
        intent.status == delivery.status == "cancelled" and follow.status == "cancelled"
    )
    event = db.scalar(select(Event))
    assert event.outreach_id == row.id and event.contact_id == ct.id
    ingest(db, m, [row], {ct.id: ct}, "student@example.com")
    assert db.scalar(select(func.count()).select_from(Event)) == 1
    with pytest.raises(Blocked):
        policy.followup(db, row, now())


def test_scheduler_duplicate_ticks_one_fixed_due_no_catchup_and_pause(db, ready):
    _, _, row = confirmed(db, ready)
    db.add(State(key="automation", value={"enabled": True}))
    db.commit()
    scheduler.tick(db)
    scheduler.tick(db)
    pending = list(db.scalars(select(Job).where(Job.kind == "followup_prepare")))
    assert len(pending) == 1 and pending[0].available_at == row.sent_at + timedelta(
        hours=168
    )
    policy.set_paused(db, False)
    assert pending[0].status == "blocked"
    assert jobs.claim_next(db) is None
    scheduler.tick(db, now() + timedelta(days=40))
    assert len(list(db.scalars(select(Job).where(Job.kind == "followup_prepare")))) == 1


def test_expired_job_fence_safe_read_recovery_and_send_never_requeued(db, ready):
    j = jobs.enqueue(db, "sync", {}, "sync")
    claimed = jobs.claim_next(db)
    token = claimed.owner_token
    claimed.lease_until = now() - timedelta(seconds=1)
    db.commit()
    jobs.recover(db, now())
    assert j.status == "queued" and j.payload["recovery_count"] == 1
    with pytest.raises(Blocked):
        jobs.require_owner(db, j.id, token)
    send = jobs.enqueue(db, "send", {"id": ready[2].id}, "send")
    jobs.claim_next(db)
    send.lease_until = now() - timedelta(seconds=1)
    db.commit()
    jobs.recover(db, now())
    assert send.status == "interrupted"


async def test_reply_during_preflight_wins_before_send_reservation(db, ready, enabled):
    c, ct, first = confirmed(db, ready)
    follow = Outreach(
        company_id=c.id,
        contact_id=ct.id,
        sequence=1,
        status="approved",
        subject=first.subject,
        body="new contribution",
        review={**first.review, "adds_new_value": True},
        evidence_ids=first.evidence_ids,
    )
    db.add(follow)
    db.commit()

    class Reply(Provider):
        async def check_conversation(self, *a):
            record_event(db, c, "reply", "new-unthreaded")

    p = Reply()
    with pytest.raises(Blocked):
        await send_company(db, follow.id, mode="worker", provider=p)
    assert p.sent == 0 and follow.status == "cancelled" and follow.attempts == 0


@pytest.mark.parametrize(
    "alter",
    [
        "uncertain",
        "confirmation_pending",
        "too_early",
        "stale_contact",
        "limit",
        "unreviewed",
    ],
)
async def test_followup_eligibility_holds_invalid_original_or_content(
    db, ready, enabled, alter
):
    c, ct, row = confirmed(db, ready)
    follow = Outreach(
        company_id=c.id,
        contact_id=ct.id,
        sequence=1,
        status="approved",
        subject=row.subject,
        body="new useful contribution",
        review={**row.review, "adds_new_value": True},
        evidence_ids=row.evidence_ids,
    )
    db.add(follow)
    db.commit()
    if alter == "uncertain":
        row.status = "unknown"
    if alter == "confirmation_pending":
        a, _ = ledger.claim(
            db,
            "send:" + row.id,
            "company_send",
            "gmail",
            lambda: {},
            outreach_id=row.id,
            entity_id=row.id,
        )
        ledger.finish(db, a, "succeeded", receipt={"confirmation_pending": True})
    if alter == "too_early":
        row.sent_at = now() - timedelta(hours=167)
    if alter == "stale_contact":
        for o in db.scalars(select(ContactObservation)):
            o.retrieved_at = now() - timedelta(days=60)
    if alter == "limit":
        db.get(State, "outreach_policy").value = {
            "enabled": True,
            "max_followups_per_company": 0,
        }
    if alter == "unreviewed":
        follow.status = "draft"
    db.commit()
    p = Provider()
    with pytest.raises(Blocked):
        await send_company(db, follow.id, mode="worker", provider=p)
    assert p.sent == 0


async def test_worker_completes_disposable_import_and_reports_idle_and_shutdown(
    db, monkeypatch
):
    @contextmanager
    def session():
        yield db

    @contextmanager
    def leader():
        yield True

    monkeypatch.setattr(worker, "Session", session)
    monkeypatch.setattr(worker, "leadership", leader)
    j = jobs.enqueue(
        db,
        "candidate_import",
        {
            "companies": [
                {
                    "name": "Example",
                    "website": "https://runtime.example",
                    "industry": "Robotics",
                }
            ]
        },
        "import",
    )
    await worker.tick()
    assert j.status == "done" and j.owner_token == "" and j.lease_until is None
    assert db.get(State, "worker_heartbeat") and db.get(State, "scheduler_heartbeat")


def copy_ready(source, target):
    for cls in (
        Profile,
        Company,
        Contact,
        Evidence,
        State,
        Outreach,
        ContactObservation,
    ):
        for row in source.scalars(select(cls)):
            target.add(
                cls(**{c.name: getattr(row, c.name) for c in cls.__table__.columns})
            )
        target.flush()
    target.commit()


def test_postgres_two_actual_send_workers_one_transmission(pg, db, ready, enabled):
    upgrade(pg)
    sessions = sessionmaker(pg, expire_on_commit=False)
    with sessions() as target:
        copy_ready(db, target)
    barrier = Barrier(2)
    guard = Lock()
    calls = []

    class Concurrent(Provider):
        async def check_conversation(self, *a):
            barrier.wait(timeout=5)

        async def deliver(self, *a):
            with guard:
                calls.append("transmit")
            await asyncio.sleep(0.03)
            return DeliveryReceipt("unique-provider", "unique-thread")

    def run(_):
        with sessions() as current:
            try:
                return asyncio.run(
                    send_company(
                        current, ready[2].id, mode="worker", provider=Concurrent()
                    )
                )
            except Blocked:
                return "blocked"

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(run, range(2)))
    assert len(calls) == 1 and any(isinstance(r, dict) for r in results)
    with sessions() as current:
        assert current.get(Outreach, ready[2].id).attempts == 1
        assert (
            current.scalar(
                select(func.count())
                .select_from(ActionAttempt)
                .join(Operation)
                .where(
                    Operation.kind == "company_send", ActionAttempt.authorized == True
                )
            )
            == 1
        )


def test_postgres_atomic_job_claim_enqueue_and_reply_before_reservation(
    pg, db, ready, enabled
):
    upgrade(pg)
    sessions = sessionmaker(pg, expire_on_commit=False)
    barrier = Barrier(2)
    with sessions() as target:
        copy_ready(db, target)
        jobs.enqueue(target, "candidate_import", {"companies": []}, "same-job")

    def claim(_):
        with sessions() as target:
            barrier.wait()
            j = jobs.claim_next(target)
            return j.id if j else None

    with ThreadPoolExecutor(2) as pool:
        assert sum(r is not None for r in pool.map(claim, range(2))) == 1

    def queue(_):
        with sessions() as target:
            barrier.wait()
            return jobs.enqueue(target, "sync", {}, "same-sync").id

    with ThreadPoolExecutor(2) as pool:
        assert len(set(pool.map(queue, range(2)))) == 1
    with sessions() as target:
        c, ct, first = confirmed(
            target,
            (
                target.get(Company, ready[0].id),
                target.get(Contact, ready[1].id),
                target.get(Outreach, ready[2].id),
            ),
        )
        follow = Outreach(
            company_id=c.id,
            contact_id=ct.id,
            sequence=1,
            status="approved",
            subject=first.subject,
            body="new contribution",
            review={**first.review, "adds_new_value": True},
            evidence_ids=first.evidence_ids,
        )
        target.add(follow)
        target.commit()
        fid = follow.id

    class Reply(Provider):
        async def check_conversation(self, *a):
            with sessions() as target:
                record_event(
                    target, target.get(Company, ready[0].id), "reply", "pg-reply"
                )

    with sessions() as target:
        p = Reply()
        with pytest.raises(Blocked):
            asyncio.run(send_company(target, fid, mode="worker", provider=p))
        assert p.sent == 0 and target.get(Outreach, fid).attempts == 0


async def test_forced_worker_cancellation_keeps_reserved_transmission_unknown(
    db, ready, enabled, monkeypatch
):
    @contextmanager
    def session():
        yield db

    @contextmanager
    def leader():
        yield True

    monkeypatch.setattr(worker, "Session", session)
    monkeypatch.setattr(worker, "leadership", leader)
    dispatched = asyncio.Event()

    class Waiting(Provider):
        async def deliver(self, *a):
            self.sent += 1
            dispatched.set()
            await asyncio.Event().wait()

    provider = Waiting()

    async def execute(db, job):
        return await send_company(db, ready[2].id, mode="worker", provider=provider)

    monkeypatch.setattr(worker, "_execute", execute)
    job = jobs.enqueue(db, "send", {"id": ready[2].id}, "cancel-send")
    task = asyncio.create_task(worker.tick())
    await asyncio.wait_for(dispatched.wait(), 3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert (
        job.status == "interrupted"
        and ready[2].status == "unknown"
        and ledger.unresolved(db)
    )
    assert not jobs.retry_allowed(db, job) and provider.sent == 1


def test_runtime_auth_and_queued_sync_has_no_provider_side_effect(db, ready):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db import session

    app.dependency_overrides[session] = lambda: db
    try:
        with TestClient(app) as client:
            assert client.get("/runtime").status_code == 401
            headers = {"Authorization": "Bearer local-development-key-change-me"}
            status = client.get("/runtime", headers=headers).json()
            assert (
                status["worker"] == "offline" and status["schema_version"] == "unknown"
            )
            a = client.post("/responses/sync", headers=headers)
            b = client.post("/mail/sync", headers=headers)
            assert (
                a.status_code == 202
                and a.json()["id"] == b.json()["id"]
                and a.json()["status"] == "queued"
            )
            assert db.get(State, "response_sync") is None
            assert "owner_token" not in a.json()
    finally:
        app.dependency_overrides.clear()


def test_sqlite005_additive_migration_and_backup_restore(tmp_path):
    from pathlib import Path
    from sqlalchemy import create_engine, text
    from alembic.config import Config
    from alembic import command
    from alembic.migration import MigrationContext
    from alembic.autogenerate import compare_metadata
    from app.db import Base

    engine = __import__("sqlalchemy").create_engine(
        "sqlite:///" + str(tmp_path / "runtime.sqlite")
    )
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
    )
    with engine.connect() as c:
        cfg.attributes["connection"] = c
        command.upgrade(cfg, "004")
        c.execute(
            State.__table__.insert().values(
                key="outreach_policy", value={"enabled": False}
            )
        )
        c.commit()
        command.upgrade(cfg, "head")
        c.commit()
        assert c.scalar(text("select version_num from alembic_version")) == "006"
        assert compare_metadata(MigrationContext.configure(c), Base.metadata) == []
        assert c.execute(select(State.value)).scalar_one() == {"enabled": False}
    from scripts.backup_database import backup

    backup("sqlite:///" + str(tmp_path / "runtime.sqlite"), tmp_path / "backup.sqlite")
    backup("sqlite:///" + str(tmp_path / "backup.sqlite"), tmp_path / "restored.sqlite")
    restored = create_engine("sqlite:///" + str(tmp_path / "restored.sqlite"))
    with restored.connect() as c:
        assert c.execute(select(State.value)).scalar_one() == {"enabled": False}
    engine.dispose()
    restored.dispose()


def test_worker_subprocess_start_sigterm_and_restart(pg, tmp_path):
    import os, sys, time, subprocess
    from pathlib import Path
    from sqlalchemy import text

    upgrade(pg)
    sessions = sessionmaker(pg, expire_on_commit=False)
    with sessions() as target:
        schema = target.scalar(text("select current_schema()"))
        j = jobs.enqueue(
            target,
            "candidate_import",
            {
                "companies": [
                    {"name": "Runtime Example", "website": "https://process.example"}
                ]
            },
            "process-import",
        )
        id = j.id
    env = {
        **os.environ,
        "DATABASE_URL": pg.url.update_query_dict(
            {"options": "-csearch_path=" + schema}
        ).render_as_string(hide_password=False),
        "DATA_DIRECTORY": str(tmp_path / "data"),
        "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
        "WORKER_POLL_SECONDS": "1",
        "MANUAL_MODE": "true",
        "DRY_RUN": "true",
        "RESPONSE_POLL_ENABLED": "false",
    }

    def start():
        return subprocess.Popen(
            [sys.executable, "-m", "app.worker"],
            cwd=tmp_path,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    process = start()
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with sessions() as target:
                if target.get(Job, id).status == "done":
                    break
            if process.poll() is not None:
                pytest.fail("Disposable worker exited before completion")
            time.sleep(0.1)
        else:
            pytest.fail("Disposable worker did not complete import")
        check = subprocess.run(
            [sys.executable, "-m", "app.worker", "--health"],
            cwd=tmp_path,
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
        )
        assert (
            check.returncode == 0
            and "encrypted_tokens" not in check.stdout
            and "communication_jobs" not in check.stdout
        )
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0
        with sessions() as target:
            assert target.get(State, "worker_heartbeat").value["status"] == "stopped"
        with sessions() as target:
            previous_instance = target.get(State, "worker_heartbeat").value[
                "instance_id"
            ]
        process = start()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with sessions() as target:
                if (
                    target.get(State, "worker_heartbeat").value.get("instance_id")
                    != previous_instance
                ):
                    break
            if process.poll() is not None:
                pytest.fail("Disposable restarted worker exited")
            time.sleep(0.1)
        else:
            pytest.fail("Restarted worker did not become ready")
        import signal

        process.send_signal(signal.SIGINT)
        process.communicate(timeout=10)
        assert process.returncode == 0
        with sessions() as target:
            assert target.get(Job, id).status == "done"
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)


async def test_response_after_reservation_preserved_even_when_acceptance_completes(
    db, ready, enabled
):
    class ReplyAfterReserve(Provider):
        async def deliver(self, *a):
            record_event(db, ready[0], "reply", "late-after-reserve")
            return DeliveryReceipt("accepted", "thread")

    result = await send_company(
        db, ready[2].id, mode="worker", provider=ReplyAfterReserve()
    )
    assert (
        result["provider_id"] == "accepted"
        and ready[2].status == "sent"
        and ready[0].stage == "replied"
    )


def test_postgres_sync_lease_allows_only_one_reader(pg, db, ready):
    upgrade(pg)
    sessions = sessionmaker(pg, expire_on_commit=False)
    barrier = Barrier(2)
    calls = []
    guard = Lock()
    with sessions() as target:
        copy_ready(db, target)

    class Slow(Box):
        async def call(self, method, url, **kw):
            if url.endswith("/profile"):
                with guard:
                    calls.append("identity")
                await asyncio.sleep(0.2)
            return await super().call(method, url, **kw)

    def run(_):
        with sessions() as target:
            barrier.wait()
            try:
                return asyncio.run(sync_session(target, Slow()))["status"]
            except Blocked:
                return "blocked"

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(run, range(2)))
    assert sorted(results) == ["blocked", "ok"] and len(calls) == 1


def test_postgres_two_workers_remaining_one_actual_send_quota(pg, db, ready, enabled):
    upgrade(pg)
    sessions = sessionmaker(pg, expire_on_commit=False)
    barrier = Barrier(2)
    guard = Lock()
    calls = []
    with sessions() as target:
        copy_ready(db, target)
        second = Company(
            name="Second",
            domain="second.example",
            website="https://second.example",
            research={"city": "Rocklin"},
        )
        target.add(second)
        target.flush()
        ct = Contact(
            company_id=second.id,
            email="lead@second.example",
            title="Engineering Lead",
            source="https://second.example/team",
            validation="valid",
            validated_at=now(),
        )
        target.add(ct)
        target.flush()
        ev = Evidence(
            company_id=second.id,
            url=second.website,
            fact="Robotics tools",
            quote="Robotics tools",
            category="product",
        )
        target.add(ev)
        target.flush()
        row = Outreach(
            company_id=second.id,
            contact_id=ct.id,
            status="approved",
            subject="Internship",
            body="Relevant proposal",
            review=ready[2].review,
            evidence_ids=[ev.id],
        )
        target.add(row)
        target.commit()
        ids = [ready[2].id, row.id]
        for i in range(24):
            a, _ = ledger.claim(
                target, "past-test:" + str(i), "self_test", "fake", lambda: {}
            )
            ledger.finish(target, a, "succeeded", receipt={"test": True})

    class Concurrent(Provider):
        async def check_conversation(self, *a):
            barrier.wait(timeout=5)

        async def deliver(self, *a):
            with guard:
                calls.append("send")
            await asyncio.sleep(0.05)
            return DeliveryReceipt("last-slot", "thread")

    def run(id):
        with sessions() as target:
            try:
                return asyncio.run(
                    send_company(target, id, mode="worker", provider=Concurrent())
                )
            except Blocked:
                return "blocked"

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(run, ids))
    assert len(calls) == 1 and results.count("blocked") == 1
    from zoneinfo import ZoneInfo

    with sessions() as target:
        start = (
            now()
            .astimezone(ZoneInfo("America/Los_Angeles"))
            .replace(hour=0, minute=0, second=0, microsecond=0)
        )
        assert policy.send_usage(target, start) == 25


@pytest.mark.parametrize(
    "change", ["recipient", "body", "subject", "thread", "self_test_company"]
)
def test_transport_envelope_cannot_bypass_reserved_scope(db, ready, change):
    from email.message import EmailMessage
    from app.services.envelope import validate
    from app.services.delivery import content_fingerprint

    row = ready[2]
    ct = ready[1]
    profile = db.get(Profile, 1)
    fingerprint = content_fingerprint(db, row, ct, profile)
    row.status = "sending"
    row.message_id = "<reserved>"
    a, _ = ledger.claim(
        db,
        "send:" + row.id,
        "company_send",
        "gmail",
        lambda: {"content_hash": fingerprint},
        outreach_id=row.id,
        entity_id=row.id,
    )
    op = db.get(Operation, a.operation_id)
    message = EmailMessage()
    message["From"] = "student@example.com"
    message["To"] = ct.email
    message["Subject"] = row.subject
    message["Message-ID"] = row.message_id
    message.set_content(row.body)
    payload = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}
    validate(db, a, op, payload, "student@example.com")
    if change == "recipient":
        message.replace_header("To", "attacker@example.com")
    if change == "body":
        message.set_content("Unsupported replacement")
    if change == "subject":
        message.replace_header("Subject", "Unsupported subject")
    if change == "thread":
        payload["threadId"] = "unrelated"
    if change == "self_test_company":
        op.kind = "self_test"
    payload["raw"] = base64.urlsafe_b64encode(message.as_bytes()).decode()
    with pytest.raises(Blocked):
        validate(db, a, op, payload, "student@example.com")


async def test_outlook_send_paths_fail_closed_including_query_suffix(monkeypatch):
    from app.mail import Mailbox

    monkeypatch.setenv("MAIL_PROVIDER", "outlook")
    box = Mailbox()
    for url in (
        "https://graph.microsoft.com/v1.0/me/sendMail",
        "https://graph.microsoft.com/v1.0/me/sendMail?x=1",
        "https://graph.microsoft.com/v1.0/me/messages/id/send",
    ):
        with pytest.raises(Blocked):
            await box.call("POST", url, json={})


def test_reconciliation_scheduler_rotates_held_operations_without_starvation(db):
    from app.models import Integration

    db.add(Integration(id="gmail", status="connected"))
    for index in range(6):
        db.add(
            Operation(
                id="pending-" + str(index),
                idempotency_key="pending-" + str(index),
                kind="company_send",
                provider="gmail",
                status="unknown",
                outreach_id=None,
            )
        )
    db.commit()
    at = now()
    scheduler.tick(db, at)
    first = list(db.scalars(select(Job).where(Job.kind == "reconcile")))
    assert len(first) == 5
    scheduler.tick(db, at + timedelta(seconds=300))
    all_jobs = list(db.scalars(select(Job).where(Job.kind == "reconcile")))
    assert len(all_jobs) == 10
    assert len({job.dedupe_key.split(":")[1] for job in all_jobs}) == 6


def test_followup_transport_requires_original_subject_and_thread_headers(db, ready):
    from email.message import EmailMessage
    from app.services.envelope import validate
    from app.services.delivery import content_fingerprint

    _, ct, original = confirmed(db, ready)
    row = Outreach(
        company_id=original.company_id,
        contact_id=ct.id,
        sequence=1,
        status="sending",
        subject=original.subject,
        body="A distinct practical proposal.",
        message_id="<followup-reserved>",
    )
    db.add(row)
    db.commit()
    a, _ = ledger.claim(
        db,
        "send:" + row.id,
        "company_send",
        "gmail",
        lambda: {"content_hash": content_fingerprint(db, row, ct, db.get(Profile, 1))},
        outreach_id=row.id,
        entity_id=row.id,
    )
    op = db.get(Operation, a.operation_id)
    message = EmailMessage()
    for key, value in {
        "From": "student@example.com",
        "To": ct.email,
        "Subject": original.subject,
        "Message-ID": row.message_id,
        "In-Reply-To": original.message_id,
        "References": original.message_id,
    }.items():
        message[key] = value
    message.set_content(row.body)
    payload = {
        "threadId": original.thread_id,
        "raw": base64.urlsafe_b64encode(message.as_bytes()).decode(),
    }
    validate(db, a, op, payload, "student@example.com")
    message.replace_header("References", "<unrelated>")
    payload["raw"] = base64.urlsafe_b64encode(message.as_bytes()).decode()
    with pytest.raises(Blocked):
        validate(db, a, op, payload, "student@example.com")


def test_scheduler_old_stopped_history_and_blocked_intents_do_not_starve_new_work(
    db, ready, enabled
):
    from datetime import datetime, timezone

    c, ct, row = confirmed(db, ready)
    db.add(State(key="automation", value={"enabled": True}))
    for index in range(101):
        old = Company(
            domain="stopped-" + str(index) + ".example",
            name="Stopped",
            website="https://stopped.example",
            stage="replied",
        )
        db.add(old)
        db.flush()
        contact = Contact(
            company_id=old.id, email="old-" + str(index) + "@stopped.example"
        )
        db.add(contact)
        db.flush()
        db.add(
            Outreach(
                company_id=old.id,
                contact_id=contact.id,
                status="sent",
                sent_at=now() - timedelta(days=60),
                provider_id="old",
                thread_id="old",
                message_id="<old>",
            )
        )
    at = datetime(2026, 10, 5, 16, 0, tzinfo=timezone.utc)
    for index in range(6):
        new_company = Company(
            domain="new-" + str(index) + ".example",
            name="New",
            website="https://new.example",
            stage="drafted",
        )
        db.add(new_company)
        db.flush()
        new_contact = Contact(
            company_id=new_company.id, email="contact-" + str(index) + "@new.example"
        )
        db.add(new_contact)
        db.flush()
        approved = Outreach(
            company_id=new_company.id,
            contact_id=new_contact.id,
            sequence=0,
            status="approved",
            due_at=at - timedelta(days=1),
        )
        db.add(approved)
        db.flush()
        if index < 5:
            db.add(
                Job(
                    kind="send",
                    payload={"id": approved.id},
                    dedupe_key="send:" + approved.id + ":0",
                    status="blocked",
                )
            )
    db.commit()
    scheduler.tick(db, at)
    assert db.scalar(select(Job).where(Job.dedupe_key == "followup-prepare:" + row.id))
    sends = list(
        db.scalars(select(Job).where(Job.kind == "send", Job.status == "queued"))
    )
    assert len(sends) == 1 and sends[0].payload["id"] == approved.id


async def test_reconciliation_preserves_existing_receipt_identity(db, ready, enabled):
    await send_company(db, ready[2].id, mode="worker", provider=Provider())
    original_receipt = dict(
        ledger.latest(db, ledger.operation(db, "send:" + ready[2].id)).receipt
    )
    with pytest.raises(Blocked, match="conflicts"):
        ledger.reconcile_sent(
            db,
            ready[2],
            "different-provider-id",
            "accepted-thread",
            ready[2].message_id,
            account="student@example.com",
        )
    assert (
        ledger.latest(db, ledger.operation(db, "send:" + ready[2].id)).receipt
        == original_receipt
    )
    assert ready[2].provider_id == "accepted-id"
