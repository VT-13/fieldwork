"""Release blockers use fake configuration and disposable databases only."""

import asyncio
from datetime import timedelta
from types import SimpleNamespace
import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError
from sqlalchemy import select, text
from app.config import Settings
from app.auth import password_hash
from app.models import Evidence, State, Company, now
from app.intelligence.evidence import observed_city
from app.services.runtime import require_schema
from test_postgres_security import pg as pg, upgrade


def production(**changes):
    values = dict(
        environment="production",
        database_url="postgresql+psycopg://test@localhost/test",
        api_key="x" * 48,
        operator_password_hash=password_hash("release-only-test-passphrase"),
        credential_keys=Fernet.generate_key().decode(),
        app_origin="https://fieldwork.example.com",
        trusted_hosts=["fieldwork.example.com"],
        data_directory="/private/release-test",
        _env_file=None,
    )
    return Settings(**(values | changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"environment": "prodution"},
        {"app_origin": "https://"},
        {"trusted_hosts": []},
        {"operator_password_hash": "scrypt$fake"},
        {"database_url": "postgresql+psycopg://"},
        {"oauth_client_id": "configured-alone"},
        {
            "oauth_client_id": "fake-id",
            "oauth_client_secret": "fake-secret",
            "oauth_redirect_uri": "https://evil.example/api/integrations/gmail/callback",
        },
    ],
)
def test_release_unsafe_configuration_fails_early(changes):
    with pytest.raises(ValidationError):
        production(**changes)


def test_api_wrong_schema_startup_fails_without_starting_maintenance(db, monkeypatch):
    import app.main as main

    class Context:
        def __enter__(self):
            return db

        def __exit__(self, *a):
            pass

    monkeypatch.setattr(
        main, "settings", lambda: SimpleNamespace(environment="production")
    )
    monkeypatch.setattr(main, "Session", Context)

    async def start():
        async with main.lifespan(main.app):
            raise AssertionError("Unsafe API started")

    with pytest.raises(RuntimeError, match="schema005"):
        asyncio.run(start())


@pytest.mark.parametrize(
    "quote,source,expected",
    [
        ("We are based in Rocklin, California.", "official", "Rocklin"),
        ("We serve clients in Rocklin, California.", "official", None),
        ("We are based in Rocklin, California.", "third-party", None),
        ("Our office is in Roseville, California.", "official", None),
    ],
)
def test_location_requires_explicit_current_official_office_statement(
    db, quote, source, expected
):
    company = Company(
        domain="example.com", name="Example", website="https://example.com"
    )
    db.add(company)
    db.flush()
    db.add(
        Evidence(
            company_id=company.id,
            url=company.website,
            quote=quote,
            fact=quote,
            category="description",
            source_kind=source,
            confidence="source-observed",
            content_hash="test-hash",
            fetched_at=now(),
            verified_at=now(),
        )
    )
    db.add(
        State(
            key="outreach_policy",
            value={"enabled": False, "allowed_cities": ["Rocklin"]},
        )
    )
    db.commit()
    observed_city(db, company)
    assert company.research.get("city") == expected
    if expected:
        assert company.research["city_evidence_id"]


def test_migration_failure_transaction_and_duplicate_invocation(pg, monkeypatch):
    from alembic import op

    upgrade(pg, "004")
    real = op.add_column
    calls = 0

    def fail_second(*a, **kw):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Disposable migration failure")
        return real(*a, **kw)

    monkeypatch.setattr(op, "add_column", fail_second)
    with pytest.raises(RuntimeError):
        upgrade(pg)
    with pg.connect() as c:
        assert c.scalar(text("SELECT version_num FROM alembic_version")) == "004"
        assert not c.scalar(
            text(
                "SELECT count(*) FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='jobs' AND column_name='available_at'"
            )
        )
    monkeypatch.setattr(op, "add_column", real)
    upgrade(pg)
    upgrade(pg)
    from sqlalchemy.orm import Session

    with Session(pg) as db:
        require_schema(db)


def test_expired_rate_bucket_does_not_break_after_sleep(db, monkeypatch):
    from app import ingress
    from app.models import RateBucket
    moment=now()
    monkeypatch.setattr(ingress, 'now', lambda:moment)
    assert ingress.rate_limit('127.0.0.1','/auth/login','POST')[0]
    moment+=timedelta(days=8)
    assert ingress.rate_limit('127.0.0.1','/auth/login','POST')[0]
    assert db.scalar(select(RateBucket.count))==1


