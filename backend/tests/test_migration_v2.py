"""Only disposable SQLite databases; no personal credentials or runtime data."""
import json
from datetime import datetime,timezone
from sqlalchemy import create_engine,MetaData,Table,select,inspect
from app.migration_v1 import metadata as v1
from app.migration_v2 import upgrade


def test_additive_migration_preserves_pause_receipts_profile_and_attempts(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'migration.sqlite'))
    stamp=datetime(2026,9,29,16,0,tzinfo=timezone.utc)
    with engine.begin() as c:
        v1.create_all(c)
        c.execute(v1.tables['profiles'].insert().values(id=1,data={'name':'Private student','verified':True},updated_at=stamp))
        c.execute(v1.tables['companies'].insert().values(id='c',domain='example.com',name='Example',website='https://example.com',industry='software',description='',source='official',research={},score=0,score_factors={},stage='contacted',demo=False,created_at=stamp))
        c.execute(v1.tables['contacts'].insert().values(id='ct',company_id='c',email='public@example.com',name='',title='',source='https://example.com/contact',validation='valid',validated_at=stamp))
        for id,sequence,status,attempts,provider_id in [('initial',0,'sent',1,'provider-1'),('uncertain',1,'unknown',1,'')]:
            c.execute(v1.tables['outreach'].insert().values(id=id,company_id='c',contact_id='ct',sequence=sequence,subject='Private subject',body='Private message',evidence_ids=[],review={},strategy='project-match',status=status,due_at=stamp,sent_at=stamp,provider_id=provider_id,thread_id='thread-1',message_id='<'+id+'>',attempts=attempts,created_at=stamp))
        values={'outreach_policy':{'enabled':False,'max_followups_per_company':1},'manual_batch':{'enabled':False,'outreach_ids':['initial']},'response_sync':{'status':'ok'},'self-test:packet:hash':{'status':'sent','at':stamp.isoformat(),'gmail_id':'self-provider','thread_id':'self-thread'}}
        for key,value in values.items():c.execute(v1.tables['state'].insert().values(key=key,value=value))
        c.execute(v1.tables['suppressions'].insert().values(email='stop@example.com',reason='opt_out',created_at=stamp))
        before={name:[dict(r) for r in c.execute(select(table)).mappings()] for name,table in v1.tables.items()}
        upgrade(c)
        after={name:[dict(r) for r in c.execute(select(table)).mappings()] for name,table in v1.tables.items()}
        assert before==after  # All legacy table contents, not just row counts.
        m=MetaData();ops=Table('operations',m,autoload_with=c);attempts=Table('action_attempts',m,autoload_with=c)
        rows=list(c.execute(select(ops)).mappings());records=list(c.execute(select(attempts)).mappings())
        assert len(rows)==3 and len(records)==3
        assert {r['idempotency_key']:r['status'] for r in rows}=={'send:initial':'succeeded','send:uncertain':'unknown','self-test:packet:hash':'succeeded'}
        sent=next(a for a in records if a['receipt'].get('provider_id')=='provider-1')
        assert sent['receipt']['message_id']=='<initial>' and sent['receipt']['thread_id']=='thread-1'
        assert sent['receipt']['sent_verified'] is None and sent['authorized'] is False
        assert sent['started_at'].replace(tzinfo=timezone.utc)==stamp
        assert 'Private' not in json.dumps(records,default=str)
    engine.dispose()


def test_migration_schema_matches_current_model(tmp_path):
    from app.db import Base
    from app import models
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    engine=create_engine('sqlite:///'+str(tmp_path/'schema.sqlite'))
    with engine.begin() as c:
        v1.create_all(c);upgrade(c)
        expected=MetaData()
        for name,table in Base.metadata.tables.items():
            if name not in {'operator_sessions','integrations','oauth_grants','rate_buckets'}:table.to_metadata(expected)
        assert compare_metadata(MigrationContext.configure(c),expected)==[]
    engine.dispose()
