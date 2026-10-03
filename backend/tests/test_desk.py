import base64
from email import message_from_string
import pytest
from app import desk,worker
from app.core import Blocked,reserve
from app.models import Profile,Job,Usage,State
from app.schemas import ProfileInput
from app.draft_mail import save_mailbox_draft
from sqlalchemy import select,func

@pytest.fixture
def packet(db):
    db.add(Profile(id=1,data=ProfileInput(name='Student',email='student@example.com').model_dump()));db.commit()
    return desk.new_packet(db,desk.DeskDraft(company='Example',subject='Small dashboard question',body='Hi, I noticed your dashboard. Could I help with a small project?',evidence='https://example.com: dashboard description',fictional=True))

def test_manual_mode_blocks_charges_before_reservation(db,monkeypatch):
    monkeypatch.setenv('MANUAL_MODE','true')
    with pytest.raises(Blocked,match='paid API calls'): reserve(db,'llm',.10)
    assert db.scalar(select(func.count()).select_from(Usage))==0

async def test_manual_mode_blocks_legacy_pipeline(db,monkeypatch):
    monkeypatch.setenv('MANUAL_MODE','true')
    with pytest.raises(Blocked,match='Manual mode'):
        await worker.execute(db,Job(kind='pipeline',payload={'id':'any'},dedupe_key='test'))

def test_actual_detector_result_not_local_fake_score(db,packet):
    assert packet['detector'] is None
    assert 'probability' not in packet['style']
    result=desk.detector_result(db,packet['id'],desk.DetectorInput(draft_hash=packet['draft_hash'],result='Highly confident AI',ai_probability=100))
    assert result['detector']['ai_probability']==100
    assert result['status']=='needs_review'

def test_edit_invalidates_signoff_and_detector(db,packet):
    desk.detector_result(db,packet['id'],desk.DetectorInput(draft_hash=packet['draft_hash'],result='AI',ai_probability=100))
    desk.signoff(db,packet['id'],desk.SignoffInput(draft_hash=packet['draft_hash'],facts_checked=True,sounds_like_me=True,recipient_checked=True,detector_reviewed=True))
    updated=desk.edit_packet(db,packet['id'],desk.DeskDraft(subject=packet['subject'],body='A different message',company='Example'))
    assert updated['detector'] is None and updated['signoff'] is None
    assert updated['status']=='needs_review' and len(updated['history'])==1
    with pytest.raises(Blocked,match='Draft changed'):
        desk.detector_result(db,packet['id'],desk.DetectorInput(draft_hash=packet['draft_hash'],result='old result'))

def test_signoff_requires_all_checks_and_real_report(db,packet):
    with pytest.raises(Blocked,match='actual detector'):
        desk.signoff(db,packet['id'],desk.SignoffInput(draft_hash=packet['draft_hash'],facts_checked=True,sounds_like_me=True,recipient_checked=True,detector_reviewed=True))

def test_eml_only_addresses_student_and_is_unsent(db,packet):
    msg=message_from_string(desk.eml(db,packet['id']))
    assert msg['To']=='student@example.com'
    assert msg['Subject'].startswith('[DRY RUN]') and msg['X-Unsent']=='1'
    assert not msg.get('Cc') and not msg.get('Bcc')

def test_header_injection_is_rejected(db):
    with pytest.raises(Blocked): desk.new_packet(db,desk.DeskDraft(subject='Hi\nBcc: stranger@example.com',body='Test'))

class Box:
    token='test'
    def __init__(self,fail=False):self.calls=[];self.fail=fail
    async def call(self,method,url,**kw):
        self.calls.append((method,url,kw))
        if self.fail:raise TimeoutError('unknown')
        return {'id':'draft123'}

@pytest.mark.parametrize('provider',['gmail','outlook'])
async def test_mailbox_save_never_uses_send_endpoint(db,packet,monkeypatch,provider):
    monkeypatch.setenv('SENDER_EMAIL','student@example.com');monkeypatch.setenv('MAIL_PROVIDER',provider)
    box=Box()
    result=await save_mailbox_draft(db,packet['id'],packet['draft_hash'],box)
    assert result['status']=='saved' and result['to']=='student@example.com'
    assert len(box.calls)==1
    method,url,payload=box.calls[0]
    assert method=='POST' and 'send' not in url.lower()
    if provider=='gmail':
        raw=payload['json']['message']['raw'];msg=message_from_string(base64.urlsafe_b64decode(raw).decode())
        assert msg['To']=='student@example.com'
    else:
        assert payload['json']['toRecipients']==[{'emailAddress':{'address':'student@example.com'}}]
    await save_mailbox_draft(db,packet['id'],packet['draft_hash'],box)
    assert len(box.calls)==1

async def test_uncertain_mailbox_save_cannot_duplicate(db,packet,monkeypatch):
    monkeypatch.setenv('SENDER_EMAIL','student@example.com')
    box=Box(fail=True)
    with pytest.raises(Blocked,match='uncertain'):await save_mailbox_draft(db,packet['id'],packet['draft_hash'],box)
    with pytest.raises(Blocked,match='uncertain'):await save_mailbox_draft(db,packet['id'],packet['draft_hash'],box)
    assert len(box.calls)==1

async def test_cannot_save_to_a_different_mailbox(db,packet,monkeypatch):
    monkeypatch.setenv('SENDER_EMAIL','someoneelse@example.com')
    box=Box()
    with pytest.raises(Blocked,match='matches your profile'):await save_mailbox_draft(db,packet['id'],packet['draft_hash'],box)
    assert not box.calls
