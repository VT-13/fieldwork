"""Create private application secrets without displaying them or accepting mail passwords."""
import argparse,getpass,os,secrets
from pathlib import Path
from cryptography.fernet import Fernet
from app.auth import password_hash
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
password=getpass.getpass('Choose a unique Fieldwork operator password (16+ characters): ')
if password!=getpass.getpass('Repeat Fieldwork operator password: '):raise SystemExit('Passwords differ')
value='API_KEY='+secrets.token_urlsafe(48)+'\nOPERATOR_PASSWORD_HASH='+password_hash(password)+'\nCREDENTIAL_KEYS='+Fernet.generate_key().decode()+'\n'
fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:f.write(value)
print('Private application-secret file created; no values printed. Store its encryption key separately from database backups.')
