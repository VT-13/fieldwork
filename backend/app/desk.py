"""Personal manual review desk. No LLM calls, no research charges, no send endpoint."""
import hashlib
import re
from email.message import EmailMessage
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from .models import State, Profile, now, uid
from .core import Blocked

class DeskDraft(BaseModel):
    company: str = Field('',max_length=200)
    subject: str = Field(min_length=1,max_length=180)
    body: str = Field(min_length=1,max_length=8000)
    evidence: str = Field('',max_length=6000)
    fictional: bool = False

class DetectorInput(BaseModel):
    draft_hash: str
    provider: str = Field('GPTZero',max_length=80)
    ai_probability: float | None = Field(None,ge=0,le=100)
    result: str = Field(min_length=1,max_length=2000)
    report_url: HttpUrl | None = None

class SignoffInput(BaseModel):
    draft_hash: str
    facts_checked: bool
    sounds_like_me: bool
    recipient_checked: bool
    detector_reviewed: bool
    notes: str = Field('',max_length=2000)

def fingerprint(packet):
    return hashlib.sha256((packet['subject']+'\n'+packet['body']+'\n'+packet.get('evidence','')+'\n'+packet.get('company','')+'\n'+str(packet.get('fictional',False))).encode()).hexdigest()

def style_check(body):
    phrases=['i hope this email finds you well','i am writing to express','esteemed company','innovative solutions','leverage my skills','passionate individual','unique blend','dynamic team','fast-paced environment','perfect fit','delve','cutting-edge']
    found=[p for p in phrases if p in body.lower()]
    words=len(body.split())
    return {'words':words,'generic_phrases':found,'long_sentences':sum(len(s.split())>32 for s in re.split(r'[.!?]+',body)),
            'has_question':'?' in body,'note':'Local writing checks only. This is not an AI detector and does not verify company facts.'}

def get_packet(db,id):
    row=db.get(State,'desk:'+id)
    if not row:
        raise Blocked('Draft not found')
    return row

def new_packet(db,body):
    if '\n' in body.subject or '\r' in body.subject:
        raise Blocked('Subject must be one line')
    id=uid()
    data={**body.model_dump(),'id':id,'updated_at':now().isoformat(),'status':'needs_review','detector':None,'signoff':None,'mailbox_draft':None,'history':[]}
    data['draft_hash']=fingerprint(data)
    data['style']=style_check(data['body'])
    db.add(State(key='desk:'+id,value=data));db.commit()
    return data

def edit_packet(db,id,body):
    row=get_packet(db,id)
    if '\n' in body.subject or '\r' in body.subject:
        raise Blocked('Subject must be one line')
    old=row.value
    data={**old,**body.model_dump(),'updated_at':now().isoformat()}
    data['draft_hash']=fingerprint(data)
    if data['draft_hash']!=old['draft_hash']:
        data['history']=(old.get('history',[])+[{'at':old['updated_at'],'subject':old['subject'],'body':old['body'],'detector':old.get('detector')}])[-10:]
        data['detector']=None
        data['signoff']=None
        data['status']='needs_review'
    data['style']=style_check(data['body'])
    row.value=data;db.commit()
    return data

def detector_result(db,id,body):
    row=get_packet(db,id)
    if body.draft_hash!=row.value['draft_hash']:
        raise Blocked('Draft changed; run the detector on the current version')
    result={**body.model_dump(mode='json'),'checked_at':now().isoformat(),'provenance':'manually_recorded_external_result'}
    row.value={**row.value,'detector':result,'signoff':None,'status':'needs_review'}
    db.commit()
    return row.value

def signoff(db,id,body):
    row=get_packet(db,id)
    if body.draft_hash!=row.value['draft_hash']:
        raise Blocked('Draft changed; review the current version')
    if not all([body.facts_checked,body.sounds_like_me,body.recipient_checked,body.detector_reviewed]):
        raise Blocked('Complete the four manual review checks')
    if not row.value.get('detector'):
        raise Blocked('Record an actual detector result first; do not invent a score')
    row.value={**row.value,'signoff':{**body.model_dump(),'at':now().isoformat()},'status':'reviewed'}
    db.commit()
    return row.value

def mailbox_address(db):
    p=db.get(Profile,1)
    address=(p.data.get('email','') if p else '').strip()
    from email_validator import validate_email,EmailNotValidError
    try:
        return validate_email(address,check_deliverability=False).normalized
    except EmailNotValidError:
        raise Blocked('Add your own email address in My profile first')

def eml(db,id):
    data=get_packet(db,id).value
    email=mailbox_address(db)
    msg=EmailMessage()
    msg['To']=email
    msg['Subject']='[DRY RUN] '+data['subject']
    msg['X-Unsent']='1'
    label='FICTIONAL PRACTICE — not a researched opportunity.\n\n' if data.get('fictional') else ''
    msg.set_content(label+data['body'])
    return msg.as_string()

def list_packets(db):
    return sorted([r.value for r in db.scalars(select(State).where(State.key.like('desk:%')))],key=lambda d:d['updated_at'],reverse=True)
