from datetime import timedelta
import pytest
import httpx
from sqlalchemy import select,func
from app.config import settings,Settings
from app.core import profile_fingerprint,Blocked,public_url,distance,reserve,cached,cache_put,record_event,score_company
from app.models import Outreach,Event,Suppression,Contact,Usage,now,Profile,Company,Evidence,Job,State
from app import mail,pipeline,providers
from app.schemas import DraftResult,ReviewResult
from app.intelligence.schemas import GeneratedClaims,Plan
from app.worker import enqueue

@pytest.mark.parametrize("url",["http://example.com","https://localhost","https://127.0.0.1","https://169.254.169.254/latest","https://internal.local","https://user:pass@example.com","https://example.com:8443"])
def test_nonpublic_urls_rejected(url):
    with pytest.raises(Blocked): public_url(url)

def test_domain_canonicalization_and_distance():
    assert public_url("https://www.example.com/about")=="example.com"
    assert distance(38.79,-121.23,38.79,-121.23)==0
    assert 8<distance(38.79,-121.23,38.65,-121.23)<11

def test_budget_and_cache(db,ready,monkeypatch):
    monkeypatch.setenv("DAILY_BUDGET_USD","0.10")
    reserve(db,"test",.08,ready[0].id)
    with pytest.raises(Blocked): reserve(db,"test",.03,ready[0].id)
    assert db.scalar(select(func.count()).select_from(Usage))==1
    cache_put(db,"page",{"fact":"same"})
    assert cached(db,"page")=={"fact":"same"}

def test_unknowns_do_not_get_friendly_scores(db,ready):
    c=ready[0]
    c.distance_miles=None
    score_company(c,False,[])
    assert c.score_factors["proximity"]==0
    assert c.score_factors["internship_history"]==0
    assert c.score_factors["student_friendliness"]==0
    assert c.score<=10

@pytest.mark.parametrize("kind",["reply","positive","negative","bounce","opt_out","interview","offer"])
def test_reply_stops_all_pending_followups(db,ready,kind):
    c,contact,initial=ready
    follow=Outreach(company_id=c.id,contact_id=contact.id,sequence=1,status="approved")
    db.add(follow);db.commit()
    record_event(db,c,kind,"evt-1")
    record_event(db,c,kind,"evt-1")
    assert follow.status=="cancelled"
    assert initial.status=="cancelled"
    assert db.scalar(select(func.count()).select_from(Event))==1
    if kind in {"bounce","opt_out","negative"}: assert db.get(Suppression,contact.email)

class FakeMailbox:
    token="valid"
    def __init__(self,error=None,messages=None): self.error=error;self.sent=0;self.items=messages or []
    async def messages(self,since): return self.items
    async def call(self,method,url,**kwargs):return {"messages":[],"labelIds":["SENT"]}
    async def send(self,db,row,contact,original):
        self.sent+=1
        if self.error: raise self.error
        return "provider-id","thread-id"

async def test_dry_run_never_calls_mailbox(db,ready):
    mailbox=FakeMailbox()
    with pytest.raises(Blocked,match="DRY_RUN"): await mail.send_one(db,ready[2],mailbox)
    assert mailbox.sent==0

@pytest.fixture
def live(monkeypatch):
    monkeypatch.setenv("DRY_RUN","false")
    monkeypatch.setenv("SENDER_EMAIL","student@example.com")

async def test_send_is_idempotent_and_persisted(db,ready,live):
    mailbox=FakeMailbox()
    await mail.send_one(db,ready[2],mailbox)
    assert ready[2].status=="sent" and ready[2].provider_id=="provider-id"
    with pytest.raises(Blocked): await mail.send_one(db,ready[2],mailbox)
    assert mailbox.sent==1

async def test_timeout_is_unknown_not_retried(db,ready,live):
    box=FakeMailbox(error=httpx.ReadTimeout("uncertain"))
    with pytest.raises(Blocked,match="uncertain"): await mail.send_one(db,ready[2],box)
    assert ready[2].status=="unknown" and ready[2].attempts==1
    with pytest.raises(Blocked): await mail.send_one(db,ready[2],box)
    assert box.sent==1

async def test_quota_counts_uncertain_attempts(db,ready,live,monkeypatch):
    monkeypatch.setenv("DAILY_SEND_LIMIT","1")
    other=Outreach(company_id=ready[0].id,contact_id=ready[1].id,sequence=1,status="unknown",sent_at=now(),attempts=1)
    db.add(other);db.commit()
    with pytest.raises(Blocked,match="Daily total"): await mail.send_one(db,ready[2],FakeMailbox())

async def test_stale_or_catchall_validation_blocks(db,ready,live):
    ready[1].validated_at=now()-timedelta(days=8)
    with pytest.raises(Blocked,match="[Ff]resh"): await mail.send_one(db,ready[2],FakeMailbox())
    ready[1].validated_at=now();ready[1].validation="risky"
    with pytest.raises(Blocked,match="validation"): await mail.send_one(db,ready[2],FakeMailbox())

async def test_reply_detected_immediately_before_followup(db,ready,live):
    c,contact,first=ready
    first.status="sent";first.sent_at=now()-timedelta(days=7);first.thread_id="thread";first.message_id="<initial@example.com>"
    follow=Outreach(company_id=c.id,contact_id=contact.id,sequence=1,status="approved",subject="Follow-up",body="A new idea",evidence_ids=first.evidence_ids,review={**first.review,"adds_new_value":True})
    db.add(follow);db.commit()
    box=FakeMailbox(messages=[{"id":"reply1","thread":"thread","headers":{"from":contact.email,"subject":"Re: project"},"body":"Sure, let's talk"}])
    with pytest.raises(Blocked,match="stopped"): await mail.send_one(db,follow,box)
    assert box.sent==0 and c.stage=="replied" and follow.status=="cancelled"

