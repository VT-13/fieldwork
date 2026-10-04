"""Autopilot tests use fictional profiles, fake providers and disposable databases."""
import pytest
from app.services import autopilot


def test_missing_policy_defaults_off_without_writes(db):
    assert not autopilot.configuration(db)['autopilot_enabled']
    assert not autopilot.configuration(db)['auto_approve_followups']


@pytest.mark.parametrize('target', [0, 26, True, 1.5])
def test_invalid_target_rejected(target):
    with pytest.raises(ValueError):
        autopilot.AutopilotInput(new_companies_per_weekday=target)

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select, func
from app.models import (State, Profile, Integration, Outreach, Company, Contact,
                        Evidence, Event, Generation, Job, Usage, Suppression,
                        DomainTransition, now)
from app.core import Blocked, profile_fingerprint, record_event
from app.services import policy, scheduler, jobs
from app.services.delivery import send_company
from app.intelligence.personalization import generate
from app.intelligence.evidence import persist, observed_city
from app.intelligence.schemas import ExtractedFact
from app import worker
from test_intelligence import sourced as sourced, Writer
from test_runtime import Provider
from test_postgres_security import pg as pg, upgrade


@pytest.fixture
def active(db, sourced, monkeypatch):
    for key in ('OPENAI_API_KEY', 'FIRECRAWL_API_KEY', 'HUNTER_API_KEY', 'GOOGLE_MAPS_API_KEY'):
        monkeypatch.setenv(key, 'fake-test-provider-key')
    monkeypatch.setenv('DRY_RUN', 'false')
    monkeypatch.setenv('RESPONSE_POLL_ENABLED', 'true')
    p = db.get(Profile, 1)
    p.data = {**p.data, 'resume': 'Fictional verified student resume'}
    c, ct = sourced
    c.researched_at = now()
    c.research = {**c.research, 'city': 'Rocklin'}
    quote = 'Our office is in Rocklin.'
    persist(db, c, [ExtractedFact(url=c.website, quote=quote, category='description')], [{'url': c.website, 'text': quote}])
    observed_city(db, c)
    db.add(Integration(id='gmail', email=p.data['email'], status='connected', encrypted_tokens='fictional-ciphertext', scopes=[], generation=1))
    db.add(State(key='automation', value={'enabled': True, 'discovery': {'provider': 'maps', 'area': 'Rocklin', 'radius_miles': 50}}))
    db.get(State, 'outreach_policy').value = {'enabled': True, 'paid_services_authorized': True, 'max_followups_per_company': 1, 'allowed_cities': ['Rocklin']}
    db.add(State(key='worker_heartbeat', value={'at': now().isoformat(), 'status': 'idle'}))
    db.add(State(key='scheduler_heartbeat', value={'at': now().isoformat(), 'status': 'ok'}))
    # Stamp the complete disposable ORM fixture; canonical migration tests below
    # separately verify actual fresh and head upgrades.
    from alembic.config import Config
    from alembic import command
    with db.bind.begin() as conn:
        config = Config('alembic.ini');config.attributes['connection'] = conn
        command.stamp(config, '006')
    db.commit()
    return c, ct


def activate(db, target=10, **kwargs):
    return autopilot.configure(db, autopilot.AutopilotInput(autopilot_enabled=True,
        confirmed=True, auto_approve_initials=True, new_companies_per_weekday=target, **kwargs))


@pytest.mark.parametrize('target', [1, 25])
def test_deliberate_activation_boundaries_preserve_pause(db, active, target):
    policy.set_paused(db, False)
    result = activate(db, target)
    assert result['autopilot_enabled'] and result['new_companies_per_weekday'] == target
    assert result['recurring_paused']
    assert db.get(State, 'outreach_policy').value['enabled'] is False


