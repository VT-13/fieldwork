"""Explicit disposable-only process bootstrap. Never loaded by normal API/worker."""

import asyncio
import base64
import fcntl
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(os.environ["FIELDWORK_RELEASE_TEST_ROOT"]).resolve()
assert ROOT.is_relative_to(Path("/private/tmp/fieldwork-module6"))
assert os.environ["DATABASE_URL"].endswith("/fieldwork_m6_e2e")
assert "127.0.0.1:55436" in os.environ["DATABASE_URL"]
assert os.environ["SENDER_EMAIL"] == "student@example.com"
assert os.environ["FIELDWORK_RELEASE_TEST"] == "disposable-only"


def clock():
    return datetime.fromisoformat((ROOT / "clock.txt").read_text().strip())


from app import models

models.now = clock
from sqlalchemy import DateTime

for table in models.Base.metadata.tables.values():
    for column in table.columns:
        if (
            isinstance(column.type, DateTime)
            and column.default
            and column.default.is_callable
        ):
            column.default.arg = lambda context: clock()


@contextmanager
def state():
    with (ROOT / "provider.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = json.loads((ROOT / "provider.json").read_text())
        yield data
        temp = ROOT / "provider.new"
        temp.write_text(json.dumps(data))
        temp.replace(ROOT / "provider.json")


import httpx

RealClient = httpx.AsyncClient


def reply(request, data):
    return httpx.Response(200, json=data, request=request)


def transport(request):
    path = request.url.path
    query = dict(request.url.params)
    if request.url.host == "oauth2.googleapis.com":
        return reply(
            request,
            {
                "access_token": "fake-access",
                "refresh_token": "fake-refresh",
                "expires_in": 3600,
                "scope": "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.compose",
                "token_type": "Bearer",
            },
        )
    assert request.url.host == "gmail.googleapis.com", (
        "No real provider network is possible in release QA"
    )
    with state() as data:
        messages = list(data["messages"].values())
        if path.endswith("/profile"):
            return reply(
                request,
                {
                    "emailAddress": "student@example.com",
                    "historyId": str(data["history"]),
                },
            )
        if path.endswith("/messages/send"):
            payload = json.loads(request.content)
            mime = BytesParser(policy=policy.default).parsebytes(
                base64.urlsafe_b64decode(payload["raw"])
            )
            mid = "fake-send-" + str(len(data["transmissions"]) + 1)
            tid = payload.get("threadId", mid)
            data["history"] += 1
            data["messages"][mid] = {
                "id": mid,
                "threadId": tid,
                "labelIds": ["SENT"],
                "internalDate": str(int(clock().timestamp() * 1000)),
                "_history": data["history"],
                "payload": {
                    "mimeType": "text/plain",
                    "headers": [{"name": k, "value": str(v)} for k, v in mime.items()],
                    "body": {
                        "data": base64.urlsafe_b64encode(
                            mime.get_body(preferencelist=("plain",))
                            .get_content()
                            .encode()
                        ).decode()
                    },
                },
            }
            data["transmissions"].append(
                {
                    "id": mid,
                    "thread": tid,
                    "to": str(mime["To"]),
                    "rfc": str(mime["Message-ID"]),
                }
            )
            if data.get("hang_next"):
                data["hang_next"] = False
                data["dispatch_entered"] = True
                (ROOT / "provider.json").write_text(json.dumps(data))
                (ROOT / "dispatch.entered").touch()
                import time

                time.sleep(30)
            if data.get("fail_next"):
                data["fail_next"] = False
                # Commit provider evidence before simulating an ambiguous response.
                (ROOT / "provider.json").write_text(json.dumps(data))
                raise httpx.ReadTimeout("Fake ambiguous dispatch", request=request)
            return reply(request, {"id": mid, "threadId": tid})
        if path.endswith("/history"):
            start = int(query.get("startHistoryId", 0))
            return reply(
                request,
                {
                    "historyId": str(data["history"]),
                    "history": [
                        {"messagesAdded": [{"message": {"id": m["id"]}}]}
                        for m in messages
                        if m["_history"] > start
                        and not (data.get("hide_sent") and "SENT" in m["labelIds"])
                    ],
                },
            )
        if path.endswith("/messages"):
            q = query.get("q", "")
            selected = messages
            if "rfc822msgid:" in q:
                rfc = q.split("rfc822msgid:")[-1]
                selected = [
                    m
                    for m in messages
                    if any(
                        h["name"].lower() == "message-id"
                        and h["value"].strip("<>") == rfc
                        for h in m["payload"]["headers"]
                    )
                ]
            elif "mailer-daemon" in q:
                selected = []
            elif "from:" in q:
                selected = [
                    m
                    for m in messages
                    if any(
                        h["name"].lower() == "from" and h["value"].lower() in q.lower()
                        for h in m["payload"]["headers"]
                    )
                    or (
                        "to:" in q
                        and any(
                            h["name"].lower() == "to"
                            and h["value"].lower() in q.lower()
                            for h in m["payload"]["headers"]
                        )
                    )
                ]
            if data.get("hide_sent"):
                selected = [m for m in selected if "SENT" not in m["labelIds"]]
            return reply(
                request,
                {
                    "messages": [
                        {"id": m["id"]}
                        for m in selected[: int(query.get("maxResults", 25))]
                    ]
                },
            )
        if "/messages/" in path:
            return reply(request, data["messages"][path.rsplit("/", 1)[-1]])
        if "/threads/" in path:
            return reply(
                request,
                {
                    "messages": [
                        m for m in messages if m["threadId"] == path.rsplit("/", 1)[-1]
                    ]
                },
            )
        if path.endswith("/drafts"):
            return reply(
                request, {"id": "fake-draft", "message": {"id": "fake-draft-message"}}
            )
    raise AssertionError("Unsupported fake endpoint")


class Client(RealClient):
    def __init__(self, *a, **kw):
        kw["transport"] = httpx.MockTransport(transport)
        super().__init__(*a, **kw)


httpx.AsyncClient = Client

from app import providers
from app.models import ContactObservation
from app.services.contracts import ScrapedPage

QUOTES = [
    ("description", "We are based in Rocklin, California."),
    ("product", "We build web software dashboards and robotics data tools."),
    (
        "technology",
        "Our engineering team uses software prototypes and sample robot logs.",
    ),
]


async def discover(db, spec):
    return [
        {
            "name": "Release QA Robotics",
            "website": "https://example.com",
            "industry": "Software robotics",
            "distance_miles": 4,
            "source": "https://example.com",
            "provider_id": "fake-place",
            "location": "Rocklin, California",
            "retrieved_at": clock().isoformat(),
        }
    ]


async def contacts(db, company):
    return [
        {
            "email": "lead@" + company.domain,
            "name": "Jordan Example",
            "title": "Engineering Lead",
            "source_url": company.website + "/team",
            "provider": "Release fake",
            "confidence": "source-observed",
            "retrieved_at": clock().isoformat(),
        }
    ]


async def scrape(db, company, url):
    return ScrapedPage("\n".join(q for _, q in QUOTES), url, clock())


async def llm(db, cid, schema, instruction, data, purpose="extract"):
    if purpose == "extract":
        return schema.model_validate(
            {
                "facts": [
                    {
                        "url": data["pages"][0]["url"],
                        "category": category,
                        "quote": quote,
                    }
                    for category, quote in QUOTES
                ]
            }
        )
    if purpose == "generate":
        task = data["tasks"][0]
        return schema.model_validate(
            {
                "plan": {
                    "evidence_ids": task["matching_evidence_ids"][:2],
                    "student_fact_ids": task["matching_student_fact_ids"][:1],
                    "proposal_id": task["id"],
                    "voice": "curious",
                }
            }
        )
    return schema.model_validate(
        {
            "personalization_score": 95,
            "grounded": True,
            "names_correct": True,
            "claims_supported": True,
            "non_generic": True,
            "non_spammy": True,
            "adds_new_value": True,
            "issues": [],
        }
    )


async def verify(db, contact):
    contact.validation = "valid"
    contact.validated_at = clock()
    db.add(
        ContactObservation(
            company_id=contact.company_id,
            contact_id=contact.id,
            field="validation",
            value="valid",
            provider="Release fake",
            source_url=contact.source,
            confidence="provider-confirmed",
            verified_at=clock(),
        )
    )
    db.commit()
    return "valid"


providers.discover = discover
providers.hunter_contacts = contacts
providers.scrape = scrape
providers.llm = llm
providers.verify = verify

if __name__ == "__main__":
    if sys.argv[1:] == ["api"]:
        import uvicorn

        uvicorn.run(
            "app.main:app",
            host="127.0.0.1",
            port=18036,
            access_log=False,
            proxy_headers=False,
        )
    elif sys.argv[1:] == ["worker"]:
        from app.worker import main

        asyncio.run(main())
    else:
        raise SystemExit("Explicit API or worker only")
