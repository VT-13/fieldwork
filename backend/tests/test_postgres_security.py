"""Real PostgreSQL migrations and row-lock claims, isolated by disposable schemas."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4
from pathlib import Path
import pytest
from sqlalchemy import create_engine,text,select,MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from alembic.config import Config
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from app.models import State,Job,Operation,ActionAttempt,DomainTransition,Profile,Company,Contact,Outreach,now
from app.db import Base
from app.core import Blocked
from app.services import ledger,policy
pytestmark=pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'),reason='No disposable PostgreSQL test URL')

@pytest.fixture
def pg():
    base=create_engine(os.environ['TEST_POSTGRES_URL']);schema='security_'+uuid4().hex
    with base.begin() as c:c.execute(text('CREATE SCHEMA '+schema))
    engine=create_engine(os.environ['TEST_POSTGRES_URL'],connect_args={'options':'-csearch_path='+schema},pool_size=5)
    yield engine
    engine.dispose()
    with base.begin() as c:c.execute(text('DROP SCHEMA '+schema+' CASCADE'))
    base.dispose()


def upgrade(engine,target='head'):
    config=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
    config.set_main_option('script_location',str(Path(__file__).resolve().parents[1]/'alembic'))
    with engine.connect() as c:
        config.attributes['connection']=c;command.upgrade(config,target);c.commit()


def test_fresh_migrations_indices_constraints_and_schema(pg):
    upgrade(pg)
    with pg.connect() as c:assert compare_metadata(MigrationContext.configure(c),Base.metadata)==[]
    Session=sessionmaker(pg,expire_on_commit=False)
    with Session() as db:
        assert db.scalar(text('select version_num from alembic_version'))=='006'
        db.add(Job(kind='research',payload={'id':'company'},dedupe_key='durable',status='queued'));db.commit()
        db.add(Contact(company_id='does-not-exist',email='test@example.com'))
        with pytest.raises(IntegrityError):db.commit()
        db.rollback()
        db.add(Operation(idempotency_key='same',kind='test',status='pending'));db.commit()
        db.add(Operation(idempotency_key='same',kind='test',status='pending'))
        with pytest.raises(IntegrityError):db.commit()
        db.rollback()
    with Session() as db:assert db.scalar(select(Job)).payload=={'id':'company'}


def test_forward_migration_preserves_pause_receipts_and_all_legacy_rows(pg):
    upgrade(pg,'001')
    from app.migration_v1 import metadata
    with pg.begin() as c:
        c.execute(metadata.tables['profiles'].insert().values(id=1,data={'name':'Test','resume':'private'},updated_at=now()))
        c.execute(metadata.tables['state'].insert().values(key='outreach_policy',value={'enabled':False,'max_followups_per_company':1}))
        c.execute(metadata.tables['companies'].insert().values(id='c',domain='example.com',name='Test',website='https://example.com'))
        c.execute(metadata.tables['contacts'].insert().values(id='ct',company_id='c',email='executive@example.com'))
        c.execute(metadata.tables['outreach'].insert().values(id='o',company_id='c',contact_id='ct',status='sent',attempts=1,sent_at=now(),provider_id='provider-original',thread_id='thread-original',message_id='<original>'))
        before={name:[dict(r) for r in c.execute(select(t)).mappings()] for name,t in metadata.tables.items()}
    upgrade(pg)
    with pg.connect() as c:
        after={name:[dict(r) for r in c.execute(select(t)).mappings()] for name,t in metadata.tables.items()}
        assert before==after
        receipt=c.execute(select(ActionAttempt.receipt)).scalar_one();assert receipt['provider_id']=='provider-original' and receipt['message_id']=='<original>'
        assert not c.execute(select(State.value).where(State.key=='outreach_policy')).scalar_one()['enabled']


def test_two_connections_same_send_only_one_reservation(pg):
    upgrade(pg);Session=sessionmaker(pg,expire_on_commit=False);barrier=Barrier(2)
    with Session() as db:
        db.add(State(key='outreach_policy',value={'enabled':True}))
        db.add(Company(id='claim-company',name='Test',domain='claim.example.com',website='https://claim.example.com'));db.flush()
        db.add(Contact(id='claim-contact',company_id='claim-company',email='test@claim.example.com'));db.flush()
        db.add(Outreach(id='claim-message',company_id='claim-company',contact_id='claim-contact',status='approved'));db.commit()
    def run():
        with Session() as db:
            barrier.wait()
            try:
                def reserve(attempt):
                    from app.domain.states import transition
                    message=db.get(Outreach,'claim-message')
                    transition(db,message,'sending',reason='postgres_concurrent_reservation')
                    message.attempts+=1;message.sent_at=attempt.started_at
                a,replay=ledger.claim(db,'send:one','company_send','fake',lambda:{'version':1},entity_id='one',outreach_id='claim-message',reserve=reserve)
                return 'won' if not replay else 'replay'
            except Blocked:return 'blocked'
    with ThreadPoolExecutor(2) as pool:result=list(pool.map(lambda _:run(),range(2)))
    assert sorted(result)==['blocked','won']
    with Session() as db:
        assert len(list(db.scalars(select(Operation))))==1
        assert len(list(db.scalars(select(ActionAttempt))))==1
        message=db.get(Outreach,'claim-message');assert message.status=='sending' and message.attempts==1


def test_pause_before_and_after_reservation_semantics(pg):
    upgrade(pg);Session=sessionmaker(pg,expire_on_commit=False)
    with Session() as db:db.add(State(key='outreach_policy',value={'enabled':True}));db.commit()
    def auth(db):
        if not db.get(State,'outreach_policy').value['enabled']:raise Blocked('Paused')
        return policy.snapshot(db,'scheduled')
    with Session() as pauser:policy.set_paused(pauser,False)
    with Session() as sender:
        with pytest.raises(Blocked):ledger.claim(sender,'send:before','company_send','fake',lambda:auth(sender),entity_id='before')
    with Session() as pauser:policy.set_paused(pauser,True)
    with Session() as sender:attempt,_=ledger.claim(sender,'send:after','company_send','fake',lambda:auth(sender),entity_id='after')
    with Session() as pauser:policy.set_paused(pauser,False)
    with Session() as sender:
        assert sender.get(ActionAttempt,attempt.id).authorized
        ledger.finish(sender,sender.get(ActionAttempt,attempt.id),'succeeded',receipt={'provider_id':'already-reserved'})
        assert not sender.get(State,'outreach_policy').value['enabled']
        assert len(list(sender.scalars(select(DomainTransition).where(DomainTransition.domain=='campaign'))))==3


def test_concurrent_global_quota_cannot_overreserve(pg):
    upgrade(pg);Session=sessionmaker(pg,expire_on_commit=False);barrier=Barrier(2)
    def run(n):
        with Session() as db:
            barrier.wait()
            def auth():
                if ledger.usage(db,now()-timedelta(days=1))>=1:raise Blocked('Quota')
                return {'cap':1}
            try:ledger.claim(db,'quota:'+str(n),'self_test','fake',auth,entity_id=str(n));return True
            except Blocked:return False
    with ThreadPoolExecutor(2) as pool:assert sum(pool.map(run,range(2)))==1
    with Session() as db:assert ledger.usage(db,now()-timedelta(days=1))==1


def test_backup_restore_retains_pause_jobs_and_receipts(pg,tmp_path):
    from scripts.backup_database import backup,restore_postgres
    tools=os.getenv('FIELDWORK_TEST_PG_TOOLS')
    if not tools:pytest.skip('PostgreSQL dump tools unavailable')
    upgrade(pg)
    with pg.begin() as c:
        c.execute(State.__table__.insert().values(key='outreach_policy',value={'enabled':False}))
        c.execute(Job.__table__.insert().values(id='saved-job',kind='sync',payload={},dedupe_key='restore-job',status='queued',error='',result={},created_at=now()))
        c.execute(Operation.__table__.insert().values(id='saved-operation',idempotency_key='receipt-preserved',kind='self_test',entity_id='personal',provider='fake',status='succeeded',created_at=now()))
        c.execute(ActionAttempt.__table__.insert().values(id='saved-attempt',operation_id='saved-operation',number=1,status='succeeded',authorized=True,network_units=1,policy={},reason='',receipt={'provider_id':'saved-provider-id'},started_at=now(),finished_at=now()))
    # Dump one disposable schema, then restore the entire disposable database to another DB.
    from scripts.backup_database import postgres_env
    import subprocess
    url=os.environ['TEST_POSTGRES_URL'];env=postgres_env(url)
    name='restore_'+uuid4().hex
    dump=tmp_path/'database.dump'
    fd=os.open(dump,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    schema=pg.url.query  # schema is configured on the connection, not embedded in its URL
    with pg.connect() as c:schema=c.scalar(text('select current_schema()'))
    subprocess.run([str(Path(tools)/'pg_dump'),'--format=custom','--schema='+schema,'--no-owner','--no-acl','--file',str(dump)],env=env,check=True,capture_output=True)
    base=create_engine(url)
    with base.connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('CREATE DATABASE '+name))
    restored=url.rsplit('/',1)[0]+'/'+name
    try:
        restore_postgres(restored,dump,tools,confirmed=True)
        e=create_engine(restored)
        with e.connect() as c:
            c.execute(text('SET search_path TO '+schema))
            assert c.execute(select(State.value)).scalar_one()=={'enabled':False}
            assert c.execute(select(Job.id)).scalar_one()=='saved-job'
            assert c.execute(select(ActionAttempt.receipt)).scalar_one()['provider_id']=='saved-provider-id'
        e.dispose()
        # Also exercise the consistent-backup helper directly, not just pg_dump.
        private=tmp_path/'full.dump';assert len(backup(restored,private,tools))==64
        assert private.stat().st_mode&0o777==0o600
    finally:
        with base.connect().execution_options(isolation_level='AUTOCOMMIT') as c:c.execute(text('DROP DATABASE '+name))
        base.dispose()
