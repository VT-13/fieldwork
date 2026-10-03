import base64
import asyncio
from datetime import timedelta
from email.message import EmailMessage
from email.utils import parseaddr
import httpx
from sqlalchemy import select, func
from .config import settings
from .core import Blocked, aware, day_start, STOP_STAGES, record_event, profile_fingerprint
from .models import Company, Contact, Outreach, Profile, State, Suppression, now

class Mailbox:
    def __init__(self):
        self.cfg = settings()
        self.token = ""

    async def connect(self):
        s = self.cfg
        if not all([s.oauth_client_id,s.oauth_refresh_token,s.sender_email]):
            raise Blocked("Mailbox OAuth credentials and SENDER_EMAIL are required")
        url = "https://oauth2.googleapis.com/token" if s.mail_provider=="gmail" else f"https://login.microsoftonline.com/{s.microsoft_tenant}/oauth2/v2.0/token"
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(url,data={"grant_type":"refresh_token","client_id":s.oauth_client_id,"client_secret":s.oauth_client_secret,"refresh_token":s.oauth_refresh_token})
        r.raise_for_status()
        self.token = r.json()["access_token"]
        # Rotated Microsoft refresh tokens may be returned. Persist only in external secret storage;
        # the original remains valid under Microsoft's normal rotation policy until revoked.
        who = await self.call("GET","https://gmail.googleapis.com/gmail/v1/users/me/profile" if s.mail_provider=="gmail" else "https://graph.microsoft.com/v1.0/me?$select=mail,userPrincipalName")
        address = who.get("emailAddress") or who.get("mail") or who.get("userPrincipalName")
        if address.lower()!=s.sender_email.lower():
            raise Blocked("OAuth mailbox identity does not match SENDER_EMAIL")

    async def call(self, method, url, **kwargs):
        async with httpx.AsyncClient(timeout=25,follow_redirects=False) as client:
            r = await client.request(method,url,headers={"Authorization":"Bearer "+self.token,**kwargs.pop("headers",{})},**kwargs)
        r.raise_for_status()
        return r.json() if r.content else {}

    async def send(self, db, row, contact, original):
        s = self.cfg
        msg = EmailMessage()
        msg["From"] = s.sender_email
        msg["To"] = contact.email
        msg["Subject"] = row.subject
        msg["Message-ID"] = row.message_id
        if original:
            msg["In-Reply-To"] = original.message_id
            msg["References"] = original.message_id
        msg.set_content(row.body)
        if s.mail_provider=="gmail":
            payload = {"raw":base64.urlsafe_b64encode(msg.as_bytes()).decode()}
            if original and original.thread_id:
                payload["threadId"] = original.thread_id
            data = await self.call("POST","https://gmail.googleapis.com/gmail/v1/users/me/messages/send",json=payload)
            return data["id"],data["threadId"]
        # Graph accepts MIME, keeping the RFC Message-ID for reconciliation/thread headers.
        await self.call("POST","https://graph.microsoft.com/v1.0/me/sendMail",
            headers={"Content-Type":"text/plain"},content=base64.b64encode(msg.as_bytes()))
        return "accepted:"+row.id,""

    async def messages(self, since):
        if self.cfg.mail_provider=="gmail":
            token = None
            result = []
            for _ in range(10):
                params = {"q":f"after:{int(since.timestamp())}","maxResults":100}
                if token:
                    params["pageToken"]=token
                data = await self.call("GET","https://gmail.googleapis.com/gmail/v1/users/me/messages",params=params)
                for item in data.get("messages",[]):
                    full = await self.call("GET",f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{item["id"]}',params={"format":"full"})
                    payload = full.get("payload",{})
                    headers = {h["name"].lower():h["value"] for h in payload.get("headers",[])}
                    def body(p):
                        raw = p.get("body",{}).get("data","")
                        txt = base64.urlsafe_b64decode(raw+"="*(-len(raw)%4)).decode(errors="replace") if raw else ""
                        return txt+"\n"+"\n".join(body(c) for c in p.get("parts",[]))
                    result.append({"id":item["id"],"thread":full.get("threadId",""),"headers":headers,"body":body(payload)[:30000]})
                token = data.get("nextPageToken")
                if not token:
                    return result
            raise Blocked("Inbox sync page budget exhausted; narrow mailbox or extend sync implementation before sending")
        url = "https://graph.microsoft.com/v1.0/me/messages"
        params = {"$filter":f"receivedDateTime ge {since.isoformat()}","$top":100,"$select":"id,conversationId,internetMessageId,internetMessageHeaders,from,subject,body"}
        result = []
        for _ in range(10):
            data = await self.call("GET",url,params=params)
            for m in data.get("value",[]):
                h = {v["name"].lower():v["value"] for v in m.get("internetMessageHeaders",[])}
                h.update({"from":m.get("from",{}).get("emailAddress",{}).get("address",""),"subject":m.get("subject",""),"message-id":m.get("internetMessageId","")})
                result.append({"id":m["id"],"thread":m.get("conversationId",""),"headers":h,"body":m.get("body",{}).get("content","")[:30000]})
            url = data.get("@odata.nextLink")
            if not url:
                return result
            if not url.startswith("https://graph.microsoft.com/"):
                raise Blocked("Unexpected Graph continuation URL")
            params = None
        raise Blocked("Inbox sync page budget exhausted")

async def sync_mailbox(db, mailbox=None):
    mailbox = mailbox or Mailbox()
    if not mailbox.token:
        await mailbox.connect()
    state = db.get(State,"mail_sync")
    start = now()
    since = aware(__import__('datetime').datetime.fromisoformat(state.value["at"]))-timedelta(minutes=10) if state else start-timedelta(days=7)
    try:
        async with asyncio.timeout(60):
            messages = await mailbox.messages(since)
    except TimeoutError:
        raise Blocked("Mailbox sync exceeded 60 seconds; sending paused until a complete sync succeeds")
    sent = list(db.scalars(select(Outreach).where(Outreach.status.in_(["sent","sending","unknown"])) ))
    for m in messages:
        h = m["headers"]
        sender = parseaddr(h.get("from",""))[1].lower()
        if sender == settings().sender_email.lower():
            for row in sent:
                if h.get("message-id")==row.message_id:
                    row.provider_id,row.thread_id = m["id"],m["thread"]
                    if row.status in {"sending","unknown"}:
                        row.status = "sent"
                        company = db.get(Company,row.company_id)
                        if company.stage not in STOP_STAGES:
                            company.stage = "contacted"
            continue
        text = m["body"].lower()
        bounce = any(x in sender for x in ("mailer-daemon","postmaster")) or "delivery-status" in h.get("content-type","")
        auto = h.get("auto-submitted","").lower() not in ("","no")
        for row in sent:
            contact = db.get(Contact,row.contact_id)
            same_thread = bool(row.thread_id and row.thread_id==m["thread"])
            reference = row.message_id in (h.get("in-reply-to","")+h.get("references","")) if row.message_id else False
            dsn = bounce and row.message_id and row.message_id.lower() in text
            if dsn or ((same_thread or reference) and sender==contact.email.lower()):
                # Stop on any matched reply, including automatic replies; resume manually only.
                kind = "bounce" if dsn else "opt_out" if any(x in text for x in ("unsubscribe","remove me","do not contact","stop emailing")) else "reply"
                record_event(db,db.get(Company,row.company_id),kind,settings().mail_provider+":"+m["id"],"Automatic response" if auto else h.get("subject",""))
    db.merge(State(key="mail_sync",value={"at":start.isoformat(),"messages":len(messages)}))
    db.commit()
    return len(messages)

async def send_one(db, row, mailbox=None):
    cfg = settings()
    if cfg.dry_run or cfg.manual_mode:
        raise Blocked("DRY_RUN is enabled; no email sent")
    company = db.get(Company,row.company_id)
    contact = db.get(Contact,row.contact_id)
    profile = db.get(Profile,1)
    if row.status!="approved" or not row.review.get("passed") or row.review.get("personalization_score",0)<=80:
        raise Blocked("Draft must pass quality review and be approved")
    if company.demo or company.stage in STOP_STAGES or db.get(Suppression,contact.email.lower()):
        raise Blocked("Demo or stopped/suppressed conversation")
    if not profile or not profile.data.get("verified") or profile.data.get("email","").lower()!=cfg.sender_email.lower():
        raise Blocked("Verify profile and match its email to SENDER_EMAIL")
    if row.review.get("profile_hash") != profile_fingerprint(profile.data):
        raise Blocked("Profile changed since quality review; regenerate this draft")
    if company.distance_miles is None:
        raise Blocked("Confirm company distance before outreach")
    if contact.validation!="valid" or not contact.validated_at or aware(contact.validated_at)<now()-timedelta(days=7):
        raise Blocked("Contact needs fresh non-catch-all email validation")
    if aware(row.due_at)>now():
        raise Blocked("Draft is not due")
    count = db.scalar(select(func.count()).select_from(Outreach).where(Outreach.sent_at>=day_start(),Outreach.attempts>0))
    if count>=cfg.daily_send_limit:
        raise Blocked("Daily sending limit reached")
    last = db.scalar(select(func.max(Outreach.sent_at)))
    if last and (now()-aware(last)).total_seconds()<cfg.send_interval_seconds:
        raise Blocked("Minimum sending interval has not elapsed")
    # Always sync immediately before a send, including explicit/manual sends.
    mailbox = mailbox or Mailbox()
    if not mailbox.token:
        await mailbox.connect()
    await sync_mailbox(db,mailbox)
    db.refresh(company)
    db.refresh(row)
    if company.stage in STOP_STAGES or row.status!="approved" or db.get(Suppression,contact.email.lower()):
        raise Blocked("Inbox update stopped the conversation")
    original = db.scalar(select(Outreach).where(Outreach.company_id==company.id,Outreach.sequence==0)) if row.sequence else None
    if original and original.status!="sent":
        raise Blocked("Original email is not confirmed sent")
    row.status="sending"
    row.attempts+=1
    row.sent_at=now()  # Reserve quota before external mutation; uncertain attempts count.
    row.message_id = f"<internship-{row.id}@{cfg.sender_email.split('@')[-1]}>"
    db.commit()
    try:
        row.provider_id,row.thread_id = await mailbox.send(db,row,contact,original)
        row.status="sent"
        company.stage="contacted"
        db.commit()
    except httpx.HTTPStatusError as exc:
        # A definite 429 rejection is safe to retry at a later worker tick (max 3).
        row.status = "approved" if exc.response.status_code==429 and row.attempts<3 else "failed" if 400<=exc.response.status_code<500 else "unknown"
        row.due_at=now()+timedelta(minutes=15)
        db.commit()
        raise Blocked(f"Mail provider HTTP {exc.response.status_code}; delivery state {row.status}")
    except Exception:
        row.status="unknown"
        db.commit()
        raise Blocked("Delivery uncertain; reconcile Sent mail before taking any further action")
