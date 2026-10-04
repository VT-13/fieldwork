"""Read-only preservation gate; no production mutation or private row export."""
import json, sqlite3, hashlib, sys
from pathlib import Path
from module5_preserve import snapshot, LIVE, ROOT

def capture():
    result=snapshot()
    with sqlite3.connect("file:"+str(LIVE/"data/fieldwork.sqlite")+"?mode=ro", uri=True) as db:
        tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        result["schema_revision"]=db.execute("SELECT version_num FROM alembic_version").fetchone()[0] if "alembic_version" in tables else "unversioned"
        result["schema_hash"]=hashlib.sha256(json.dumps(list(db.execute("SELECT name, sql FROM sqlite_master WHERE type IN ('table','index') ORDER BY name"))).encode()).hexdigest()
        result["extended_counts"]={name:db.execute("SELECT count(*) FROM "+name).fetchone()[0] for name in ("contacts","suppressions","jobs","operations","action_attempts","integrations") if name in tables}
    return result

if __name__=="__main__":
    out=ROOT/"docs/module6";out.mkdir(exist_ok=True)
    current=capture();before=out/"preservation-before.json"
    if "--before" in sys.argv:
        if before.exists():raise SystemExit("Baseline exists; do not overwrite it")
        before.write_text(json.dumps(current,indent=2)+"\n")
    else:
        unchanged=json.loads(before.read_text())==current
        (out/"preservation.json").write_text(json.dumps({"unchanged":unchanged,**current},indent=2)+"\n")
        if not unchanged:raise SystemExit("Installed state changed; inspect before claiming preservation")
    print("Read-only installed-state evidence captured")
