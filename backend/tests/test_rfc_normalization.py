import asyncio,base64
from datetime import timedelta
from types import SimpleNamespace
import pytest
from sqlalchemy import select,func
from app.models import ActionAttempt,now
from app.services import ledger,reconciliation
from app.responses import ingest
from app.services.email_provider import MailboxProvider
from app.core import Blocked

@pytest.fixture
def accepted(db,ready):
    row=ready[2];row.status='sent';row.sent_at=now();row.message_id='<reserved@example.com>';row.provider_id='accepted-id';row.thread_id='accepted-thread';db.commit()
    attempt,_=ledger.claim(db,'send:'+row.id,'company_send','gmail',lambda:{},entity_id=row.id,outreach_id=row.id)
    ledger.finish(db,attempt,'succeeded',receipt={'provider_id':row.provider_id,'thread_id':row.thread_id,'message_id':row.message_id,'sent_verified':None})
    return row,attempt

def message(row,ct):
    return {'id':row.provider_id,'threadId':row.thread_id,'internalDate':str(int(now().timestamp()*1000)),'labelIds':['SENT'],'payload':{'headers':[{'name':k,'value':v} for k,v in {'From':'student@example.com','To':ct.email,'Subject':row.subject,'Message-ID':'<provider-generated@mail.gmail.com>'}.items()],'body':{'data':base64.urlsafe_b64encode(row.body.encode()).decode()}}}

class Box:
    token='fake';cfg=SimpleNamespace(sender_email='student@example.com',mail_provider='gmail')
    def __init__(self,msg):self.msg=msg;self.calls=[]
    async def call(self,method,url,**kw):
        self.calls.append((method,url,kw));assert method=='GET'
        if url.endswith('/profile'):return {'emailAddress':'student@example.com','historyId':'100'}
        if url.endswith('/messages'):return {'messages':[{'id':self.msg['id']}]}
        return self.msg

def test_company_receipt_rfc_alias_preserves_identity_and_replays_without_send(db,ready,accepted):
    row,attempt=accepted;b=Box(message(row,ready[1]));original=row.message_id
    first=asyncio.run(reconciliation.reconcile(db,row.id,b));second=asyncio.run(reconciliation.reconcile(db,row.id,b))
    assert first==second and first['status']=='confirmed'
    assert row.message_id=='<provider-generated@mail.gmail.com>'
    assert attempt.receipt['reserved_message_id']==original and attempt.receipt['message_id']==row.message_id
    assert attempt.receipt['sent_verified'] is True and db.scalar(select(func.count()).select_from(ActionAttempt))==1
    assert all(c[0]=='GET' for c in b.calls)

@pytest.mark.parametrize('field',['id','threadId','body','recipient','label'])
def test_receipt_alias_refuses_conflicting_evidence(db,ready,accepted,field):
    row,attempt=accepted;msg=message(row,ready[1]);original=row.message_id
    if field in ('id','threadId'):msg[field]='other'
    elif field=='body':msg['payload']['body']['data']=base64.urlsafe_b64encode(b'Other').decode()
    elif field=='label':msg['labelIds']=[]
    else:msg['payload']['headers'][1]['value']='other@example.com'
    with pytest.raises(Blocked):asyncio.run(reconciliation.reconcile(db,row.id,Box(msg)))
    assert row.message_id==original and not attempt.receipt.get('sent_verified')

def test_unknown_without_accepted_receipt_cannot_alias(db,ready,accepted):
    row,attempt=accepted;row.provider_id='';row.thread_id='';row.status='unknown';attempt.status='unknown';db.commit()
    msg=message(row,ready[1]);msg.update(id='candidate',threadId='candidate-thread')
    result=asyncio.run(reconciliation.reconcile(db,row.id,Box(msg)))
    assert result['status']=='held' and row.message_id=='<reserved@example.com>'

def test_current_sent_ingestion_normalizes_accepted_rfc_for_followup_headers(db,ready,accepted):
    row,attempt=accepted
    ingest(db,message(row,ready[1]),[row],{ready[1].id:ready[1]},'student@example.com')
    assert row.message_id=='<provider-generated@mail.gmail.com>' and attempt.receipt['reserved_message_id']=='<reserved@example.com>'
    assert attempt.receipt['sent_verified'] is True

def test_confirmation_uses_full_canonical_evidence_not_sent_label_alone(db,ready,accepted):
    row,attempt=accepted;b=Box(message(row,ready[1]));p=MailboxProvider(b)
    assert asyncio.run(p.confirm_message(db,row,None)) is True
    assert row.message_id=='<provider-generated@mail.gmail.com>'
    assert all(c[2].get('params',{}).get('format')!='minimal' for c in b.calls)
