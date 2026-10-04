from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import json
import pytest
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
from app.models import Operation,ActionAttempt,Outreach,State,DomainTransition,now
from app.core import Blocked
from app.services import ledger,policy
from app.domain.states import transition


def test_transition_rejects_send_without_approval(db,ready):
    r=ready[2];r.status='draft';db.commit()
    with pytest.raises(Blocked,match='Invalid message'):transition(db,r,'sending')
    transition(db,r,'approved',reason='reviewed');transition(db,r,'sending',reason='reserved');db.commit()
    assert len(list(db.scalars(select(DomainTransition))))==2
    with pytest.raises(Blocked):transition(db,r,'draft')


def test_ledger_records_denial_then_explicit_retry_link(db):
    def denied():raise Blocked('paused')
    with pytest.raises(Blocked):ledger.claim(db,'operation','research','mock',denied)
    a,replay=ledger.claim(db,'operation','research','mock',lambda:{'version':'test'})
    assert not replay and a.retry_of and a.number==2
    assert db.get(ActionAttempt,a.retry_of).authorized is False
    ledger.finish(db,a,'succeeded',receipt={'cache_key':'result-1'})
    b,replay=ledger.claim(db,'operation','research','mock',lambda:pytest.fail('No replay authorization needed'))
    assert replay and b.id==a.id


def test_failed_retry_requires_explicit_intent(db):
    a,_=ledger.claim(db,'research','research','mock',lambda:{})
    ledger.finish(db,a,'failed',reason='provider_rejected')
    with pytest.raises(Blocked,match='explicit retry'):ledger.claim(db,'research','research','mock',lambda:{})
    b,_=ledger.claim(db,'research','research','mock',lambda:{},retry=True)
    assert b.retry_of==a.id


def test_unknown_is_never_retried_even_explicitly(db):
    a,_=ledger.claim(db,'send:one','company_send','mock',lambda:{})
    ledger.finish(db,a,'unknown')
    with pytest.raises(Blocked,match='uncertain'):ledger.claim(db,'send:one','company_send','mock',lambda:{},retry=True)


def test_global_unknown_blocks_different_approved_message(db,ready,monkeypatch):
    monkeypatch.setenv("DRY_RUN","false")
    c,ct,r=ready
    db.add(Outreach(company_id=c.id,contact_id=ct.id,sequence=2,status='unknown',attempts=1,sent_at=now()-timedelta(days=2)))
    db.commit()
    with pytest.raises(Blocked,match='Uncertain'):policy.company(db,r,now(),'worker')


def test_policy_pause_audited_and_blocks_queued_send(db,ready,monkeypatch):
    monkeypatch.setenv('DRY_RUN','false')
    policy.set_paused(db,False)
    with pytest.raises(Blocked,match='paused'):policy.company(db,ready[2],now(),'worker')
    assert db.scalar(select(DomainTransition).where(DomainTransition.domain=='campaign')).to_state=='paused'


def test_idempotent_claim_across_independent_connections(tmp_path):
    from app.db import Base
    engine=create_engine('sqlite:///'+str(tmp_path/'claim.sqlite'),connect_args={'timeout':10})
    Base.metadata.create_all(engine)
    barrier=Barrier(2)
    def compete(_):
        with Session(engine,expire_on_commit=False) as db:
            barrier.wait()
            try:
                a,_=ledger.claim(db,'same-send','company_send','mock',lambda:{})
                return a.id
            except Blocked:return 'blocked'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(compete,range(2)))
    assert results.count('blocked')==1
    with Session(engine) as db:assert db.scalar(select(func.count()).select_from(ActionAttempt))==1
    engine.dispose()


def test_transport_rejects_unreserved_send(db,ready):
    import asyncio
    from app.mail import Mailbox
    with pytest.raises(Blocked,match='reservation'):
        asyncio.run(Mailbox().send(db,ready[2],ready[1],None))
    with pytest.raises(Blocked,match='reservation'):
        asyncio.run(Mailbox().call('POST','https://gmail.googleapis.com/gmail/v1/users/me/messages/send',json={}))


