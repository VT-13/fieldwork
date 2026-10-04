"""FW-026: exact identities, provenance, read-only source and fail-safe staging."""
import hashlib
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app.db import Base
from app.models import State
from app.core import Blocked
from scripts.transfer_legacy import preflight, snapshot, transfer
from test_postgres_security import pg as pg, upgrade
from test_release_migration import (
    old_state, LEGACY_TEST_KEY, LEGACY_TEST_VALUE, PACKET_ID,
    assert_self_test_provenance,
)


@pytest.mark.parametrize('fresh', [False, True])
def test_sqlite006_exact_identity_repeat_and_backup_restore(tmp_path, fresh):
    from scripts.backup_database import backup
    if fresh:
        source = tmp_path / 'fresh.sqlite'
        expected = None
    else:
        source, expected = old_state(tmp_path)
    engine = create_engine('sqlite:///' + str(source))
    upgrade(engine)
    upgrade(engine)  # Repetition cannot duplicate002's history backfill.
    if expected is not None:
        assert snapshot(engine) == expected
        with engine.connect() as c:
            assert_self_test_provenance(c)
    with engine.begin() as c:
        assert c.scalar(text('SELECT version_num FROM alembic_version')) == '006'
        assert compare_metadata(MigrationContext.configure(c), Base.metadata) == []
        c.execute(State.__table__.insert().values(key='normal-state', value={'paused': True}))
    saved = tmp_path / 'schema006-backup.sqlite'
    backup(str(engine.url), saved)
    restored = create_engine('sqlite:///' + str(saved))
    assert snapshot(restored) == snapshot(engine)
    with restored.connect() as c:
        assert inspect(c).get_columns('state')[0]['type'].length == 255
        assert c.scalar(text('SELECT version_num FROM alembic_version')) == '006'
    engine.dispose(); restored.dispose()


def test_read_only_preflight_preserves_source_credentials_and_all_rows(tmp_path, monkeypatch):
    source, expected = old_state(tmp_path)
    credentials = tmp_path / '.env'
    credentials.write_bytes(b'SYNTHETIC_TOKEN=external-reference\n')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    writes = []
    original = sqlite3.connect
    forbidden = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
                 sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_CREATE_TABLE,
                 sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_CREATE_INDEX,
                 sqlite3.SQLITE_DROP_INDEX}
    def connect(*args, **kwargs):
        assert '?mode=ro' in args[0] and kwargs['uri']
        conn = original(*args, **kwargs)
        def authorize(action, *_):
            if action in forbidden:
                writes.append(action)
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        conn.set_authorizer(authorize)
        return conn
    monkeypatch.setattr(sqlite3, 'connect', connect)
    result = preflight(source)
    assert result['safely_migratable'] and not result['applied']
    assert result['state_keys_requiring_widening'] == 4
    assert result['target_revision'] == '006' and not writes
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    assert credentials.read_bytes() == b'SYNTHETIC_TOKEN=external-reference\n'
    monkeypatch.setattr(sqlite3, 'connect', original)
    engine = create_engine('sqlite:///' + str(source))
    assert snapshot(engine) == expected
    engine.dispose()