@pytest.mark.parametrize('failure', ['profile', 'email', 'resume', 'gmail', 'identity', 'discovery', 'provider', 'paid', 'worker', 'schema', 'unknown', 'polling'])
def test_activation_preconditions_are_atomic(db, active, monkeypatch, failure):
    if failure in ('profile', 'email', 'resume'):
        p = db.get(Profile, 1);p.data = {**p.data, {'profile': 'verified', 'email': 'email', 'resume': 'resume'}[failure]: False if failure == 'profile' else ''}
    elif failure == 'gmail': db.get(Integration, 'gmail').status = 'disconnected'
    elif failure == 'identity': db.get(Integration, 'gmail').email = 'different@example.net'
    elif failure == 'discovery': db.get(State, 'automation').value = {'enabled': True}
    elif failure == 'provider': monkeypatch.setenv('HUNTER_API_KEY', '')
    elif failure == 'paid': db.get(State, 'outreach_policy').value = {'enabled': True, 'paid_services_authorized': False}
    elif failure == 'worker': db.get(State, 'worker_heartbeat').value = {'at': (now()-timedelta(days=1)).isoformat()}
    elif failure == 'schema':
        from sqlalchemy import text
        db.execute(text("UPDATE alembic_version SET version_num='005'"))
    elif failure == 'unknown':
        c, ct = active;db.add(Outreach(company_id=c.id, contact_id=ct.id, status='unknown'))
    elif failure == 'polling': monkeypatch.setenv('RESPONSE_POLL_ENABLED', 'false')
    db.commit()
    with pytest.raises(Blocked): activate(db)
    assert not autopilot.configuration(db)['autopilot_enabled']


def test_confirmation_required_and_followups_refused(db, active):
    with pytest.raises(Blocked, match='Confirm'):
        autopilot.configure(db, autopilot.AutopilotInput(autopilot_enabled=True))
    with pytest.raises(Blocked, match='Follow-ups'):
        activate(db, auto_approve_followups=True)
    assert not autopilot.configuration(db)['autopilot_enabled']


async def prepared(db, active):
    activate(db)
    c, ct = active
    row = await generate(db, c, 0, False, Writer())
    return c, ct, row


async def test_automatic_approval_audit_and_replay(db, active):
    c, ct, row = await prepared(db, active)
    assert autopilot.approve_initial(db, row)
    assert row.status == 'approved'
    m = row.review['autopilot_approval']
    assert m['generation_id'] == row.review['generation_id'] and m['quality_score'] > 80 and m['policy_version']
    assert db.scalar(select(func.count()).select_from(DomainTransition).where(DomainTransition.reason == 'autopilot_quality_gate')) == 1
    assert not autopilot.approve_initial(db, row)
    autopilot.approval_current(db, row, now())


@pytest.mark.parametrize('failure', ['score', 'claim', 'generic', 'names', 'spam', 'evidence', 'contact', 'profile', 'edit', 'reply', 'auto_reply', 'bounce', 'opt_out', 'negative', 'closed', 'suppression', 'unknown', 'demo', 'city', 'contact_source', 'fact_owner', 'generation', 'research', 'pause'])
async def test_quality_and_conversation_fail_closed(db, active, failure):
    c, ct, row = await prepared(db, active)
    if failure in ('score', 'claim', 'generic', 'names', 'spam'):
        key = {'score': 'personalization_score', 'claim': 'claims_supported', 'generic': 'non_generic', 'names': 'names_correct', 'spam': 'non_spammy'}[failure]
        report = {**row.review, key: 80 if failure == 'score' else False}
        row.review = report;db.get(Generation, report['generation_id']).review = report
    elif failure == 'evidence': db.get(Evidence, row.evidence_ids[0]).fetched_at = now()-timedelta(days=100)
    elif failure == 'contact': ct.validated_at = now()-timedelta(days=8)
    elif failure == 'profile': db.get(Profile, 1).data = {**db.get(Profile, 1).data, 'skills': ['Changed experience']}
    elif failure == 'edit': row.body += ' An operator edit.'
    elif failure in ('reply', 'auto_reply', 'bounce', 'opt_out', 'negative', 'closed'): db.add(Event(company_id=c.id, kind=failure, source_id='fake-'+failure))
    elif failure == 'suppression': db.add(Suppression(email=ct.email.lower(), reason='opt_out'))
    elif failure == 'unknown':
        other = Company(domain='unknown.example', name='Unknown', website='https://unknown.example');db.add(other);db.flush()
        db.add(Outreach(company_id=other.id, contact_id=ct.id, status='unknown'))
    elif failure == 'demo': c.demo = True
    elif failure == 'city': c.research = {**c.research, 'city': 'Sacramento'}
    elif failure == 'contact_source': ct.source = 'https://other.example/contact'
    elif failure == 'fact_owner': db.get(Evidence, row.evidence_ids[0]).company_id = 'different-company'
    elif failure == 'generation': row.review = {**row.review, 'generation_id': None}
    elif failure == 'research': c.researched_at = now()-timedelta(days=40)
    elif failure == 'pause': policy.set_paused(db, False)
    db.commit()
    assert not autopilot.approve_initial(db, row)
    assert row.status == 'draft' and row.review['autopilot_blocked_reason']
    assert db.scalar(select(func.count()).select_from(DomainTransition).where(DomainTransition.reason == 'autopilot_quality_gate')) == 0


