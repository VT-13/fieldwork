"""Explicit stopped-sender schema001 SQLite backup -> EMPTY PostgreSQL staging DB.

Defaults to validation only. No credential guessing, receipt matching, deployment,
worker startup or source mutation. Other source revisions fail closed.
"""
import argparse
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from app.migration_v1 import metadata
from app.migration_v6 import STATE_KEY_LIMIT, widen_state_key


def upgrade(engine, revision):
    config=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
    config.set_main_option('script_location',str(Path(__file__).resolve().parents[1]/'alembic'))
    with engine.begin() as connection:
        config.attributes['connection']=connection
        command.upgrade(config,revision)


def normalized(row):
    return {k:(v.replace(tzinfo=timezone.utc) if isinstance(v,datetime) and v.tzinfo is None else v) for k,v in row.items()}


def snapshot(engine):
    with engine.connect() as connection:
        return {table.name:sorted([normalized(dict(r)) for r in connection.execute(select(table)).mappings()],key=repr) for table in metadata.sorted_tables}


def read_legacy(source):
    """Read-only, consistent schema001 snapshot; no private rows in diagnostics."""
    source=Path(source)
    if not source.is_file() or source.is_symlink():raise ValueError('Explicit regular SQLite backup required')
    source=source.resolve()
    original=hashlib.sha256(source.read_bytes()).hexdigest()
    old=create_engine('sqlite://',creator=lambda:sqlite3.connect(source.as_uri()+'?mode=ro',uri=True))
    try:
        with old.connect() as connection:
            connection.exec_driver_sql('PRAGMA query_only=ON')
            connection.exec_driver_sql('BEGIN')
            observed=inspect(connection)
            if set(observed.get_table_names()) != set(metadata.tables)|{'alembic_version'}:raise ValueError('Unrecognized legacy tables; do not guess a mapping')
            if connection.scalar(text('SELECT version_num FROM alembic_version'))!='001':raise ValueError('Only representative schema001 backups are supported')
            if any({x['name'] for x in observed.get_columns(name)}!=set(table.c.keys()) for name,table in metadata.tables.items()):raise ValueError('Legacy columns differ; reconcile explicitly')
            rows={table.name:sorted([normalized(dict(r)) for r in connection.execute(select(table)).mappings()],key=repr) for table in metadata.sorted_tables}
        # SQLite does not enforce varchar widths. Never truncate historical
        # identifiers to force an incompatible PostgreSQL transfer to pass.
        from sqlalchemy import String
        for table in metadata.sorted_tables:
            for column in table.c:
                limit=STATE_KEY_LIMIT if table.name=='state' and column.name=='key' else getattr(column.type,'length',None)
                if isinstance(column.type,String) and limit and any(isinstance(row.get(column.name),str) and len(row[column.name])>limit for row in rows[table.name]):
                    raise ValueError('Legacy value exceeds PostgreSQL column width; source requires explicit reconciliation')
        policies={r['key']:r['value'] for r in rows['state']}
        if policies.get('outreach_policy',{}).get('enabled',True) or policies.get('manual_batch',{}).get('enabled',False) or policies.get('automation',{}).get('enabled',False):raise ValueError('Source must have all communication paused')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=original:raise ValueError('Source changed during read-only preflight')
        return rows,original
    finally:
        old.dispose()


def preflight(source):
    """Count-only source compatibility. Never creates or connects to a target."""
    rows,digest=read_legacy(source)
    return {'source_revision':'001','target_revision':'006',
            'counts':{n:len(v) for n,v in rows.items()},'source_sha256':digest,
            'state_keys_requiring_widening':sum(len(r['key'])>100 for r in rows['state']),
            'state_key_limit':STATE_KEY_LIMIT,'safely_migratable':True,'applied':False}


def transfer(source, target_url, *, apply=False, stopped=False):
    rows,original=read_legacy(source)
    target=create_engine(target_url)
    try:
        if target.dialect.name!='postgresql':raise ValueError('Target must be an empty PostgreSQL database')
        with target.connect() as connection:
            if inspect(connection).get_table_names():raise ValueError('Target is not empty; never overlay existing records')
        result={'source_revision':'001','target_revision':'006','counts':{n:len(v) for n,v in rows.items()},'source_sha256':original,'applied':False}
        if apply:
            if not stopped:raise ValueError('Stopped senders must be explicitly confirmed')
            # One transaction creates, copies and migrates. Failure leaves target empty.
            config=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
            config.set_main_option('script_location',str(Path(__file__).resolve().parents[1]/'alembic'))
            with target.begin() as connection:
                config.attributes['connection']=connection
                command.upgrade(config,'001')
                # Apply only versioned006's widening before copy; do not stamp
                # past002, whose ledger backfill must see original State rows.
                widen_state_key(connection)
                for table in metadata.sorted_tables:
                    if rows[table.name]:connection.execute(table.insert(),rows[table.name])
                command.upgrade(config,'006')
                for table in metadata.sorted_tables:
                    actual=sorted([normalized(dict(r)) for r in connection.execute(select(table)).mappings()],key=repr)
                    if actual!=rows[table.name]:raise ValueError('Legacy preservation mismatch; transaction rolled back')
                if hashlib.sha256(Path(source).read_bytes()).hexdigest()!=original:raise ValueError('Backup changed during transfer')
            result['applied']=True
        return result
    finally:
        target.dispose()


if __name__=='__main__':
    import json,os
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-backup',required=True,type=Path)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--preflight-only',action='store_true',help='Read-only source check; no target connection or writes')
    parser.add_argument('--confirm-senders-stopped',action='store_true')
    args=parser.parse_args()
    if args.preflight_only:
        if args.apply or args.confirm_senders_stopped:parser.error('Read-only preflight cannot apply or confirm a transfer')
        try:print(json.dumps(preflight(args.source_backup),indent=2))
        except Exception:raise SystemExit('Read-only preflight failed safely; reconcile source schema, widths and pause. No private contents logged.') from None
        raise SystemExit(0)
    url=os.environ.get('FIELDWORK_TRANSFER_DATABASE_URL','')
    if not url:raise SystemExit('Explicit FIELDWORK_TRANSFER_DATABASE_URL required')
    try:print(json.dumps(transfer(args.source_backup,url,apply=args.apply,stopped=args.confirm_senders_stopped),indent=2))
    except Exception:raise SystemExit('Transfer failed safely; validate source schema, pause, stopped senders and empty target. No credentials or record contents logged.') from None