def test_postgres_exact_keys_no_alias_collisions_or_duplicate_backfill(pg, tmp_path):
    source, expected = old_state(tmp_path)
    with pg.connect() as c:
        schema = c.scalar(text('SELECT current_schema()'))
    url = pg.url.update_query_dict({'options': '-csearch_path=' + schema}).render_as_string(hide_password=False)
    transfer(source, url, apply=True, stopped=True)
    upgrade(pg)
    assert snapshot(pg) == expected
    with Session(pg) as db:
        assert db.get(State, LEGACY_TEST_KEY).value == LEGACY_TEST_VALUE
        assert db.get(State, 'history:' + 'x' * 100 + 'A').value != db.get(State, 'history:' + 'x' * 100 + 'a').value
        db.add(State(key=LEGACY_TEST_KEY, value={'replacement': True}))
        with pytest.raises(IntegrityError): db.commit()
        db.rollback()
        assert db.get(State, LEGACY_TEST_KEY).value == LEGACY_TEST_VALUE
    with pg.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM operations WHERE kind='self_test'")) == 1
        assert_self_test_provenance(c)


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['sent', 'unknown'])
async def test_migrated_historical_identity_remains_a_delivery_guard(pg, tmp_path, monkeypatch, status):
    from app import self_test, desk
    source, _ = old_state(tmp_path)
    with pg.connect() as c: schema = c.scalar(text('SELECT current_schema()'))
    url = pg.url.update_query_dict({'options': '-csearch_path=' + schema}).render_as_string(hide_password=False)
    transfer(source, url, apply=True, stopped=True)
    monkeypatch.setattr(desk, 'mailbox_address', lambda db: 'student@example.com')
    class ForbiddenMailbox:
        async def connect(self): raise AssertionError('Historical test must never reach a provider')
    with Session(pg) as db:
        if status == 'unknown':
            db.get(State, LEGACY_TEST_KEY).value = {**LEGACY_TEST_VALUE, 'status': status}
            db.commit()
            with pytest.raises(Blocked, match='uncertain'):
                await self_test.send(db, PACKET_ID, ForbiddenMailbox())
        else:
            assert await self_test.send(db, PACKET_ID, ForbiddenMailbox()) == LEGACY_TEST_VALUE


def test_staging_failure_rolls_back_all_ddl_and_can_retry(pg, tmp_path, monkeypatch):
    from scripts import transfer_legacy
    source, expected = old_state(tmp_path)
    with pg.connect() as c: schema = c.scalar(text('SELECT current_schema()'))
    url = pg.url.update_query_dict({'options': '-csearch_path=' + schema}).render_as_string(hide_password=False)
    original = transfer_legacy.command.upgrade
    def fail(config, revision):
        original(config, revision)
        if revision == '006': raise RuntimeError('Synthetic post-migration failure')
    monkeypatch.setattr(transfer_legacy.command, 'upgrade', fail)
    with pytest.raises(RuntimeError, match='Synthetic'):
        transfer(source, url, apply=True, stopped=True)
    with pg.connect() as c: assert inspect(c).get_table_names() == []
    monkeypatch.setattr(transfer_legacy.command, 'upgrade', original)
    assert transfer(source, url, apply=True, stopped=True)['applied']
    assert snapshot(pg) == expected


def test_over_bound_state_refuses_before_006_ddl(tmp_path):
    source, _ = old_state(tmp_path)
    engine = create_engine('sqlite:///' + str(source))
    with engine.begin() as c:
        c.execute(State.__table__.insert().values(key='x' * 256, value={'historical': True}))
    upgrade(engine, '005')
    with pytest.raises(ValueError, match='column width'): upgrade(engine)
    with engine.connect() as c:
        assert c.scalar(text('SELECT version_num FROM alembic_version')) == '005'
        assert inspect(c).get_columns('state')[0]['type'].length == 100
    engine.dispose()


def test_unrecognized_state_schema_is_not_silently_coerced():
    from app.migration_v6 import widen_state_key
    engine = create_engine('sqlite://')
    with engine.begin() as c:
        c.execute(text('CREATE TABLE state (key VARCHAR(200) PRIMARY KEY, value JSON NOT NULL)'))
        with pytest.raises(ValueError, match='Unrecognized'): widen_state_key(c)
        assert inspect(c).get_columns('state')[0]['type'].length == 200
    engine.dispose()


def test_preflight_cli_never_requires_or_connects_to_a_target(tmp_path):
    source, _ = old_state(tmp_path)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    env = {**os.environ, 'PYTHONPATH': '.', 'FIELDWORK_TRANSFER_DATABASE_URL': 'deliberately-invalid'}
    script = Path(__file__).resolve().parents[1] / 'scripts/transfer_legacy.py'
    args = [sys.executable, str(script), '--source-backup', str(source), '--preflight-only']
    result = subprocess.run(args, env=env, text=True, capture_output=True, timeout=15)
    assert result.returncode == 0 and '"safely_migratable": true' in result.stdout
    assert LEGACY_TEST_KEY not in result.stdout and 'original-self-test' not in result.stdout
    invalid = subprocess.run([*args, '--apply'], env=env, text=True, capture_output=True, timeout=15)
    assert invalid.returncode != 0
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