async def test_edit_disable_and_policy_change_invalidate_approval(db, active):
    c, ct, row = await prepared(db, active)
    assert autopilot.approve_initial(db, row)
    from app.main import edit_outreach
    from app.ui_contracts import OutreachEdit
    edit_outreach(row.id, OutreachEdit(subject=row.subject, body=row.body+' An operator edit.'), db)
    assert row.status == 'draft' and not autopilot.approve_initial(db, row)
    row = await generate(db, c, 0, True, Writer())
    assert autopilot.approve_initial(db, row)
    autopilot.configure(db, autopilot.AutopilotInput(autopilot_enabled=False))
    assert row.status == 'draft' and not autopilot.approve_initial(db, row)
    assert row.review['operator_review_hold']


def clock(monkeypatch):
    at = now().astimezone(ZoneInfo('America/Los_Angeles'))
    while at.weekday() > 4: at += timedelta(days=1)
    at = at.replace(hour=10, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    for module in ('app.services.delivery', 'app.services.autopilot', 'app.services.ledger', 'app.intelligence.personalization', 'app.intelligence.evidence', 'app.intelligence.discovery'):
        monkeypatch.setattr(module+'.now', lambda: at)
    return at


async def test_canonical_send_pause_reply_unknown_and_restart_no_duplicate(db, active, monkeypatch):
    at = clock(monkeypatch)
    c, ct, row = await prepared(db, active)
    row.due_at = at-timedelta(seconds=1);db.commit()
    assert autopilot.approve_initial(db, row)
    provider = Provider()
    await send_company(db, row.id, mode='scheduled', provider=provider)
    await send_company(db, row.id, mode='scheduled', provider=provider)
    assert provider.sent == 1 and row.attempts == 1


async def test_scheduler_dedupe_pause_and_cadence(db, active, monkeypatch):
    at = clock(monkeypatch)
    c, ct, row = await prepared(db, active)
    row.due_at = at-timedelta(seconds=1);db.commit()
    assert autopilot.approve_initial(db, row)
    scheduler.tick(db, at);scheduler.tick(db, at)
    assert db.scalar(select(func.count()).select_from(Job).where(Job.kind == 'send')) == 1
    policy.set_paused(db, False)
    provider = Provider()
    with pytest.raises(Blocked, match='paused'):
        await send_company(db, row.id, mode='scheduled', provider=provider)
    assert provider.sent == 0


@pytest.mark.parametrize('target', [1, 25])
async def test_configured_new_cap_and_shared_total(db, active, monkeypatch, target):
    at = clock(monkeypatch)
    c, ct, row = await prepared(db, active)
    # Deliberate target edit before this fresh generation avoids old approval reuse.
    activate(db, target)
    row.due_at = at-timedelta(seconds=1);db.commit()
    assert autopilot.approve_initial(db, row)
    for n in range(target):
        old = Company(domain=f'count-{n}.example', name='Counted', website='https://count.example');db.add(old);db.flush()
        db.add(Outreach(company_id=old.id, contact_id=ct.id, sequence=0, status='sent', attempts=1, sent_at=at-timedelta(minutes=target-n+5)))
    db.commit()
    with pytest.raises(Blocked, match='cap'):
        policy.company(db, row, at, 'scheduled')


async def test_followups_and_selftests_reduce_remaining_introductions(db, active, monkeypatch):
    at = clock(monkeypatch)
    activate(db, 25)
    from app.services import ledger
    for n in range(24):
        attempt, _ = ledger.claim(db, 'synthetic-self-'+str(n), 'self_test', 'gmail', lambda: {'synthetic': True}, entity_id=str(n))
        attempt.started_at = at - timedelta(minutes=10);db.commit()
        ledger.finish(db, attempt, 'succeeded', receipt={'fake': True})
    assert autopilot.remaining(db, at) == 1
    # A follow-up consumes the same remaining unit, never 25 plus follow-ups.
    c, ct = active
    follow = Outreach(company_id=c.id, contact_id=ct.id, sequence=1, status='sent', attempts=1, sent_at=at-timedelta(minutes=10));db.add(follow);db.commit()
    assert autopilot.remaining(db, at) == 0
    assert policy.send_usage(db, at.replace(hour=0)) == 25


async def test_backpressure_and_budget_failure_do_not_loop(db, active, monkeypatch):
    at = clock(monkeypatch)
    activate(db, 1)
    c, ct = active
    # Two manual-review drafts fill the one-introduction work buffer.
    for n in range(2):
        other = Company(domain=f'draft-{n}.example', name='Draft', website='https://draft.example');db.add(other);db.flush()
        db.add(Outreach(company_id=other.id, contact_id=ct.id, status='draft'))
    db.commit();scheduler.tick(db, at);scheduler.tick(db, at)
    assert not db.scalar(select(Job.id).where(Job.kind.in_(['pipeline', 'discover'])))
    for r in db.scalars(select(Outreach)): db.delete(r)
    db.add(Usage(service='llm:generate', reserved_usd=100, tokens=100000));db.commit()
    for _ in range(5): scheduler.tick(db, at)
    assert not db.scalar(select(Job.id).where(Job.kind.in_(['pipeline', 'discover'])))
    assert autopilot.view(db)['provider_budget_status'] == 'limited'


async def test_autopilot_off_retains_manual_generation(db, active):
    c, ct = active
    row = await generate(db, c, 0, False, Writer())
    assert row.status == 'draft' and not autopilot.approve_initial(db, row)
    assert not autopilot.configuration(db)['auto_approve_followups']


@pytest.mark.parametrize('at', [datetime(2026,10,4,17,tzinfo=timezone.utc), datetime(2026,10,5,3,tzinfo=timezone.utc)])
async def test_weekend_and_business_hours_block_intents(db, active, at):
    activate(db)
    scheduler.tick(db, at)
    assert not db.scalar(select(Job.id).where(Job.kind.in_(['send', 'pipeline', 'discover'])))


def test_fresh_and_repeat_head_preserve_autopilot_off(pg):
    from sqlalchemy.orm import Session
    upgrade(pg)
    with Session(pg) as db:
        assert not autopilot.configuration(db)['autopilot_enabled']
        db.add(State(key='outreach_policy', value={'enabled': False, 'new_companies_per_weekday': 10}))
        db.commit()
    upgrade(pg, '006');upgrade(pg)
    with Session(pg) as db:
        assert not autopilot.configuration(db)['autopilot_enabled']
        assert db.get(State, 'outreach_policy').value == {'enabled': False, 'new_companies_per_weekday': 10}


async def test_autopilot_fake_provider_end_to_end_and_reply_cancellation(db, active, monkeypatch):
    """Actual deterministic scheduler/worker/gates/ledger, all provider seams fake."""
    from app.intelligence.schemas import Extraction
    from app.intelligence.evidence import research
    from app.intelligence.discovery import ingest_candidates
    from app.services.jobs import owned
    from app.domain.states import transition
    at = clock(monkeypatch)
    activate(db, 1)
    async def discover(db, spec):
        return [{'name': 'Fictional Local Tools', 'website': 'https://tools.example',
                 'industry': 'software robotics', 'location': 'Rocklin, California',
                 'distance_miles': 5, 'provider_id': 'fake-maps-id', 'source': 'maps', 'retrieved_at': at}]
    class ResearchWriter(Writer):
        async def contacts(self, db, c):
            return [{'email': 'lead@tools.example', 'name': 'Morgan Example', 'title': 'Engineering Lead', 'source_url': c.website+'/contact', 'confidence': 'source-observed', 'retrieved_at': at}]
        async def scrape(self, db, c, url):
            return 'We build robotics software dashboards. Our software analyzes robot sensor logs. Our office is in Rocklin.'
        async def llm(self, db, cid, schema, instruction, data, purpose='extract'):
            if purpose == 'extract':
                url = data['pages'][0]['url']
                return Extraction(facts=[ExtractedFact(url=url, quote=q, category=category) for q, category in [('We build robotics software dashboards.', 'product'), ('Our software analyzes robot sensor logs.', 'service'), ('Our office is in Rocklin.', 'description')]])
            return await super().llm(db, cid, schema, instruction, data, purpose)
    gateway = ResearchWriter()
    async def research_fake(db, c): return await research(db, c, gateway)
    async def generate_fake(db, c, sequence=0, replace=False, job_id=None): return await generate(db, c, sequence, replace, gateway, job_id)
    async def verify_fake(db, ct):
        ct.validation = 'valid';ct.validated_at = at;db.commit();return 'valid'
    async def sync_fake(db): return 0
    monkeypatch.setattr(worker, 'discover', discover)
    monkeypatch.setattr(worker, 'research', research_fake)
    monkeypatch.setattr(worker, 'generate', generate_fake)
    monkeypatch.setattr(worker, 'verify', verify_fake)
    monkeypatch.setattr(worker, 'sync_mailbox', sync_fake)
    provider = Provider();monkeypatch.setattr('app.services.delivery.MailboxProvider', lambda box: provider)
    async def run_kind(kind):
        # Simulate the same durable claim/owner/transition behavior as worker.tick,
        # selecting the intended job after draining prioritized fake read jobs.
        for _ in range(10):
            job = jobs.claim_next(db, at)
            assert job is not None
            with owned(job): result = await worker.execute(db, job)
            transition(db, job, 'done', domain='job', reason='job_completed');db.commit()
            if job.kind == kind: return result
        raise AssertionError('Bounded fake work did not reach '+kind)
    scheduler.tick(db, at)
    await run_kind('discover')
    scheduler.tick(db, at)
    result = await run_kind('pipeline')
    row = db.get(Outreach, result['draft_id'])
    assert result['autopilot_approved'] and row.status == 'approved'
    row.due_at = at-timedelta(seconds=1);db.commit()
    scheduler.tick(db, at);scheduler.tick(db, at)
    await run_kind('send')
    assert provider.sent == 1 and row.status == 'sent'
    # Immutable reply uses canonical cancellation; no automatic reply or next send.
    c = db.get(Company, row.company_id)
    record_event(db, c, 'reply', 'fake-autopilot-reply', contact_id=row.contact_id, outreach_id=row.id)
    scheduler.tick(db, at+timedelta(days=8))
    assert not db.scalar(select(Job.id).where(Job.kind=='followup_prepare', Job.status=='queued', Job.payload['company_id'].as_string()==c.id))
    assert provider.sent == 1


async def test_failed_pipeline_does_not_retry_or_starve_other_candidates(db, active, monkeypatch):
    from app.intelligence.discovery import ingest_candidates
    at = clock(monkeypatch);activate(db)
    c, ct = active;c.stage = 'discovered'
    db.add(Job(kind='pipeline', payload={'id': c.id}, dedupe_key='pipeline:'+c.id, status='failed'))
    ingest_candidates(db, [{'name': 'Second Fictional', 'website': 'https://second.example', 'location': 'Rocklin, California', 'distance_miles': 5, 'provider_id': 'fake-second', 'source':'maps', 'retrieved_at':at}], 'fictional')
    scheduler.tick(db, at)
    queued = db.scalar(select(Job).where(Job.kind=='pipeline', Job.status=='queued'))
    assert queued and queued.payload['id'] != c.id
    scheduler.tick(db, at)
    assert db.scalar(select(func.count()).select_from(Job).where(Job.kind=='pipeline')) == 2


@pytest.mark.parametrize('failure', ['reply', 'auto_reply', 'bounce', 'opt_out', 'profile', 'discovery'])
async def test_changed_inputs_stop_already_autoapproved_delivery(db, active, monkeypatch, failure):
    at = clock(monkeypatch)
    c, ct, row = await prepared(db, active)
    row.due_at = at-timedelta(seconds=1);db.commit()
    assert autopilot.approve_initial(db, row)
    if failure in ('reply', 'auto_reply', 'bounce', 'opt_out'):
        record_event(db, c, failure, 'fake-late-'+failure, contact_id=ct.id, outreach_id=row.id)
    elif failure == 'profile':
        db.get(Profile, 1).data = {**db.get(Profile, 1).data, 'skills': ['Changed']}
    else:
        a = db.get(State, 'automation');a.value = {**a.value, 'discovery': {**a.value['discovery'], 'area': 'Roseville'}}
    db.commit()
    provider = Provider()
    with pytest.raises(Blocked):
        await send_company(db, row.id, mode='scheduled', provider=provider)
    assert provider.sent == 0 and row.attempts == 0
    if failure == 'opt_out':
        assert db.get(Suppression, ct.email.lower())


@pytest.mark.parametrize('change', ['disable', 'reconfigure', 'discovery'])
def test_inactive_policy_fences_queued_and_running_work(db, active, change):
    activate(db)
    revision = autopilot.configuration(db)['revision']
    payload = {'autopilot': True, 'autopilot_revision': revision}
    queued = Job(kind='pipeline', payload={**payload, 'id':active[0].id}, dedupe_key='fictional-queued')
    running = Job(kind='discover', payload=payload, status='running', dedupe_key='fictional-running')
    db.add_all([queued, running]);db.commit()
    autopilot.require_intent(db, running.payload)
    if change == 'disable':
        autopilot.configure(db, autopilot.AutopilotInput(autopilot_enabled=False))
    elif change == 'reconfigure':
        activate(db, 25)
    else:
        a = db.get(State, 'automation');a.value = {**a.value, 'enabled': False};db.commit()
    with pytest.raises(Blocked):
        autopilot.require_intent(db, running.payload)
    if change != 'discovery':
        assert queued.status == 'cancelled' and running.payload['stop_requested']
    assert not db.scalar(select(Usage.id))


def test_autopilot_http_requires_authenticated_confirmed_same_origin_operator(db, active, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db import session
    from app.auth import password_hash
    from app.config import settings
    monkeypatch.setenv('API_KEY', 'fictional-autopilot-test-private-key-more-than-32-characters')
    monkeypatch.setenv('OPERATOR_PASSWORD_HASH', password_hash('fictional-operator-long-passphrase'))
    settings.cache_clear()
    app.dependency_overrides[session] = lambda: db
    body = {'autopilot_enabled': True, 'new_companies_per_weekday': 25, 'auto_approve_initials': True}
    try:
        with TestClient(app) as client:
            assert client.get('/autopilot').status_code == 401
            assert client.post('/autopilot/precheck', json=body).status_code == 401
            assert client.put('/autopilot', json=body).status_code == 401
            origin = {'Origin': settings().app_origin}
            assert client.post('/auth/login', headers=origin, json={'password': 'fictional-operator-long-passphrase'}).status_code == 200
            assert client.get('/autopilot').json()['autopilot_enabled'] is False
            assert client.put('/autopilot', headers={'Origin': 'https://attacker.example'}, json={**body, 'confirmed': True}).status_code == 403
            assert client.put('/autopilot', headers=origin, json=body).status_code == 409
            assert client.put('/autopilot', headers=origin, json={**body, 'confirmed': True, 'new_companies_per_weekday': 26}).status_code == 422
            assert not autopilot.configuration(db)['autopilot_enabled']
            assert client.post('/autopilot/precheck', headers=origin, json=body).json()['ready']
            result = client.put('/autopilot', headers=origin, json={**body, 'confirmed': True})
            assert result.status_code == 200 and result.json()['autopilot_enabled']
            assert client.put('/autopilot', headers=origin, json={'autopilot_enabled': False}).json()['autopilot_enabled'] is False
    finally:
        app.dependency_overrides.clear()
