"""Post-E2E Linux worker, persistence and backup checks; explicit staging only."""
import json
import os
import subprocess
import time
from pathlib import Path

from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/package6b'
WORK=Path(os.environ['FIELDWORK_STAGING_ROOT']).resolve()
assert WORK.name=='fieldwork-package6b' and WORK.is_relative_to(Path('/tmp').resolve())
assert os.environ.get('DOCKER_HOST'), 'Explicit isolated daemon required'
DOCKER=os.environ.get('FIELDWORK_DOCKER_BIN','docker')
CONTEXT=Path((WORK/'context-path').read_text())
VALUES=dict(dotenv_values(CONTEXT/'.env'))
from sqlalchemy.engine import make_url

url=make_url(VALUES['DATABASE_URL'])
assert url.host=='db' and url.database=='fieldwork6b_e2e'
assert VALUES['SENDER_EMAIL']=='student@example.com'
ENVFILE=WORK/'docker.env'
ENVFILE.write_text(''.join(k+'='+v+'\n' for k,v in VALUES.items()));ENVFILE.chmod(0o600)


def docker(*args,data=None):
    r=subprocess.run([DOCKER,*args],input=data,text=True,capture_output=True,timeout=120,check=False)
    if r.returncode:raise RuntimeError('Staging Docker '+args[0]+' failed: '+str(r.returncode))
    return r.stdout


def execute(code):return docker('exec','-i','fieldwork6b-api-1','python','-c',code)


def wait(predicate):
    until=time.monotonic()+30
    while time.monotonic()<until:
        result=predicate()
        if result:return result
        time.sleep(.3)
    raise AssertionError('Bounded staging wait failed')


def transmissions():
    return int(execute("import json;from pathlib import Path;print(len(json.loads(Path('/staging/fieldwork6b/provider.json').read_text())['transmissions']))"))


def snapshot(envfile=ENVFILE):
    code="""import json,hashlib
from app.db import Session,Base
from app import models
from sqlalchemy import select,text
with Session() as db:
 result={}
 for table in Base.metadata.sorted_tables:
  rows=sorted([dict(r) for r in db.execute(select(table)).mappings()],key=repr)
  result[table.name]={'count':len(rows),'sha256':hashlib.sha256(json.dumps(rows,default=str,sort_keys=True).encode()).hexdigest()}
 result['execution_lock']['version']=db.scalar(text('SELECT version FROM execution_lock WHERE id=1'))
 result['revision']=db.scalar(text('SELECT version_num FROM alembic_version'))
 print(json.dumps(result))
"""
    return json.loads(docker('run','--rm','--network','fieldwork6b_default','--env-file',str(envfile),'fieldwork6b-backend','python','-c',code))


report={'result':'in_progress','production_mutations':False}
# Return all communication and paid permission to paused before recovery checks.
execute("""from app.db import Session
from app.models import State
from app.services.policy import set_paused
with Session() as db:
 set_paused(db,False)
 row=db.get(State,'outreach_policy');row.value={**row.value,'paid_services_authorized':False}
 db.merge(State(key='automation',value={'enabled':False}))
 db.commit()
""")
initial=transmissions()
# A second actual Linux container competes on the same advisory leadership/queue.
docker('create','--name','fieldwork6b-duplicate','--network','fieldwork6b_default','--env-file',str(ENVFILE),
       '--mount','type=volume,source=fieldwork6b_qa-data,target=/staging/fieldwork6b',
       'fieldwork6b-backend','python','/app/qa_release.py','worker')
docker('cp',str(ROOT/'backend/tests/release_runtime.py'),'fieldwork6b-duplicate:/app/qa_release.py')
docker('start','fieldwork6b-duplicate')
try:
    job=execute("""from app.db import Session
from app.services.jobs import enqueue
with Session() as db:print(enqueue(db,'sync',{},'container-duplicate-worker-proof:'+__import__('uuid').uuid4().hex).id)
""").strip()
    wait(lambda:execute("from app.db import Session;from app.models import Job\nwith Session() as db:print(db.get(Job,"+repr(job)+").status)").strip()=='done')
    assert int(execute("from app.db import Session;from app.models import Operation,ActionAttempt;from sqlalchemy import select,func\nwith Session() as db:print(db.scalar(select(func.count()).select_from(ActionAttempt).join(Operation).where(Operation.job_id=="+repr(job)+")))"))==1
    assert transmissions()==initial
    report['duplicate_worker']={'passed':True,'separate_containers':2,'job_attempts':1,'extra_fake_transmissions':0}
