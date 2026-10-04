"""Positive Sent evidence only. An absent search result never grants retry permission."""

from datetime import timedelta, datetime, timezone
from email.utils import getaddresses
from sqlalchemy import select
from ..core import Blocked, aware
from ..models import Contact, Profile, Outreach
from . import ledger

BASE = "https://gmail.googleapis.com/gmail/v1/users/me/"


def headers(msg):
    return {
        h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])
    }


def matches_envelope(msg, account, recipient, message_id, subject, body, sent_at):
    from ..responses import text_body
    h = headers(msg)
    recipients = {a.lower() for _, a in getaddresses([h.get("to", "")])}
    sender = {a.lower() for _, a in getaddresses([h.get("from", "")])}
    try:
        at = datetime.fromtimestamp(int(msg["internalDate"]) / 1000, timezone.utc)
    except (KeyError, ValueError, OverflowError):
        return False
    return bool(sent_at and "SENT" in msg.get("labelIds", [])
        and sender == {account.lower()} and recipients == {recipient.lower()}
        and not h.get("cc") and not h.get("bcc")
        and h.get("message-id") == message_id and h.get("subject") == subject
        and text_body(msg.get("payload", {})).replace("\r\n", "\n").strip() == body.replace("\r\n", "\n").strip()
        and aware(sent_at) - timedelta(minutes=2) <= at <= aware(sent_at) + timedelta(hours=1))


def accepted_rfc(msg, account, recipient, provider_id, thread_id, subject, body, sent_at):
    """Observe an RFC alias only through an exact accepted immutable API receipt."""
    import re
    actual = headers(msg).get("message-id", "")
    if (not provider_id or not thread_id or msg.get("id") != provider_id
        or msg.get("threadId") != thread_id or len(actual) > 255
        or not re.fullmatch(r"<[^<>\s@]+@[^<>\s@]+>", actual)
        or not matches_envelope(msg, account, recipient, actual, subject, body, sent_at)):
        raise Blocked("Accepted receipt conflicts with provider Sent evidence")
    return actual


def accepted_company_rfc(db, row, msg, account):
    op = ledger.operation(db, "send:" + row.id)
    attempt = ledger.latest(db, op) if op else None
    receipt = attempt.receipt if attempt else {}
    if (not op or op.status != "succeeded" or attempt.status != "succeeded"
        or receipt.get("provider_id") != row.provider_id or receipt.get("thread_id") != row.thread_id):
        raise Blocked("Durable accepted receipt required for RFC normalization")
    ct = db.get(Contact, row.contact_id)
    if not ct: raise Blocked("Original contact required")
    return accepted_rfc(msg, account, ct.email, row.provider_id, row.thread_id, row.subject, row.body, row.sent_at)


def matches(db, row, msg, account):
    ct = db.get(Contact, row.contact_id)
    return bool(ct and matches_envelope(msg, account, ct.email, row.message_id, row.subject, row.body, row.sent_at))


async def reconcile(db, id, box=None):
    from ..mail import Mailbox
    from ..responses import verify_identity

    row = db.get(Outreach, id)
    if not row:
        from ..gmail_validation import reconcile as reconcile_validation
        return await reconcile_validation(db, id, box or Mailbox())
    if not row.message_id or not row.sent_at:
        raise Blocked("Reserved message identity required")
    box = box or Mailbox()
    account, _ = await verify_identity(db, box)
    reserved = row.message_id
    message_id = reserved
    if row.provider_id:
        msg = await box.call("GET", BASE + "messages/" + row.provider_id, params={"format": "full"})
        message_id = accepted_company_rfc(db, row, msg, account)
    # Unknown attempts without an accepted API receipt retain strict reserved-ID search.
    result = await box.call(
        "GET",
        BASE + "messages",
        params={
            "q": "in:sent rfc822msgid:" + message_id.strip("<>"),
            "maxResults": 5,
        },
    )
    matched = []
    for item in result.get("messages", [])[:5]:
        msg = await box.call(
            "GET", BASE + "messages/" + item["id"], params={"format": "full"}
        )
        ct = db.get(Contact, row.contact_id)
        if ct and matches_envelope(msg, account, ct.email, message_id, row.subject, row.body, row.sent_at):
            matched.append(msg)
    if len(matched) != 1 or result.get("nextPageToken"):
        return {
            "status": "held",
            "reason": "No unique matching Sent evidence; never resend",
        }
    msg = matched[0]
    ledger.reconcile_sent(
        db, row, msg["id"], msg.get("threadId", ""), message_id, account=account, reserved_message_id=reserved
    )
    return {"status": "confirmed", "provider_id": msg["id"], "outreach_id": id}
