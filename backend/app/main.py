import hashlib
import json
import secrets
from datetime import timedelta
from typing import Annotated, Literal
from fastapi import FastAPI, Depends, Header, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session as DBSession
from .config import settings
from .db import session
from .models import Company, Contact, Evidence, Outreach, Event, Profile, Job, Usage, State, now
from .schemas import ProfileInput, CompanyInput, ContactInput, DiscoveryInput, EventInput
from .intelligence.schemas import SearchSpec,CandidateImport,ContactRecord
from .intelligence.discovery import ingest_contact,contact_confidence
from .models import Candidate,ContactObservation,Generation
from . import ui_contracts as ui
from .core import Blocked, public_url, record_event, day_start, score_company, profile_fingerprint
from .pipeline import learning
from .worker import enqueue

import asyncio
from contextlib import asynccontextmanager, suppress
from . import responses
@asynccontextmanager
async def lifespan(app):
    task=asyncio.create_task(responses.loop()) if settings().response_poll_enabled else None
    from .privacy import retention_loop
    maintenance=asyncio.create_task(retention_loop())
    yield
    maintenance.cancel()
    with suppress(asyncio.CancelledError):await maintenance
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError): await task

app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan,title="Fieldwork — Internship Outreach",version="0.1.0")

from .auth import authorize
from .ingress import Ingress
from starlette.middleware.trustedhost import TrustedHostMiddleware
app.add_middleware(Ingress)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=settings().trusted_hosts, www_redirect=False)
from .redaction import redact,install_logging
install_logging()
DB=Annotated[DBSession,Depends(session)]
Auth=Depends(authorize)

@app.exception_handler(Blocked)
async def blocked(_,exc):
    return JSONResponse(status_code=409,content={"detail":redact(str(exc))})

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

@app.get("/profile",dependencies=[Auth],response_model=ProfileInput)
def profile(db:DB):
    row=db.get(Profile,1)
    return row.data if row else ProfileInput().model_dump()

@app.put("/profile",dependencies=[Auth])
def update_profile(body:ProfileInput,db:DB):
    if body.verified and (not body.name or "@" not in body.email):
        raise HTTPException(422,"Name and email required for a verified profile")
    if len(json.dumps(body.model_dump()))>40000:
        raise HTTPException(422,"Profile exceeds 40 KB")
    from .services.ledger import lock
    lock(db)
    db.merge(Profile(id=1,data=body.model_dump(),updated_at=now()))
    from .models import Integration
    connected=db.get(Integration,'gmail')
    if connected and connected.status=='connected' and connected.email.lower()!=body.email.strip().lower():
        gmail_oauth.change(db,connected,'identity_mismatch','profile_identity_changed',clear=True)
    # Profile changes invalidate pending approvals so old claims cannot silently send.
    for row in db.scalars(select(Outreach).where(Outreach.status.in_(["draft","approved"]))):
        from .domain.states import transition
        transition(db,row,"rejected",reason="profile_changed")
        row.review={**row.review,"passed":False,"issues":["Profile changed. Regenerate and review this draft."]}
    db.commit()
    return body

def company_view(db,row):
    from .intelligence.evidence import bundle
    from .intelligence.discovery import best_contact
    facts=bundle(db,row);contact=best_contact(db,row)
    confidence=contact_confidence(db,contact) if contact else 'unknown'
    if not contact:
        values=[contact_confidence(db,c) for c in db.scalars(select(Contact).where(Contact.company_id==row.id))]
        confidence=next((v for v in ('conflicting','stale','provider-confirmed','source-observed','inferred') if v in values),'unknown')
    return {**asdict(row),'evidence_quality':'strong' if len([e for e in facts if e.source_kind=='official'])>=2 else 'partial' if facts else 'unknown','contact_confidence':confidence}

@app.get("/companies",dependencies=[Auth],response_model=list[ui.CompanyView])
def companies(db:DB):
    return [company_view(db,r) for r in db.scalars(select(Company).order_by(Company.score.desc(),Company.created_at.desc()).limit(1000))]

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

