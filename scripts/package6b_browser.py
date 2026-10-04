"""One host-browser smoke through actual Linux web/API; no design suite."""
import base64
import hashlib
import json
import os
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
WORK=Path(os.environ['FIELDWORK_STAGING_ROOT']).resolve()
assert WORK.name=='fieldwork-package6b' and WORK.is_relative_to(Path('/tmp').resolve())
TEST=WORK/'e2e'
from package6b_staging import tls_edge

server=tls_edge()
leaf=x509.load_pem_x509_certificate((TEST/'server.pem').read_bytes())
public=leaf.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
spki=base64.b64encode(hashlib.sha256(public).digest()).decode()
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=os.environ.get('FIELDWORK_BROWSER_PATH','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),headless=True,args=['--ignore-certificate-errors-spki-list='+spki])
  context=browser.new_context();page=context.new_page()
  page.goto('https://localhost:13466/login')
  page.get_by_label('Operator password',exact=True).fill('release-disposable-operator-passphrase')
  page.get_by_role('button',name='Sign in',exact=True).click()
  page.wait_for_url('https://localhost:13466/',timeout=15000)
  profile=page.evaluate("async () => {const r=await fetch('/api/profile'); return {status:r.status,data:await r.json()}}")
  assert profile['status']==200 and profile['data']['email']=='student@example.com'
  runtime=page.evaluate("async () => {const r=await fetch('/api/runtime'); return {status:r.status,data:await r.json()}}")
  assert runtime['status']==200 and runtime['data']['schema_version']=='006' and runtime['data']['recurring_paused']
  result={'result':'passed','scope':'One isolated host Chromium browser through actual Node22 Linux container -> Python3.13 API -> PG17; no UI suite','login_and_secure_session':True,'authenticated_profile':True,'schema':'006','recurring_paused':True,'certificate_scope':'Only ephemeral staging leaf public-key hash permitted; no system trust change','browser_version':browser.version}
  (ROOT/'docs/package6b/browser-smoke.json').write_text(json.dumps(result,indent=2)+'\n')
  print('One browser login/profile/runtime smoke passed')
  context.close();browser.close()
finally:server.shutdown()
