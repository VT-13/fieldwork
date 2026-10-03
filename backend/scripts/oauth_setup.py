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
import httpx
from app.config import settings

parser=argparse.ArgumentParser()
parser.add_argument('--no-browser', action='store_true', help='Print the consent URL without launching a browser')
args=parser.parse_args()
s=settings()
if not s.oauth_client_id:
    raise SystemExit("Set OAUTH_CLIENT_ID (and OAUTH_CLIENT_SECRET for a confidential web client)")
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
r=httpx.post(endpoint,data={"client_id":s.oauth_client_id,"client_secret":s.oauth_client_secret,"code":result["code"],"redirect_uri":redirect,"grant_type":"authorization_code","code_verifier":verifier},timeout=30)
if r.status_code!=200: raise SystemExit(f"Token exchange failed (HTTP {r.status_code}); check app registration and redirect URI")
token=r.json().get("refresh_token")
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
