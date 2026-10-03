from contextlib import contextmanager
from app import campaign
from app.models import State

def test_current_batch_counts_confirmed_receipts_and_stops_scope(db,ready,monkeypatch,tmp_path):
 _,_,row=ready
 db.add(State(key='manual_batch',value={'enabled':True,'outreach_ids':[row.id]}))
 db.add(State(key='manual_batch_progress',value={'status':'running','results':[]}))
 db.merge(State(key='outreach_policy',value={'enabled':False}));db.commit()
 @contextmanager
 def session():yield db
 monkeypatch.setattr(campaign,'Session',session)
 monkeypatch.setenv('LIVE_BATCH_DIRECTORY',str(tmp_path))
 assert campaign.status()['verified']==0
 assert campaign.status()['can_stop'] is True
 row.status='sent';db.commit()
 assert campaign.status()['verified']==0 # Sent status alone is not receipt confirmation.
 db.get(State,'manual_batch_progress').value={'status':'running','results':[{'outreach_id':row.id,'sent_verified':True}]};db.commit()
 assert campaign.status()['verified']==1
 campaign.stop()
 assert db.get(State,'manual_batch').value['enabled'] is False
 assert campaign.status()['stop_requested'] is True
 assert not (tmp_path/'STOP').exists() # Never mutate the historical batch.
