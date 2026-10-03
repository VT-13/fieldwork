import asyncio,base64
from types import SimpleNamespace
import pytest
from app.self_test import send
from app.desk import new_packet,DeskDraft
from app.core import Blocked
class Box:
 cfg=SimpleNamespace(mail_provider='gmail',sender_email='student@example.com')
 def __init__(self,fail=False):self.calls=[];self.fail=fail
 async def connect(self):pass
 async def call(self,method,url,**kw):
  self.calls.append(kw)
  if self.fail:raise RuntimeError('network')
  return {'id':'test','threadId':'thread'}
def test_self_only_idempotent(db,ready):
 p=new_packet(db,DeskDraft(subject='Test',body='Hello',company='Company'))
 b=Box();asyncio.run(send(db,p['id'],b));asyncio.run(send(db,p['id'],b))
 assert len(b.calls)==1
 text=base64.urlsafe_b64decode(b.calls[0]['json']['raw']).decode()
 assert 'To: student@example.com' in text and '[DRY RUN]' in text
 assert 'X-Unsent' not in text

def test_unknown_no_retry(db,ready):
 p=new_packet(db,DeskDraft(subject='Test',body='Hello'))
 b=Box(True)
 with pytest.raises(Blocked):asyncio.run(send(db,p['id'],b))
 with pytest.raises(Blocked):asyncio.run(send(db,p['id'],b))
 assert len(b.calls)==1

def test_wrong_account_blocked(db,ready):
 p=new_packet(db,DeskDraft(subject='Test',body='Hello'));b=Box();b.cfg=SimpleNamespace(mail_provider='gmail',sender_email='other@example.com')
 with pytest.raises(Blocked):asyncio.run(send(db,p['id'],b))
 assert not b.calls
