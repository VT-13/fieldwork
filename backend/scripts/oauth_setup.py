"""Interactive authorization-code + PKCE bootstrap; saves token to private .env.
Run from backend with .env loaded by Settings. Redirect URI: http://localhost:8765/callback
"""
import base64
import argparse
import hashlib
import os
from pathlib import Path
import secrets
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs
import json
import shlex
import ssl
from types import SimpleNamespace
from urllib.request import Request, urlopen
from urllib.error import HTTPError

parser=argparse.ArgumentParser()
parser.add_argument('--no-browser', action='store_true', help='Print the consent URL without launching a browser')
args=parser.parse_args()
values={}
if Path('.env').exists():
    for line in Path('.env').read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key,value=line.split('=',1)
            parts=shlex.split(value, comments=True)
            values[key.strip()]=' '.join(parts)
values.update(os.environ)
s=SimpleNamespace(**{key:values.get(key.upper(),default) for key,default in {
    'oauth_client_id':'','oauth_client_secret':'','mail_provider':'gmail','microsoft_tenant':'common'
}.items()}, manual_mode=values.get('MANUAL_MODE','true').lower() in {'true','1','yes'})
if not s.oauth_client_id:
    raise SystemExit("Set OAUTH_CLIENT_ID (and OAUTH_CLIENT_SECRET for a confidential web client)")
# Prefer an explicitly configured CA bundle; macOS system trust fixes Python.org
# installations without a populated default certificate bundle. Never disable TLS.
ca_file=os.environ.get("SSL_CERT_FILE")
if not ca_file and Path('/etc/ssl/cert.pem').is_file():
    ca_file='/etc/ssl/cert.pem'
tls_context=ssl.create_default_context(cafile=ca_file)
state=secrets.token_urlsafe(32)
verifier=secrets.token_urlsafe(64)
challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
redirect="http://localhost:8765/callback"
google=s.mail_provider=="gmail"
base="https://accounts.google.com/o/oauth2/v2/auth" if google else f"https://login.microsoftonline.com/{s.microsoft_tenant}/oauth2/v2.0/authorize"
scopes=("https://www.googleapis.com/auth/gmail.compose https://www.googleapis.com/auth/gmail.readonly" if s.manual_mode else "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly") if google else ("offline_access User.Read Mail.ReadWrite" if s.manual_mode else "offline_access User.Read Mail.ReadWrite Mail.Send")
query={"client_id":s.oauth_client_id,"redirect_uri":redirect,"response_type":"code","scope":scopes,"state":state,"code_challenge":challenge,"code_challenge_method":"S256"}
if google:
    query.update(access_type="offline",prompt="consent")
result={}
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed=urlparse(self.path)
        q=parse_qs(parsed.query)
        valid=parsed.path=="/callback" and secrets.compare_digest(q.get("state",[""])[0],state) and "code" in q
        self.send_response(200 if valid else 400)
        self.end_headers()
        self.wfile.write(b"Authorization captured. Return to your terminal." if valid else b"Invalid authorization response.")
        if valid: result["code"]=q["code"][0]
    def log_message(self,*args): pass
url=base+"?"+urlencode(query)
print("Open this authorization URL if the browser does not open:\n"+url)
if not args.no_browser:
    webbrowser.open(url)
server=HTTPServer(("127.0.0.1",8765),Handler)
server.timeout=180
server.handle_request()
server.server_close()
if not result.get("code"): raise SystemExit("Authorization not received; retry bootstrap")
endpoint="https://oauth2.googleapis.com/token" if google else f"https://login.microsoftonline.com/{s.microsoft_tenant}/oauth2/v2.0/token"
payload={"client_id":s.oauth_client_id,"client_secret":s.oauth_client_secret,"code":result["code"],"redirect_uri":redirect,"grant_type":"authorization_code","code_verifier":verifier}
try:
    with urlopen(Request(endpoint,data=urlencode(payload).encode(),headers={"Content-Type":"application/x-www-form-urlencoded"}),timeout=30,context=tls_context) as response:
        token=json.load(response).get("refresh_token")
except HTTPError as exc:
    raise SystemExit(f"Token exchange failed (HTTP {exc.code}); check app registration and redirect URI")

if not token: raise SystemExit("No refresh token returned; repeat with offline consent")
path=Path('.env')
lines=path.read_text().splitlines() if path.exists() else []
lines=[line for line in lines if not line.strip().startswith('OAUTH_REFRESH_TOKEN=')]
lines.append('OAUTH_REFRESH_TOKEN='+token)
temp=path.with_suffix('.env.tmp')
fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as handle:
    handle.write('\n'.join(lines)+'\n')
os.replace(temp,path)
print('Mailbox authorization saved privately to backend/.env. Restart the API and worker. No token was printed.')
