from datetime import datetime,timedelta,timezone
import pytest
from app.scheduled_send import guards
from app.models import State,Outreach,Evidence
from app.core import Blocked
AT=datetime(2026,9,25,16,tzinfo=timezone.utc)
@pytest.fixture
def scheduled(db,ready):
 c,ct,row=ready;c.research={'city':'Rocklin'};ct.source='https://example.com/contact';ct.validated_at=AT
 db.add(Evidence(id='fact',company_id=c.id,url='https://example.com',fact='Confirmed company service',quote='',category='service'));row.evidence_ids=['fact'];row.due_at=AT;row.review={**row.review,'grounded':True,'claims_supported':True,'non_generic':True,'names_correct':True,'non_spammy':True}
 db.merge(State(key='outreach_policy',value={'enabled':True,'max_followups_per_company':1}));db.commit();return c,ct,row

def test_due_initial_allowed(db,scheduled):assert guards(db,scheduled[2],AT)[0]==scheduled[0]
def test_pause_blocks(db,scheduled):
 db.get(State,'outreach_policy').value={'enabled':False};db.commit()
 with pytest.raises(Blocked,match='paused'):guards(db,scheduled[2],AT)
def test_weekend_blocks(db,scheduled):
 with pytest.raises(Blocked,match='business hours'):guards(db,scheduled[2],AT+timedelta(days=1))
def test_uncertain_cannot_retry(db,scheduled):
 scheduled[2].status='unknown';scheduled[2].attempts=1
 with pytest.raises(Blocked,match='unattempted'):guards(db,scheduled[2],AT)
def test_followup_too_early(db,scheduled):
 c,ct,first=scheduled;first.status='sent';first.sent_at=AT-timedelta(days=6);first.thread_id='thread';first.message_id='<id>'
 follow=Outreach(company_id=c.id,contact_id=ct.id,sequence=1,status='approved',due_at=AT,subject='Follow-up',body='New proposal',review={**first.review,'adds_new_value':True},evidence_ids=['fact'])
 db.add(follow);db.commit()
 with pytest.raises(Blocked,match='Seven full days'):guards(db,follow,AT)
def test_auto_reply_stops(db,scheduled):
 scheduled[0].stage='auto_reply'
 with pytest.raises(Blocked,match='stopped'):guards(db,scheduled[2],AT)


def test_pacific_day_does_not_count_previous_evening(db,scheduled):
 c,ct,_=scheduled
 db.add(Outreach(company_id=c.id,contact_id=ct.id,sequence=2,status='sent',attempts=25,sent_at=AT.replace(hour=4)))
 db.commit()
 assert guards(db,scheduled[2],AT)

def test_total_daily_cap_includes_uncertain_attempts(db,scheduled):
 c,ct,_=scheduled
 db.add(Outreach(company_id=c.id,contact_id=ct.id,sequence=2,status='unknown',attempts=25,sent_at=AT-timedelta(hours=1)))
 db.commit()
 with pytest.raises(Blocked,match='Daily total cap'):guards(db,scheduled[2],AT)

def test_explicit_batch_scoped_and_expiring(db,scheduled):
 c,ct,row=scheduled;at=AT+timedelta(hours=12)
 db.get(State,'outreach_policy').value={'enabled':False}
 db.add(State(key='manual_batch',value={'enabled':True,'outreach_ids':[row.id],'expires_at':(at+timedelta(hours=1)).isoformat()}));db.commit()
 assert guards(db,row,at)
 with pytest.raises(Blocked,match='paused'):guards(db,row,at+timedelta(hours=2))
 db.get(State,'manual_batch').value={'enabled':True,'outreach_ids':['other'],'expires_at':(at+timedelta(hours=1)).isoformat()};db.commit()
 with pytest.raises(Blocked,match='paused'):guards(db,row,at)

def test_expanded_region_requires_policy(db,scheduled):
 c,ct,row=scheduled;c.research={'city':'Roseville'}
 with pytest.raises(Blocked,match='city evidence'):guards(db,row,AT)
 p=db.get(State,'outreach_policy');p.value={**p.value,'allowed_cities':['Rocklin','Roseville']};db.commit()
 assert guards(db,row,AT)

def test_manual_stop_cannot_fall_back_to_recurring_policy(db,scheduled):
 row=scheduled[2]
 db.add(State(key='manual_batch',value={'enabled':False,'stop_requested':True,'outreach_ids':[row.id]}));db.commit()
 with pytest.raises(Blocked,match='stopped by user'):guards(db,row,AT)
