"""Sign-in/logout and private proxy checks against disposable local services."""
import json,os,subprocess,time
from pathlib import Path
from module1_check import isolated
import module1_check
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/module2';PYTHON='/private/tmp/fieldwork-module2-venv/bin/python'

def main():
    root,env=isolated();module1_check.OUT=OUT
    env.update(API_KEY='browser-test-only-private-api-key-more-than-32-characters',APP_ORIGIN='http://localhost:13020',BACKEND_URL='http://127.0.0.1:18020',OAUTH_REDIRECT_URI='http://localhost:13020/api/integrations/gmail/callback',CREDENTIAL_KEYS='',ALLOW_LEGACY_OAUTH='false')
    # Generate only a fake operator password hash; no live credentials are used.
    import sys
    sys.path.insert(0,str(root/'backend'))
    from app.auth import password_hash
    env['OPERATOR_PASSWORD_HASH']=password_hash('browser-test-only-passphrase')
    results={'temporary_root':str(root),'checks':{}}
    for name,args,cwd in [('frontend-install',['npm','ci','--ignore-scripts'],root/'frontend'),('frontend-typecheck',['npm','run','typecheck'],root/'frontend'),('frontend-build',['npm','run','build'],root/'frontend'),('migration-browser',[PYTHON,'-m','alembic','upgrade','head'],root/'backend')]:
        results['checks'][name]=module1_check.run(name,args,cwd,env)
        if results['checks'][name]['exit_code']:raise RuntimeError(name+' failed')
    api_log=(OUT/'browser-api.log').open('w');web_log=(OUT/'browser-web.log').open('w')
    api=subprocess.Popen([PYTHON,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','18020','--no-access-log'],cwd=root/'backend',env=env,stdout=api_log,stderr=subprocess.STDOUT)
    web=subprocess.Popen(['node','node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port','13020'],cwd=root/'frontend',env=env,stdout=web_log,stderr=subprocess.STDOUT)
    try:
        import urllib.request
        for _ in range(100):
            try:
                with urllib.request.urlopen('http://127.0.0.1:18020/health',timeout=.5):pass
                with urllib.request.urlopen('http://localhost:13020/login',timeout=.5):pass
                break
            except Exception:time.sleep(.2)
        else:raise RuntimeError('Disposable servers did not start')
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True)
            context=browser.new_context();page=context.new_page()
            page.route('**/*',lambda route:route.continue_() if route.request.url.startswith(('http://localhost:13020','http://127.0.0.1:18020')) else route.abort())
            assert context.request.get('http://localhost:13020/api/profile').status==401
            context.add_cookies([{'name':'fieldwork_session','value':'forged','url':'http://localhost:13020'}])
            assert context.request.get('http://localhost:13020/api/profile').status==401
            context.clear_cookies();page.goto('http://localhost:13020/');page.wait_for_url('**/login')
            page.get_by_label('Operator password').fill('browser-test-only-passphrase');page.get_by_role('button',name='Sign in',exact=True).click();page.wait_for_url('http://localhost:13020/')
            assert context.request.get('http://localhost:13020/api/profile').status==200
            assert context.request.put('http://localhost:13020/api/profile',data={},headers={'Origin':'https://evil.example'}).status==403
            page.get_by_role('button',name='Settings',exact=True).click();page.get_by_text('Gmail: disconnected',exact=True).wait_for()
            cookies=context.cookies();session=next(c for c in cookies if c['name']=='fieldwork_session');assert session['httpOnly'] and session['sameSite']=='Lax'
            page.screenshot(path=str(OUT/'login-session-smoke.png'))
            page.get_by_role('button',name='Sign out',exact=True).click();page.wait_for_url('**/login')
            context.add_cookies([session]);assert context.request.get('http://localhost:13020/api/profile').status==401
            browser.close()
        results['browser']={'result':'passed','coverage':['anonymous private API rejected','forged cookie rejected','sign-in creates server session','same-origin policy enforced','disconnected Gmail shown','logout invalidates copied cookie'],'real_provider_calls':0,'real_emails_sent':0}
    finally:
        for proc in (web,api):
            proc.terminate()
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
        api_log.close();web_log.close()
        (OUT/'browser-checks.json').write_text(json.dumps(results,indent=2)+'\n')
if __name__=='__main__':main()
