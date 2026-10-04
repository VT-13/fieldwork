"""Explicit database operating mode; deterministic gates, never a second sender.

Missing fields mean OFF. Readiness does no provider I/O. Paid calls, generation
and delivery retain their existing reservation boundaries and immutable history.
"""
from datetime import timedelta, datetime
from uuid import uuid4
import re
from pydantic import BaseModel, ConfigDict, Field, EmailStr, TypeAdapter
from sqlalchemy import select, func
from ..models import (State, Profile, Integration, Company, Contact, ContactObservation,
                      Evidence, Generation, Outreach, Event, Suppression, Usage, Job,
                      DomainTransition, Operation, now)
from ..core import Blocked, aware, profile_fingerprint, day_start, public_url, STOP_STAGES
from ..config import settings
from . import ledger, policy

VERSION = 'autopilot/1'


class AutopilotInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    autopilot_enabled: bool = False
    new_companies_per_weekday: int = Field(10, ge=1, le=25, strict=True)
    auto_approve_initials: bool = False
    auto_approve_followups: bool = False
    confirmed: bool = False


def configuration(db):
    row = db.get(State, 'outreach_policy')
    p = row.value if row else {}
    target = p.get('new_companies_per_weekday', 10)
    valid = type(target) is int and 1 <= target <= 25
    return {'autopilot_enabled': p.get('autopilot_enabled') is True and valid,
            'new_companies_per_weekday': target if valid else 10,
            'auto_approve_initials': p.get('auto_approve_initials') is True,
            'auto_approve_followups': False,
            'policy_version': VERSION, 'revision': p.get('autopilot_revision', '')}


def budget_status(db):
    cfg = settings()
    rows = list(db.scalars(select(Usage).where(Usage.created_at >= day_start())))
    from ..intelligence.capabilities import capabilities
    caps = capabilities(db)
    if not caps['paid_allowed'] or not all(next(r for r in caps['providers'] if r['id'] == k)['available'] for k in ('research', 'generate', 'contacts')):
        return 'blocked'
    # Admission is conservative; exact per-company/request/token reservations
    # still happen in core.reserve / Bounds / providers, not in the scheduler.
    cost = cfg.scrape_reserve_usd + cfg.extract_reserve_usd + cfg.generate_reserve_usd + cfg.review_reserve_usd
    generation = sum(r.reserved_usd for r in rows if r.service in ('llm:generate', 'llm:review'))
    tokens = sum(max(r.tokens, r.details.get('reserved_tokens', 0)) for r in rows if r.service.startswith('llm:'))
    if (sum(r.reserved_usd for r in rows) + cost > cfg.daily_budget_usd
        or generation + cfg.generate_reserve_usd + cfg.review_reserve_usd > cfg.daily_generation_budget_usd
        or tokens + cfg.max_output_tokens * 2 >= cfg.daily_token_limit):
        return 'limited'
    return 'healthy'


def precheck(db, spec):
    failures = []
    profile = db.get(Profile, 1)
    if not profile or not profile.data.get('verified') or not all(profile.data.get(k) for k in ('name', 'grade', 'location', 'resume')):
        failures.append('Complete and verify your student profile, including resume text.')
    try:
        TypeAdapter(EmailStr).validate_python((profile.data if profile else {}).get('email', ''))
    except ValueError:
        failures.append('Set a valid verified student email.')
    from ..gmail_oauth import status
    account = status(db)
    if not account['connected']:
        failures.append('Connect Gmail with the encrypted account integration.')
    elif not profile or account['email'].lower() != profile.data.get('email', '').lower():
        failures.append('Connected Gmail identity must match the student profile.')
    from ..schemas import DiscoveryInput
    automation = db.get(State, 'automation')
    discovery = (automation.value if automation else {}).get('discovery')
    try:
        discovery = DiscoveryInput.model_validate(discovery).model_dump()
    except ValueError:
        discovery = None
        failures.append('Configure automatic discovery criteria.')
    if not automation or not automation.value.get('enabled'):
        failures.append('Enable the configured discovery automation separately.')
    from ..intelligence.capabilities import capabilities
    caps = {r['id']: r for r in capabilities(db)['providers']}
    for provider in ([discovery['provider']] if discovery else []) + ['research', 'generate', 'contacts']:
        if not caps[provider]['available']:
            failures.append(provider + ': ' + caps[provider]['reason'])
    state = db.get(State, 'outreach_policy')
    if not state or state.value.get('paid_services_authorized') is not True:
        failures.append('Authorize provider spending separately within configured budgets.')
    if budget_status(db) != 'healthy':
        failures.append('Provider budget is unavailable or exhausted.')
    if settings().dry_run or settings().manual_mode:
        failures.append('Runtime dry-run/manual safety mode prevents autonomous sending.')
    if not settings().response_poll_enabled:
        failures.append('Enable the existing bounded reply polling before activation.')
    from .runtime import status as runtime_status
    runtime = runtime_status(db)
    if runtime['schema_version'] != '006':
        failures.append('Database migration head must be schema006.')
    if runtime['worker'] == 'offline' or runtime['scheduler'] == 'offline':
        failures.append('Start the canonical worker and confirm scheduler health.')
    if runtime['unresolved']:
        failures.append('Reconcile unresolved delivery before activation.')
    if spec.auto_approve_followups:
        failures.append('Automatic follow-up approval is not supported; keep independent manual review.')
    return {'ready': not failures, 'failures': failures,
            'recurring_paused': runtime['recurring_paused']}


