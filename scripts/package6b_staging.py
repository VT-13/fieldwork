"""Disposable Linux/Docker release verification. Never mounts installed data.

Requires an explicit isolated Docker daemon and production images built from a
clean source context. Provider bootstrap is copied into test containers only;
production images remain unmodified. No real provider credentials are accepted.
"""
import base64
import json
import os
import ssl
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/package6b'
WORK = Path(os.environ['FIELDWORK_STAGING_ROOT']).resolve()
assert WORK.name == 'fieldwork-package6b' and WORK.is_relative_to(Path('/tmp').resolve())
DOCKER = os.environ.get('FIELDWORK_DOCKER_BIN', 'docker')
assert os.environ.get('DOCKER_HOST'), 'Explicit isolated Docker daemon required'
CONTEXT = Path((WORK / 'context-path').read_text())
BASE = 'https://localhost:13466'
TEST = WORK / 'e2e'
TEST.mkdir(exist_ok=True)
clock = datetime(2026, 10, 5, 16, 0, tzinfo=timezone.utc)
password = 'release-disposable-operator-passphrase'
logs = []
report = {'scope': 'Actual Linux production images: HTTPS -> Node22 Next -> Python3.13 API -> separate worker/scheduler -> persistent PG17; fake provider seams, internal network', 'production_mutations': False, 'scenarios': {}}


def docker(*args, data=None, check=True):
    r = subprocess.run([DOCKER, *args], input=data, text=True, capture_output=True, timeout=150, check=False)
    if check and r.returncode:
        # Do not print inspect/env/config outputs containing runtime secrets.
        raise RuntimeError('Docker action failed: ' + args[0] + ' exit=' + str(r.returncode))
    return r.stdout + (r.stderr if args[0]=='logs' else '')


def compose(*args):
    return docker('compose', '--project-name', 'fieldwork6b', '--project-directory', str(CONTEXT),
                  '--env-file', str(CONTEXT / '.env'), '-f', str(CONTEXT / 'compose.yaml'),
                  '-f', str(WORK / 'override.yaml'), '--profile', 'worker', *args)


def execute(code, data=None, container='fieldwork6b-api-1'):
    return docker('exec', '-i', container, 'python', '-c', code, data=data)


def fixture_code(code, data=None):
    return execute("from pathlib import Path\nimport json,fcntl\nroot=Path('/staging/fieldwork6b')\n" + code, data)


def set_clock(value):
    global clock
    clock = value
    fixture_code("(root/'clock.txt').write_text(" + repr(clock.isoformat()) + ")")


def store(**changes):
    return json.loads(fixture_code("""import sys
with (root/'provider.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 value=json.loads((root/'provider.json').read_text())
 value.update(json.loads(sys.stdin.read()))
 tmp=root/'parent.new';tmp.write_text(json.dumps(value));tmp.replace(root/'provider.json')
 print(json.dumps(value))
""", json.dumps(changes)))


class Worker:
    def kill(self): docker('kill', 'fieldwork6b-worker-1')
    def wait(self, timeout=None): return docker('wait', 'fieldwork6b-worker-1')
    def poll(self):
        return None if json.loads(docker('inspect', 'fieldwork6b-worker-1'))[0]['State']['Running'] else 1


def boot_worker():
    docker('start', 'fieldwork6b-worker-1')
    return Worker()


