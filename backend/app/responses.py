"""Targeted, read-only Gmail response tracking. Never marks email read or sends mail."""
import asyncio,base64,fcntl,html,re
from datetime import datetime,timedelta,timezone
from email.utils import parseaddr
from pathlib import Path
from urllib.parse import quote
from sqlalchemy import select
from .db import Session
from .models import Company,Contact,Outreach,Event,State,now
from .core import aware,record_event,Blocked
from .mail import Mailbox
from .config import settings
BASE='https://gmail.googleapis.com/gmail/v1/users/me/'

def text_body(p):
 raw=p.get('body',{}).get('data','')
 txt=base64.urlsafe_b64decode(raw+'='*(-len(raw)%4)).decode(errors='replace') if raw else ''
 if p.get('mimeType')=='text/html':
  txt=re.sub(r'<(style|script)\b[^>]*>.*?</\1>', '', txt, flags=re.I|re.S)
  txt=html.unescape(re.sub('<[^>]*>',' ',txt))
 parts=p.get('parts',[])
 if p.get('mimeType')=='multipart/alternative':
  plain=[c for c in parts if c.get('mimeType')=='text/plain']
  parts=plain or parts[:1]
 return txt+'\n'+'\n'.join(text_body(c) for c in parts)

def ingest(db,msg,rows,contacts,sender_email):
 h={h['name'].lower():h['value'] for h in msg.get('payload',{}).get('headers',[])}
 sender=parseaddr(h.get('from',''))[1].lower()
 if sender==sender_email.lower() and 'SENT' in msg.get('labelIds',[]):
  from .services.ledger import reconcile_sent
  for row in rows:
   if row.message_id and h.get('message-id')==row.message_id:
    reconcile_sent(db,row,msg['id'],msg.get('threadId',''),row.message_id)
  return None
 if not sender or sender==sender_email.lower() or 'SENT' in msg.get('labelIds',[]):return None
 text=text_body(msg.get('payload',{}));lower=text.lower()
 bounce=any(x in sender for x in ['mailer-daemon','postmaster']) or 'delivery-status' in h.get('content-type','')
 references=h.get('in-reply-to','')+' '+h.get('references','')
 received=datetime.fromtimestamp(int(msg.get('internalDate','0'))/1000,timezone.utc)
 matched=None
 for row in rows:
  if row.sent_at and received<aware(row.sent_at)-timedelta(minutes=1):continue
  ct=contacts[row.contact_id]
  recipient=re.search(r'final-recipient:\s*rfc822;\s*'+re.escape(ct.email.lower())+r'(?:\s|$)',lower)
  if bounce:
   match=bool(recipient or (row.message_id and row.message_id.lower() in lower))
  else:
   match=(row.thread_id and row.thread_id==msg.get('threadId')) or (row.message_id and row.message_id in references) or sender==ct.email.lower()
  if match:matched=row;break
 if not matched:return None
 auto=h.get('auto-submitted','').lower() not in ('','no') or bool(h.get('x-autoreply') or h.get('x-autorespond'))
 # Avoid opt-out false positives from quoted historical emails.
 newest=re.split(r'\n(?:On .+wrote:|From:|>)',text,maxsplit=1)[0].lower()
 kind='bounce' if bounce else 'auto_reply' if auto else 'opt_out' if any(x in newest for x in ['do not contact','remove me','stop emailing','unsubscribe me']) else 'reply'
 key='response:'+msg['id'];existing=db.get(State,key)
 if existing:return existing.value
 company=db.get(Company,matched.company_id)
 record_event(db,company,kind,'gmail:'+msg['id'],'Automatic acknowledgment' if auto else h.get('subject','')[:200])
 data={'id':msg['id'],'company_id':company.id,'company':company.name,'kind':kind,'sender':sender,'subject':h.get('subject',''),'preview':text.strip()[:3000],'received_at':received.isoformat(),'thread_id':msg.get('threadId',''),'handled':False,'gmail_url':'https://mail.google.com/mail/u/?authuser='+quote(sender_email)+'#all/'+msg.get('threadId',msg['id'])}
 db.merge(State(key=key,value=data));db.commit();return data

