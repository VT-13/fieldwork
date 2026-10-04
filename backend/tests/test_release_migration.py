"""Sanitized installed-schema shape, cross-engine transfer and PG17 restore."""
import hashlib
import json
import os
import subprocess
from pathlib import Path
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, select, text
from app.migration_v1 import metadata, now
from app.models import Integration, ActionAttempt
from scripts.backup_database import backup, restore_postgres, postgres_env
from scripts.transfer_legacy import transfer, snapshot
from test_postgres_security import pg as pg


def old_state(tmp_path):
    source=tmp_path/'old.sqlite'
    engine=create_engine('sqlite:///'+str(source))
    metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text('CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY)'))
        c.execute(text("INSERT INTO alembic_version VALUES ('001')"))
        for key,value in [('outreach_policy',{'enabled':False,'allowed_cities':['Rocklin'],'paid_services_authorized':False}),('automation',{'enabled':False}),('manual_batch',{'enabled':False,'stop_requested':True})]:
            c.execute(metadata.tables['state'].insert().values(key=key,value=value))
        c.execute(metadata.tables['profiles'].insert().values(id=1,data={'name':'Sanitized Student','verified':False}))
        c.execute(metadata.tables['companies'].insert().values(id='old-company',domain='example.com',name='Sanitized Robotics',website='https://example.com'))
        c.execute(metadata.tables['contacts'].insert().values(id='old-contact',company_id='old-company',email='lead@example.com'))
        c.execute(metadata.tables['outreach'].insert().values(id='old-confirmed',company_id='old-company',contact_id='old-contact',status='sent',sequence=0,attempts=1,sent_at=now(),provider_id='original-provider',thread_id='original-thread',message_id='<original@example.com>'))
        c.execute(metadata.tables['outreach'].insert().values(id='old-uncertain',company_id='old-company',contact_id='old-contact',status='unknown',sequence=1,attempts=1,sent_at=now(),message_id='<uncertain@example.com>'))
        c.execute(metadata.tables['events'].insert().values(id='old-event',company_id='old-company',kind='auto_reply',source_id='original-ack',detail='Sanitized acknowledgment'))
        c.execute(metadata.tables['suppressions'].insert().values(email='bounced@example.org',reason='bounce'))
        c.execute(metadata.tables['jobs'].insert().values(id='old-job',kind='sync',dedupe_key='old-sync',status='queued'))
    expected=snapshot(engine);engine.dispose()
    saved=tmp_path/'old-backup.sqlite'
    backup('sqlite:///'+str(source),saved)
    assert saved.stat().st_mode&0o777==0o600
    return saved,expected


def test_representative_sqlite001_transfer_backup_restore_and_immutable_history(pg,tmp_path):
    source,expected=old_state(tmp_path)
    target=pg.url
    with pg.connect() as c:schema=c.scalar(text('SELECT current_schema()'))
    target=target.update_query_dict({'options':'-csearch_path='+schema})
    url=target.render_as_string(hide_password=False)
    dry=transfer(source,url)
    assert not dry['applied']
    with pg.connect() as c:assert not c.scalar(text("SELECT to_regclass('outreach')"))
    with pytest.raises(ValueError,match='Stopped'):transfer(source,url,apply=True)
    result=transfer(source,url,apply=True,stopped=True)
    assert result['applied'] and snapshot(pg)==expected
    with pytest.raises(ValueError,match='not empty'):transfer(source,url,apply=True,stopped=True)
    with pg.begin() as c:
        assert c.scalar(text('SELECT version_num FROM alembic_version'))=='005'
        receipts=list(c.execute(select(ActionAttempt.receipt)).scalars())
        assert any(r.get('provider_id')=='original-provider' for r in receipts)
        assert c.scalar(text("SELECT count(*) FROM operations WHERE status='unknown'"))==1
        c.execute(Integration.__table__.insert().values(id='gmail',email='student@example.com',status='disconnected',encrypted_tokens='synthetic-encrypted-reference',scopes=['fake.scope'],generation=3))
    tools=os.environ.get('FIELDWORK_TEST_PG_TOOLS')
    if not tools:pytest.skip('PG17 backup tools unavailable; migration transfer passed, restore not verified')
    dump=tmp_path/'pg17.dump'
    digest=backup(url,dump,tools)
    assert dump.stat().st_mode&0o777==0o600 and digest==hashlib.sha256(dump.read_bytes()).hexdigest()
    with pg.begin() as c:c.execute(text("UPDATE state SET value='{}' WHERE key='outreach_policy'"))
    restore_name='module6_restore_'+uuid4().hex
    base=create_engine(os.environ['TEST_POSTGRES_URL'],isolation_level='AUTOCOMMIT')
    with base.connect() as c:c.execute(text('CREATE DATABASE '+restore_name))
    restored=target.set(database=restore_name).render_as_string(hide_password=False)
    try:
        restore_postgres(restored,dump,tools,confirmed=True)
        restored_engine=create_engine(restored)
        assert snapshot(restored_engine)==expected
        with restored_engine.connect() as c:
            assert c.scalar(select(Integration.generation))==3
            assert c.scalar(select(Integration.encrypted_tokens))=='synthetic-encrypted-reference'
            assert c.scalar(text("SELECT count(*) FROM operations WHERE status='unknown'"))==1
            assert c.scalar(text("SELECT count(*) FROM jobs WHERE id='old-job'"))==1
        restored_engine.dispose()
        report={'result':'passed','source_revision':'001','target_revision':'005','transport':'typed frozen-schema SQLite -> PG17 transaction','old_record_counts':result['counts'],'old_backup_private':True,'pg17_backup_private':True,'restore_old_records_equal':True,'integration_metadata_restored':True,'unknown_preserved':True,'repeat_refused':True,'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==result['source_sha256']}
        if os.environ.get('FIELDWORK_RELEASE_MIGRATION_REPORT'):
            Path(os.environ['FIELDWORK_RELEASE_MIGRATION_REPORT']).write_text(json.dumps(report,indent=2)+'\n')
    finally:
        with base.connect() as c:c.execute(text('DROP DATABASE '+restore_name))
        base.dispose()


def test_transfer_refuses_oversized_legacy_identifier_without_truncation(pg,tmp_path):
    source,_=old_state(tmp_path)
    engine=create_engine('sqlite:///'+str(source))
    with engine.begin() as c:c.execute(metadata.tables['state'].insert().values(key='historical-self-test:'+('x'*100),value={'status':'sent'}))
    engine.dispose()
    with pg.connect() as c:schema=c.scalar(text('SELECT current_schema()'))
    url=pg.url.update_query_dict({'options':'-csearch_path='+schema}).render_as_string(hide_password=False)
    with pytest.raises(ValueError,match='column width'):transfer(source,url,apply=True,stopped=True)
    with pg.connect() as c:assert not c.scalar(text("SELECT to_regclass('outreach')"))
