"""Transport fence binds MIME to its durable reservation; no raw caller-supplied send."""

import base64
import binascii
from email import policy as mime_policy
from email.parser import BytesParser
from email.utils import getaddresses
from sqlalchemy import select
from ..models import Outreach, Contact, Profile
from ..core import Blocked


def validate(db, attempt, op, payload, account):
    try:
        raw = payload["raw"]
        if not isinstance(raw, str) or len(raw) > 150000:
            raise ValueError()
        msg = BytesParser(policy=mime_policy.default).parsebytes(
            base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        )
        profile = db.get(Profile, 1)
        if not profile or account.lower() != profile.data.get("email", "").lower():
            raise ValueError()
        sender = {a.lower() for _, a in getaddresses(msg.get_all("From", []))}
        recipients = {a.lower() for _, a in getaddresses(msg.get_all("To", []))}
        if sender != {account.lower()} or msg.get_all("Cc") or msg.get_all("Bcc"):
            raise ValueError()
        content = msg.get_body(preferencelist=("plain",))
        body = content.get_content().replace("\r\n", "\n").strip() if content else ""
        if op.kind == "company_send":
            row = db.get(Outreach, op.outreach_id)
            ct = db.get(Contact, row.contact_id) if row else None
            if (
                not row
                or not ct
                or row.status != "sending"
                or recipients != {ct.email.lower()}
                or msg["Subject"] != row.subject
                or body != row.body.replace("\r\n", "\n").strip()
                or msg["Message-ID"] != row.message_id
            ):
                raise ValueError()
            from .delivery import content_fingerprint

            if content_fingerprint(db, row, ct, profile) != attempt.policy.get(
                "content_hash"
            ):
                raise ValueError()
            original = (
                db.scalar(
                    select(Outreach).where(
                        Outreach.company_id == row.company_id, Outreach.sequence == 0
                    )
                )
                if row.sequence
                else None
            )
            if original:
                if (
                    payload.get("threadId") != original.thread_id
                    or msg["In-Reply-To"] != original.message_id
                    or msg["References"] != original.message_id
                ):
                    raise ValueError()
            elif payload.get("threadId") or msg["In-Reply-To"] or msg["References"]:
                raise ValueError()
        elif op.kind == "self_test":
            from ..desk import get_packet

            packet = get_packet(db, op.entity_id).value
            if (
                recipients != {account.lower()}
                or msg["Message-ID"] != "<fieldwork-test-" + op.id + "@gmail.com>"
                or msg["Subject"] != "[DRY RUN] " + packet["subject"]
                or body
                != (
                    "TEST COPY TO YOURSELF — no company was contacted.\n\n"
                    + packet["body"]
                ).strip()
                or not op.idempotency_key.endswith(":" + packet["draft_hash"])
                or payload.get("threadId")
            ):
                raise ValueError()
        else:
            raise ValueError()
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        binascii.Error,
    ):
        raise Blocked("Send content does not match its durable reservation") from None
