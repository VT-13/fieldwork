"""Run targeted checks in a sanitized copy; never use live env or data."""
import json,os,shutil,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/module1'
PYTHON=Path.home()/'.local/share/fieldwork/.venv/bin/python'

def isolated():
    root=Path(tempfile.mkdtemp(prefix='fieldwork-module1-'))
    for part in ('backend','frontend','scripts'):
        shutil.copytree(ROOT/part,root/part,ignore=shutil.ignore_patterns('.env*','*.db','*.db-*','*.sqlite*','node_modules','.next','__pycache__','.pytest_cache','*.egg-info','*.tsbuildinfo'))
    env=os.environ.copy()
    for key in list(env):
        if any(v in key for v in ('API_KEY','TOKEN','PASSWORD','OAUTH','DATABASE_URL','TEST_POSTGRES_URL','LIVE_BATCH')):env.pop(key,None)
    env.update(DATABASE_URL='sqlite:///'+str(root/'test.sqlite'),DATA_DIRECTORY=str(root/'data'),ENVIRONMENT='development',DRY_RUN='true',MANUAL_MODE='true',AUTO_APPROVE='false',RESPONSE_POLL_ENABLED='false',API_KEY='local-development-key-change-me',SSL_CERT_FILE='/etc/ssl/cert.pem')
    for key in ('OPENAI_API_KEY','TAVILY_API_KEY','FIRECRAWL_API_KEY','GOOGLE_MAPS_API_KEY','APOLLO_API_KEY','HUNTER_API_KEY','OAUTH_CLIENT_ID','OAUTH_CLIENT_SECRET','OAUTH_REFRESH_TOKEN','SENDER_EMAIL'):env[key]=''
    return root,env

def run(name,args,cwd,env):
    start=time.monotonic()
    r=subprocess.run(args,cwd=cwd,env=env,text=True,capture_output=True,timeout=180)
    (OUT/(name+'.log')).write_text(r.stdout+r.stderr)
    result={'command':args,'exit_code':r.returncode,'seconds':round(time.monotonic()-start,2)}
    print(name,result,flush=True)
    return result

if __name__=='__main__':
    OUT.mkdir(exist_ok=True)
    root,env=isolated()
    results={'temporary_root':str(root),'checks':{}}
    for name,args in [('pytest',[str(PYTHON),'-m','pytest','-q','-ra']),('migration',[str(PYTHON),'-m','alembic','upgrade','head'])]:
        results['checks'][name]=run(name,args,root/'backend',env)
    (OUT/'checks.json').write_text(json.dumps(results,indent=2)+'\n')
