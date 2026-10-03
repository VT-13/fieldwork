"""Module 2 checks in sanitized snapshots and explicitly disposable PostgreSQL."""
import json,os,subprocess
from pathlib import Path
from module1_check import isolated,run
import module1_check
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/module2'
PYTHON=Path('/private/tmp/fieldwork-module2-venv/bin/python')
if __name__=='__main__':
    OUT.mkdir(exist_ok=True);module1_check.OUT=OUT
    root,env=isolated()
    env.update(OPERATOR_PASSWORD_HASH='',CREDENTIAL_KEYS='',ALLOW_LEGACY_OAUTH='false')
    # A test URL is opt-in and never derived from the production database setting.
    if os.getenv('FIELDWORK_DISPOSABLE_POSTGRES_URL'):env['TEST_POSTGRES_URL']=os.environ['FIELDWORK_DISPOSABLE_POSTGRES_URL']
    if os.getenv('FIELDWORK_TEST_PG_TOOLS'):env['FIELDWORK_TEST_PG_TOOLS']=os.environ['FIELDWORK_TEST_PG_TOOLS']
    results={'temporary_root':str(root),'checks':{}}
    commands=[('security',[str(PYTHON),'-m','pytest','-q','-ra','tests/test_security.py','tests/test_postgres_security.py']),('pytest',[str(PYTHON),'-m','pytest','-q','-ra']),('migration',[str(PYTHON),'-m','alembic','upgrade','head']),('pip-check',[str(PYTHON),'-m','pip','check']),('lint',[str(PYTHON),'-m','ruff','check','app','scripts','tests'])]
    for name,args in commands:results['checks'][name]=run(name,args,root/'backend',env)
    (OUT/'checks.json').write_text(json.dumps(results,indent=2)+'\n')
