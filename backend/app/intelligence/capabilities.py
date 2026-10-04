"""Configured is never a live health check; unavailable actions fail before enqueue."""

from ..config import settings
from ..models import State
from ..core import Blocked


def capabilities(db):
    cfg = settings()
    p = db.get(State, "outreach_policy")
    allowed = not cfg.manual_mode and not (
        p and p.value.get("paid_services_authorized") is False
    )
    keys = {
        "maps": cfg.google_maps_api_key,
        "tavily": cfg.tavily_api_key,
        "apollo": cfg.apollo_api_key,
        "contacts": cfg.hunter_api_key,
        "research": cfg.firecrawl_api_key and cfg.openai_api_key,
        "generate": cfg.openai_api_key,
    }
    return {
        "paid_allowed": allowed,
        "providers": [
            {
                "id": id,
                "configured": bool(value),
                "available": allowed and bool(value),
                "reason": "Paid calls disabled by mode/policy"
                if not allowed
                else "Configured; live health untested"
                if value
                else "Provider configuration required",
            }
            for id, value in keys.items()
        ],
        "manual_import": True,
        "limits": {
            "companies": cfg.discovery_batch_limit,
            "contacts": cfg.max_contacts,
            "pages": cfg.max_pages,
            "requests": cfg.max_provider_requests,
            "ai_calls": cfg.max_llm_calls,
            "generation_attempts": cfg.max_generation_attempts,
            "job_tokens": cfg.max_job_tokens,
            "daily_tokens": cfg.daily_token_limit,
            "research_seconds": cfg.research_seconds,
            "discovery_seconds": cfg.discovery_seconds,
            "daily_generation_reservation_usd": cfg.daily_generation_budget_usd,
            "daily_reservation_usd": cfg.daily_budget_usd,
            "company_reservation_usd": cfg.company_budget_usd,
        },
        "worker_note": "Queued work needs the dedicated Fieldwork worker. Check communication processing status; this build does not activate the installed runtime.",
    }


def require_capability(db, id):
    row = next((r for r in capabilities(db)["providers"] if r["id"] == id), None)
    if not row or not row["available"]:
        raise Blocked(row["reason"] if row else "Unsupported provider capability")
