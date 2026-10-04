"""Module 4 isolated regression gate; never loads installed configuration."""
import json,os
from pathlib import Path
from module1_check import isolated,run
import module1_check
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/module4';PYTHON='/private/tmp/fieldwork-module2-venv/bin/python'
def main():
    OUT.mkdir(parents=True,exist_ok=True);module1_check.OUT=OUT
    root,env=isolated();env['TEST_POSTGRES_URL']=os.environ.get('FIELDWORK_DISPOSABLE_POSTGRES_URL','')
    env['FIELDWORK_TEST_PG_TOOLS']='/private/tmp/fieldwork-module2-pg-tools/pgserver/pginstall/bin'
    env['PATH']=env['FIELDWORK_TEST_PG_TOOLS']+':'+env.get('PATH','')
    results={'temporary_root':str(root),'checks':{}}
    for name,args,cwd in [('contract-check',[PYTHON,'scripts/frontend_contracts.py','--check'],root),('fixture-check',[PYTHON,'scripts/module3_fixture.py','--check'],root),('backend-tests',[PYTHON,'-m','pytest','-q','-ra'],root/'backend'),('backend-lint',[PYTHON,'-m','ruff','check','app','scripts','tests'],root/'backend')]:results['checks'][name]=run(name,args,cwd,env)
    (OUT/'backend-checks.json').write_text(json.dumps(results,indent=2)+'\n')
    if any(r['exit_code'] for r in results['checks'].values()):raise SystemExit(1)
if __name__=='__main__':main()