def initialize():
    count=execute("from app.db import Session;from sqlalchemy import text\nwith Session() as db: print(db.scalar(text('SELECT count(*) FROM outreach')))").strip()
    assert count=='0', 'Use a fresh disposable staging project; never replay an existing run'
    compose('stop', '-t', '20', 'worker', 'api')
    value = json.loads((WORK / 'runtime.json').read_text())
    value.update(DATA_DIRECTORY='/staging/fieldwork6b', DRY_RUN='false', MANUAL_MODE='false',
                 RESPONSE_POLL_ENABLED='true', DAILY_SEND_LIMIT='4', SENDER_EMAIL='student@example.com',
                 OAUTH_CLIENT_ID='fake-client', OAUTH_CLIENT_SECRET='fake-client-secret',
                 OAUTH_REDIRECT_URI=BASE+'/api/integrations/gmail/callback',
                 OPENAI_API_KEY='fake-model-key', FIRECRAWL_API_KEY='fake-scrape-key',
                 HUNTER_API_KEY='fake-contact-key', GOOGLE_MAPS_API_KEY='fake-places-key',
                 FIELDWORK_RELEASE_TEST='disposable-only', FIELDWORK_RELEASE_CONTAINER_TEST='disposable-only',
                 FIELDWORK_RELEASE_TEST_ROOT='/staging/fieldwork6b')
    (CONTEXT/'.env').write_text(''.join(k+"='"+v+"'\n" for k,v in value.items()))
    (CONTEXT/'.env').chmod(0o600)
    override=(WORK/'override.yaml').read_text()
    for mode in ('api','worker'):
        override=override.replace('    command: [\"python\", \"/app/qa_release.py\", \"'+mode+'\"]\n','')
    override=override.replace('    volumes: [\"qa-data:/staging/fieldwork6b\"]\n','')
    override=override.replace('    image: fieldwork6b-backend\n    ports:', '    image: fieldwork6b-backend\n    command: ["python", "/app/qa_release.py", "api"]\n    volumes: ["qa-data:/staging/fieldwork6b"]\n    ports:')
    override=override.replace('  worker:\n    image: fieldwork6b-backend', '  worker:\n    image: fieldwork6b-backend\n    command: ["python", "/app/qa_release.py", "worker"]\n    volumes: ["qa-data:/staging/fieldwork6b"]')
    if '\nvolumes:\n' not in override:override+='\nvolumes:\n  qa-data:\n'
    (WORK/'override.yaml').write_text(override)
    docker('volume', 'create', 'fieldwork6b_qa-data')
    docker('run','--rm','--network','none','--user','0','--mount','type=volume,source=fieldwork6b_qa-data,target=/staging','fieldwork6b-backend','chown','-R','1000:1000','/staging')
    compose('create','--force-recreate','api','worker')
    for name in ('api','worker'):
        docker('cp',str(ROOT/'backend/tests/release_runtime.py'),'fieldwork6b-'+name+'-1:/app/qa_release.py')
    docker('run','--rm','--network','none','--mount','type=volume,source=fieldwork6b_qa-data,target=/staging/fieldwork6b','fieldwork6b-backend','python','-c',
           "from pathlib import Path;import json;p=Path('/staging/fieldwork6b');(p/'clock.txt').write_text('2026-10-05T16:00:00+00:00');(p/'provider.json').write_text(json.dumps({'history':100,'messages':{},'transmissions':[],'hide_sent':False}))")
    compose('start','api')
    execute("""from datetime import datetime,timezone
from app.db import Session
from app.models import State,Integration
from app.credentials import encrypt
from app.gmail_oauth import SEND,READ,COMPOSE
with Session() as db:
 db.merge(State(key='outreach_policy',value={'enabled':False,'paid_services_authorized':True,'max_followups_per_company':1,'allowed_cities':['Rocklin'],'daily_total_attempt_limit':4}))
 db.merge(State(key='automation',value={'enabled':False}))
 db.merge(Integration(id='gmail',email='student@example.com',status='connected',scopes=[SEND,READ,COMPOSE],encrypted_tokens=encrypt({'refresh_token':'fake-refresh','access_token':'fake-access','expires_at':datetime(2027,1,1,tzinfo=timezone.utc).isoformat()})))
 db.commit()
""")
    return boot_worker()