def configure(db, spec):
    ledger.lock(db)
    current = configuration(db)
    if spec.auto_approve_followups:
        db.rollback()
        raise Blocked('Follow-ups remain independently review-gated')
    if spec.autopilot_enabled:
        if not spec.confirmed:
            db.rollback()
            raise Blocked('Confirm explicit Autopilot activation; recurring pause remains independent')
        result = precheck(db, spec)
        if not result['ready']:
            db.rollback()
            raise Blocked(' '.join(result['failures']))
    state = db.get(State, 'outreach_policy')
    value = state.value if state else {'enabled': False}
    # Every deliberate reconfiguration fences approvals from the prior policy.
    for row in db.scalars(select(Outreach).where(Outreach.status == 'approved', Outreach.attempts == 0)):
        if row.review.get('autopilot_approval'):
            from ..domain.states import transition
            transition(db, row, 'draft', reason='autopilot_policy_changed')
            row.review = {**row.review, 'autopilot_approval': None, 'operator_review_hold': True}
    for job in db.scalars(select(Job).where(Job.status.in_(['queued', 'running']))):
        if job.payload.get('autopilot'):
            from ..domain.states import transition
            job.payload = {**job.payload, 'stop_requested': True}
            if job.status == 'queued':
                transition(db, job, 'cancelled', domain='job', reason='autopilot_policy_changed')
    profile = db.get(Profile, 1)
    account = db.get(Integration, 'gmail')
    automation = db.get(State, 'automation')
    value = {**value, **spec.model_dump(exclude={'confirmed'}),
             'autopilot_revision': str(uuid4()), 'autopilot_policy_version': VERSION,
             'autopilot_profile_hash': profile_fingerprint(profile.data) if profile else '',
             'autopilot_account_generation': account.generation if account else None,
             'autopilot_discovery_hash': profile_fingerprint(automation.value) if automation else ''}
    db.merge(State(key='outreach_policy', value=value))
    db.add(DomainTransition(domain='autopilot', entity_id='personal',
           from_state='on' if current['autopilot_enabled'] else 'off',
           to_state='on' if spec.autopilot_enabled else 'off', reason='operator_confirmed_mode_change'))
    db.commit()
    return view(db)


def authority(db, *, approving=False):
    cfg = configuration(db)
    state = db.get(State, 'outreach_policy')
    p = state.value if state else {}
    if not cfg['autopilot_enabled'] or approving and not cfg['auto_approve_initials']:
        raise Blocked('Autopilot initial approval is off')
    if not p.get('enabled') or p.get('stop_requested'):
        raise Blocked('Recurring outreach is paused or stopped')
    if settings().dry_run or settings().manual_mode or not settings().response_poll_enabled:
        raise Blocked('Runtime safety mode or reply polling prevents Autopilot')
    if p.get('paid_services_authorized') is not True:
        raise Blocked('Autopilot provider spending is not authorized')
    profile = db.get(Profile, 1)
    account = db.get(Integration, 'gmail')
    from ..gmail_oauth import status
    if (not profile or not profile.data.get('verified')
        or p.get('autopilot_profile_hash') != profile_fingerprint(profile.data)):
        raise Blocked('Profile changed; deliberately recheck and reactivate Autopilot')
    if (not status(db)['connected'] or account.email.lower() != profile.data.get('email', '').lower()
        or p.get('autopilot_account_generation') != account.generation):
        raise Blocked('Gmail account changed; recheck Autopilot activation')
    automation = db.get(State, 'automation')
    if not automation or not automation.value.get('enabled') or p.get('autopilot_discovery_hash') != profile_fingerprint(automation.value):
        raise Blocked('Discovery configuration changed; deliberately recheck Autopilot')
    return cfg