async def sync(box=None):
 lockdir=Path(settings().data_directory) if settings().data_directory else Path.home()/'.local/share/fieldwork/data';lockdir.mkdir(parents=True,exist_ok=True)
 with (lockdir/'response-sync.lock').open('a') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return {'status':'already_running'}
  with Session() as db:
   previous=db.get(State,'response_sync');old=previous.value if previous else {}
   from .services import ledger,policy
   start=now()
   attempt,_=ledger.claim(db,'reply-sync:'+start.isoformat(),'reply_sync','gmail',lambda:policy.snapshot(db,'read_only'),entity_id='personal')
   db.merge(State(key='response_sync',value={**old,'status':'syncing','last_attempt':start.isoformat()}));db.commit()
   try:
    box=box or Mailbox()
    if not box.token:await box.connect()
    if box.cfg.mail_provider!='gmail':raise Blocked('This response tracker requires the connected Gmail account')
    rows=list(db.scalars(select(Outreach).where(Outreach.sent_at!=None,Outreach.status.in_(['sent','unknown','sending']))))
    contacts={c.id:c for c in db.scalars(select(Contact))}
    rows=[r for r in rows if r.contact_id in contacts]
    # Rotate through up to 100 threads per pass; contact searches cover new unthreaded replies.
    threads=sorted({r.thread_id for r in rows if r.thread_id});cursor=int(old.get('thread_cursor',0))
    selected=(threads[cursor:]+threads[:cursor])[:100];seen=set();history=dict(old.get('thread_history',{}))
    async with asyncio.timeout(180):
     for tid in selected:
      minimal=await box.call('GET',BASE+'threads/'+tid,params={'format':'minimal'})
      hid=minimal.get('historyId')
      if hid and history.get(tid)==hid:continue
      thread=await box.call('GET',BASE+'threads/'+tid,params={'format':'full'})
      for msg in thread.get('messages',[]):ingest(db,msg,rows,contacts,box.cfg.sender_email);seen.add(msg['id'])
      if hid:history[tid]=hid
     since=datetime.fromisoformat(old['last_success'])-timedelta(minutes=10) if old.get('last_success') else min([aware(r.sent_at) for r in rows],default=start)-timedelta(minutes=1)
     addresses=sorted({contacts[r.contact_id].email for r in rows})
     for n in range(0,len(addresses),30):
      query='after:'+str(int(since.timestamp()))+' {'+' '.join('from:'+a for a in addresses[n:n+30])+(' from:mailer-daemon from:postmaster' if n==0 else '')+'}'
      token=None
      for page in range(10):
       params={'q':query,'maxResults':100,'includeSpamTrash':True}
       if token:params['pageToken']=token
       result=await box.call('GET',BASE+'messages',params=params)
       for item in result.get('messages',[]):
        if item['id'] in seen or db.get(State,'response:'+item['id']):continue
        msg=await box.call('GET',BASE+'messages/'+item['id'],params={'format':'full'})
        ingest(db,msg,rows,contacts,box.cfg.sender_email);seen.add(item['id'])
       token=result.get('nextPageToken')
       if not token:break
      if token:raise Blocked('Response page budget reached; will retry without advancing sync time')
    result={'status':'ok','last_success':start.isoformat(),'last_attempt':start.isoformat(),'thread_cursor':(cursor+len(selected))%max(1,len(threads)),'thread_history':history,'poll_seconds':300}
    db.merge(State(key='response_sync',value=result));ledger.finish(db,attempt,'succeeded',receipt={'checked_at':start.isoformat()});return {k:v for k,v in result.items() if k!='thread_history'}
   except Exception as exc:
    error='Gmail connection needs attention' if getattr(getattr(exc,'response',None),'status_code',None) in (400,401,403) else 'Response check failed: '+type(exc).__name__
    db.rollback();db.merge(State(key='response_sync',value={**old,'status':'error','last_attempt':start.isoformat(),'error':error,'poll_seconds':300}));ledger.finish(db,attempt,'failed',reason='mailbox_check_failed');return {'status':'error','error':error}

def listing(db):
 rows=[r.value for r in db.scalars(select(State).where(State.key.like('response:%')))]
 rows.sort(key=lambda r:r['received_at'],reverse=True)
 s=db.get(State,'response_sync');status=s.value if s else {'status':'not_checked'}
 return {'sync':{k:v for k,v in status.items() if k!='thread_history'},'enabled':settings().response_poll_enabled,'responses':rows[:500],'needs_attention':sum(r['kind']=='reply' and not r['handled'] for r in rows)}

async def loop():
 while True:
  try:await sync()
  except Exception:
   import logging
   logging.getLogger(__name__).error("Response tracker failed; retrying in five minutes")
  await asyncio.sleep(300)

if __name__=="__main__":
 import json
 print(json.dumps(asyncio.run(sync())))
