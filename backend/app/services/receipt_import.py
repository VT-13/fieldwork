"""Import immutable receipt evidence into the ledger. Never replay an action."""
import hashlib,json
from pathlib import Path
from sqlalchemy import select
from ..models import Outreach
from ..core import Blocked
from . import ledger

def import_receipts(db,path,*,apply=False):
    path=Path(path)
    raw=path.read_bytes()
    if len(raw)>10_000_000:raise Blocked('Receipt file exceeds 10 MB')
    digest=hashlib.sha256(raw).hexdigest()
    if path.suffix=='.jsonl':rows=[json.loads(line) for line in raw.splitlines() if line.strip()]
    else:
        data=json.loads(raw)
        rows=data if isinstance(data,list) else data.get('attempts',data.get('results',[data]))
    planned=[]
    for index,r in enumerate(rows):
        row=db.get(Outreach,r.get('outreach_id')) if r.get('outreach_id') else None
        if not row and r.get('message_id'):
            matches=list(db.scalars(select(Outreach).where(Outreach.message_id==r['message_id'])))
            if len(matches)==1:row=matches[0]
        if not row:raise Blocked(f'Receipt {index} lacks unambiguous outreach linkage; resolve manually')
        receipt={k:r[k] for k in ('outreach_id','message_id','gmail_id','provider_id','thread_id','at','attempt_at','status','sent_verified','sent_label_verified') if k in r}
        receipt['source_sha256']=digest;receipt['source_entry']=index
        planned.append((row.id,receipt))
    if not apply:return {'records':len(planned),'source_sha256':digest,'applied':False}
    for index,(id,receipt) in enumerate(planned):
        attempt,replay=ledger.claim(db,f'receipt:{digest}:{index}','receipt_import','legacy',lambda:{'version':'receipt-import-v1','source_sha256':digest},outreach_id=id,entity_id=str(index))
        if not replay:
            attempt.network_units=0
            ledger.finish(db,attempt,'succeeded',receipt=receipt,reason='immutable_receipt_import')
    return {'records':len(planned),'source_sha256':digest,'applied':True}