async def test_unknown_send_reconciles_from_sent_mail(db,ready,live):
    row=ready[2];row.status="unknown";row.message_id="<test@example.com>";row.sent_at=now()
    db.commit()
    box=FakeMailbox(messages=[{"id":"confirmed","thread":"thread1","headers":{"from":"student@example.com","message-id":row.message_id},"body":row.body,"sent_verified":True}])
    await mail.sync_mailbox(db,box)
    assert row.status=="sent" and row.provider_id=="confirmed"

async def test_dsn_matches_message_not_random_bounce(db,ready,live):
    row=ready[2];row.status="sent";row.message_id="<unique@example.com>";db.commit()
    box=FakeMailbox(messages=[{"id":"bounce1","thread":"","headers":{"from":"mailer-daemon@example.net"},"body":"Delivery failed <unique@example.com>"}])
    await mail.sync_mailbox(db,box)
    assert ready[0].stage=="bounce" and db.get(Suppression,ready[1].email)

async def test_regeneration_is_bounded_and_bad_evidence_rejected(db,ready,monkeypatch):
    c,contact,row=ready
    db.delete(row)
    db.add_all([Evidence(company_id=c.id,url=c.website,quote="Our robotics service",fact="Our robotics service",category="product",source_kind="official",confidence="source-observed",content_hash="fixture"),Evidence(company_id=c.id,url=c.website,quote="Robot logs and data",fact="Robot logs and data",category="service",source_kind="official",confidence="source-observed",content_hash="fixture")]);db.commit()
    calls=[]
    async def fake(db,cid,schema,instruction,data,purpose="extract"):
        calls.append(purpose)
        if purpose=="generate": return GeneratedClaims(plan=Plan(evidence_ids=["invented-id"],student_fact_ids=[data["student_facts"][0]["id"]],proposal_id="robotics",voice="direct"))
        return ReviewResult(personalization_score=95,grounded=True,names_correct=True,claims_supported=True,non_generic=True,non_spammy=True,adds_new_value=True,issues=[])
    monkeypatch.setattr(providers,"llm",fake)
    draft=await pipeline.generate(db,c)
    assert draft.status=="rejected"
    assert calls==["generate","generate"]  # Invalid IDs fail before paying for review.
    assert "Missing or invalid evidence references" in draft.review["issues"]

def test_job_deduplication(db):
    first=enqueue(db,"discover",{},"same")
    second=enqueue(db,"discover",{},"same")
    assert first.id==second.id

def test_production_requires_private_credentials():
    with pytest.raises(ValueError): Settings(environment="production",api_key="short",database_url="sqlite://")

async def test_profile_change_blocks_old_approved_email(db,ready,live):
    p=db.get(Profile,1)
    p.data={**p.data,"projects":["Changed experience"]}
    db.commit()
    box=FakeMailbox()
    with pytest.raises(Blocked,match="Profile changed"): await mail.send_one(db,ready[2],box)
    assert box.sent==0

async def test_expired_research_cache_skips_all_provider_calls(db,ready,monkeypatch):
    ready[0].researched_at=now();ready[0].description='Robotics'
    for i in range(2):db.add(Evidence(company_id=ready[0].id,url=ready[0].website,quote='Sourced robot observation '+str(i),fact='Robot tools',category='product',source_kind='official',confidence='source-observed',content_hash='fixture'))
    db.commit()
    async def fail(*args,**kwargs): raise AssertionError("Should not rescrape")
    monkeypatch.setattr(providers,"scrape",fail)
    await pipeline.research(db,ready[0])

async def test_quality_score_must_be_strictly_above_80(db,ready,live):
    ready[2].review={**ready[2].review,"personalization_score":80}
    with pytest.raises(Blocked,match="quality review"): await mail.send_one(db,ready[2],FakeMailbox())

async def test_demo_cannot_send_even_if_manually_approved(db,ready,live):
    ready[0].demo=True
    with pytest.raises(Blocked,match="Demo"): await mail.send_one(db,ready[2],FakeMailbox())

async def test_no_followup_policy_blocks_explicit_send(db,ready,live):
    company,contact,first=ready
    company.research={'followups':False}
    follow=Outreach(company_id=company.id,contact_id=contact.id,sequence=1,status='approved')
    db.add(follow);db.commit();box=FakeMailbox()
    with pytest.raises(Blocked,match='Follow-ups are disabled'):
        await mail.send_one(db,follow,box)
    assert box.sent==0

async def test_auto_response_stops_followups_but_is_not_human_reply(db,ready,live):
    from app.models import Event
    row=ready[2];row.status='sent';row.thread_id='thread';db.commit()
    box=FakeMailbox(messages=[{'id':'auto1','thread':'thread','headers':{'from':ready[1].email,'auto-submitted':'auto-replied','subject':'Thanks'},'body':'We received your email'}])
    await mail.sync_mailbox(db,box)
    event=db.scalar(select(Event).where(Event.source_id=='gmail:auto1'))
    assert event.kind=='auto_reply' and ready[0].stage=='auto_reply'
