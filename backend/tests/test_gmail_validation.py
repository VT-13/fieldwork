import asyncio,base64
from datetime import timedelta
from email import message_from_bytes
from types import SimpleNamespace
import pytest
from sqlalchemy import select,func
from app.models import State,Profile,Company,Event,Operation,ActionAttempt,Outreach,now
from app import desk,gmail_validation as validation
from app.core import Blocked
from app.self_test import send
from app.draft_mail import save_mailbox_draft
from app.services import ledger,envelope,reconciliation

@pytest.fixture
def scope(db,monkeypatch):
    monkeypatch.setenv('LIVE_GMAIL_VALIDATION_ENABLED','true');monkeypatch.setenv('RAILWAY_ENVIRONMENT_NAME','staging');monkeypatch.setenv('MANUAL_MODE','true')
    db.add(Profile(id=1,data={'email':'student@example.com','verified':True}))
    c=Company(name='Existing synthetic audit fixture',website='https://example.com',domain='example.com',demo=True);db.add(c);db.commit()
    packets={p:desk.new_packet(db,desk.DeskDraft(subject=validation.PREFIX+('Gmail live verification' if p=='send' else 'Gmail draft verification'),body='Fieldwork staging synthetic '+p+' verification. No company outreach.')) for p in ('send','draft')}
    at=now();v={'version':1,'account_a':'student@example.com','account_b':'reply@example.com','audit_company_id':c.id,'created_at':at.isoformat(),'expires_at':(at+timedelta(hours=1)).isoformat(),'followup_status':'held'}
    for p in packets:v[p+'_packet_id']=packets[p]['id'];v[p+'_hash']=packets[p]['draft_hash']
    db.add(State(key=validation.KEY,value=v));db.commit();return v

class Box:
    token='fake';cfg=SimpleNamespace(mail_provider='gmail',sender_email='student@example.com')
    def __init__(self,db,fail=False):self.db=db;self.fail=fail;self.calls=[];self.sent=None
    async def connect(self):pass
    async def call(self,method,url,**kw):
        self.calls.append((method,url,kw))
        if url.endswith('/messages/send'):
            a=self.db.get(ActionAttempt,ledger.active_delivery.get());op=self.db.get(Operation,a.operation_id)
            envelope.validate(self.db,a,op,kw['json'],self.cfg.sender_email)
            if self.fail:raise TimeoutError()
            self.sent=message_from_bytes(base64.urlsafe_b64decode(kw['json']['raw']))
            return {'id':'sent-id','threadId':'test-thread'}
        if url.endswith('/drafts'):return {'id':'draft-id','message':{'id':'draft-message','threadId':'draft-thread'}}
        if url.endswith('/profile'):return {'emailAddress':'student@example.com','historyId':'101'}
        if url.endswith('/messages'):return {'messages':[{'id':'sent-id'}]}
        if url.endswith('/messages/sent-id'):return sent_message(self.sent)
        raise AssertionError('Unexpected request')

def sent_message(msg):
    return {'id':'sent-id','threadId':'test-thread','labelIds':['SENT'],'internalDate':str(int(now().timestamp()*1000)), 'payload':{'headers':[{'name':k,'value':v} for k,v in msg.items()], 'mimeType':'text/plain','body':{'data':base64.urlsafe_b64encode(msg.get_payload(decode=True)).decode()}}}

def test_validation_send_is_one_scoped_transmission_no_outreach(db,scope):
    b=Box(db);a=asyncio.run(send(db,scope['send_packet_id'],b));assert a['to']==scope['account_b']
    assert b.sent['Subject']==validation.PREFIX+'Gmail live verification'
    assert b.sent['From']==scope['account_a'] and b.sent['To']==scope['account_b']
    assert b.sent.get_payload(decode=True).decode().strip()=='Fieldwork staging synthetic send verification. No company outreach.'
    assert asyncio.run(send(db,scope['send_packet_id'],b))==a
    assert len(b.calls)==1 and db.scalar(select(func.count()).select_from(Outreach))==0
    assert ledger.usage(db,now()-timedelta(days=1))==1

@pytest.mark.parametrize('change',['flag','environment','expired','recipient','body','hash','purpose','pause'])
def test_scope_cannot_relax_default_self_test_fence(db,scope,monkeypatch,change):
    v=db.get(State,validation.KEY)
    if change=='flag':monkeypatch.setenv('LIVE_GMAIL_VALIDATION_ENABLED','false')
    elif change=='environment':monkeypatch.setenv('RAILWAY_ENVIRONMENT_NAME','production')
    elif change=='expired':v.value={**v.value,'expires_at':(now()-timedelta(minutes=1)).isoformat()};db.commit()
    elif change=='recipient':v.value={**v.value,'account_b':'reply@example.com\nBcc: other@example.com'};db.commit()
    elif change=='body':desk.edit_packet(db,scope['send_packet_id'],desk.DeskDraft(subject=validation.PREFIX+'Gmail live verification',body='Changed'))
    elif change=='hash':v.value={**v.value,'send_hash':'changed'};db.commit()
    elif change=='purpose':scope['send_packet_id']=scope['draft_packet_id']
    elif change=='pause':monkeypatch.setenv('DRY_RUN','false')
    b=Box(db)
    with pytest.raises(Blocked):asyncio.run(send(db,scope['send_packet_id'],b))
    assert not b.calls

