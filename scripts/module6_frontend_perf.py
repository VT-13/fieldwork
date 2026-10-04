"""Production-built Chromium timing on 500 fictional campaign companies.

API fixture interception only; not a network/provider E2E or Lighthouse score.
"""
import json,os,subprocess,time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/module6'
source=Path('/private/tmp/fieldwork-module6/frontend');env=os.environ.copy();env.update(PORT='13037',HOSTNAME='127.0.0.1',APP_ORIGIN='http://localhost:13037',BACKEND_URL='http://127.0.0.1:18037')
handle=(OUT/'frontend-perf-server.log').open('w')
process=subprocess.Popen(['node',str(source/'.next/standalone/server.js')],env=env,stdout=handle,stderr=subprocess.STDOUT)
fixture=json.loads((ROOT/'frontend/tests/fixture.json').read_text())
base=fixture['companies'][0];fixture['companies']=[base|{'id':'bench-'+str(i),'name':'Fictional company '+str(i)} for i in range(500)]
reads=[]
try:
    import httpx
    for i in range(50):
        try:
            if httpx.get('http://localhost:13037/login').status_code==200:break
        except httpx.TransportError:pass
        time.sleep(.2)
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(viewport={'width':1280,'height':900})
        context.add_cookies([{'name':'fieldwork_session','value':'fictional-perf-only','url':'http://localhost:13037'}])
        page=context.new_page()
        def route(r):
            path=r.request.url.split('/api/')[1].split('?')[0];reads.append(path)
            names={'outreach':'outreach','companies':'companies','metrics':'metrics','settings':'settings','profile':'profile','runtime':'runtime','campaign':'campaign','responses':'responses','intelligence/capabilities':'capabilities','integrations/gmail':'connection','jobs':'jobs','desk':'desk','discovery/candidates':'candidates'}
            r.fulfill(json=fixture.get(names.get(path,''),{}))
        page.route('**/api/**',route)
        page.add_init_script("""window.releasePerf={longTasks:[],cls:0};new PerformanceObserver(list=>list.getEntries().forEach(e=>window.releasePerf.longTasks.push(e.duration))).observe({type:'longtask',buffered:true});new PerformanceObserver(list=>list.getEntries().forEach(e=>{if(!e.hadRecentInput)window.releasePerf.cls+=e.value})).observe({type:'layout-shift',buffered:true});""")
        samples=[]
        for _ in range(3):
            reads.clear();started=time.perf_counter();page.goto('http://localhost:13037/?view=campaign');page.locator('.register-row').first.wait_for() if page.locator('.register-row').count() else page.get_by_text('500 targets in the workspace').wait_for()
            page.get_by_text('500 targets in the workspace').wait_for();elapsed=(time.perf_counter()-started)*1000
            page.wait_for_timeout(300)
            metrics=page.evaluate("({navigation:performance.getEntriesByType('navigation')[0].toJSON(),observed:window.releasePerf,js:performance.getEntriesByType('resource').filter(e=>e.name.includes('.js')).map(e=>({bytes:e.encodedBodySize,duration:e.duration}))})")
            samples.append({'ready_ms':round(elapsed,2),'dom_content_loaded_ms':round(metrics['navigation']['domContentLoadedEventEnd'],2),'long_tasks_ms':metrics['observed']['longTasks'],'cls':metrics['observed']['cls'],'js_encoded_bytes':sum(e['bytes'] for e in metrics['js']),'api_reads':dict((name,reads.count(name)) for name in set(reads))})
        browser.close()
    (OUT/'performance-frontend.json').write_text(json.dumps({'scope':'Production Next build, 500 fictional companies, intercepted API, local unthrottled Chromium; not hosted Lighthouse','samples':samples},indent=2)+'\n')
finally:
    process.terminate();process.wait(timeout=10);handle.close()
