"""Production-server smoke/visual baseline on disposable copies and loopback ports."""
import json
from pathlib import Path
import subprocess
import time
import urllib.request
from playwright.sync_api import sync_playwright
from phase0_baseline import OUT, PYTHON, environment

def wait(url):
    for _ in range(60):
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(.25)
    raise RuntimeError('Local server startup failed: ' + url)

def main():
    root = Path(json.loads((OUT / 'results.json').read_text())['temporary_root'])
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless=True)
        try:
            for n, name in enumerate(('workspace', 'runtime')):
                snapshot = root / name
                env = environment(snapshot)
                api_port, web_port = 18010+n, 13010+n
                origin = 'http://127.0.0.1:' + str(web_port)
                env.update(ALLOW_LOCAL_NO_AUTH='true', BACKEND_URL='http://127.0.0.1:'+str(api_port), APP_ORIGIN=origin)
                log = (OUT / (name+'-startup.log')).open('w')
                api = subprocess.Popen([str(PYTHON), '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(api_port)], cwd=snapshot/'backend', env=env, stdout=log, stderr=log)
                web = subprocess.Popen(['node', 'node_modules/next/dist/bin/next', 'start', '--hostname', '127.0.0.1', '--port', str(web_port)], cwd=snapshot/'frontend', env=env, stdout=log, stderr=log)
                context = browser.new_context(viewport={'width':1440,'height':1000})
                # Browser QA never transmits draft/profile content to external services.
                context.route('**/*', lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                try:
                    wait('http://127.0.0.1:'+str(api_port)+'/health')
                    wait(origin)
                    page.goto(origin)
                    page.get_by_role('button', name='My email desk', exact=False).first.click()
                    page.get_by_role('button', name='Save draft', exact=False).wait_for()
                    page.screenshot(path=str(OUT/(name+'-desktop.png')), full_page=True)
                    reply = page.request.get(origin+'/api/profile')
                    assert reply.status == 200
                    unauthorized = urllib.request.Request('http://127.0.0.1:'+str(api_port)+'/companies')
                    try:
                        urllib.request.urlopen(unauthorized)
                        raise AssertionError('Unauthenticated API was accepted')
                    except urllib.error.HTTPError as e:
                        assert e.code == 401
                    cross_origin = page.request.post(origin+'/api/demo', headers={'Origin':'https://untrusted.example'}, data='{}')
                    assert cross_origin.status == 403
                    for name_button in ['Opportunities','Outreach','Insights','My profile','Settings','My email desk']:
                        page.get_by_role('button', name=name_button, exact=False).first.click()
                        page.wait_for_timeout(200)
                    page.set_viewport_size({'width':390,'height':844})
                    page.screenshot(path=str(OUT/(name+'-mobile.png')), full_page=True)
                    overflow = page.evaluate('({viewport:innerWidth,document:document.documentElement.scrollWidth})')
                    results[name] = {'startup':'ok','title':page.title(),'api_auth_401':True,'cross_origin_mutation_403':True,'navigation':'six views visited','page_errors':errors,'mobile_dimensions':overflow,'external_requests':'blocked; remote fonts unavailable in this test','scope':'smoke and screenshots, not full E2E or WCAG audit'}
                finally:
                    context.close()
                    for proc in (web, api):
                        proc.terminate()
                        try:
                            proc.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            proc.kill(); proc.wait()
                    log.close()
        finally:
            browser.close()
    (OUT/'browser-results.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(results,indent=2))

if __name__ == '__main__':
    main()