# Trusted ephemeral TLS edge exercises Secure session cookies; no trust-store change.
def tls_edge():
    (TEST/'ca.cnf').write_text('[req]\ndistinguished_name=dn\nx509_extensions=v3ca\nprompt=no\n[dn]\nCN=Fieldwork isolated staging CA\n[v3ca]\nbasicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid:always\n')
    for args in ([ 'req','-x509','-newkey','rsa:2048','-nodes','-days','2','-keyout',str(TEST/'ca.key'),'-out',str(TEST/'ca.pem'),'-config',str(TEST/'ca.cnf')],
                 ['req','-newkey','rsa:2048','-nodes','-keyout',str(TEST/'server.key'),'-out',str(TEST/'server.csr'),'-subj','/CN=localhost']):
        subprocess.run(['openssl',*args],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
    (TEST/'leaf.ext').write_text('subjectAltName=DNS:localhost,IP:127.0.0.1\nextendedKeyUsage=serverAuth\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n')
    subprocess.run(['openssl','x509','-req','-in',str(TEST/'server.csr'),'-CA',str(TEST/'ca.pem'),'-CAkey',str(TEST/'ca.key'),'-CAcreateserial','-days','2','-out',str(TEST/'server.pem'),'-extfile',str(TEST/'leaf.ext')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
    for p in TEST.glob('*.key'):p.chmod(0o600)
    class Proxy(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def run_proxy(self):
            conn=HTTPConnection('127.0.0.1',13066,timeout=65)
            body=self.rfile.read(int(self.headers.get('Content-Length',0)))
            headers={k:v for k,v in self.headers.items() if k.lower() not in ('connection','transfer-encoding','x-forwarded-for','x-forwarded-host','x-forwarded-proto')}
            headers['Host']='localhost:13466'
            try:
                conn.request(self.command,self.path,body=body,headers=headers);response=conn.getresponse();content=response.read()
            except OSError:
                conn.close();self.send_error(503,'Starting disposable web');return
            self.send_response(response.status)
            for k,v in response.getheaders():
                if k.lower() not in ('connection','transfer-encoding','content-length'):self.send_header(k,v)
            self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content);conn.close()
        do_GET=run_proxy;do_POST=run_proxy;do_PUT=run_proxy;do_PATCH=run_proxy
    server=ThreadingHTTPServer(('127.0.0.1',13466),Proxy)
    tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.minimum_version=ssl.TLSVersion.TLSv1_2;tls.load_cert_chain(TEST/'server.pem',TEST/'server.key');server.socket=tls.wrap_socket(server.socket,server_side=True)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server

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
def main():
    global worker, server, client
    worker=initialize()
    server=tls_edge()
    client=httpx.Client(base_url=BASE,verify=ssl.create_default_context(cafile=str(TEST/'ca.pem')),headers={'Origin':BASE},timeout=65)
    try:
        def ready():
            try:return client.get('/login').status_code==200
            except httpx.TransportError as error:
                report['readiness_error']=str(error)
                return False
        wait(ready)
        wait(lambda:client.get('/api/profile').status_code==401)
        login();assert client.get('/api/runtime').headers.get('x-request-id');cookie=next(c for c in client.cookies.jar if c.name=='fieldwork_session');assert cookie.secure and cookie.has_nonstandard_attr('HttpOnly')
        assert client.get('/api/profile',headers={'X-Forwarded-For':'203.0.113.8','X-Forwarded-Host':'evil.example'}).status_code==200
        assert client.get('/login',headers={'Host':'evil.example'}).status_code==200  # The isolated edge overwrites Host; direct spoof is covered below.
        assert httpx.get('http://127.0.0.1:13066/login',headers={'Host':'evil.example','X-Forwarded-Host':'localhost:13466'}).status_code==400
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
        _unknown_company,unknown=company('example.org');store(hang_next=True,hide_sent=True)
        send(unknown)
        wait(lambda:fixture_code("print((root/'dispatch.entered').exists())").strip()=='True')
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
        before=transmissions();_overflow_company,overflow=company('example.edu');request('POST','outreach/'+overflow['id']+'/approve');overflow_job=request('POST','outreach/'+overflow['id']+'/send')
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
        report['result']='passed'
    except Exception as error:
        report['result']='failed';report['failure_type']=type(error).__name__
        raise
    finally:
        execute("from app.db import Session;from app.models import State;from app.services.policy import set_paused\nwith Session() as db:\n set_paused(db,False);r=db.get(State,'outreach_policy');r.value={**r.value,'paid_services_authorized':False};db.merge(State(key='automation',value={'enabled':False}));db.commit()")
        client.close();server.shutdown()
        for name in ('api','worker','web','db'):
            logs=docker('logs','fieldwork6b-'+name+'-1',check=False)
            (OUT/('container-'+name+'.log')).write_text(logs)
        (OUT/'e2e-results.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__ == '__main__':
    main()
