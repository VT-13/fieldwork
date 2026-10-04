"""One bounded read-only Gmail history reader and idempotent response ingestion."""

import asyncio
import base64
import html
import re
from datetime import datetime, timedelta, timezone
from email.utils import getaddresses, parseaddr
from urllib.parse import quote
from sqlalchemy import select
from .db import Session
from .models import Company, Contact, Outreach, State, Profile, now
from .core import aware, record_event, Blocked
from .config import settings
from .services import ledger
from .services.contracts import MailboxFailure

BASE = "https://gmail.googleapis.com/gmail/v1/users/me/"


def text_body(p, depth=0):
    if depth > 8:
        return ""
    raw = p.get("body", {}).get("data", "")[:50000]
    try:
        txt = (
            base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode(
                errors="replace"
            )
            if raw
            else ""
        )
    except (ValueError, __import__("binascii").Error):
        txt = ""
    if p.get("mimeType") == "text/html":
        txt = re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", txt, flags=re.I | re.S)
        txt = html.unescape(re.sub("<[^>]*>", " ", txt))
    parts = p.get("parts", [])[:32]
    if p.get("mimeType") == "multipart/alternative":
        parts = [c for c in parts if c.get("mimeType") == "text/plain"] or parts[:1]
    return (txt + "\n" + "\n".join(text_body(c, depth + 1) for c in parts))[:30000]


async def verify_identity(db, box):
    if not getattr(box, "token", ""):
        await box.connect()
    if getattr(getattr(box, "cfg", settings()), "mail_provider", "gmail") != "gmail":
        raise Blocked("Response tracking requires Gmail")
    identity = await box.call("GET", BASE + "profile")
    account = identity.get("emailAddress", "").lower()
    profile = db.get(Profile, 1)
    if (
        not account
        or not profile
        or not profile.data.get("verified")
        or account != profile.data.get("email", "").lower()
    ):
        raise Blocked("Mailbox identity mismatch; reconnect or investigate")
    if hasattr(box, "ensure_authorized"):
        box.ensure_authorized(db)
    return account, identity.get("historyId", "")


def ingest(db, msg, rows, contacts, sender_email):
    from .services.reconciliation import headers, matches, accepted_company_rfc

    from .gmail_validation import ingest as ingest_validation
    if ingest_validation(db, msg):return None
    h = headers(msg)
    sender = parseaddr(h.get("from", ""))[1].lower()
    if sender == sender_email.lower() and "SENT" in msg.get("labelIds", []):
        for row in rows:
            reserved = row.message_id
            actual = reserved
            matched = matches(db, row, msg, sender_email)
            if not matched and row.provider_id == msg.get('id'):
                try:
                    actual = accepted_company_rfc(db, row, msg, sender_email)
                    matched = True
                except Blocked: pass
            if matched:
                ledger.reconcile_sent(
                    db,
                    row,
                    msg["id"],
                    msg.get("threadId", ""),
                    actual,
                    account=sender_email,
                    reserved_message_id=reserved,
                )
        return None
    if (
        not sender
        or sender == sender_email.lower()
        or "SENT" in msg.get("labelIds", [])
    ):
        return None
    try:
        received = datetime.fromtimestamp(int(msg["internalDate"]) / 1000, timezone.utc)
    except (KeyError, ValueError, OverflowError):
        return None
    if received > now() + timedelta(minutes=5):
        return None
    text = text_body(msg.get("payload", {}))
    lower = text.lower()
    bounce = sender.split("@")[0] in (
        "mailer-daemon",
        "postmaster",
    ) or "delivery-status" in h.get("content-type", "")
    references = set(
        re.findall(
            r"<[^<>\s]+>", h.get("in-reply-to", "") + " " + h.get("references", "")
        )
    )
    destinations = {
        a.lower() for _, a in getaddresses([h.get("to", ""), h.get("cc", "")])
    }
    eligible = [
        r
        for r in rows
        if r.contact_id in contacts
        and r.sent_at
        and received >= aware(r.sent_at) - timedelta(minutes=1)
    ]
    exact = []
    for row in eligible:
        ct = contacts[row.contact_id]
        if bounce:
            match = bool(
                re.search(
                    r"final-recipient:\s*rfc822;\s*"
                    + re.escape(ct.email.lower())
                    + r"(?:\s|$)",
                    lower,
                )
                or (row.message_id and row.message_id.lower() in lower)
            )
        else:
            match = sender_email.lower() in destinations and (
                (row.thread_id and row.thread_id == msg.get("threadId"))
                or row.message_id in references
            )
        if match:
            exact.append(row)
    if (
        not exact
        and not bounce
        and not references
        and sender_email.lower() in destinations
    ):
        # Known sender + exact own recipient + bounded recent outreach; never subject matching.
        exact = [
            r
            for r in eligible
            if contacts[r.contact_id].email.lower() == sender
            and received
            <= aware(r.sent_at) + timedelta(days=settings().mailbox_lookback_days)
        ]
    if not exact or len({r.company_id for r in exact}) != 1:
        return None
    matched = max(exact, key=lambda r: aware(r.sent_at))
    auto = h.get("auto-submitted", "").lower() not in ("", "no") or bool(
        h.get("x-autoreply") or h.get("x-autorespond")
    )
    newest = re.split(r"\n(?:On .+wrote:|From:|>)", text, maxsplit=1)[0].lower()
    kind = (
        "bounce"
        if bounce
        else "auto_reply"
        if auto
        else "opt_out"
        if any(
            x in newest
            for x in ["do not contact", "remove me", "stop emailing", "unsubscribe me"]
        )
        else "reply"
    )
    ledger.lock(db)
    key = "response:" + msg["id"]
    existing = db.get(State, key)
    if existing:
        db.commit()
        return existing.value
    company = db.get(Company, matched.company_id)
    record_event(
        db,
        company,
        kind,
        "gmail:" + msg["id"],
        "Automatic acknowledgment" if auto else h.get("subject", "")[:200],
        contact_id=matched.contact_id,
        outreach_id=matched.id,
        received_at=received,
    )
    data = {
        "id": msg["id"],
        "company_id": company.id,
        "company": company.name,
        "contact_id": matched.contact_id,
        "outreach_id": matched.id,
        "campaign_id": "personal",
        "kind": kind,
        "sender": sender,
        "subject": h.get("subject", "")[:200],
        "preview": text.strip()[:3000],
        "received_at": received.isoformat(),
        "thread_id": msg.get("threadId", ""),
        "handled": False,
        "followup_stopped": True,
        "gmail_url": "https://mail.google.com/mail/u/?authuser="
        + quote(sender_email)
        + "#all/"
        + quote(msg.get("threadId", msg["id"])),
    }
    db.merge(State(key=key, value=data))
    db.commit()
    return data