def require_intent(db, payload):
    cfg = authority(db)
    if payload.get('autopilot_revision') != cfg['revision'] or payload.get('stop_requested'):
        raise Blocked('Autopilot work belongs to an inactive policy; deliberate new work required')
    return cfg


def assert_eligible(db, row, at=None):
    at = at or now()
    cfg = authority(db, approving=True)
    if row.sequence != 0 or row.status not in ('draft', 'approved') or row.attempts:
        raise Blocked('Only an unattempted initial draft can receive automatic approval')
    review = row.review
    if review.get('operator_review_hold'):
        raise Blocked('Operator returned this message to manual review; regenerate explicitly')
    if review.get('personalization_score', 0) <= 80 or review.get('issues') or not all(review.get(k) is True for k in ('passed', 'grounded', 'claims_supported', 'names_correct', 'non_generic', 'non_spammy')):
        raise Blocked('Strict independent quality review must pass with score above 80')
    generation = db.get(Generation, review['generation_id']) if review.get('generation_id') else None
    if (not generation or not generation.student_fact_ids or not generation.evidence_ids
        or generation.review != {k: v for k, v in review.items() if k not in ('autopilot_approval', 'autopilot_blocked_reason')}
        or generation.input_hash != review.get('input_hash')
        or generation.evidence_ids != row.evidence_ids):
        raise Blocked('Current immutable generation and review references are required')
    from ..intelligence.personalization import assert_current, PROMPT_VERSION
    if generation.prompt_version != PROMPT_VERSION:
        raise Blocked('Writing/review pipeline changed; regenerate with current version')
    assert_current(db, row)
    company = db.get(Company, row.company_id)
    contact = db.get(Contact, row.contact_id)
    from ..intelligence.discovery import best_contact, role_fit
    if not company or company.demo or company.stage in STOP_STAGES or not company.description or not company.researched_at:
        raise Blocked('Current researched non-demo company is required')
    if aware(company.researched_at) < at - timedelta(days=30):
        raise Blocked('Company research is stale')
    if not contact or contact.company_id != company.id or best_contact(db, company) is not contact or role_fit(contact.title, company.research.get('size', 'unknown')) <= 0:
        raise Blocked('Current suitable company contact is required')
    TypeAdapter(EmailStr).validate_python(contact.email)
    if (contact.validation not in ('valid', 'public_source_dns') or not contact.validated_at
        or aware(contact.validated_at) < at - timedelta(days=7)):
        raise Blocked('Contact validation is stale or insufficient')
    if not contact.source.startswith('https://') or public_url(contact.source) != company.domain and not public_url(contact.source).endswith('.' + company.domain):
        raise Blocked('Public company contact source required')
    observed = db.scalar(select(ContactObservation.id).where(ContactObservation.contact_id == contact.id,
        ContactObservation.company_id == company.id, ContactObservation.field == 'email',
        ContactObservation.value == contact.email.lower(), ContactObservation.source_url == contact.source,
        ContactObservation.confidence.in_(['source-observed', 'provider-confirmed']),
        ContactObservation.retrieved_at >= at - timedelta(days=30)))
    if not observed:
        raise Blocked('Current public contact provenance is missing')
    evidence = list(db.scalars(select(Evidence).where(Evidence.company_id == company.id)))
    from ..intelligence.evidence import usable, INJECTION
    if len([e for e in evidence if usable(e)]) < 2:
        raise Blocked('At least two current company facts required')
    state = db.get(State, 'outreach_policy')
    city = company.research.get('city_evidence_id')
    fact = db.get(Evidence, city) if city else None
    if (company.research.get('city') not in state.value.get('allowed_cities', ['Rocklin'])
        or not fact or fact.company_id != company.id or fact.source_kind != 'official' or not usable(fact)
        or not re.search(r'\b(?:based|located|headquartered|office)\s+(?:is\s+)?in\s+' + re.escape(company.research.get('city', '')) + r'(?=\s*[,.;]|$)', fact.quote, re.I)):
        raise Blocked('Current official evidence of an allowed company city required')
    if (db.get(Suppression, contact.email.lower())
        or db.scalar(select(Event.id).where(Event.company_id == company.id, Event.kind.in_(['reply', 'auto_reply', 'positive', 'interview', 'offer', 'bounce', 'opt_out', 'negative', 'closed'])))
        or ledger.unresolved(db)
        or db.scalar(select(Outreach.id).where(Outreach.status.in_(['unknown', 'sending'])))):
        raise Blocked('Response, suppression or unresolved delivery holds outreach')
    if not row.subject.strip() or not row.body.strip() or '\r' in row.subject or '\n' in row.subject or INJECTION.search(row.subject + row.body):
        raise Blocked('Message content failed the integrity/injection gate')
    if 'let me know' not in row.body or "won’t follow up" not in row.body:
        raise Blocked('Recipient-respectful opt-out sentence required')
    return cfg


