import hashlib
import json
import secrets
from datetime import timedelta
from typing import Annotated
from fastapi import FastAPI, Depends, Header, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session as DBSession
from .config import settings
from .db import session
from .models import Company, Contact, Evidence, Outreach, Event, Profile, Job, Usage, State, now
from .schemas import ProfileInput, CompanyInput, ContactInput, DiscoveryInput, EventInput
from .core import Blocked, public_url, record_event, day_start, score_company, profile_fingerprint
from .pipeline import learning
from .worker import enqueue

import asyncio
from contextlib import asynccontextmanager, suppress
from . import responses
@asynccontextmanager
async def lifespan(app):
    task=asyncio.create_task(responses.loop()) if settings().response_poll_enabled else None
    yield
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError): await task

app=FastAPI(lifespan=lifespan,title="Fieldwork — Internship Outreach",version="0.1.0")

def authorize(authorization: Annotated[str | None, Header()]=None):
    expected="Bearer "+settings().api_key
    if not authorization or not secrets.compare_digest(authorization,expected):
        raise HTTPException(401,"Authentication required")
DB=Annotated[DBSession,Depends(session)]
Auth=Depends(authorize)

@app.exception_handler(Blocked)
async def blocked(_,exc):
    return JSONResponse(status_code=409,content={"detail":str(exc)})

def get(db,model,id):
    row=db.get(model,id)
    if not row:
        raise HTTPException(404,"Not found")
    return row

def asdict(row):
    return {c.name:getattr(row,c.name) for c in row.__table__.columns}

@app.get("/health")
def health(db:DB):
    db.execute(text("SELECT 1"))
    return {"status":"ok"}

@app.get("/profile",dependencies=[Auth])
def profile(db:DB):
    row=db.get(Profile,1)
    return row.data if row else ProfileInput().model_dump()

@app.put("/profile",dependencies=[Auth])
def update_profile(body:ProfileInput,db:DB):
    if body.verified and (not body.name or "@" not in body.email):
        raise HTTPException(422,"Name and email required for a verified profile")
    if len(json.dumps(body.model_dump()))>40000:
        raise HTTPException(422,"Profile exceeds 40 KB")
    db.merge(Profile(id=1,data=body.model_dump(),updated_at=now()))
    # Profile changes invalidate pending approvals so old claims cannot silently send.
    for row in db.scalars(select(Outreach).where(Outreach.status.in_(["draft","approved"]))):
        from .domain.states import transition
        transition(db,row,"rejected",reason="profile_changed")
        row.review={**row.review,"passed":False,"issues":["Profile changed. Regenerate and review this draft."]}
    db.commit()
    return body

@app.get("/companies",dependencies=[Auth])
def companies(db:DB):
    return [asdict(r) for r in db.scalars(select(Company).order_by(Company.score.desc(),Company.created_at.desc()).limit(1000))]

@app.post("/companies",dependencies=[Auth])
def add_company(body:CompanyInput,db:DB):
    domain=public_url(str(body.website))
    existing=db.scalar(select(Company).where(Company.domain==domain))
    if existing:
        return asdict(existing)
    row=Company(**{**body.model_dump(),"website":str(body.website)},domain=domain)
    db.add(row)
    db.commit()
    return asdict(row)

@app.post("/companies/import",dependencies=[Auth])
def import_companies(body:list[CompanyInput],db:DB):
    if len(body)>50:
        raise HTTPException(422,"Import at most 50 companies per batch")
    return [add_company(c,db) for c in body]

@app.get("/companies/{id}",dependencies=[Auth])
def company_detail(id:str,db:DB):
    row=get(db,Company,id)
    return {**asdict(row),"contacts":[asdict(c) for c in db.scalars(select(Contact).where(Contact.company_id==id))],
        "evidence":[asdict(c) for c in db.scalars(select(Evidence).where(Evidence.company_id==id))],
        "events":[asdict(c) for c in db.scalars(select(Event).where(Event.company_id==id).order_by(Event.created_at.desc()))]}

@app.patch("/companies/{id}",dependencies=[Auth])
def edit_company(id:str,body:CompanyInput,db:DB):
    row=get(db,Company,id)
    if public_url(str(body.website))!=row.domain:
        raise HTTPException(422,"Import a separate company to change its domain")
    for k,v in body.model_dump().items():
        setattr(row,k,str(v) if k=="website" else v)
    profile=db.get(Profile,1)
    score_company(row,bool(db.scalar(select(Contact).where(Contact.company_id==id))),profile.data["interests"] if profile else [])
    db.commit()
    return asdict(row)

