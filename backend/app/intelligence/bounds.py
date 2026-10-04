"""Request/job bounds, shared Usage accounting and sanitized provider failures."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import monotonic
from sqlalchemy import select
from ..config import settings
from ..core import Blocked, day_start
from ..models import Job, Usage


class IntelligenceFailure(Blocked):
    def __init__(self, code, *, retryable=False):
        self.code = code
        self.retryable = retryable
        super().__init__(
            {
                "unsupported": "Unsupported provider capability",
                "unconfigured": "Configure the selected provider before queueing this work",
                "provider_unavailable": "Provider unavailable; an explicit bounded retry may help",
                "provider_rejected": "Provider rejected the request; check configuration",
                "budget": "Intelligence budget reached; keep partial results",
                "stopped": "Intelligence job stopped; partial results retained",
                "malformed": "Provider returned an invalid structured result",
            }.get(code, code)
        )


@dataclass
class Bounds:
    db: object
    job_id: str | None = None
    requests: int = 0
    pages: int = 0
    ai_calls: int = 0
    reserved_tokens: int = 0
    cache_hits: int = 0
    started: float = field(default_factory=monotonic)

    def check(self):
        if self.job_id:
            job = self.db.get(Job, self.job_id, populate_existing=True)
            if not job or job.payload.get("stop_requested"):
                raise IntelligenceFailure("stopped")

    def request(self, *, ai=False, input_chars=0):
        self.check()
        cfg = settings()
        if self.requests >= cfg.max_provider_requests:
            raise IntelligenceFailure("budget")
        if ai:
            # UTF-8 byte count is a conservative token reservation, not measured usage.
            units = input_chars + cfg.max_output_tokens
            if (
                input_chars > cfg.max_input_chars
                or self.ai_calls >= cfg.max_llm_calls
                or self.reserved_tokens + units > cfg.max_job_tokens
            ):
                raise IntelligenceFailure("budget")
            self.reserved_tokens += units
            self.ai_calls += 1
        self.requests += 1

    def page(self):
        self.check()
        if self.pages >= settings().max_pages:
            raise IntelligenceFailure("budget")
        self.pages += 1

    def summary(self):
        return {
            "provider_requests": self.requests,
            "pages": self.pages,
            "ai_calls": self.ai_calls,
            "reserved_tokens": self.reserved_tokens,
            "cache_hits": self.cache_hits,
        }

    def progress(self, **values):
        if self.job_id:
            job = self.db.get(Job, self.job_id, populate_existing=True)
            job.result = {**job.result, **values, **self.summary()}
            self.db.commit()


current: ContextVar[Bounds | None] = ContextVar("intelligence_bounds", default=None)


@contextmanager
def scope(db, job_id=None):
    active = current.get()
    if active:
        yield active
        return
    token = current.set(Bounds(db, job_id))
    try:
        yield current.get()
    finally:
        current.reset(token)


def checkpoint():
    if current.get():
        current.get().check()


def hit(db, service, company_id=None):
    if current.get():
        current.get().cache_hits += 1
    db.add(
        Usage(
            service="cache:" + service,
            company_id=company_id,
            reserved_usd=0,
            details={"cache_hit": True, "network_units": 0},
        )
    )
    db.commit()


def token_budget(db, input_chars):
    cfg = settings()
    units = input_chars + cfg.max_output_tokens
    rows = list(
        db.scalars(
            select(Usage).where(
                Usage.created_at >= day_start(), Usage.service.like("llm:%")
            )
        )
    )
    if (
        sum(max(r.tokens, r.details.get("reserved_tokens", 0)) for r in rows) + units
        > cfg.daily_token_limit
    ):
        raise IntelligenceFailure("budget")
    return units
