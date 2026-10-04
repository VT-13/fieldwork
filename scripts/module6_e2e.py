"""Native production-build/API/worker E2E on isolated PG17 and fake providers.

No browser interception, real credentials, mailbox, paid calls or live DB. TLS
uses an isolated test CA explicitly trusted by the HTTP client, never verify=False.
"""
import base64, json, os, secrets, shutil, ssl, subprocess, sys, threading, time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.client import HTTPConnection
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/module6'
TEST=Path('/private/tmp/fieldwork-module6/e2e');TEST.mkdir(exist_ok=True)
BACK=TEST/'source/backend'
shutil.copytree(ROOT/'backend',BACK,ignore=shutil.ignore_patterns('.env*','*.db','*.db-*','*.sqlite*','__pycache__','.pytest_cache','*.egg-info'),dirs_exist_ok=True)
PY=os.environ.get('FIELDWORK_RELEASE_PYTHON','/private/tmp/fieldwork-module6/runtime-venv/bin/python');PG='/private/tmp/fieldwork-module6/pg17/install/bin'
BASE='https://localhost:13443';URL='postgresql+psycopg://fieldwork_test@127.0.0.1:55436/fieldwork_m6_e2e'
sys.path.insert(0,str(BACK))
def password_hash(value):
    import hashlib
    salt=secrets.token_bytes(16)
    digest=hashlib.scrypt(value.encode(),salt=salt,n=16384,r=8,p=1,dklen=32)
    return 'scrypt$'+base64.urlsafe_b64encode(salt).decode()+'$'+base64.urlsafe_b64encode(digest).decode()
from cryptography.fernet import Fernet
from sqlalchemy import create_engine,text
admin=create_engine('postgresql+psycopg://fieldwork_test@127.0.0.1:55436/postgres',isolation_level='AUTOCOMMIT')
with admin.connect() as db:
    for name in ('fieldwork_m6_e2e','fieldwork_m6_restore'):
        db.execute(text('DROP DATABASE IF EXISTS '+name+' WITH (FORCE)'))
        db.execute(text('CREATE DATABASE '+name+' ENCODING \'UTF8\''))
admin.dispose()
clock=datetime(2026,10,5,16,0,tzinfo=timezone.utc)
def set_clock(value):
    global clock
    clock=value;(TEST/'clock.txt').write_text(clock.isoformat())
set_clock(clock)
(TEST/'dispatch.entered').unlink(missing_ok=True)
(TEST/'provider.json').write_text(json.dumps({'history':100,'messages':{},'transmissions':[],'hide_sent':False}))
password='release-disposable-operator-passphrase'
env={k:v for k,v in os.environ.items() if not any(s in k for s in ('KEY','TOKEN','PASSWORD','OAUTH','DATABASE','SENDER','BACKEND','APP_ORIGIN','LIVE_BATCH'))}
env.update(OAUTH_REFRESH_TOKEN='',ALLOW_LEGACY_OAUTH='false',DATABASE_URL=URL,DATA_DIRECTORY=str(TEST),API_KEY=secrets.token_hex(32),CREDENTIAL_KEYS=Fernet.generate_key().decode(),OPERATOR_PASSWORD_HASH=password_hash(password),ENVIRONMENT='production',APP_ORIGIN=BASE,TRUSTED_HOSTS='["localhost","127.0.0.1"]',OAUTH_CLIENT_ID='fake-client',OAUTH_CLIENT_SECRET='fake-client-secret',OAUTH_REDIRECT_URI=BASE+'/api/integrations/gmail/callback',SENDER_EMAIL='student@example.com',DRY_RUN='false',MANUAL_MODE='false',DAILY_SEND_LIMIT='4',RESPONSE_POLL_ENABLED='true',WORKER_POLL_SECONDS='1',OPENAI_API_KEY='fake-model-key',FIRECRAWL_API_KEY='fake-scrape-key',HUNTER_API_KEY='fake-contact-key',GOOGLE_MAPS_API_KEY='fake-places-key',FIELDWORK_RELEASE_TEST='disposable-only',FIELDWORK_RELEASE_TEST_ROOT=str(TEST),PYTHONPATH=str(BACK),PATH=PG+':'+env.get('PATH',''))
subprocess.run([PY,'-m','alembic','upgrade','head'],cwd=BACK,env=env,stdout=(OUT/'e2e-migration.log').open('w'),stderr=subprocess.STDOUT,check=True)
# Seed fake authorization/control fixtures only. All profile/prospect/message work uses authenticated HTTP.
os.environ.update(env)
from app.db import Session
from app.models import State,Integration
from app.credentials import encrypt
from app.gmail_oauth import SEND,READ,COMPOSE
with Session() as db:
    db.add(State(key='outreach_policy',value={'enabled':False,'paid_services_authorized':True,'max_followups_per_company':1,'allowed_cities':['Rocklin'],'daily_total_attempt_limit':4}))
    db.add(State(key='automation',value={'enabled':False}))
    db.add(Integration(id='gmail',email='student@example.com',status='connected',scopes=[SEND,READ,COMPOSE],encrypted_tokens=encrypt({'refresh_token':'fake-refresh','access_token':'fake-access','expires_at':datetime(2027,1,1,tzinfo=timezone.utc).isoformat()})))
    db.commit()