@app.post("/companies/{id}/contacts",dependencies=[Auth])
def add_contact(id:str,body:ContactInput,db:DB):
    get(db,Company,id)
    email=str(body.email).lower()
    if db.scalar(select(Contact).where(Contact.email==email)):
        raise HTTPException(409,"Contact already exists")
    row=Contact(company_id=id,**{**body.model_dump(),"email":email})
    db.add(row)
    db.commit()
    return asdict(row)

@app.post("/companies/{id}/events",dependencies=[Auth])
def add_event(id:str,body:EventInput,db:DB):
    record_event(db,get(db,Company,id),body.kind,"manual:"+secrets.token_hex(16),body.detail)
    return {"recorded":True}

@app.post("/discover",dependencies=[Auth])
def discovery(body:DiscoveryInput,db:DB):
    spec=body.model_dump()
    key=hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()
    return asdict(enqueue(db,"discover",spec,"discover:"+key+":"+now().strftime("%Y-%m-%d")))

@app.post("/companies/{id}/actions/{action}",dependencies=[Auth])
def company_action(id:str,action:str,db:DB):
    get(db,Company,id)
    if action not in {"research","generate","pipeline"}:
        raise HTTPException(404,"Unknown action")
    return asdict(enqueue(db,action,{"id":id},action+":"+id+":"+now().strftime("%Y-%m-%d")))

@app.post("/contacts/{id}/verify",dependencies=[Auth])
def verify_contact(id:str,db:DB):
    get(db,Contact,id)
    return asdict(enqueue(db,"verify",{"id":id},"verify:"+id+":"+now().strftime("%Y-%m-%d")))

@app.get("/outreach",dependencies=[Auth])
def outreach(db:DB):
    return [asdict(r) for r in db.scalars(select(Outreach).order_by(Outreach.created_at.desc()).limit(1000))]

@app.post("/outreach/{id}/approve",dependencies=[Auth])
def approve(id:str,db:DB):
    row=get(db,Outreach,id)
    if row.status!="draft" or not row.review.get("passed"):
        raise Blocked("Only quality-passed drafts can be approved")
    profile=get(db,Profile,1)
    if row.review.get("profile_hash")!=profile_fingerprint(profile.data):
        raise Blocked("Profile changed; regenerate the draft")
    from .domain.states import transition
    transition(db,row,"approved",reason="operator_approved")
    db.commit()
    return asdict(row)

@app.post("/outreach/{id}/regenerate",dependencies=[Auth])
def regenerate(id:str,db:DB):
    row=get(db,Outreach,id)
    if row.status not in {"draft","rejected","approved"}:
        raise Blocked("Only unsent drafts may be regenerated")
    return asdict(enqueue(db,"regenerate",{"id":row.id},"regenerate:"+row.id+":"+now().strftime("%Y-%m-%dT%H:%M")))

@app.post("/outreach/{id}/send",dependencies=[Auth])
def send(id:str,db:DB):
    row=get(db,Outreach,id)
    if settings().dry_run:
        raise Blocked("Dry-run mode: no email will be sent")
    if row.status!="approved":
        raise Blocked("Draft must be approved first")
    return asdict(enqueue(db,"send",{"id":id},"send:"+id+":"+str(row.attempts)))

@app.post("/mail/sync",dependencies=[Auth])
def mail_sync(db:DB):
    return asdict(enqueue(db,"sync",{},"sync:"+now().strftime("%Y-%m-%dT%H:%M")))

@app.get("/jobs",dependencies=[Auth])
def jobs(db:DB):
    return [asdict(r) for r in db.scalars(select(Job).order_by(Job.created_at.desc()).limit(50))]

@app.post("/jobs/{id}/retry",dependencies=[Auth])
def retry_job(id:str,db:DB):
    job=get(db,Job,id)
    if job.kind=="send" or job.status not in {"failed","blocked","interrupted"}:
        raise Blocked("Only failed non-send jobs may be explicitly retried")
    from .domain.states import transition
    transition(db,job,"queued",domain="job",reason="operator_retry")
    job.error=""
    db.commit()
    return asdict(job)

class AutomationInput(BaseModel):
    enabled: bool
    discovery: DiscoveryInput | None = None

@app.put("/automation",dependencies=[Auth])
def automation(body:AutomationInput,db:DB):
    db.merge(State(key="automation",value=body.model_dump()))
    db.commit()
    return body