async def sync_session(db, box=None):
    from .mail import Mailbox

    box = box or Mailbox()
    at = now()
    prior = db.get(State, "response_sync")
    old = prior.value if prior else {}
    # A read-sync lease is separate from delivery uncertainty and is database-scoped.
    ledger.lock(db)
    prior = db.get(State, "response_sync")
    old = prior.value if prior else {}
    if old.get("lease_until") and datetime.fromisoformat(old["lease_until"]) > at:
        db.commit()
        raise Blocked("Mailbox sync already running")
    state = {
        **old,
        "status": "syncing",
        "last_attempt": at.isoformat(),
        "lease_until": (at + timedelta(seconds=180)).isoformat(),
    }
    db.merge(State(key="response_sync", value=state))
    db.commit()
    count = 0
    requests = 0

    async def call(path, params=None):
        nonlocal requests
        if requests >= settings().mailbox_max_requests:
            raise Blocked("Mailbox request budget reached")
        requests += 1
        return await box.call("GET", BASE + path, params=params)

    try:
        async with asyncio.timeout(120):
            account, current_history = await verify_identity(db, box)
            requests += 1
            if state.get("account") and state["account"] != account:
                raise Blocked(
                    "Stored sync account differs; investigate before cursor reset"
                )
            state["account"] = account
            rows = list(
                db.scalars(
                    select(Outreach).where(
                        Outreach.sent_at != None,
                        Outreach.status.in_(["sent", "unknown", "sending"]),
                    )
                )
            )
            contacts = {c.id: c for c in db.scalars(select(Contact))}
            pending = list(state.get("pending_ids", []))
            while count < settings().mailbox_max_messages:
                if pending:
                    mid = pending[0]
                    try:
                        from .gmail_validation import context, send_state, related
                        validation = context(db)
                        if validation:
                            # Active staging validation never reads unrelated message bodies.
                            metadata = await call("messages/" + mid, {"format": "metadata", "metadataHeaders": ["From", "To", "References", "In-Reply-To"]})
                            receipt = send_state(db, validation)
                            msg = await call("messages/" + mid, {"format": "full"}) if receipt and related(validation, receipt.value, metadata) else metadata
                        else:
                            msg = await call("messages/" + mid, {"format": "full"})
                    except MailboxFailure as exc:
                        if exc.code != "not_found":
                            raise
                    else:
                        ingest(db, msg, rows, contacts, account)
                    pending.pop(0)
                    count += 1
                    state["pending_ids"] = pending
                    db.merge(State(key="response_sync", value={**state}))
                    db.commit()
                    continue
                if state.get("page_loaded") and not state.get("page_token"):
                    state["history_id"] = state.pop("target_history", current_history)
                    for k in (
                        "bootstrap_since",
                        "bootstrap_history",
                        "page_loaded",
                        "page_token",
                        "pending_ids",
                    ):
                        state.pop(k, None)
                    state.update(status="ok", last_success=at.isoformat())
                    break
                params = {"maxResults": 25}
                if state.get("page_token"):
                    params["pageToken"] = state["page_token"]
                if state.get("history_id"):
                    params.update(
                        startHistoryId=state["history_id"], historyTypes="messageAdded"
                    )
                    try:
                        page = await call("history", params)
                    except MailboxFailure as exc:
                        if exc.code != "cursor_invalid":
                            raise
                        state = {
                            **state,
                            "history_id": "",
                            "page_token": "",
                            "page_loaded": False,
                            "cursor_recovered": True,
                        }
                        continue
                    ids = [
                        m["message"]["id"]
                        for entry in page.get("history", [])
                        for m in entry.get("messagesAdded", [])
                    ]
                    state["target_history"] = page.get("historyId", current_history)
                else:
                    # Initial/expired cursor recovery is a recent bounded backfill, not mailbox-wide polling.
                    state.setdefault(
                        "bootstrap_since",
                        int(
                            (
                                at - timedelta(days=settings().mailbox_lookback_days)
                            ).timestamp()
                        ),
                    )
                    state.setdefault("bootstrap_history", current_history)
                    params.update(
                        q="after:" + str(state["bootstrap_since"]),
                        includeSpamTrash=True,
                    )
                    page = await call("messages", params)
                    ids = [m["id"] for m in page.get("messages", [])]
                    state["target_history"] = state["bootstrap_history"]
                if len(ids) > 250:
                    raise Blocked(
                        "Mailbox history page too large; operator attention required"
                    )
                pending = list(dict.fromkeys(ids))
                state.update(
                    pending_ids=pending,
                    page_token=page.get("nextPageToken", ""),
                    page_loaded=True,
                )
                db.merge(State(key="response_sync", value={**state}))
                db.commit()
            else:
                state["status"] = "partial"
            if state.get("status") == "syncing":
                state["status"] = "partial"
            state.update(
                lease_until="",
                messages=count,
                requests=requests,
                poll_seconds=settings().mailbox_poll_seconds,
            )
            state.pop("error", None)
            state.pop("next_retry_at", None)
            state.pop("failure_count", None)
            db.merge(State(key="response_sync", value=state))
            db.commit()
            return {
                k: v
                for k, v in state.items()
                if k
                not in (
                    "pending_ids",
                    "history_id",
                    "target_history",
                    "page_token",
                    "account",
                )
            }
    except Exception as exc:
        db.rollback()
        # Persist the last committed pagination; do not overwrite ingestion or advance past unseen IDs.
        current = db.get(State, "response_sync")
        saved = current.value if current else state
        result = {
            **saved,
            "status": "error",
            "lease_until": "",
            "last_attempt": at.isoformat(),
            "error": "Mailbox needs attention: "
            + (exc.code if isinstance(exc, MailboxFailure) else "sync_incomplete"),
            "messages": count,
            "requests": requests,
        }
        failures = min(6, int(saved.get("failure_count", 0)) + 1)
        result.update(
            failure_count=failures,
            next_retry_at=(
                at + timedelta(seconds=min(3600, 30 * 2**failures))
            ).isoformat(),
        )
        db.merge(State(key="response_sync", value=result))
        db.commit()
        return {"status": "error", "error": result["error"]}


async def sync(box=None):
    with Session() as db:
        return await sync_session(db, box)


def listing(db):
    rows = [
        r.value for r in db.scalars(select(State).where(State.key.like("response:%")))
    ]
    rows.sort(key=lambda r: r["received_at"], reverse=True)
    s = db.get(State, "response_sync")
    status = s.value if s else {"status": "not_checked"}
    return {
        "sync": {
            k: status[k]
            for k in ("status", "last_success", "error", "last_attempt")
            if k in status
        },
        "enabled": settings().response_poll_enabled,
        "responses": rows[:500],
        "needs_attention": sum(r["kind"] == "reply" and not r["handled"] for r in rows),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(asyncio.run(sync())))
