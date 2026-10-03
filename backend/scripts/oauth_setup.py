"""Launch the authenticated application OAuth lifecycle; never write tokens to .env."""
import argparse
import webbrowser
from app.config import settings
p=argparse.ArgumentParser();p.add_argument('--no-browser',action='store_true');args=p.parse_args()
url=settings().app_origin+'/login'
if not args.no_browser:webbrowser.open(url)
print('Sign in to Fieldwork, open Settings, then Connect / reconnect Gmail.')
print('Application sign-in page:',url)
print('Tokens are stored encrypted by the API. No Gmail password is requested.')