@app.get("/settings",dependencies=[Auth])
def config(db:DB):
    s=settings()
    state=db.get(State,"automation")
    return {"manual_mode":s.manual_mode,"dry_run":s.dry_run,"auto_approve":s.auto_approve,"daily_send_limit":s.daily_send_limit,"daily_budget_usd":s.daily_budget_usd,"company_budget_usd":s.company_budget_usd,
        "max_pages":s.max_pages,"research_seconds":s.research_seconds,"mail_provider":s.mail_provider,
        "automation":state.value if state else {"enabled":False},
        "integrations":{name:bool(getattr(s,name+"_api_key")) for name in ["openai","tavily","firecrawl","google_maps","apollo","hunter"]},
        "mail_connected":bool(s.oauth_refresh_token and s.sender_email),"demo_allowed":s.environment!="production"}

@app.get("/metrics",dependencies=[Auth])
def metrics(db:DB):
    real_ids=list(db.scalars(select(Company.id).where(Company.demo==False)))
    sent_ids=set(db.scalars(select(Outreach.company_id).where(Outreach.status=="sent",Outreach.sequence==0,Outreach.company_id.in_(real_ids))))
    ev=list(db.scalars(select(Event).where(Event.company_id.in_(sent_ids))))
    count=lambda kinds:len({e.company_id for e in ev if e.kind in kinds})
    n=len(sent_ids)
    replied=count({"reply","positive","negative","interview","offer"})
    interviews=count({"interview","offer"})
    offers=count({"offer"})
    return {"companies":len(real_ids),"sent":n,"replies":replied,"interviews":interviews,"offers":offers,
        "response_rate":replied/n if n else 0,"interview_rate":interviews/n if n else 0,"conversion_rate":offers/n if n else 0,
        "opens_observed":count({"open"}),"open_rate":None,"open_note":"Not tracked automatically; provider pixels are unreliable. Manual observations are separate.",
        "sent_today":db.scalar(select(func.count()).select_from(Outreach).where(Outreach.sent_at>=day_start(),Outreach.attempts>0)),
        "reserved_today_usd":round(db.scalar(select(func.coalesce(func.sum(Usage.reserved_usd),0)).where(Usage.created_at>=day_start())),3),
        "learning":learning(db)}

@app.post("/demo",dependencies=[Auth])
def demo(db:DB):
    if settings().environment=="production":
        raise HTTPException(403,"Demo seeding disabled in production")
    from .seed import seed
    return seed(db)


from . import desk

@app.get("/desk",dependencies=[Auth])
def desk_list(db:DB):
    return desk.list_packets(db)

@app.post("/desk",dependencies=[Auth])
def desk_create(body:desk.DeskDraft,db:DB):
    return desk.new_packet(db,body)

@app.put("/desk/{id}",dependencies=[Auth])
def desk_edit(id:str,body:desk.DeskDraft,db:DB):
    return desk.edit_packet(db,id,body)

@app.post("/desk/{id}/detector",dependencies=[Auth])
def desk_detect(id:str,body:desk.DetectorInput,db:DB):
    return desk.detector_result(db,id,body)

@app.post("/desk/{id}/signoff",dependencies=[Auth])
def desk_signoff(id:str,body:desk.SignoffInput,db:DB):
    return desk.signoff(db,id,body)

@app.get("/desk/{id}/eml",dependencies=[Auth])
def desk_eml(id:str,db:DB):
    return {"filename":"dry-run.eml","content":desk.eml(db,id)}

@app.post("/desk/{id}/mailbox",dependencies=[Auth])
def desk_mailbox(id:str,db:DB):
    packet=desk.get_packet(db,id).value
    return asdict(enqueue(db,"mailbox_draft",{"id":id,"draft_hash":packet["draft_hash"]},"mailbox-draft:"+id+":"+packet["draft_hash"]))

from . import campaign
@app.get('/campaign', dependencies=[Auth])
def campaign_status():
    return campaign.status()

@app.post('/campaign/stop', dependencies=[Auth])
def campaign_stop():
    return campaign.stop()

class PolicySwitch(BaseModel):
    enabled: bool

@app.put('/outreach-policy', dependencies=[Auth])
def switch_outreach_policy(body:PolicySwitch,db:DB):
    from .services.policy import set_paused
    return set_paused(db,body.enabled)

@app.get('/responses',dependencies=[Auth])
def response_list(db:DB):
    return responses.listing(db)

@app.post('/responses/sync',dependencies=[Auth],status_code=202)
async def response_sync(background:BackgroundTasks):
    background.add_task(responses.sync)
    return {'status':'queued'}

class ResponseHandled(BaseModel):
    handled: bool

@app.put('/responses/{id}',dependencies=[Auth])
def response_handle(id:str,body:ResponseHandled,db:DB):
    row=get(db,State,'response:'+id)
    row.value={**row.value,'handled':body.handled}
    db.commit()
    return row.value

@app.post('/desk/{id}/self-test',dependencies=[Auth])
async def send_self_test(id:str,db:DB):
    from .self_test import send
    return await send(db,id)