def approval_current(db, row, at):
    meta = row.review.get('autopilot_approval')
    if not meta:
        return
    cfg = assert_eligible(db, row, at)
    expected = profile_fingerprint({k: v for k, v in row.review.items() if k not in ('autopilot_approval', 'autopilot_blocked_reason')})
    if meta.get('revision') != cfg['revision'] or meta.get('review_hash') != expected or meta.get('generation_id') != row.review.get('generation_id'):
        raise Blocked('Autopilot approval no longer matches current policy/review')


def approve_initial(db, row):
    ledger.lock(db)
    row = db.get(Outreach, row.id)
    try:
        cfg = assert_eligible(db, row)
    except (Blocked, ValueError) as exc:
        row.review = {**row.review, 'autopilot_blocked_reason': str(exc)[:240]}
        db.commit()
        return False
    if row.status != 'draft':
        db.commit()
        return False
    from ..domain.states import transition
    transition(db, row, 'approved', reason='autopilot_quality_gate')
    row.review = {**row.review, 'autopilot_blocked_reason': None,
                  'autopilot_approval': {'policy_version': VERSION, 'revision': cfg['revision'],
                  'quality_score': row.review['personalization_score'], 'generation_id': row.review['generation_id'],
                  'at': now().isoformat(), 'review_hash': profile_fingerprint({k: v for k, v in row.review.items() if k not in ('autopilot_approval', 'autopilot_blocked_reason')})}}
    db.commit()
    return True


def remaining(db, at):
    from zoneinfo import ZoneInfo
    local = at.astimezone(ZoneInfo(settings().timezone))
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    target = configuration(db)['new_companies_per_weekday']
    return max(0, min(target - policy.send_usage(db, start, initial_only=True),
                      policy.snapshot(db, 'scheduled')['daily_cap'] - policy.send_usage(db, start)))


def view(db):
    cfg = configuration(db)
    p = db.get(State, 'outreach_policy')
    rows = list(db.scalars(select(Outreach)))
    # A legacy/ledger representation of the same attempted company is one hold.
    holds = {'company:' + r.id for r in rows if r.status in ('unknown', 'sending')}
    for op in db.scalars(select(Operation).where(Operation.kind.in_(['company_send', 'self_test', 'mailbox_draft']), Operation.status.in_(['running', 'unknown']))):
        holds.add('company:' + op.outreach_id if op.outreach_id else 'operation:' + op.id)
    return {**cfg, 'recurring_paused': not p or not p.value.get('enabled'),
            'daily_attempts': policy.send_usage(db, day_start()), 'daily_limit': policy.snapshot(db, 'read_only')['daily_cap'],
            'new_introductions_today': policy.send_usage(db, day_start(), initial_only=True),
            'approved_queue': sum(r.status == 'approved' and not r.attempts for r in rows),
            'needs_review': sum(r.status in ('draft', 'rejected') and not r.attempts for r in rows),
            'replies': db.scalar(select(func.count()).select_from(Event).where(Event.kind.in_(['reply', 'positive', 'interview', 'offer']))),
            'delivery_holds': len(holds),
            'provider_budget_status': budget_status(db), 'followups_supported': False}


