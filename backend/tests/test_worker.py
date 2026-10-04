from contextlib import contextmanager
from datetime import timedelta
from sqlalchemy import select
from app import worker
from app.models import Company,Job,Outreach,State,now


def patch_worker(db,monkeypatch):
    @contextmanager
    def session(): yield db
    @contextmanager
    def leader(): yield True
    monkeypatch.setattr(worker,'Session',session)
    monkeypatch.setattr(worker,'leadership',leader)

async def test_blocked_company_does_not_starve_next(db,ready,monkeypatch):
    patch_worker(db,monkeypatch)
    c=ready[0];c.stage='discovered'
    another=Company(name='Second',domain='second.example.com',website='https://second.example.com')
    db.add(another)
    db.add(State(key='automation',value={'enabled':True}))
    db.commit()
    job=worker.enqueue(db,'pipeline',{'id':c.id},'pipeline:'+c.id)
    async def blocked(*args): raise worker.Blocked('Missing key')
    monkeypatch.setattr(worker,'execute',blocked)
    await worker.tick()
    assert c.stage=='needs_attention' and job.status=='blocked'
    import app.intelligence.capabilities as caps
    monkeypatch.setattr(caps,'capabilities',lambda db:{'providers':[{'id':'research','available':True},{'id':'generate','available':True}]})
    await worker.tick()
    pending=db.scalar(select(Job).where(Job.kind=='pipeline',Job.dedupe_key=='pipeline:'+another.id))
    assert pending and pending.status=='blocked' and another.stage=='needs_attention'

async def test_day7_followup_is_deduplicated(db,ready,monkeypatch):
    patch_worker(db,monkeypatch)
    c,contact,initial=ready
    c.stage='contacted';initial.status='sent';initial.sent_at=now()-timedelta(days=7,minutes=1)
    db.add(State(key='automation',value={'enabled':True}));db.commit()
    await worker.tick()
    pending=list(db.scalars(select(Job).where(Job.kind=='followup_prepare')))
    assert len(pending)==1 and pending[0].payload['id']==initial.id
    # Existing dedupe key remains unique on another schedule evaluation.
    pending[0].status='blocked';db.commit()
    await worker.tick()
    assert len(list(db.scalars(select(Job).where(Job.kind=='followup_prepare'))))==1

async def test_long_outage_does_not_queue_three_followups(db,ready,monkeypatch):
    patch_worker(db,monkeypatch)
    c,contact,initial=ready
    c.stage='contacted';initial.status='sent';initial.sent_at=now()-timedelta(days=40)
    recent=Outreach(company_id=c.id,contact_id=contact.id,sequence=1,status='sent',sent_at=now()-timedelta(hours=1))
    db.add_all([recent,State(key='automation',value={'enabled':True})]);db.commit()
    await worker.tick()
    assert not db.scalar(select(Job).where(Job.kind=='followup_prepare'))

async def test_crash_marks_sending_unknown_without_resend(db,ready,monkeypatch):
    patch_worker(db,monkeypatch)
    ready[2].status='sending'
    j=Job(kind='send',payload={'id':ready[2].id},dedupe_key='crashed',status='running')
    db.add(j);db.commit()
    await worker.tick()
    assert j.status=='interrupted' and ready[2].status=='unknown'

async def test_company_no_followup_policy_survives_automation_enable(db,ready,monkeypatch):
    patch_worker(db,monkeypatch)
    company,_,initial=ready
    company.research={'followups':False}
    company.stage='contacted';initial.status='sent';initial.sent_at=now()-timedelta(days=40)
    db.add(State(key='automation',value={'enabled':True}));db.commit()
    await worker.tick()
    assert not db.scalar(select(Job).where(Job.kind=='followup_prepare'))