# Ephemeral CA and localhost leaf; nothing is added to the Mac trust store.
(TEST/'ca.cnf').write_text('[req]\ndistinguished_name=dn\nx509_extensions=v3ca\nprompt=no\n[dn]\nCN=Fieldwork isolated release QA CA\n[v3ca]\nbasicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid:always\n')
for args in ([ 'req','-x509','-newkey','rsa:2048','-nodes','-days','2','-keyout',str(TEST/'ca.key'),'-out',str(TEST/'ca.pem'),'-config',str(TEST/'ca.cnf')],['req','-newkey','rsa:2048','-nodes','-keyout',str(TEST/'server.key'),'-out',str(TEST/'server.csr'),'-subj','/CN=localhost']):
    subprocess.run(['openssl',*args],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
(TEST/'leaf.ext').write_text('subjectAltName=DNS:localhost,IP:127.0.0.1\nextendedKeyUsage=serverAuth\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n')
subprocess.run(['openssl','x509','-req','-in',str(TEST/'server.csr'),'-CA',str(TEST/'ca.pem'),'-CAkey',str(TEST/'ca.key'),'-CAcreateserial','-days','2','-out',str(TEST/'server.pem'),'-extfile',str(TEST/'leaf.ext')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
for p in TEST.glob('*.key'):p.chmod(0o600)
class Proxy(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def run_proxy(self):
        conn=HTTPConnection('127.0.0.1',13036,timeout=65)
        body=self.rfile.read(int(self.headers.get('Content-Length',0)))
        headers={k:v for k,v in self.headers.items() if k.lower() not in ('connection','transfer-encoding','x-forwarded-for','x-forwarded-host','x-forwarded-proto')}
        headers['Host']='localhost:13443'
        try:
            conn.request(self.command,self.path,body=body,headers=headers);response=conn.getresponse();content=response.read()
        except OSError:
            conn.close();self.send_error(503,'Starting disposable web');return
        self.send_response(response.status)
        for k,v in response.getheaders():
            if k.lower() not in ('connection','transfer-encoding','content-length'):self.send_header(k,v)
        self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content);conn.close()
    do_GET=run_proxy;do_POST=run_proxy;do_PUT=run_proxy;do_PATCH=run_proxy
server=ThreadingHTTPServer(('127.0.0.1',13443),Proxy)
tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.minimum_version=ssl.TLSVersion.TLSv1_2;tls.load_cert_chain(TEST/'server.pem',TEST/'server.key');server.socket=tls.wrap_socket(server.socket,server_side=True)
threading.Thread(target=server.serve_forever,daemon=True).start()
frontend=Path('/private/tmp/fieldwork-module6/frontend');standalone=frontend/'.next/standalone'
shutil.copytree(frontend/'.next/static',standalone/'.next/static',dirs_exist_ok=True)
shutil.copytree(frontend/'public',standalone/'public',dirs_exist_ok=True)
logs=[];processes=[]
def process(args,name,extra=None):
    handle=(OUT/(name+'.log')).open('w');logs.append(handle)
    child=subprocess.Popen(args,cwd=BACK,env=env| (extra or {}),stdout=handle,stderr=subprocess.STDOUT);processes.append(child);return child
def boot_worker():return process([PY,str(BACK/'tests/release_runtime.py'),'worker'],'e2e-worker-'+str(len(processes)))
api=process([PY,str(BACK/'tests/release_runtime.py'),'api'],'e2e-api')
web=process(['node',str(standalone/'server.js')],'e2e-web',{'BACKEND_URL':'http://127.0.0.1:18036','HOSTNAME':'127.0.0.1','PORT':'13036','NODE_ENV':'production'})
worker=boot_worker()
import httpx
client=httpx.Client(base_url=BASE,verify=ssl.create_default_context(cafile=str(TEST/'ca.pem')),headers={'Origin':BASE},timeout=65)
report={'scope':'Real TLS HTTP -> production Next proxy -> authenticated API -> actual worker process -> disposable PG17; fake provider seams only','production_mutations':False,'scenarios':{}}
def wait(predicate,seconds=35):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        result=predicate()
        if result:return result
        time.sleep(.4)
    raise AssertionError('Bounded E2E wait failed')
def request(method,path,data=None,expected=(200,202)):
    response=client.request(method,'/api/'+path,json=data)
    if response.status_code not in expected:raise AssertionError(path+' status='+str(response.status_code)+' '+response.text[:160])
    return response.json()
def login():return request('POST','auth/login',{'password':password})
def job_done(job):
    def state():
        row=next((j for j in request('GET','jobs') if j['id']==job['id']),None)
        if row and row['status'] in ('blocked','failed','interrupted','cancelled'):raise AssertionError('Job '+row['kind']+' '+row['status']+' '+row['error'])
        return row if row and row['status']=='done' else None
    return wait(state)
def store(**changes):
    import fcntl
    with (TEST/'provider.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);value=json.loads((TEST/'provider.json').read_text());value.update(changes);tmp=TEST/'fixture.new';tmp.write_text(json.dumps(value));tmp.replace(TEST/'provider.json');return value
def transmissions():return len(store()['transmissions'])
def company(domain=None):
    if domain:
        job=request('POST','discovery/import',{'companies':[{'name':'Release QA '+domain,'website':'https://'+domain,'industry':'Software robotics','source':'https://'+domain,'distance_miles':4}]});job_done(job)
    else:job_done(request('POST','discover',{'area':'Rocklin, California','provider':'maps','industry':'Software robotics','limit':1}))
    candidate=next(c for c in request('GET','discovery/candidates') if c['domain']==(domain or 'example.com'))
    c=request('POST','discovery/candidates/'+candidate['id']+'/accept');job_done(request('POST','companies/'+c['id']+'/actions/pipeline'))
    return c,next(r for r in request('GET','outreach') if r['company_id']==c['id'] and r['sequence']==0)
def send(row):
    request('POST','outreach/'+row['id']+'/approve');return request('POST','outreach/'+row['id']+'/send')
def row(id):return next(r for r in request('GET','outreach') if r['id']==id)
def add_reply(r,ct):
    value=store();mid='fake-reply-'+r['id'];value['history']+=1
    value['messages'][mid]={'id':mid,'threadId':r['thread_id'],'labelIds':['INBOX','UNREAD'],'internalDate':str(int(clock.timestamp()*1000)),'_history':value['history'],'payload':{'mimeType':'text/plain','headers':[{'name':'From','value':ct['email']},{'name':'To','value':'student@example.com'},{'name':'Subject','value':r['subject']},{'name':'Message-ID','value':'<'+mid+'@example.com>'},{'name':'In-Reply-To','value':r['message_id']}],'body':{'data':base64.urlsafe_b64encode(b'Could you share your portfolio?').decode()}}}
    store(**value)
def prepare(c,r):
    request('PUT','automation',{'enabled':False});set_clock(clock+timedelta(days=8));login()
    ct=request('GET','companies/'+c['id'])['contacts'][0];job_done(request('POST','contacts/'+ct['id']+'/verify'))
    request('PUT','automation',{'enabled':True})
    return wait(lambda:next((o for o in request('GET','outreach') if o['company_id']==c['id'] and o['sequence']==1),None))
try:
    def ready():
        try:return client.get('/login').status_code==200
        except httpx.TransportError:return False
    wait(ready)
    wait(lambda:client.get('/api/profile').status_code==401)
    login();assert client.get('/api/runtime').headers.get('x-request-id');cookie=next(c for c in client.cookies.jar if c.name=='fieldwork_session');assert cookie.secure and cookie.has_nonstandard_attr('HttpOnly')
    assert client.get('/api/profile',headers={'X-Forwarded-For':'203.0.113.8','X-Forwarded-Host':'evil.example'}).status_code==200
    assert client.get('/login',headers={'Host':'evil.example'}).status_code==200  # The isolated edge overwrites Host; direct spoof is covered below.
    assert httpx.get('http://127.0.0.1:13036/login',headers={'Host':'evil.example','X-Forwarded-Host':'localhost:13443'}).status_code==400
    assert client.post('/api/outreach-policy',headers={'Origin':'https://evil.example'},json={'enabled':True}).status_code==403
    request('PUT','profile',{'name':'Release QA Student','email':'student@example.com','verified':True,'projects':['Built websites for local businesses'],'awards':['VEX Robotics World Championship competitor'],'skills':['Web development','Robotics'],'interests':['Software','Robotics']})
    request('PUT','outreach-policy',{'enabled':True})
    c,initial=company();detail=request('GET','companies/'+c['id']);assert detail['research']['city_evidence_id'] and detail['score']>0 and len(detail['evidence'])>=2
    assert initial['status']=='draft' and initial['review']['passed'] and initial['attempts']==0
    job_done(send(initial));initial=row(initial['id']);assert initial['status']=='sent' and initial['sent_verified'] and transmissions()==1
    follow=prepare(c,initial);assert follow['status']=='draft' and follow['subject']==initial['subject'] and follow['body']!=initial['body']
    job_done(send(follow));follow=row(follow['id']);assert follow['thread_id']==initial['thread_id'] and transmissions()==2
    assert client.post('/api/outreach/'+follow['id']+'/send').status_code==409 and transmissions()==2
    add_reply(follow,detail['contacts'][0]);job_done(request('POST','responses/sync'))
    assert request('GET','companies/'+c['id'])['stage']=='replied' and request('GET','responses')['needs_attention']==1
    report['scenarios']['initial_followup_reply']={'passed':True,'transmissions':2,'operator_review_before_each_send':True,'same_subject_thread':True,'replay_no_duplicate':True,'reply_linkage_and_cancellation':True}
    request('PUT','automation',{'enabled':False});set_clock(clock+timedelta(minutes=5));login()
    unknown_company,unknown=company('example.org');store(hang_next=True,hide_sent=True)
    attempt=send(unknown)
    wait(lambda:(TEST/'dispatch.entered').exists())
    worker.kill();worker.wait(timeout=10)
    set_clock(clock+timedelta(minutes=3));store(hang_next=False);worker=boot_worker()
    wait(lambda:row(unknown['id'])['status']=='unknown')
    before=transmissions();assert request('GET','runtime')['daily_attempts']==2
    packet=request('POST','desk',{'subject':'Release QA own-account test','body':'Fictional isolated validation, no company recipient.'})
    assert client.post('/api/desk/'+packet['id']+'/self-test').status_code==409 and transmissions()==before
    job_done(request('POST','outreach/'+unknown['id']+'/reconcile'));assert row(unknown['id'])['status']=='unknown'
    store(hide_sent=False);set_clock(clock+timedelta(minutes=5))
    job_done(request('POST','outreach/'+unknown['id']+'/reconcile'));assert row(unknown['id'])['status']=='sent' and transmissions()==before
    report['scenarios']['forced_crash_uncertain_reconciliation']={'passed':True,'no_evidence_held':True,'exact_evidence_sent':True,'no_resend':True,'transmissions':1}
    set_clock(clock+timedelta(minutes=5));request('POST','desk/'+packet['id']+'/self-test');assert request('GET','runtime')['daily_attempts']==3
    set_clock(clock+timedelta(minutes=5));race_company,race_initial=company('example.net');job_done(send(race_initial));race_initial=row(race_initial['id'])
    assert request('GET','runtime')['daily_attempts']==4
    before=transmissions();overflow_company,overflow=company('example.edu');request('POST','outreach/'+overflow['id']+'/approve');overflow_job=request('POST','outreach/'+overflow['id']+'/send')
    wait(lambda:next((j for j in request('GET','jobs') if j['id']==overflow_job['id'] and j['status']=='blocked'),None))
    assert transmissions()==before and row(overflow['id'])['attempts']==0
    another=request('POST','desk',{'subject':'Release QA capped self-test','body':'Another isolated test.'})
    assert client.post('/api/desk/'+another['id']+'/self-test').status_code==409 and transmissions()==before
    report['scenarios']['shared_daily_quota']={'passed':True,'cap':4,'types':['followup','uncertain_initial','self_test','initial'],'overflow_calls':0,'unknown_counted':True}
    race_follow=prepare(race_company,race_initial);assert request('GET','runtime')['daily_attempts']==0
    report['scenarios']['timezone_rollover_no_catchup']={'passed':True,'timezone':'America/Los_Angeles','new_day_attempts':0}
    request('POST','outreach/'+race_follow['id']+'/approve')
    add_reply(race_initial,request('GET','companies/'+race_company['id'])['contacts'][0])
    before=transmissions();request('POST','outreach/'+race_follow['id']+'/send')
    wait(lambda:row(race_follow['id'])['status']=='cancelled')
    assert transmissions()==before and request('GET','companies/'+race_company['id'])['stage']=='replied'
    report['scenarios']['due_followup_reply_race']={'passed':True,'reserved_transmissions':0,'pending_message_cancelled':True}
    # A bounded three-minute worker soak with repeated real process ticks.
    started=time.monotonic();samples=[];counts=[];report['soak']={'planned_seconds':180}
    for index in range(60):
        time.sleep(3);set_clock(clock+timedelta(seconds=15))
        assert worker.poll() is None
        with Session() as db:
            counts.append(db.scalar(text('SELECT count(*) FROM jobs')))
        values=subprocess.check_output(['ps','-o','rss=,%cpu=','-p',str(worker.pid)],text=True).split();samples.append([int(values[0]),float(values[1])])
        if index%20==0:print('Soak elapsed',round(time.monotonic()-started),'seconds',flush=True)
    assert max(counts)-min(counts)<=4 and transmissions()==before
    report['soak']={'seconds':round(time.monotonic()-started,2),'samples':len(samples),'rss_first_kib':samples[0][0],'rss_last_kib':samples[-1][0],'rss_max_kib':max(x[0] for x in samples),'max_cpu_percent':max(x[1] for x in samples),'job_growth':max(counts)-min(counts),'extra_transmissions':0,'scope':'Bounded native fake-provider soak, not long-term hosted reliability'}
    report['result']='passed'
except Exception as error:
    report['result']='failed'
    report['failure_type']=type(error).__name__
    raise
finally:
    client.close();server.shutdown()
    for child in reversed(processes):
        if child.poll() is None:
            child.terminate()
            try:child.wait(timeout=20)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=10)
    for handle in logs:handle.close()
    (OUT/'e2e-results.json').write_text(json.dumps(report,indent=2)+'\n')