def candidate_allowed(candidate, spec, cities, at):
    if candidate.status != 'candidate' or not candidate.name or candidate.company_id:
        return False
    observations = candidate.observations
    def observed(field, value=None):
        for o in observations:
            if o.get('field') != field or o.get('confidence') != 'provider-confirmed':
                continue
            try:
                if aware(datetime.fromisoformat(o['retrieved_at'])) < at - timedelta(days=30):
                    continue
            except (ValueError, KeyError, TypeError):
                continue
            if field == 'website':
                try:
                    if o.get('value', '').startswith('https://') and public_url(o['value']) == candidate.domain:
                        return True
                except Blocked:
                    continue
            elif value is None or o.get('value') == value:
                return True
        return False
    if not observed('name', candidate.name) or not observed('website', candidate.website):
        return False
    if not observed('location') or not observed('distance_miles', str(candidate.distance_miles)):
        return False
    if candidate.distance_miles is None or candidate.distance_miles < 0 or candidate.distance_miles > spec['radius_miles']:
        return False
    locations = [o.get('value', '') for o in observations if o.get('field') == 'location']
    return any(re.search(r'\b' + re.escape(city) + r'\b', location, re.I) for city in cities for location in locations)


def plan(db, at, caps):
    """Called under the scheduler lock. Bounded work, no network or approval."""
    from zoneinfo import ZoneInfo
    from ..models import Candidate
    from ..schemas import DiscoveryInput
    from . import jobs
    try:
        authority(db)
    except Blocked:
        return
    local = at.astimezone(ZoneInfo(settings().timezone))
    if local.weekday() > 4 or not 9 <= local.hour < 17 or ledger.unresolved(db):
        return
    if budget_status(db) != 'healthy' or not all(caps[k]['available'] for k in ('research', 'generate', 'contacts')):
        return
    state = db.get(State, 'outreach_policy')
    if state.value.get('paid_services_authorized') is not True:
        return
    allowance = remaining(db, at)
    if not allowance:
        return
    automation = db.get(State, 'automation')
    try:
        spec = DiscoveryInput.model_validate(automation.value.get('discovery')).model_dump()
    except (ValueError, AttributeError):
        return
    # Inventory includes manual-review drafts and active work, not only approvals.
    # Terminal failures never auto-retry. Operator retry remains bounded/explicit.
    unsent = db.scalar(select(func.count()).select_from(Outreach).where(Outreach.status.in_(['draft', 'approved', 'rejected']), Outreach.attempts == 0))
    active = list(db.scalars(select(Job).where(Job.kind.in_(['pipeline', 'research', 'generate', 'discover', 'verify']), Job.status.in_(['queued', 'running']))))
    ceiling = min(50, allowance * 2)
    if unsent + len(active) >= ceiling:
        return
    candidates = list(db.scalars(select(Candidate).where(Candidate.status == 'candidate').order_by(Candidate.updated_at).limit(50)))
    companies = list(db.scalars(select(Company).where(Company.stage.in_(['discovered', 'researched']), Company.demo == False,
        ~select(Outreach.id).where(Outreach.company_id == Company.id).exists(),
        ~select(Job.id).where(Job.dedupe_key == 'pipeline:' + Company.id).exists()).order_by(Company.score.desc()).limit(50)))
    # Do not replenish while any prior discovery is active or enough work exists.
    if not any(j.kind == 'discover' for j in active) and unsent + len(active) + len(companies) + len(candidates) < ceiling and caps[spec['provider']]['available']:
        jobs.enqueue(db, 'discover', {**spec, 'limit': min(spec['limit'], ceiling - unsent - len(active) - len(companies) - len(candidates)), 'autopilot': True, 'autopilot_revision': configuration(db)['revision']}, 'scheduled-discovery:' + local.date().isoformat(), commit=False)
    # Acceptance is a strict prospect-buffer transition; still no contact/send grant.
    if not companies:
        from ..intelligence.discovery import accept
        for candidate in candidates:
            if candidate_allowed(candidate, spec, state.value.get('allowed_cities', ['Rocklin']), at):
                company = accept(db, candidate, source='Autopilot sourced candidate acceptance', commit=False)
                companies.append(company)
                break
    if len([j for j in active if j.kind != 'discover']) >= 3:
        return
    for company in companies:
        if company.distance_miles is None or company.distance_miles > spec['radius_miles']:
            continue
        if db.scalar(select(Job.id).where(Job.dedupe_key == 'pipeline:' + company.id)):
            continue
        jobs.enqueue(db, 'pipeline', {'id': company.id, 'autopilot': True, 'autopilot_revision': configuration(db)['revision']}, 'pipeline:' + company.id, commit=False)
        break