def test_uncertain_test_never_resends(db,scope):
    b=Box(db,True)
    with pytest.raises(Blocked):asyncio.run(send(db,scope['send_packet_id'],b))
    with pytest.raises(Blocked):asyncio.run(send(db,scope['send_packet_id'],b))
    assert len(b.calls)==1

def test_exact_draft_subject_sender_and_message_receipt(db,scope,monkeypatch):
    monkeypatch.setenv('SENDER_EMAIL',scope['account_a']);b=Box(db)
    result=asyncio.run(save_mailbox_draft(db,scope['draft_packet_id'],scope['draft_hash'],b))
    msg=message_from_bytes(base64.urlsafe_b64decode(b.calls[0][2]['json']['message']['raw']))
    assert msg['Subject']==validation.PREFIX+'Gmail draft verification' and msg['From']==msg['To']==scope['account_a']
    assert result['gmail_id']=='draft-message'
    assert all('/messages/send' not in call[1] for call in b.calls)
    assert ledger.usage(db,now()-timedelta(days=1))==0

def test_live_shape_sent_reconciliation_replay_and_test_reply(db,scope):
    b=Box(db);saved=asyncio.run(send(db,scope['send_packet_id'],b))
    first=asyncio.run(reconciliation.reconcile(db,scope['send_packet_id'],b));second=asyncio.run(reconciliation.reconcile(db,scope['send_packet_id'],b))
    assert first==second and first['status']=='confirmed'
    assert sum(c[1].endswith('/messages/send') for c in b.calls)==1
    assert db.scalar(select(func.count()).select_from(ActionAttempt))==1
    reply={'id':'reply-id','threadId':saved['thread_id'],'labelIds':['INBOX'],'internalDate':str(int(now().timestamp()*1000)),'payload':{'headers':[{'name':'From','value':scope['account_b']},{'name':'To','value':scope['account_a']},{'name':'In-Reply-To','value':saved['message_id']}],'mimeType':'text/plain','body':{'data':base64.urlsafe_b64encode(b'Fieldwork staging controlled reply test.').decode()}}}
    assert validation.ingest(db,reply)['kind']=='test_reply';validation.ingest(db,reply)
    assert db.scalar(select(func.count()).select_from(Event))==1
    assert db.get(State,validation.KEY).value['followup_status']=='cancelled'
    assert db.get(Company,scope['audit_company_id']).stage!='replied'
    assert db.scalar(select(func.count()).select_from(Outreach))==0
    reply['payload']['headers'][0]['value']='unrelated@example.com'
    assert validation.ingest(db,reply) is None
    assert db.scalar(select(func.count()).select_from(Event))==1

def test_reserved_scope_change_rejected_at_transport_fence(db,scope):
    class Tamper(Box):
        async def call(self,method,url,**kw):
            row=self.db.get(State,validation.KEY);row.value={**row.value,'account_b':'third@example.com'};self.db.commit()
            return await super().call(method,url,**kw)
    b=Tamper(db)
    with pytest.raises(Blocked):asyncio.run(send(db,scope['send_packet_id'],b))
    assert b.sent is None

def test_incremental_sync_reads_only_test_body_and_replays_checkpoint(db,scope):
    from app.responses import sync_session
    b=Box(db);saved=asyncio.run(send(db,scope['send_packet_id'],b))
    db.add(State(key='response_sync',value={'account':scope['account_a'],'history_id':'100','status':'ok'}));db.commit()
    reply={'id':'reply-id','threadId':saved['thread_id'],'labelIds':['INBOX'],'internalDate':str(int(now().timestamp()*1000)),'payload':{'headers':[{'name':'From','value':scope['account_b']},{'name':'To','value':scope['account_a']},{'name':'In-Reply-To','value':saved['message_id']}],'mimeType':'text/plain','body':{'data':base64.urlsafe_b64encode(b'Fieldwork staging controlled reply test.').decode()}}}
    class Reader(Box):
        async def call(self,method,url,**kw):
            self.calls.append((method,url,kw))
            if url.endswith('/profile'):return {'emailAddress':scope['account_a'],'historyId':'102'}
            if url.endswith('/history'):
                if kw['params']['startHistoryId']=='102':return {'historyId':'102'}
                return {'historyId':'102','history':[{'messagesAdded':[{'message':{'id':'unrelated'}},{'message':{'id':'reply-id'}}]}]}
            if url.endswith('/messages/unrelated'):
                assert kw['params']['format']=='metadata'
                return {'id':'unrelated','threadId':'other-thread','payload':{'headers':[{'name':'From','value':'private@example.com'},{'name':'To','value':scope['account_a']}]}}
            if url.endswith('/messages/reply-id'):return reply
            raise AssertionError('No mailbox search or unrelated body request allowed')
    reader=Reader(db)
    assert asyncio.run(sync_session(db,reader))['status']=='ok'
    assert asyncio.run(sync_session(db,reader))['status']=='ok'
    assert db.get(State,'response_sync').value['history_id']=='102'
    assert db.scalar(select(func.count()).select_from(Event))==1
    assert sum(c[1].endswith('/messages/reply-id') and c[2]['params']['format']=='full' for c in reader.calls)==1
    assert not db.get(State,'response:unrelated')
