"""Versioned source integrity and portable release bundle; never deploys or copies state."""
import argparse,hashlib,json,subprocess,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MANIFEST='docs/module1/canonical-source.json'
PREFIXES=('backend/','frontend/','desktop/','scripts/')
CONFIGS={'ARCHITECTURE.md','SECURITY.md','README.md','docs/SETUP.md','docs/MIGRATION_PLAN.md','docs/BACKUP_RESTORE.md','docs/DATA_LIFECYCLE.md','backend/pyproject.toml','backend/requirements.lock.txt','backend/alembic.ini','backend/Dockerfile','backend/.dockerignore','frontend/package.json','frontend/package-lock.json','frontend/tsconfig.json','frontend/next.config.ts','frontend/proxy.ts','frontend/Dockerfile','frontend/.dockerignore','compose.yaml','start-personal.sh','.env.example','.github/workflows/checks.yml'}

def tracked(root):
    files=subprocess.check_output(['git','ls-files'],cwd=root,text=True).splitlines()
    selected=sorted(f for f in files if f.startswith(PREFIXES) or f in CONFIGS)
    for name in selected:
        p=Path(name)
        if (p.name.startswith('.env') and p.name!='.env.example') or p.suffix in {'.db','.sqlite','.sqlite3'}:
            raise ValueError('Sensitive runtime file cannot enter a release: '+name)
    return selected

def make(root):
    return {'format':1,'files':{f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in tracked(root)}}

def verify(root,manifest):
    failures=[]
    for name,digest in manifest['files'].items():
        p=root/name
        if not p.is_file() or p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:failures.append(name)
    # In a development checkout, additions must also be acknowledged by the manifest.
    if (root/'.git').exists():
        failures+=['unmanifested:'+p for p in set(tracked(root))-set(manifest['files'])]
        candidates=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=root,text=True).splitlines()
        failures+=['untracked:'+p for p in candidates if p.startswith(PREFIXES) or p in CONFIGS]
    # Auto-discovered Next routes / Python modules added in an installed tree are drift too.
    for folder in ('backend/app','backend/scripts','backend/alembic','frontend/app','frontend/public','desktop','scripts'):
        for path in (root/folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.name!='.DS_Store':
                name=str(path.relative_to(root))
                if name not in manifest['files']:failures.append('unmanifested:'+name)
    return sorted(set(failures))

def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['create','verify','bundle'])
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--output',type=Path)
    args=p.parse_args();root=args.root.resolve()
    if args.action=='create':
        (root/MANIFEST).write_text(json.dumps(make(root),indent=2)+'\n');print('Source manifest written');return
    manifest=json.loads((root/MANIFEST).read_text())
    errors=verify(root,manifest)
    if errors:raise SystemExit('Source integrity failed: '+', '.join(errors))
    if args.action=='bundle':
        if not args.output:raise SystemExit('--output is required')
        # Only a committed, reviewed revision may become a release artifact.
        subprocess.run(['git','diff','--exit-code','HEAD','--',*manifest['files'],MANIFEST],cwd=root,check=True,stdout=subprocess.DEVNULL)
        with tarfile.open(args.output,'w:gz') as out:
            for name in [*manifest['files'],MANIFEST]:out.add(root/name,arcname=name,recursive=False)
        print('Source-only bundle created; nothing deployed')
    else:print('Canonical source integrity verified')

if __name__=='__main__':main()
