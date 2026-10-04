"""One communication policy; mode is a trusted server entry point, never client data."""
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select,func,exists
from ..models import Company,Contact,Outreach,Profile,State,Suppression,Event,Evidence,Operation,ActionAttempt,DomainTransition,now
from ..config import settings
from ..core import Blocked,aware,profile_fingerprint,STOP_STAGES
from . import ledger
STOP=STOP_STAGES
VERSION='personal-v3'

def send_usage(db,start,initial_only=False):
 # Legacy rows not yet represented in the ledger count too. Never double count.
 old=select(func.coalesce(func.sum(Outreach.attempts),0)).where(Outreach.sent_at>=start,~exists().where(Operation.outreach_id==Outreach.id,Operation.kind=='company_send'))
 new=select(func.coalesce(func.sum(ActionAttempt.network_units),0)).join(Operation).where(ActionAttempt.started_at>=start)
 if initial_only:
  old=old.where(Outreach.sequence==0)
  new=new.join(Outreach,Operation.outreach_id==Outreach.id).where(Operation.kind=='company_send',Outreach.sequence==0)
 else:new=new.where(Operation.kind.in_(['company_send','self_test']))
 return db.scalar(old)+db.scalar(new)

def snapshot(db,mode):
 p=db.get(State,'outreach_policy');b=db.get(State,'manual_batch')
 value=p.value if p else {}
 return {'version':VERSION,'mode':mode,'policy_hash':profile_fingerprint(value),'enabled':bool(value.get('enabled')),
         'daily_cap':min(25,settings().daily_send_limit,value.get('daily_total_attempt_limit',25)),
         'batch_hash':profile_fingerprint(b.value) if b else None}

def company(db,row,at,mode="scheduled"):
 if mode not in {"scheduled","worker"}:raise Blocked("Unknown delivery mode")
 if row and row.status=="cancelled":raise Blocked("Conversation stopped")
 if mode=="worker" and (settings().dry_run or settings().manual_mode):raise Blocked("DRY_RUN/manual mode: no email sent")
 state=db.get(State,'outreach_policy');p=state.value if state else {}
 if row and row.review.get('autopilot_approval'):
  from .autopilot import approval_current
  approval_current(db,row,at)
 batch=db.get(State,'manual_batch');b=batch.value if batch else {}
 if row and row.id in b.get('outreach_ids',[]) and b.get('stop_requested'):raise Blocked('Manual batch stopped by user')
 manual=bool(row and row.id in b.get('outreach_ids',[]) and b.get('enabled') and at<datetime.fromisoformat(b['expires_at']) and row.sequence==0)
 if p.get('stop_requested'):raise Blocked('Campaign stopped')
 if not p.get('enabled') and not manual:raise Blocked('Scheduled outreach is paused')
 local=at.astimezone(ZoneInfo(settings().timezone))
 if (mode=='scheduled' or settings().environment=='production') and not manual and (local.weekday()>4 or not 9<=local.hour<17):raise Blocked('Weekday business hours only')
 if not row or row.status!='approved' or row.attempts:raise Blocked('Only reviewed, unattempted approved rows may send')
 c=db.get(Company,row.company_id);ct=db.get(Contact,row.contact_id);profile=db.get(Profile,1)
 if not c or not ct or ct.company_id!=c.id:raise Blocked('Invalid company/contact linkage')
 if row.sequence and c.research.get('followups') is False:raise Blocked('Follow-ups are disabled for this company')
 if db.scalar(select(Event.id).where(Event.company_id==c.id,Event.kind.in_(['reply','auto_reply','bounce','opt_out','negative','closed']))):raise Blocked('Existing response stops conversation')
 if c.demo or c.stage in STOP or db.get(Suppression,ct.email.lower()):raise Blocked('Demo or company/contact is stopped')
 allowed=p.get('allowed_cities',['Rocklin'])
 if c.research.get('city') not in allowed:raise Blocked('Authorized local city evidence required')
 city_evidence=c.research.get('city_evidence_id')
 if city_evidence:
  from ..intelligence.evidence import usable
  city_fact=db.get(Evidence,city_evidence)
  if not city_fact or city_fact.company_id!=c.id or city_fact.source_kind!='official' or not usable(city_fact):raise Blocked('Current official location evidence required')
 from pydantic import TypeAdapter,EmailStr,ValidationError
 try:TypeAdapter(EmailStr).validate_python(ct.email)
 except ValidationError:raise Blocked('Valid recipient email required') from None
 if not ct.source.startswith('https://') or ct.validation not in {'valid','public_source_dns'} or not ct.validated_at or aware(ct.validated_at)<at-timedelta(days=7):raise Blocked('Fresh official-source contact validation required')
 if not profile or not profile.data.get('verified'):raise Blocked('Verified profile required')
 review=row.review
 if review.get('profile_hash')!=profile_fingerprint(profile.data):raise Blocked('Profile changed; regenerate the draft')
 if review.get('personalization_score',0)<=80 or not review.get('names_correct') or not review.get('non_spammy') or not review.get('passed') or not review.get('grounded') or not review.get('claims_supported') or not review.get('non_generic') or review.get('profile_hash')!=profile_fingerprint(profile.data):raise Blocked('Grounded quality review required')
 from ..intelligence.personalization import assert_current
 assert_current(db,row)
 if not row.evidence_ids or not row.subject or not row.body:raise Blocked('Email and evidence required')
 evidence=list(db.scalars(select(Evidence).where(Evidence.id.in_(row.evidence_ids),Evidence.company_id==c.id)))
 if len(evidence)!=len(set(row.evidence_ids)) or any(not e.fact or not e.url.startswith('https://') for e in evidence):raise Blocked('Actual company evidence required')
 if any(x in row.subject for x in '\r\n'):raise Blocked('Invalid subject')
 start=local.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc)
 used=send_usage(db,start)
 if used>=min(25,settings().daily_send_limit,p.get('daily_total_attempt_limit',25)):raise Blocked('Daily total cap reached')
 bounces=set(db.scalars(select(Event.company_id).where(Event.kind=='bounce',Event.created_at>=start)))
 if len(bounces)>=min(2,p.get('stop_after_bounces_per_day',2)):raise Blocked('Daily bounce stop reached')
 if ledger.unresolved(db) or db.scalar(select(Outreach.id).where(Outreach.status.in_(['unknown','sending'])).limit(1)):raise Blocked('Uncertain delivery exists; reconcile before further communication')
 last=db.scalar(select(func.max(Outreach.sent_at)))
 if last and (at-aware(last)).total_seconds()<max(60,settings().send_interval_seconds,p.get('send_interval_seconds',60)):raise Blocked('Minimum send interval not elapsed')
 original=None
 if row.sequence:
  if row.sequence!=1 or p.get('max_followups_per_company')!=1:raise Blocked('Only one follow-up is authorized')
  original=db.scalar(select(Outreach).where(Outreach.company_id==c.id,Outreach.sequence==0))
  followup(db,original,at)
  if row.subject!=original.subject:raise Blocked('Follow-up must retain original subject')
  if at<aware(original.sent_at)+timedelta(days=7):raise Blocked('Seven full days have not elapsed')
  if not review.get('adds_new_value'):raise Blocked('Follow-up must add a concrete new contribution')
 else:
  new=send_usage(db,start,initial_only=True)
  target=p.get('new_companies_per_weekday',10)
  if type(target) is not int or not 1<=target<=25:raise Blocked('Invalid configured weekday introduction target')
  if new>=(25 if manual else target):raise Blocked('Daily new-company cap reached')
 if aware(row.due_at)>at:raise Blocked('Not due')
 return c,ct,profile,original


