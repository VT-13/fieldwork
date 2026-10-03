import hashlib
import json
import ipaddress
import math
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from sqlalchemy import select, func
from .models import Usage, Cache, Contact, Event, Outreach, Suppression, now
from .config import settings

class Blocked(Exception):
    pass

def aware(dt):
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

def day_start():
    local = now().astimezone(ZoneInfo(settings().timezone))
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)

def public_url(url):
    p = urlsplit(url)
    if p.scheme != "https" or p.username or p.password or p.port not in (None, 443):
        raise Blocked("Only public HTTPS company URLs are accepted")
    host = (p.hostname or "").lower().rstrip(".")
    if "." not in host or host.endswith((".local", ".internal", ".localhost", ".test")):
        raise Blocked("Nonpublic hostname")
    try:
        if not ipaddress.ip_address(host).is_global:
            raise Blocked("Nonpublic IP address")
    except ValueError:
        pass
    return host.removeprefix("www.")

def distance(lat, lng, lat2, lng2):
    a, b = map(math.radians, [lat, lat2])
    dlat, dlng = map(math.radians, [lat2-lat, lng2-lng])
    x = math.sin(dlat/2)**2 + math.cos(a)*math.cos(b)*math.sin(dlng/2)**2
    return 3958.8*2*math.asin(min(1, math.sqrt(x)))

def reserve(db, service, amount, company_id=None):
    # Called only by the database-leased worker; reservations include failures.
    cfg = settings()
    if cfg.manual_mode:
        raise Blocked("Personal manual mode: paid API calls are disabled. Use the review desk.")
    daily = db.scalar(select(func.coalesce(func.sum(Usage.reserved_usd), 0)).where(Usage.created_at >= day_start()))
    if daily + amount > cfg.daily_budget_usd:
        raise Blocked("Daily cost reservation budget reached")
    if company_id:
        used = db.scalar(select(func.coalesce(func.sum(Usage.reserved_usd), 0)).where(Usage.company_id == company_id, Usage.created_at >= day_start()))
        if used + amount > cfg.company_budget_usd:
            raise Blocked("Company daily cost reservation budget reached")
    row = Usage(service=service, reserved_usd=amount, company_id=company_id)
    db.add(row)
    db.commit()
    return row

def cached(db, key):
    row = db.get(Cache, hashlib.sha256(key.encode()).hexdigest())
    return row.value if row and aware(row.expires_at) > now() else None

def cache_put(db, key, value, days=14):
    db.merge(Cache(key=hashlib.sha256(key.encode()).hexdigest(), value=value, expires_at=now()+timedelta(days=days)))
    db.commit()

def score_company(company, has_contact, interests):
    r = company.research or {}
    text = " ".join([company.industry, company.description, *r.get("technologies", [])]).lower()
    align = sum(1 for s in interests if s.lower() in text)
    factors = {
        "proximity": 0 if company.distance_miles is None else round(15*max(0,1-company.distance_miles/150)),
        "company_size": 10 if r.get("size") in ["1-10", "11-50", "51-200"] else 3,
        "response_likelihood": 8 if has_contact else 2,
        "startup_friendliness": 10 if r.get("startup_friendly") else 0,
        "internship_history": 15 if any(f.get("category")=="internship" for f in r.get("facts", [])) else 0,
        "technology_alignment": min(20, align*7),
        "student_friendliness": 10 if r.get("student_friendly") else 0,
        "contact_availability": 10 if has_contact else 0,
    }
    company.score_factors = factors
    company.score = min(100, sum(factors.values()))
    return company.score

STOP_STAGES = {"replied", "positive", "negative", "bounce", "opt_out", "interview", "offer", "closed"}

def record_event(db, company, kind, source_id, detail=""):
    if db.scalar(select(Event).where(Event.source_id == source_id)):
        return
    db.add(Event(company_id=company.id, kind=kind, source_id=source_id, detail=detail[:2000]))
    if kind != "open":
        # Never downgrade an offer or interview merely because a reply arrives.
        if company.stage not in {"offer", "interview"} or kind in {"offer", "bounce", "opt_out", "closed"}:
            company.stage = "replied" if kind == "reply" else kind
        for row in db.scalars(select(Outreach).where(Outreach.company_id == company.id, Outreach.status.in_(["draft", "approved", "rejected"]))):
            row.status = "cancelled"
    if kind in {"bounce", "opt_out", "negative"}:
        for c in db.scalars(select(Contact).where(Contact.company_id == company.id)):
            db.merge(Suppression(email=c.email.lower(), reason=kind))
    db.commit()


def profile_fingerprint(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
