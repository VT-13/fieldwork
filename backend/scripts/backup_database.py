"""Private consistent backup. Restore targets must be explicit; never includes external key files."""
import argparse,hashlib,os,sqlite3,subprocess
from pathlib import Path
from urllib.parse import urlsplit,unquote


def postgres_env(url):
    p=urlsplit(url.replace('postgresql+psycopg://','postgresql://'))
    if p.scheme!='postgresql' or not p.hostname:raise ValueError('Explicit PostgreSQL URL required')
    env=os.environ.copy()
    env.update(PGHOST=p.hostname,PGPORT=str(p.port or 5432),PGUSER=unquote(p.username or ''),PGPASSWORD=unquote(p.password or ''),PGDATABASE=p.path.lstrip('/'))
    return env


def backup(url,output,tools=''):
    output=Path(output)
    fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    os.close(fd)
    try:
        if url.startswith('sqlite:///'):
            source=Path(url.removeprefix('sqlite:///')).resolve()
            with sqlite3.connect('file:'+str(source)+'?mode=ro',uri=True) as src,sqlite3.connect(output) as dest:src.backup(dest)
        else:
            command=str(Path(tools)/'pg_dump') if tools else 'pg_dump'
            subprocess.run([command,'--format=custom','--no-owner','--no-acl','--file',str(output)],env=postgres_env(url),capture_output=True,check=True,timeout=180)
        return hashlib.sha256(output.read_bytes()).hexdigest()
    except Exception:
        output.unlink(missing_ok=True)
        raise RuntimeError('Database backup failed; no credentials or provider output logged') from None


def restore_postgres(url,source,tools='',confirmed=False):
    if not confirmed:raise ValueError('Explicit restore confirmation is required')
    command=str(Path(tools)/'pg_restore') if tools else 'pg_restore'
    try:
        subprocess.run([command,'--exit-on-error','--single-transaction','--no-owner','--no-acl','--dbname',postgres_env(url)['PGDATABASE'],str(source)],env=postgres_env(url),capture_output=True,check=True,timeout=180)
    except Exception:raise RuntimeError('Database restore failed; inspect target safely') from None


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['backup','restore']);p.add_argument('--file',required=True,type=Path);p.add_argument('--tools',default='');p.add_argument('--confirm-empty-restore-target',action='store_true');args=p.parse_args()
    url=os.environ.get('FIELDWORK_BACKUP_DATABASE_URL','')
    if not url:raise SystemExit('Set FIELDWORK_BACKUP_DATABASE_URL explicitly; no runtime default is used')
    if args.action=='backup':print('Private backup created; SHA-256:',backup(url,args.file,args.tools))
    else:restore_postgres(url,args.file,args.tools,args.confirm_empty_restore_target);print('Restore complete; retain pause and verify before starting services')
