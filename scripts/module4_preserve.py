"""Read-only installed-runtime preservation evidence. Never copy private content."""
import hashlib,json,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; LIVE=Path('/Users/vihaantirumala/.local/share/fieldwork')
def snapshot():
    files={}
    for scope in ('backend/app','frontend/app','frontend/components','frontend/lib','scripts'):
        for p in sorted((LIVE/scope).rglob('*')):
            if p.is_file() and p.suffix in ('.py','.ts','.tsx','.css','.mjs','.sh'):
                files[str(p.relative_to(LIVE))]=hashlib.sha256(p.read_bytes()).hexdigest()
    with sqlite3.connect('file:'+str(LIVE/'data/fieldwork.sqlite')+'?mode=ro',uri=True) as db:
        counts={n:db.execute('SELECT count(*) FROM '+n).fetchone()[0] for n in ('companies','outreach','events')}
        policy=db.execute("SELECT value FROM state WHERE key='outreach_policy'").fetchone()
        value=json.loads(policy[0]) if policy else {}
    return {'source':files,'counts':counts,'policy_hash':hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest(),'recurring_enabled':value.get('enabled')}
if __name__=='__main__':
    at=snapshot();base=ROOT/'docs/module4/preservation-before.json'
    if '--before' in sys.argv:base.write_text(json.dumps(at,indent=2)+'\n')
    else:
        before=json.loads(base.read_text());result={'unchanged':before==at,'deployed':False,'outreach_sent':0,'real_oauth_changed':False,'paid_provider_calls':0,**at}
        (ROOT/'docs/module4/preservation.json').write_text(json.dumps(result,indent=2)+'\n')
        if before!=at:raise SystemExit('Installed runtime changed; inspect before claiming preservation')