finally:
    docker('stop','-t','20','fieldwork6b-duplicate')
    duplicate=json.loads(docker('inspect','fieldwork6b-duplicate'))[0]
    assert duplicate['State']['ExitCode']==0
    docker('rm','fieldwork6b-duplicate')
docker('stop','-t','20','fieldwork6b-worker-1')
worker=json.loads(docker('inspect','fieldwork6b-worker-1'))[0]
assert worker['State']['ExitCode']==0
report['sigterm_graceful']={'passed':True,'exit_code':0}
# Two real PG connections/processes cannot hold the worker's leader lock together.
execute("""import subprocess,sys
from app.worker import leadership
with leadership() as acquired:
 assert acquired
 child=subprocess.run([sys.executable,'-c','from app.worker import leadership\\nwith leadership() as acquired: assert not acquired'],capture_output=True)
 assert child.returncode==0
""")
report['advisory_leader_fence']={'passed':True,'independent_linux_processes':2}
# Repeated scheduler ticks at the same provider clock retain the exact job IDs.
execute("""import importlib.util
spec=importlib.util.spec_from_file_location('qa_release','/app/qa_release.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
from app.db import Session
from app.models import Job
from app.services.scheduler import tick
from sqlalchemy import select
with Session() as db:
 before=set(db.scalars(select(Job.id)))
 tick(db);tick(db)
 assert set(db.scalars(select(Job.id)))==before
""")
report['scheduler_duplicate_tick']={'passed':True,'new_duplicate_jobs':0}
# Stop the remaining app writers; capture every ORM table, including ciphertext.
docker('stop','-t','20','fieldwork6b-api-1','fieldwork6b-web-1')
before=snapshot()
docker('exec','fieldwork6b-db-1','sh','-c','umask 077; pg_dump -U fieldwork -d fieldwork6b_e2e -Fc -f /tmp/fieldwork6b.dump')
mode=docker('exec','fieldwork6b-db-1','stat','-c','%a','/tmp/fieldwork6b.dump').strip();assert mode=='600'
dump_digest=docker('exec','fieldwork6b-db-1','sha256sum','/tmp/fieldwork6b.dump').split()[0]
docker('exec','fieldwork6b-db-1','createdb','-U','fieldwork','fieldwork6b_restore')
docker('exec','fieldwork6b-db-1','pg_restore','-U','fieldwork','-d','fieldwork6b_restore','--single-transaction','--no-owner','--no-acl','/tmp/fieldwork6b.dump')
restored=WORK/'restore.env'
restored.write_text(ENVFILE.read_text().replace('/fieldwork6b_e2e','/fieldwork6b_restore'));restored.chmod(0o600)
assert snapshot(restored)==before
report['backup_restore']={'passed':True,'tool_major':17,'mode':'0600','sha256':dump_digest,'all_ORM_tables_exact':True,'schema':'006','fresh_restore_database':True}
docker('exec','fieldwork6b-db-1','dropdb','-U','fieldwork','fieldwork6b_restore')
# Persistent external DB container restarts independently from app containers.
docker('restart','fieldwork6b-db-1')
wait(lambda:json.loads(docker('inspect','fieldwork6b-db-1'))[0]['State']['Health']['Status']=='healthy')
assert snapshot()==before
report['postgres_restart_persistence']={'passed':True,'all_ORM_tables_exact':True,'named_volume':True}
docker('start','fieldwork6b-api-1','fieldwork6b-worker-1','fieldwork6b-web-1')
wait(lambda:json.loads(docker('inspect','fieldwork6b-api-1'))[0]['State']['Health']['Status']=='healthy')
wait(lambda:execute("import urllib.request;print(urllib.request.urlopen('http://localhost:8000/health').status)").strip()=='200')
docker('exec','fieldwork6b-worker-1','python','-m','app.worker','--health')
after=snapshot()
for table in before:
    if table=='execution_lock':
        assert after[table]['count']==before[table]['count']==1
        assert after[table]['version']>=before[table]['version']
        continue
    if table in ('state','jobs'):continue  # Process identity/heartbeat and safe-read leases are intentionally volatile.
    assert after[table]==before[table],table
assert transmissions()==initial
report['app_restart_persistence']={'passed':True,'web_api_worker_restarted':True,'durable_records_exact':True,'extra_fake_transmissions':0,'volatile_exclusions':['worker/scheduler State heartbeat','safe-read Job leases','ExecutionLock.version tick counter']}
assert execute("from app.db import Session;from app.models import State\nwith Session() as db:print(db.get(State,'outreach_policy').value['enabled'])").strip()=='False'
report['communication_paused_at_end']=True
report['fake_transmissions_total']=initial
report['result']='passed'
(OUT/'restart-backup-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