def test_receipts_are_idempotent_linked_evidence_without_contents(db,ready,tmp_path):
    from app.services.receipt_import import import_receipts
    r=ready[2]
    p=tmp_path/'receipt.jsonl'
    original={'outreach_id':r.id,'gmail_id':'provider-123','thread_id':'thread-123','at':'2026-09-29T16:00:00+00:00','sent_verified':True,'email':'private@example.com','subject':'Sensitive subject'}
    p.write_text(json.dumps(original)+'\n');raw=p.read_bytes()
    assert not import_receipts(db,p)['applied']
    import_receipts(db,p,apply=True);import_receipts(db,p,apply=True)
    a=db.scalar(select(ActionAttempt))
    assert a.receipt['gmail_id']=='provider-123' and a.receipt['at']==original['at']
    assert 'email' not in a.receipt and 'subject' not in a.receipt and a.network_units==0
    assert db.scalar(select(func.count()).select_from(ActionAttempt))==1
    assert p.read_bytes()==raw and r.attempts==0


def test_paused_self_test_has_own_recipient_policy_and_quota(db,ready,monkeypatch):
    from app.self_test import send
    from app.desk import new_packet,DeskDraft
    from test_self_test import Box
    import asyncio
    policy.set_paused(db,False)
    packet=new_packet(db,DeskDraft(subject='Self test',body='Private test'))
    b=Box();asyncio.run(send(db,packet['id'],b))
    assert len(b.calls)==1 and db.get(State,'outreach_policy').value['enabled'] is False
    assert db.scalar(select(Operation).where(Operation.kind=='self_test')).status=='succeeded'


def test_changed_key_identity_cannot_replay_another_result(db):
    a,_=ledger.claim(db,'same','research','mock',lambda:{},entity_id='a')
    ledger.finish(db,a,'succeeded')
    with pytest.raises(Blocked,match='different operation'):
        ledger.claim(db,'same','research','mock',lambda:{},entity_id='b')


async def test_fresh_unthreaded_reply_blocks_followup(db,ready,monkeypatch):
    from app.services.email_provider import MailboxProvider
    from app.services.delivery import send_company
    from test_workflow import FakeMailbox
    monkeypatch.setenv('DRY_RUN','false');monkeypatch.setenv('SENDER_EMAIL','student@example.com')
    c,ct,first=ready;first.provider_id='original-id';first.status='sent';first.sent_at=now()-timedelta(days=8);first.thread_id='original';first.message_id='<original>'
    follow=Outreach(company_id=c.id,contact_id=ct.id,sequence=1,status='approved',subject=first.subject,body='New useful idea',evidence_ids=first.evidence_ids,review={**first.review,'adds_new_value':True})
    db.add(follow);db.commit()
    class ReplyBox(FakeMailbox):
        async def call(self,method,url,**kwargs):
            q=kwargs.get('params',{}).get('q','')
            return {'messages':[{'id':'unthreaded'}]} if q==f'in:anywhere from:{ct.email}' else await super().call(method,url,**kwargs)
    box=ReplyBox()
    with pytest.raises(Blocked,match='reply'):await send_company(db,follow.id,mode='worker',provider=MailboxProvider(box))
    assert box.sent==0


async def test_pause_changed_during_preflight_prevents_delivery(db,ready,monkeypatch):
    from app.services.delivery import send_company
    from app.services.contracts import DeliveryReceipt
    monkeypatch.setenv('DRY_RUN','false')
    class Provider:
        sender='student@example.com';name='gmail';sent=0
        async def connect(self):pass
        async def check_conversation(self,*args):policy.set_paused(db,False)
        async def deliver(self,*args):self.sent+=1;return DeliveryReceipt('id')
    p=Provider()
    with pytest.raises(Blocked,match='paused'):await send_company(db,ready[2].id,mode='worker',provider=p)
    assert p.sent==0 and ready[2].attempts==0
    assert db.scalar(select(ActionAttempt).join(Operation).where(Operation.kind=='company_send')).status=='blocked'


