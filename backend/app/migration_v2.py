"""Frozen additive schema 002. Do not import current ORM models here."""
import sqlalchemy as sa
metadata=sa.MetaData()
# Only the FK stubs are reflected at migration time; no existing tables changed.

def define(existing):
    m=sa.MetaData()
    for name in ('outreach','jobs'):
        sa.Table(name,m,sa.Column('id',sa.String(36),primary_key=True))
    sa.Table('operations',m,
        sa.Column('id',sa.String(36),primary_key=True),sa.Column('idempotency_key',sa.String(255),nullable=False,unique=True),
        sa.Column('kind',sa.String(60),nullable=False,index=True),sa.Column('entity_id',sa.String(100),nullable=False),
        sa.Column('outreach_id',sa.String(36),sa.ForeignKey('outreach.id'),index=True),sa.Column('job_id',sa.String(36),sa.ForeignKey('jobs.id')),
        sa.Column('provider',sa.String(40),nullable=False),sa.Column('status',sa.String(20),nullable=False,index=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint("status in ('pending','running','succeeded','failed','unknown','blocked','skipped')",name='operation_status'))
    sa.Table('action_attempts',m,
        sa.Column('id',sa.String(36),primary_key=True),sa.Column('operation_id',sa.String(36),sa.ForeignKey('operations.id'),nullable=False,index=True),
        sa.Column('number',sa.Integer,nullable=False),sa.Column('retry_of',sa.String(36),sa.ForeignKey('action_attempts.id')),
        sa.Column('status',sa.String(20),nullable=False,index=True),sa.Column('authorized',sa.Boolean,nullable=False),sa.Column('network_units',sa.Integer,nullable=False),
        sa.Column('policy',sa.JSON,nullable=False),sa.Column('reason',sa.String(160),nullable=False),sa.Column('receipt',sa.JSON,nullable=False),
        sa.Column('started_at',sa.DateTime(timezone=True),nullable=False,index=True),sa.Column('finished_at',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('operation_id','number'),sa.CheckConstraint("status in ('running','succeeded','failed','unknown','blocked','skipped')",name='attempt_status'))
    sa.Table('domain_transitions',m,sa.Column('id',sa.String(36),primary_key=True),sa.Column('domain',sa.String(40),nullable=False),
        sa.Column('entity_id',sa.String(100),nullable=False,index=True),sa.Column('from_state',sa.String(40),nullable=False),
        sa.Column('to_state',sa.String(40),nullable=False),sa.Column('reason',sa.String(120),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    sa.Table('execution_lock',m,sa.Column('id',sa.Integer,primary_key=True),sa.Column('version',sa.Integer,nullable=False))
    return m


def upgrade(connection):
    from datetime import datetime,timezone
    from uuid import uuid5,NAMESPACE_URL
    import json
    m=define(connection)
    tables=[m.tables[n] for n in ('operations','action_attempts','domain_transitions','execution_lock')]
    m.create_all(connection,tables=tables)
    connection.execute(m.tables['execution_lock'].insert().values(id=1,version=0))
    old=sa.MetaData()
    outreach=sa.Table('outreach',old,autoload_with=connection)
    state=sa.Table('state',old,autoload_with=connection)
    imported_at=datetime.now(timezone.utc)
    def add(key,kind,entity,status,stamp,units,receipt,outreach_id=None):
        oid=str(uuid5(NAMESPACE_URL,'fieldwork:'+key));aid=str(uuid5(NAMESPACE_URL,oid+':legacy'))
        connection.execute(m.tables['operations'].insert().values(id=oid,idempotency_key=key,kind=kind,entity_id=entity,outreach_id=outreach_id,job_id=None,provider='legacy',status=status,created_at=stamp or imported_at))
        connection.execute(m.tables['action_attempts'].insert().values(id=aid,operation_id=oid,number=1,retry_of=None,status=status,authorized=False,network_units=units,
            policy={'version':'legacy-import','authorization':'not_reconstructed','timestamp_source':'original' if stamp else 'import_time','aggregate_attempt_count':units},reason='legacy_evidence_import',receipt=receipt,started_at=stamp or imported_at,finished_at=stamp if status=='succeeded' else None))
    for row in connection.execute(sa.select(outreach)).mappings():
        if not row['attempts'] and row['status'] not in ('sent','sending','unknown','failed'):continue
        status={'sent':'succeeded','failed':'failed'}.get(row['status'],'unknown')
        receipt={'provider_id':row['provider_id'],'thread_id':row['thread_id'],'message_id':row['message_id'],'legacy_status':row['status'],'sent_verified':None,'source':'outreach'}
        add('send:'+row['id'],'company_send',row['id'],status,row['sent_at'],row['attempts'],receipt,row['id'])
    for key,value in connection.execute(sa.select(state.c.key,state.c.value)):
        if not key.startswith('self-test:'):continue
        data=json.loads(value) if isinstance(value,str) else value
        stamp=datetime.fromisoformat(data['at']) if data.get('at') else None
        status='succeeded' if data.get('status')=='sent' else 'unknown'
        receipt={k:data[k] for k in ('gmail_id','thread_id','at') if k in data}
        receipt.update(source='state:'+key,legacy_status=data.get('status'),sent_verified=None)
        add(key,'self_test',key.split(':')[1],status,stamp,1,receipt)
    # Existing policy JSON (including pause), credentials and all receipts are untouched.
