"""Read-only view and emergency stop for the explicitly authorized local campaign."""
import json,os
from pathlib import Path
from fastapi import HTTPException
from .db import Session
from sqlalchemy import select
from .models import State,Outreach,DomainTransition,now
from .services import ledger

def current_batch(db):
 row=db.get(State,'manual_batch');progress=db.get(State,'manual_batch_progress')
 if not row or not progress or not row.value.get('outreach_ids'):return None
 scope=row.value;p=progress.value;ids=scope['outreach_ids']
 records=list(db.scalars(select(Outreach).where(Outreach.id.in_(ids))))
 # Receipt confirmations, rather than approval or provider acceptance, drive this count.
 verified={r['outreach_id'] for r in p.get('results',[]) if r.get('sent_verified') and r['outreach_id'] in ids}
 policy=db.get(State,'outreach_policy')
 stopping=bool(scope.get('stop_requested'))
 return {'active':True,'batch_name':'Greater Sacramento outreach','status':'stopping' if stopping and p.get('status') in {'running','sending'} else p.get('status','pending'),'detail':p.get('detail',''),'limit':25,'planned':len(ids),'sent':sum(r.status=='sent' for r in records),'verified':len(verified),'skipped':0,'followups':False,'ongoing_policy':policy.value if policy else {},'validation_policy':'Published business contacts checked against primary sources; syntax and domain MX checked. Gmail Sent confirmation does not guarantee inbox delivery.','stop_requested':stopping,'can_stop':scope.get('enabled',False) and p.get('status') in {'running','sending'},'manual':True}

def directory():
 value=os.environ.get('LIVE_BATCH_DIRECTORY','')
 return Path(value) if value else None

def status():
 with Session() as db:
  current=current_batch(db)
  if current:return current
 root=directory()
 if not root or not (root/'receipts.json').exists():return {'active':False}
 with Session() as db:
  row=db.get(State,'outreach_policy');policy=row.value if row else {}
 receipt=json.loads((root/'receipts.json').read_text())
 manifest=json.loads((root/'manifest.json').read_text())
 responses=json.loads((root/'responses.json').read_text()).get('responses',[]) if (root/'responses.json').exists() else []
 return {'active':True,'batch_id':receipt['batch_id'],'status':receipt['status'],'limit':receipt['limit'],'planned':len(manifest['emails']),'sent':sum(a['status']=='accepted' for a in receipt['attempts']),'verified':sum(a.get('sent_label_verified',False) for a in receipt['attempts']),'skipped':len(receipt['skipped']),'followups':bool(policy.get('enabled')),'ongoing_policy':policy,'bounces':sum(r['kind']=='bounce' for r in responses),'auto_replies':sum(r['kind']=='auto_reply' for r in responses),'human_replies':sum(r['kind']=='reply' for r in responses),'validation_policy':manifest['validation_policy'],'stop_requested':(root/'STOP').exists(),'attempts':[{'company':a['company'],'status':a['status'],'sent_at':a['attempt_at']} for a in receipt['attempts']]}

def stop():
 with Session() as db:
  ledger.lock(db)
  current=current_batch(db)
  if current:
   row=db.get(State,'manual_batch')
   if not row.value.get('stop_requested'):
    db.add(DomainTransition(domain='campaign',entity_id='manual_batch',from_state='active' if row.value.get('enabled') else 'paused',to_state='stopped',reason='operator_stop'))
   row.value={**row.value,'enabled':False,'stop_requested':True,'stopped_at':now().isoformat()}
   db.commit()
   return {'stop_requested':True,'detail':'A message already being transmitted may complete; remaining sends are stopped.'}
 root=directory()
 if not root:raise HTTPException(404,'No configured campaign')
 (root/'STOP').touch()
 return {'stop_requested':True}
