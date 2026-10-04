import base64
from app.responses import ingest,listing
from app.models import now,State,Suppression

def message(body='Happy to talk.',sender='colleague@example.com',headers=None,thread='thread',id='reply'):
 return {'id':id,'threadId':thread,'internalDate':str(int(now().timestamp()*1000)),'payload':{'headers':[{'name':'To','value':'student@example.com'},{'name':'From','value':sender},{'name':'Subject','value':'Re: Internship'},*(headers or [])],'body':{'data':base64.urlsafe_b64encode(body.encode()).decode()}}}

def setup(ready,db):
 c,ct,r=ready;r.sent_at=now();r.thread_id='thread';r.message_id='<original@example.com>';r.status='sent';db.commit();return c,ct,r

def test_reply_alias_stops_and_deduplicates(db,ready):
 c,ct,r=setup(ready,db)
 ingest(db,message(),[r],{ct.id:ct},'student@example.com')
 assert c.stage=='replied' and listing(db)['needs_attention']==1
 state=db.get(State,'response:reply');state.value={**state.value,'handled':True};db.commit()
 ingest(db,message(),[r],{ct.id:ct},'student@example.com')
 assert listing(db)['needs_attention']==0 and len(listing(db)['responses'])==1

def test_auto_ack_separate(db,ready):
 c,ct,r=setup(ready,db)
 result=ingest(db,message(headers=[{'name':'Auto-Submitted','value':'auto-replied'}]),[r],{ct.id:ct},'student@example.com')
 assert result['kind']=='auto_reply' and listing(db)['needs_attention']==0

def test_bounce_requires_recipient_evidence(db,ready):
 c,ct,r=setup(ready,db)
 assert ingest(db,message('Mentioning founder@example.com casually',sender='mailer-daemon@google.com'),[r],{ct.id:ct},'student@example.com') is None
 result=ingest(db,message('Final-Recipient: rfc822; founder@example.com',sender='mailer-daemon@google.com'),[r],{ct.id:ct},'student@example.com')
 assert result['kind']=='bounce' and db.get(Suppression,ct.email)

def test_own_mail_and_unrelated_ignored(db,ready):
 c,ct,r=setup(ready,db)
 assert ingest(db,message(sender='student@example.com'),[r],{ct.id:ct},'student@example.com') is None
 assert ingest(db,message(thread='unrelated'),[r],{ct.id:ct},'student@example.com') is None

def test_quoted_optout_not_counted(db,ready):
 c,ct,r=setup(ready,db)
 result=ingest(db,message('Sure, send more details.\nOn Monday someone wrote:\nstop emailing'),[r],{ct.id:ct},'student@example.com')
 assert result['kind']=='reply'

def test_unthreaded_known_contact(db,ready):
 c,ct,r=setup(ready,db)
 result=ingest(db,message(sender=ct.email,thread='new'),[r],{ct.id:ct},'student@example.com')
 assert result['kind']=='reply'

def test_preview_prefers_plain_text():
 from app.responses import text_body
 p={'mimeType':'multipart/alternative','parts':[{'mimeType':'text/plain','body':{'data':base64.urlsafe_b64encode(b'Hello').decode()}},{'mimeType':'text/html','body':{'data':base64.urlsafe_b64encode(b'<style>bad css</style>Hello').decode()}}]}
 assert text_body(p).strip()=='Hello'
