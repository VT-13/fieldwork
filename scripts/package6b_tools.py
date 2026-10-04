"""Build/inspect disposable Fieldwork Linux images; no production configuration."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
p=Path(os.environ['FIELDWORK_STAGING_ROOT']).resolve()
assert p.name=='fieldwork-package6b' and p.is_relative_to(Path('/tmp').resolve())
assert os.environ.get('DOCKER_HOST'), 'Explicit isolated Docker daemon required'
p.mkdir(exist_ok=True)
out=ROOT/'docs/package6b';out.mkdir(exist_ok=True)
d=os.environ.get('FIELDWORK_DOCKER_BIN','docker')
env=os.environ.copy()
mode=sys.argv[1] if len(sys.argv)==2 else ''


if mode=='prepare':
    import base64
    import hashlib
    import secrets
    import shutil

    from cryptography.fernet import Fernet
    from module1_check import isolated
    assert not (p/'context-path').exists(), 'Do not overwrite an existing staging run'
    root,_=isolated();shutil.copy2(ROOT/'compose.yaml',root/'compose.yaml')
    (p/'context-path').write_text(str(root))
    salt=secrets.token_bytes(16);password='release-disposable-operator-passphrase'
    hashed='scrypt$'+base64.urlsafe_b64encode(salt).decode()+'$'+base64.urlsafe_b64encode(hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1,dklen=32)).decode()
    dbpassword=secrets.token_hex(24)
    values={'ENVIRONMENT':'production','DATABASE_URL':'postgresql+psycopg://fieldwork:'+dbpassword+'@db:5432/fieldwork6b_e2e','POSTGRES_PASSWORD':dbpassword,'API_KEY':secrets.token_hex(32),'OPERATOR_PASSWORD_HASH':hashed,'CREDENTIAL_KEYS':Fernet.generate_key().decode(),'APP_ORIGIN':'https://localhost:13466','TRUSTED_HOSTS':'["localhost","127.0.0.1","api"]','DATA_DIRECTORY':'/app/data','DRY_RUN':'true','MANUAL_MODE':'true','RESPONSE_POLL_ENABLED':'false','AUTO_APPROVE':'false','WORKER_POLL_SECONDS':'1','OAUTH_REFRESH_TOKEN':'','ALLOW_LEGACY_OAUTH':'false'}
    (root/'.env').write_text(''.join(k+"='"+v+"'\n" for k,v in values.items()));(root/'.env').chmod(0o600)
    (p/'runtime.json').write_text(json.dumps(values));(p/'runtime.json').chmod(0o600)
    (p/'override.yaml').write_text('services:\n  db:\n    environment:\n      POSTGRES_DB: fieldwork6b_e2e\n  migrate:\n    image: fieldwork6b-backend\n  api:\n    image: fieldwork6b-backend\n    ports: !reset []\n  worker:\n    image: fieldwork6b-backend\n  web:\n    image: fieldwork6b-frontend\n    networks: [default, edge]\n    ports: !override ["127.0.0.1:13066:3000"]\nnetworks:\n  default:\n    internal: true\n  edge: {}\n')
    print('Clean context and private synthetic runtime configuration created')
if mode=='build':
    root=Path((p/'context-path').read_text())
    for part in ('backend','frontend'):
        with (out/(part+'-build.log')).open('w') as log:
            r=subprocess.run([d,'build','--no-cache','--progress=plain','-t','fieldwork6b-'+part,str(root/part)],env=env,stdout=log,stderr=subprocess.STDOUT,check=False)
        if r.returncode:raise SystemExit('Clean '+part+' Docker build failed')
if mode=='up':
    root=Path((p/'context-path').read_text())
    args=[d,'compose','--project-name','fieldwork6b','--project-directory',str(root),'--env-file',str(root/'.env'),'-f',str(root/'compose.yaml'),'-f',str(p/'override.yaml'),'--profile','worker','up','-d','--no-build','--wait','--wait-timeout','120']
    with (out/'safe-start.log').open('w') as log:r=subprocess.run(args,env=env,stdout=log,stderr=subprocess.STDOUT,check=False)
    if r.returncode:raise SystemExit('Paused staging startup failed')
if mode=='qa-build':
    import shutil
    root=Path((p/'context-path').read_text())
    shutil.copytree(ROOT/'backend/tests',root/'backend/tests',dirs_exist_ok=True)
    (root/'backend/Dockerfile.qa').write_text('FROM fieldwork6b-backend\nUSER root\nRUN pip install --no-cache-dir pytest==9.1.1 pytest-asyncio==1.4.0\nCOPY tests ./tests\nUSER app\n')
    with (out/'qa-build.log').open('w') as log:r=subprocess.run([d,'build','--progress=plain','-f',str(root/'backend/Dockerfile.qa'),'-t','fieldwork6b-qa',str(root/'backend')],env=env,stdout=log,stderr=subprocess.STDOUT,check=False)
    if r.returncode:raise SystemExit('Disposable test image build failed')
if mode not in {'prepare','build','up','defaults','scan','qa-build','tests'}:
    raise SystemExit('Choose prepare/build/up/defaults/scan/qa-build/tests')

if mode=='defaults':
    import json
    import os
    import subprocess
    from pathlib import Path
    out=ROOT/'docs/package6b'
    env=os.environ.copy();d=os.environ.get('FIELDWORK_DOCKER_BIN','docker')
    def run(*args):return subprocess.check_output([d,*args],env=env,text=True)
    def py(code):return run('exec','fieldwork6b-api-1','python','-c',code)
    r=json.loads(py('''import json,os,platform,importlib.metadata as m,importlib.util as u
    from app.config import settings
    from app.db import Session
    from app.models import State,Job,ActionAttempt,Profile,Integration
    from sqlalchemy import select,func,text
    s=settings()
    with Session() as db:
     print(json.dumps({'os':platform.system(),'python':platform.python_version(),'uid':os.getuid(),'environment':s.environment,'schema':db.scalar(text('SELECT version_num FROM alembic_version')),'dry_run':s.dry_run,'manual_mode':s.manual_mode,'response_poll':s.response_poll_enabled,'auto_approve':s.auto_approve,'profiles':db.scalar(select(func.count()).select_from(Profile)),'integrations':db.scalar(select(func.count()).select_from(Integration)),'attempts':db.scalar(select(func.count()).select_from(ActionAttempt)),'jobs':db.scalar(select(func.count()).select_from(Job)),'worker_heartbeat':bool(db.get(State,'worker_heartbeat')),'scheduler_heartbeat':bool(db.get(State,'scheduler_heartbeat')),'pytest_present':u.find_spec('pytest') is not None,'playwright_present':u.find_spec('playwright') is not None,'writable_data':os.access('/app',os.W_OK)}))
    '''))
    assert r['os']=='Linux' and r['python'].startswith('3.13.') and r['schema']=='006' and r['uid']!=0
    assert r['dry_run'] and r['manual_mode'] and not r['response_poll'] and not r['auto_approve']
    assert r['attempts']==r['profiles']==r['integrations']==0 and not r['pytest_present'] and not r['playwright_present']
    assert r['worker_heartbeat'] and r['scheduler_heartbeat']
    r['node']=run('exec','fieldwork6b-web-1','node','--version').strip();assert r['node'].startswith('v22.')
    r['node_uid']=run('exec','fieldwork6b-web-1','id','-u').strip();assert r['node_uid']!='0'
    r['postgres']=run('exec','fieldwork6b-db-1','postgres','--version').strip();assert '17.' in r['postgres']
    run('exec','fieldwork6b-api-1','python','-m','pip','check');run('exec','fieldwork6b-worker-1','python','-m','app.worker','--health')
    for name in ['api','worker','web','db']:
     v=json.loads(run('inspect','fieldwork6b-'+name+'-1'))[0]
     if name=='db':assert not any(v['NetworkSettings']['Ports'].values())
     if name=='api':assert not v['HostConfig']['PortBindings']
     if name=='web':assert v['HostConfig']['PortBindings']['3000/tcp'][0]['HostIp']=='127.0.0.1'
    r['postgres_not_published']=True;r['api_internal_only']=True;r['web_loopback_only']=True
    v=json.loads(run('network','inspect','fieldwork6b_default'))[0];assert v['Internal'];r['staging_external_egress_disabled']=True
    r['result']='passed';(out/'safe-start-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))

if mode=='scan':
    import hashlib
    import json
    import os
    import subprocess
    import tarfile
    from pathlib import Path
    out=ROOT/'docs/package6b';runtime=json.loads((p/'runtime.json').read_text())
    needles=[runtime[k].encode() for k in ('API_KEY','POSTGRES_PASSWORD','CREDENTIAL_KEYS','OPERATOR_PASSWORD_HASH')]
    needles += [b'fake-client-secret',b'fake-refresh',b'fake-model-key',b'fake-scrape-key',b'fake-contact-key']
    env=os.environ.copy();d=os.environ.get('FIELDWORK_DOCKER_BIN','docker');report={}
    for image in ('fieldwork6b-backend','fieldwork6b-frontend'):
     a=p/(image+'.tar');subprocess.run([d,'image','save','-o',str(a),image],env=env,check=True)
     hits=0;layers=0;badpaths=[]
     with tarfile.open(a) as tf:
      for entry in tf:
       if not entry.isfile():continue
       handle=tf.extractfile(entry);tail=b''
       while True:
        chunk=handle.read(1024*1024)
        if not chunk:break
        block=tail+chunk;hits+=sum(n in block for n in needles);tail=block[-256:]
       handle=tf.extractfile(entry)
       try:
        with tarfile.open(fileobj=handle,mode='r|*') as layer:
         layers+=1
         for item in layer:
          name=item.name
          if item.isfile():
           content=layer.extractfile(item);tail=b''
           while True:
            chunk=content.read(1024*1024)
            if not chunk:break
            block=tail+chunk;hits+=sum(n in block for n in needles);tail=block[-256:]
          if name.startswith('app/') and (name.endswith(('.sqlite','.db','.env','.env.production','qa_release.py')) or name.startswith('app/tests/')):badpaths.append(name)
       except tarfile.ReadError:pass
     assert hits==0 and not badpaths,(image,'Image security assertion failed')
     info=json.loads(subprocess.check_output([d,'image','inspect',image],env=env,text=True))[0]
     assert not any(k in '\n'.join(info['Config'].get('Env',[])) for k in ('API_KEY=','POSTGRES_PASSWORD=','CREDENTIAL_KEYS=','OAUTH_CLIENT_SECRET='))
     report[image]={'result':'passed','image_id':info['Id'],'os':info['Os'],'architecture':info['Architecture'],'runtime_user':info['Config']['User'],'saved_image_bytes':a.stat().st_size,'layer_archives_checked':layers,'decompressed_layer_file_contents_checked':True,'secret_matches':0,'private_database_or_QA_fixture_paths':badpaths,'runtime_secret_variables_baked':False}
     a.unlink()
    (out/'image-scan.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if mode=='tests':
    import json
    import os
    import subprocess
    from pathlib import Path
    root=Path((p/'context-path').read_text());value=json.loads((p/'runtime.json').read_text());envfile=p/'linux-tests.env'
    envfile.write_text('TEST_POSTGRES_URL='+value['DATABASE_URL']+'\nDATABASE_URL=sqlite:////tmp/qa.sqlite\nDATA_DIRECTORY=/tmp/qa-data\nENVIRONMENT=development\nDRY_RUN=true\nMANUAL_MODE=true\nRESPONSE_POLL_ENABLED=false\nAPI_KEY=local-development-key-change-me\n');envfile.chmod(0o600)
    env=os.environ.copy()
    tests=['tests/test_postgres_security.py::test_fresh_migrations_indices_constraints_and_schema','tests/test_postgres_security.py::test_forward_migration_preserves_pause_receipts_and_all_legacy_rows','tests/test_postgres_security.py::test_two_connections_same_send_only_one_reservation','tests/test_postgres_security.py::test_pause_before_and_after_reservation_semantics','tests/test_postgres_security.py::test_concurrent_global_quota_cannot_overreserve','tests/test_release.py::test_migration_failure_transaction_and_duplicate_invocation','tests/test_release.py::test_release_unsafe_configuration_fails_early','tests/test_runtime.py::test_worker_subprocess_start_sigterm_and_restart','tests/test_runtime.py::test_scheduler_duplicate_ticks_one_fixed_due_no_catchup_and_pause','tests/test_runtime.py::test_expired_job_fence_safe_read_recovery_and_send_never_requeued']
    with Path('docs/package6b/linux-regressions.log').open('w') as f:r=subprocess.run([d,'run','--rm','--network','fieldwork6b_default','--env-file',str(envfile),'fieldwork6b-qa','python','-m','pytest','-q','-ra',*tests],env=env,stdout=f,stderr=subprocess.STDOUT,check=False)
    print('Target Linux concurrency/schema/config/worker regressions exit',r.returncode)
    if r.returncode:print(Path('docs/package6b/linux-regressions.log').read_text()[-4000:])
    raise SystemExit(r.returncode)
