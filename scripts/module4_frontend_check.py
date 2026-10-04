"""Verify frontend in a clean temp copy, away from duplicated local .next artifacts.

No install, live backend, credentials or providers. Dependencies are read-only
inputs copied by hard link (ordinary copy fallback across volumes).
"""
import json,os,shutil,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/module4'
def link(source,target):
    try:return os.link(source,target)
    except OSError:return shutil.copy2(source,target)
def main():
    root=Path(tempfile.mkdtemp(prefix='fieldwork-module4-ui-'));frontend=root/'frontend';out=root/'docs/module4';out.mkdir(parents=True)
    shutil.copytree(ROOT/'frontend',frontend,ignore=shutil.ignore_patterns('node_modules','.next','.next*','test-results','.env*','*.tsbuildinfo','.DS_Store'))
    shutil.copytree(ROOT/'frontend/node_modules',frontend/'node_modules',copy_function=link,symlinks=True)
    env={k:v for k,v in os.environ.items() if not any(s in k for s in ('API_KEY','TOKEN','PASSWORD','CREDENTIAL','OAUTH','BACKEND','DATABASE','LIVE_BATCH'))}
    env.update(APP_ORIGIN='http://localhost:13030',BACKEND_URL='http://127.0.0.1:18030',FIELDWORK_BROWSER_ARTIFACT_DIR='../docs/module4')
    env['FIELDWORK_BROWSER_EXECUTABLE']=os.environ.get('FIELDWORK_BROWSER_EXECUTABLE','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    results={'temporary_root':str(root),'checks':{}}
    for name,args in [('frontend-lint',['npm','run','lint']),('frontend-typecheck',['npm','run','typecheck']),('frontend-format',['npm','run','format:check']),('frontend-build',['npm','run','build']),('browser',['npm','exec','--','playwright','test','--reporter=json'])]:
        start=time.monotonic();r=subprocess.run(args,cwd=frontend,env=env,text=True,capture_output=True,timeout=240)
        (OUT/(name+'.log')).write_text(r.stdout+r.stderr)
        results['checks'][name]={'command':args,'exit_code':r.returncode,'seconds':round(time.monotonic()-start,2)}
        print(name,results['checks'][name],flush=True)
        if name=='browser' and r.stdout.strip().startswith('{'):(OUT/'browser-results.json').write_text(r.stdout)
        if r.returncode:break
    for file in out.glob('*.png'):shutil.copy2(file,OUT/file.name)
    (OUT/'frontend-checks.json').write_text(json.dumps(results,indent=2)+'\n')
    if len(results['checks'])!=5 or any(r['exit_code'] for r in results['checks'].values()):raise SystemExit(1)
if __name__=='__main__':main()