async def test_confirmation_failure_retains_acceptance_and_prevents_resend(db,ready,monkeypatch):
    from app.services.delivery import send_company
    from app.services.contracts import DeliveryReceipt
    monkeypatch.setenv('DRY_RUN','false')
    class Provider:
        sender='student@example.com';name='gmail';sent=0
        async def connect(self):pass
        async def check_conversation(self,*args):pass
        async def deliver(self,*args):self.sent+=1;return DeliveryReceipt('provider-id','thread-id')
        async def confirm(self,*args):raise TimeoutError()
    p=Provider();result=await send_company(db,ready[2].id,mode='worker',provider=p)
    assert result['provider_id']=='provider-id' and result['confirmation_pending']
    assert ledger.unresolved(db)
    assert (await send_company(db,ready[2].id,mode='worker',provider=p))['confirmation_pending']
    assert p.sent==1
    ledger.reconcile_sent(db,ready[2],'provider-id','thread-id',ready[2].message_id)
    assert not ledger.unresolved(db)


def test_source_integrity_detects_runtime_edit_or_missing_file(tmp_path):
    import importlib.util,hashlib
    from pathlib import Path
    script=Path(__file__).resolve().parents[2]/'scripts/source_manifest.py'
    spec=importlib.util.spec_from_file_location('source_manifest',script)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    p=tmp_path/'entry.py';p.write_text('original')
    manifest={'files':{'entry.py':hashlib.sha256(p.read_bytes()).hexdigest()}}
    assert module.verify(tmp_path,manifest)==[]
    p.write_text('runtime-only edit');assert module.verify(tmp_path,manifest)==['entry.py']
    p.unlink();assert module.verify(tmp_path,manifest)==['entry.py']


def test_reconciled_runtime_api_surface_is_preserved():
    from app.main import app
    paths=app.openapi()['paths']
    for path in ['/campaign','/campaign/stop','/outreach-policy','/responses','/responses/sync','/responses/{id}','/desk/{id}/self-test']:
        assert path in paths


async def test_message_change_during_preflight_invalidates_authorization(db,ready,monkeypatch):
    from app.services.delivery import send_company
    monkeypatch.setenv('DRY_RUN','false')
    class Provider:
        sender='student@example.com';name='gmail';sent=0
        async def connect(self):pass
        async def check_conversation(self,*args):ready[2].body='Changed without review';db.commit()
        async def deliver(self,*args):self.sent+=1;raise AssertionError('Must not send')
    p=Provider()
    with pytest.raises(Blocked,match='changed during preflight'):await send_company(db,ready[2].id,mode='worker',provider=p)
    assert p.sent==0


def test_self_test_cap_is_shared_with_company_attempts(db,ready,monkeypatch):
    monkeypatch.setenv('DAILY_SEND_LIMIT','1')
    a,_=ledger.claim(db,'existing','self_test','mock',lambda:{})
    ledger.finish(db,a,'succeeded')
    with pytest.raises(Blocked,match='cap'):policy.own_mailbox(db,'student@example.com','student@example.com','self_test')


def test_skipped_operation_has_no_external_attempt(db):
    # Explicit terminal skipped work is recorded without invoking an adapter.
    op=Operation(idempotency_key='skip',kind='research',entity_id='c',provider='local',status='pending')
    db.add(op);db.flush();transition(db,op,'skipped',domain='operation',reason='insufficient_provenance');db.commit()
    assert db.scalar(select(func.count()).select_from(ActionAttempt))==0
    with pytest.raises(Blocked):ledger.claim(db,'skip','research','local',lambda:{},entity_id='c')


def test_paid_prohibition_applies_even_if_manual_flag_is_disabled(db,ready,monkeypatch):
    from app.core import reserve
    monkeypatch.setenv('MANUAL_MODE','false')
    p=db.get(State,'outreach_policy');p.value={**p.value,'paid_services_authorized':False};db.commit()
    with pytest.raises(Blocked,match='paid API calls'):reserve(db,'llm',0.10,ready[0].id)


def test_source_integrity_detects_unmanifested_new_route(tmp_path):
    import importlib.util
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('source_manifest',Path(__file__).resolve().parents[2]/'scripts/source_manifest.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    p=tmp_path/'frontend/app/unreviewed/route.ts';p.parent.mkdir(parents=True);p.write_text('export {}')
    assert module.verify(tmp_path,{'files':{}})==['unmanifested:frontend/app/unreviewed/route.ts']