def own_mailbox(db,address,sender,kind):
 if not address or address.lower()!=sender.lower():raise Blocked('Test recipient must match the connected Gmail account / profile')
 if ledger.unresolved(db) or db.scalar(select(Outreach.id).where(Outreach.status.in_(['unknown','sending'])).limit(1)):
  raise Blocked('Uncertain delivery exists; reconcile before further communication')
 if kind=='self_test':
  start=now().astimezone(ZoneInfo(settings().timezone)).replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc)
  if send_usage(db,start)>=snapshot(db,kind)['daily_cap']:raise Blocked('Daily total cap reached')
 return snapshot(db,kind)

def set_paused(db,enabled):
 ledger.lock(db)
 row=db.get(State,'outreach_policy')
 if not row:raise Blocked('Outreach policy has not been configured')
 before='active' if row.value.get('enabled') else 'paused'
 after='active' if enabled else 'paused'
 row.value={**row.value,'enabled':enabled}
 if not enabled:
  from ..models import Job
  from ..domain.states import transition
  for job in db.scalars(select(Job).where(Job.kind.in_(['send','followup_prepare']),Job.status=='queued')):
   transition(db,job,'blocked',domain='job',reason='campaign_paused')
   job.error='Campaign paused; deliberate requeue required'
   job.finished_at=now()
 if before!=after:db.add(DomainTransition(domain='campaign',entity_id='personal',from_state=before,to_state=after,reason='operator_policy_change'))
 db.commit()
 return row.value


def background(db,kind):
 paid={'discover','research','pipeline','generate','regenerate','verify','followup_prepare','paid_provider'}
 p=db.get(State,'outreach_policy')
 if kind in paid and (settings().manual_mode or (p and p.value.get('paid_services_authorized') is False)):
  raise Blocked('Manual mode / policy: paid API calls are disabled')
 return snapshot(db,'background:'+kind)


def followup(db, original, at):
 """Shared preparation/delivery eligibility; it never approves a new message."""
 if original and original.sent_at and at<aware(original.sent_at)+timedelta(hours=168):raise Blocked('Seven full days have not elapsed')
 if not original or original.status!='sent' or not original.provider_id or not original.thread_id or not original.message_id or not original.sent_at:
  raise Blocked('Confirmed original thread required')
 op=ledger.operation(db,'send:'+original.id)
 if op and (op.status!='succeeded' or ledger.latest(db,op).receipt.get('sent_verified') is not True):raise Blocked('Original confirmation pending')
 p=db.get(State,'outreach_policy');value=p.value if p else {}
 if not value.get('enabled') or value.get('stop_requested'):raise Blocked('Campaign paused or stopped')
 if value.get('max_followups_per_company')!=1:raise Blocked('Only one follow-up permitted')
 if at<aware(original.sent_at)+timedelta(hours=168):raise Blocked('Seven full days have not elapsed')
 c=db.get(Company,original.company_id);ct=db.get(Contact,original.contact_id)
 if not c or not ct or c.demo or c.stage in STOP or c.research.get('followups') is False or db.get(Suppression,ct.email.lower()):raise Blocked('Conversation stopped or follow-ups disabled')
 if db.scalar(select(Event.id).where(Event.company_id==c.id,Event.kind.in_(['reply','auto_reply','bounce','opt_out','negative','closed']))):raise Blocked('Existing response stops follow-up')
 from ..intelligence.discovery import best_contact
 if best_contact(db,c) is not ct:raise Blocked('Current suitable contact required; research again')
 if ledger.unresolved(db):raise Blocked('Uncertain delivery exists')
 return c,ct