def test_structured_logs_exclude_request_and_operation_private_content(db, caplog):
    import logging, json
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db import session
    from app.services import ledger
    app.dependency_overrides[session]=lambda:db
    try:
        with caplog.at_level(logging.INFO, logger='uvicorn.error'):
            with TestClient(app) as client:
                response=client.get('/profile?secret=never-log-this',headers={'Authorization':'Bearer never-log-this','X-Request-ID':'never-log-this'})
                assert response.status_code==401
                from uuid import UUID
                UUID(response.headers['x-request-id'])
            attempt,_=ledger.claim(db,'private-key','self_test','fake',lambda:{'resume':'never-log-this'},entity_id='private')
            ledger.finish(db,attempt,'succeeded',receipt={'body':'never-log-this'})
        records=[json.loads(r.message) for r in caplog.records if r.name=='uvicorn.error']
        assert any(r.get('request_id') for r in records)
        assert any(r.get('operation_id') and r['status']=='succeeded' for r in records)
        assert 'never-log-this' not in json.dumps(records)
    finally:
        app.dependency_overrides.clear()


def test_operational_counts_use_shared_attempt_ledger(db):
    from app.services import ledger
    from app.services.runtime import status
    from app.models import Event
    db.execute(text('CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY)'))
    db.execute(text("INSERT INTO alembic_version VALUES ('005')"))
    db.commit()
    first,_=ledger.claim(db,'test-quota','self_test','fake',lambda:{},entity_id='self')
    ledger.finish(db,first,'unknown')
    db.add_all([Company(id='bounce1',domain='one.example.com',name='One',website='https://one.example.com'),Company(id='bounce2',domain='two.example.com',name='Two',website='https://two.example.com')]);db.flush()
    db.add_all([Event(company_id='bounce1',kind='bounce',source_id='b1'),Event(company_id='bounce2',kind='bounce',source_id='b2')]);db.commit()
    report=status(db)
    assert report['daily_attempts']==1 and report['daily_limit']==25 and report['unresolved']==1 and report['bounce_stop'] and report['daily_bounces']==2


from test_intelligence import sourced as sourced, Writer

async def test_followup_generation_preserves_original_subject_and_distinct_proposal(db,sourced):
    from app.intelligence.personalization import generate
    company,contact=sourced
    writer=Writer()
    initial=await generate(db,company,0,False,writer)
    initial.status='sent';initial.provider_id='fake-confirmed';initial.thread_id='fake-thread';db.commit()
    followup=await generate(db,company,1,False,writer)
    assert followup.status=='draft' and followup.review['passed']
    assert followup.subject==initial.subject
    assert followup.review['proposal_id']!=initial.review['proposal_id']
    assert 'Following my earlier note' in followup.body


def test_self_test_honors_lower_database_policy_cap(db):
    from app.services import ledger,policy
    db.add(State(key='outreach_policy',value={'enabled':False,'daily_total_attempt_limit':1}));db.commit()
    attempt,_=ledger.claim(db,'quota-policy','self_test','fake',lambda:{})
    ledger.finish(db,attempt,'succeeded')
    from app.core import Blocked
    with pytest.raises(Blocked,match='cap'):
        policy.own_mailbox(db,'student@example.com','student@example.com','self_test')


@pytest.mark.parametrize('http_status,code,definite',[(401,'authorization_rejected',True),(403,'authorization_rejected',True),(429,'rate_limited',True),(500,'provider_unavailable',False),(503,'provider_unavailable',False)])
async def test_google_http_failures_map_safely_without_payload_disclosure(db,monkeypatch,http_status,code,definite):
    import httpx
    from app.mail import Mailbox
    from app.services.contracts import MailboxFailure
    real=httpx.AsyncClient
    def transport(request):
        assert request.url.host=='gmail.googleapis.com'
        return httpx.Response(http_status,json={'private':'never-log-provider-body'},request=request)
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real(**kw,transport=httpx.MockTransport(transport)))
    box=Mailbox();monkeypatch.setattr(box,'ensure_authorized',lambda *a:None)
    with pytest.raises(MailboxFailure) as error:
        await box.call('GET','https://gmail.googleapis.com/gmail/v1/users/me/profile')
    assert error.value.code==code and error.value.definite is definite
    assert 'never-log-provider-body' not in str(error.value)


def test_uvicorn_owned_handler_strips_private_tracebacks():
    import io,logging
    from app.redaction import install_logging
    sink=io.StringIO();handler=logging.StreamHandler(sink)
    logger=logging.getLogger('uvicorn.error');previous=logger.level
    logger.addHandler(handler);logger.setLevel(logging.ERROR)
    try:
        install_logging()
        try:raise RuntimeError('private-provider-body-that-must-not-be-logged')
        except RuntimeError:logger.exception('Release failure category=RuntimeError')
        assert 'category=RuntimeError' in sink.getvalue()
        assert 'private-provider-body' not in sink.getvalue() and 'Traceback' not in sink.getvalue()
    finally:
        logger.removeHandler(handler);logger.setLevel(previous)