@app.get("/companies/{id}",dependencies=[Auth],response_model=ui.CompanyDetail)
def company_detail(id:str,db:DB):
    row=get(db,Company,id)
    return {**company_view(db,row),"contacts":[{**asdict(c),"confidence":contact_confidence(db,c),"observations":[asdict(o) for o in db.scalars(select(ContactObservation).where(ContactObservation.contact_id==c.id))]} for c in db.scalars(select(Contact).where(Contact.company_id==id))],
        "evidence":[{**asdict(c),"fresh":__import__("app.intelligence.evidence",fromlist=["usable"]).usable(c)} for c in db.scalars(select(Evidence).where(Evidence.company_id==id))],
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
    source=body.source if body.source.startswith('https://') else ''
    row=ingest_contact(db,get(db,Company,id),ContactRecord(email=body.email,name=body.name,title=body.title,provider='manual',source_url=source,confidence='source-observed' if source else 'unknown').model_dump())
    return asdict(row)

@app.post("/companies/{id}/events",dependencies=[Auth])
def add_event(id:str,body:EventInput,db:DB):
    record_event(db,get(db,Company,id),body.kind,"manual:"+secrets.token_hex(16),body.detail)
    return {"recorded":True}

@app.post("/discover",dependencies=[Auth],response_model=ui.JobView,status_code=202)
def discovery(body:SearchSpec,db:DB):
    from .intelligence.capabilities import require_capability
    require_capability(db,body.provider)
    spec=body.model_dump()
    key=hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()
    return asdict(enqueue(db,"discover",spec,"discover:"+key+":"+now().strftime("%Y-%m-%d")))

@app.post("/companies/{id}/actions/{action}",dependencies=[Auth],response_model=ui.JobView,status_code=202)
def company_action(id:str,action:str,db:DB):
    get(db,Company,id)
    if action not in {"research","generate","pipeline"}:
        raise HTTPException(404,"Unknown action")
    from .intelligence.capabilities import require_capability
    require_capability(db,'research' if action in ('research','pipeline') else 'generate')
    return asdict(enqueue(db,action,{"id":id},action+":"+id+":"+now().strftime("%Y-%m-%d")))

@app.post("/contacts/{id}/verify",dependencies=[Auth],response_model=ui.JobView,status_code=202)
def verify_contact(id:str,db:DB):
    get(db,Contact,id)
    from .intelligence.capabilities import require_capability
    require_capability(db,'contacts')
    return asdict(enqueue(db,"verify",{"id":id},"verify:"+id+":"+now().strftime("%Y-%m-%d")))

@app.get("/outreach",dependencies=[Auth],response_model=list[ui.OutreachView])
def outreach(db:DB):
    return [asdict(r) for r in db.scalars(select(Outreach).order_by(Outreach.created_at.desc()).limit(1000))]

@app.post("/outreach/{id}/approve",dependencies=[Auth])
def approve(id:str,db:DB):
    from .services import ledger
    ledger.lock(db)
    row=get(db,Outreach,id)
    if row.status!="draft" or row.attempts or not row.review.get("passed"):
        raise Blocked("Only quality-passed drafts can be approved")
    profile=get(db,Profile,1)
    if row.review.get("profile_hash")!=profile_fingerprint(profile.data):
        raise Blocked("Profile changed; regenerate the draft")
    from .intelligence.personalization import assert_current
    assert_current(db,row)
    from .domain.states import transition
    transition(db,row,"approved",reason="operator_approved")
    db.commit()
    return asdict(row)

@app.patch("/outreach/{id}",dependencies=[Auth],response_model=ui.OutreachView)
def edit_outreach(id:str,body:ui.OutreachEdit,db:DB):
    from .services import ledger
    from .domain.states import transition
    ledger.lock(db)
    row=get(db,Outreach,id)
    if row.status not in {"draft","approved","rejected"} or row.attempts:
        raise Blocked("Only unsent messages without an attempt can be edited")
    if "\n" in body.subject or "\r" in body.subject:
        raise Blocked("Subject must be one line")
    if body.subject!=row.subject or body.body!=row.body:
        transition(db,row,"draft",reason="operator_edit")
        row.subject=body.subject;row.body=body.body
        row.review={"passed":False,"issues":["Message edited. Regenerate to run quality review before approval."]}
    db.commit()
    return asdict(row)

@app.post("/outreach/{id}/review/{decision}",dependencies=[Auth],response_model=ui.OutreachView)
def review_outreach(id:str,decision:Literal["reject","draft"],db:DB):
    from .services import ledger
    from .domain.states import transition
    ledger.lock(db)
    row=get(db,Outreach,id)
    if row.status not in {"draft","approved","rejected"} or row.attempts:
        raise Blocked("Only unsent messages without an attempt may return to review")
    transition(db,row,"rejected" if decision=="reject" else "draft",reason="operator_"+decision)
    db.commit()
    return asdict(row)

@app.post("/outreach/{id}/regenerate",dependencies=[Auth],response_model=ui.JobView,status_code=202)
def regenerate(id:str,db:DB):
    row=get(db,Outreach,id)
    if row.status not in {"draft","rejected","approved"} or row.attempts:
        raise Blocked("Only unsent drafts may be regenerated")
    from .intelligence.capabilities import require_capability
    require_capability(db,'generate')
    return asdict(enqueue(db,'regenerate',{'id':row.id},'regenerate:'+row.id+':'+secrets.token_hex(16)))

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

@app.get("/jobs",dependencies=[Auth],response_model=list[ui.JobView])
def jobs(db:DB):
    return [asdict(r) for r in db.scalars(select(Job).order_by(Job.created_at.desc()).limit(50))]

@app.post("/jobs/{id}/retry",dependencies=[Auth])
def retry_job(id:str,db:DB):
    job=get(db,Job,id)
    if job.payload.get('stop_requested'):raise Blocked('Stopped work requires a new deliberate operation')
    if job.kind=="send" or job.status not in {"failed","blocked","interrupted"}:
        raise Blocked("Only failed non-send jobs may be explicitly retried")
    from .models import Operation,ActionAttempt
    op=db.scalar(select(Operation).where(Operation.job_id==job.id))
    attempts=list(db.scalars(select(ActionAttempt).where(ActionAttempt.operation_id==op.id))) if op else []
    if len(attempts)>settings().max_job_retries:raise Blocked('Explicit retry limit reached')
    from .core import aware
    backoff=min(60,5*(2**len(attempts)))
    if job.finished_at and now()-aware(job.finished_at)<timedelta(seconds=backoff):raise Blocked(f'Explicit retry requires {backoff} seconds of backoff')
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

@app.get("/settings",dependencies=[Auth],response_model=ui.SettingsView)
def config(db:DB):
    s=settings()
    state=db.get(State,"automation")
    return {"manual_mode":s.manual_mode,"dry_run":s.dry_run,"auto_approve":False,"daily_send_limit":s.daily_send_limit,"daily_budget_usd":s.daily_budget_usd,"company_budget_usd":s.company_budget_usd,
        "max_pages":s.max_pages,"research_seconds":s.research_seconds,"mail_provider":s.mail_provider,
        "automation":state.value if state else {"enabled":False},
        "integrations":{name:bool(getattr(s,name+"_api_key")) for name in ["openai","tavily","firecrawl","google_maps","apollo","hunter"]},
        "mail_connected":gmail_oauth.status(db)["connected"],"demo_allowed":s.environment!="production"}

@app.get("/metrics",dependencies=[Auth],response_model=ui.MetricsView)
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

@app.get("/desk",dependencies=[Auth],response_model=list[ui.PacketView])
def desk_list(db:DB):
    return desk.list_packets(db)

@app.post("/desk",dependencies=[Auth],response_model=ui.PacketView)
def desk_create(body:desk.DeskDraft,db:DB):
    return desk.new_packet(db,body)

@app.put("/desk/{id}",dependencies=[Auth],response_model=ui.PacketView)
def desk_edit(id:str,body:desk.DeskDraft,db:DB):
    return desk.edit_packet(db,id,body)

@app.post("/desk/{id}/detector",dependencies=[Auth],response_model=ui.PacketView)
def desk_detect(id:str,body:desk.DetectorInput,db:DB):
    return desk.detector_result(db,id,body)

@app.post("/desk/{id}/signoff",dependencies=[Auth],response_model=ui.PacketView)
def desk_signoff(id:str,body:desk.SignoffInput,db:DB):
    return desk.signoff(db,id,body)

@app.get("/desk/{id}/eml",dependencies=[Auth],response_model=ui.EmlView)
def desk_eml(id:str,db:DB):
    return {"filename":"dry-run.eml","content":desk.eml(db,id)}

@app.post("/desk/{id}/mailbox",dependencies=[Auth])
def desk_mailbox(id:str,db:DB):
    packet=desk.get_packet(db,id).value
    return asdict(enqueue(db,"mailbox_draft",{"id":id,"draft_hash":packet["draft_hash"]},"mailbox-draft:"+id+":"+packet["draft_hash"]))

from . import campaign
@app.get('/campaign', dependencies=[Auth],response_model=ui.CampaignView)
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

@app.get('/responses',dependencies=[Auth],response_model=ui.InboxView)
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


from fastapi import Request
from fastapi.exceptions import RequestValidationError
@app.exception_handler(RequestValidationError)
async def invalid_request(_,exc):
    return JSONResponse(status_code=422,content={'detail':[{'loc':list(e['loc']),'type':e['type'],'msg':'Invalid value'} for e in exc.errors()]})

@app.exception_handler(Exception)
async def internal_failure(_,exc):
    return JSONResponse(status_code=500,content={'detail':'Internal operation failed; inspect service health'})

from .auth import browser_operator,origin_check,create_session,set_cookie,COOKIE
from .models import OperatorSession
class LoginInput(BaseModel):
    password: str = Field(min_length=1,max_length=1024)

@app.post('/auth/login')
def login(body:LoginInput,request:Request,db:DB):
    origin_check(request)
    # Rotate an existing browser session when signing in again.
    from .auth import digest
    old=db.get(OperatorSession,digest(request.cookies.get(COOKIE,'')))
    if old:old.revoked_at=now()
    token=create_session(db,body.password)
    result=JSONResponse({'operator':'personal'});set_cookie(result,token);return result

@app.get('/auth/session',dependencies=[Auth])
def auth_session():return {'operator':'personal'}

@app.post('/auth/logout')
def logout(db:DB,operator:Annotated[object,Depends(browser_operator)]):
    db.get(OperatorSession,operator.session_hash).revoked_at=now();db.commit()
    result=JSONResponse({'logged_out':True});result.delete_cookie(COOKIE,path='/');return result

from . import gmail_oauth
@app.get('/integrations/gmail',dependencies=[Auth],response_model=ui.ConnectionView)
def gmail_status(db:DB):return gmail_oauth.status(db)

@app.post('/integrations/gmail/connect')
def gmail_connect(db:DB,operator:Annotated[object,Depends(browser_operator)]):return gmail_oauth.start(db,operator)

@app.get('/integrations/gmail/callback')
async def gmail_callback(db:DB,operator:Annotated[object,Depends(browser_operator)],state:str='',code:str='',error:str=''):
    return await gmail_oauth.callback(db,operator,state,code,error)

class DisconnectInput(BaseModel):
    revoke: bool=True
@app.post('/integrations/gmail/disconnect',dependencies=[Auth])
async def gmail_disconnect(body:DisconnectInput,db:DB):return await gmail_oauth.disconnect(db,body.revoke)

from . import privacy
@app.get('/privacy/export',dependencies=[Auth])
def privacy_export(db:DB):return privacy.export(db)

class DeleteInput(BaseModel):
    scope: Literal['resume','generated','personal']
    confirmation: str
@app.post('/privacy/delete',dependencies=[Auth])
async def privacy_delete(body:DeleteInput,db:DB):
    # Validate deletion before credential invalidation; deleting personal content also disconnects Gmail.
    result=privacy.remove(db,body.scope,body.confirmation)
    if body.scope=='personal':await gmail_oauth.disconnect(db,revoke=True)
    return result


@app.get('/discovery/candidates',dependencies=[Auth],response_model=list[ui.CandidateView])
def candidates(db:DB):
    return [asdict(r) for r in db.scalars(select(Candidate).order_by(Candidate.updated_at.desc()).limit(1000))]

@app.get('/intelligence/capabilities',dependencies=[Auth],response_model=ui.CapabilitiesView)
def intelligence_capabilities(db:DB):
    from .intelligence.capabilities import capabilities
    return capabilities(db)

@app.post('/discovery/import',dependencies=[Auth],response_model=ui.JobView,status_code=202)
def candidate_import(body:CandidateImport,db:DB):
    for company in body.companies:
        public_url(str(company.website))
        if company.source.startswith('https://'):public_url(company.source)
    payload=body.model_dump(mode='json')
    return asdict(enqueue(db,'candidate_import',payload,'candidate_import:'+profile_fingerprint(payload)))

@app.post('/discovery/candidates/{id}/{decision}',dependencies=[Auth])
def candidate_decision(id:str,decision:Literal['accept','dismiss'],db:DB):
    row=get(db,Candidate,id)
    if decision=='accept':
        from .intelligence.discovery import accept
        return asdict(accept(db,row))
    if row.status=='accepted':raise Blocked('Accepted prospect cannot be dismissed from candidate list')
    row.status='dismissed';db.commit();return asdict(row)

@app.post('/jobs/{id}/stop',dependencies=[Auth],response_model=ui.JobView)
def stop_intelligence_job(id:str,db:DB):
    from .services.ledger import lock
    lock(db);job=get(db,Job,id)
    if job.kind not in ('discover','candidate_import','research','pipeline','generate','regenerate','verify') or job.status not in ('queued','running'):
        raise Blocked('Only active intelligence jobs may be stopped here')
    job.payload={**job.payload,'stop_requested':True}
    if job.status=='queued':
        from .domain.states import transition
        transition(db,job,'running',domain='job',reason='operator_stop')
        transition(db,job,'blocked',domain='job',reason='operator_stop')
        job.error='Stopped by operator';job.finished_at=now()
    db.commit();return asdict(job)

@app.get('/companies/{id}/generations',dependencies=[Auth],response_model=list[ui.GenerationView])
def generation_history(id:str,db:DB):
    get(db,Company,id)
    return [asdict(r) for r in db.scalars(select(Generation).where(Generation.company_id==id).order_by(Generation.created_at.desc()).limit(40))]
