import base64
from email.message import EmailMessage
import httpx
from .config import settings
from .core import Blocked

class Mailbox:
    def __init__(self):
        self.cfg = settings()
        self.token = ""
        self.generation = None
        self.managed = False

    async def connect(self):
        s = self.cfg
        if s.mail_provider=='gmail':
            from .gmail_oauth import access
            self.token,address,self.generation=await access()
            self.cfg=s.model_copy(update={'sender_email':address});self.managed=True
            return
        if not s.allow_legacy_oauth or s.environment=='production':raise Blocked('Legacy mailbox authorization is disabled')
        if not all([s.oauth_client_id,s.oauth_refresh_token,s.sender_email]):
            raise Blocked("Mailbox OAuth credentials and SENDER_EMAIL are required")
        url = "https://oauth2.googleapis.com/token" if s.mail_provider=="gmail" else f"https://login.microsoftonline.com/{s.microsoft_tenant}/oauth2/v2.0/token"
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(url,data={"grant_type":"refresh_token","client_id":s.oauth_client_id,"client_secret":s.oauth_client_secret,"refresh_token":s.oauth_refresh_token})
        if r.status_code>=400:raise Blocked("Mailbox refresh failed; reconnect")
        self.token = r.json()["access_token"]
        # Rotated Microsoft refresh tokens may be returned. Persist only in external secret storage;
        # the original remains valid under Microsoft's normal rotation policy until revoked.
        who = await self.call("GET","https://gmail.googleapis.com/gmail/v1/users/me/profile" if s.mail_provider=="gmail" else "https://graph.microsoft.com/v1.0/me?$select=mail,userPrincipalName")
        address = who.get("emailAddress") or who.get("mail") or who.get("userPrincipalName")
        if not address or address.lower()!=s.sender_email.lower():
            raise Blocked("OAuth mailbox identity does not match SENDER_EMAIL")

    def ensure_authorized(self,db=None):
        if self.managed:
            from .gmail_oauth import require_connection
            if db is not None:require_connection(db,self.generation)
            else:
                from .db import Session
                with Session() as current:require_connection(current,self.generation)
        elif not self.cfg.allow_legacy_oauth:raise Blocked('Mailbox authorization unavailable')

    async def call(self, method, url, **kwargs):
        from .services.ledger import active_delivery
        if self.cfg.mail_provider!='gmail':
            from urllib.parse import urlsplit
            import re
            p=urlsplit(url)
            drafting=method.upper()=='POST' and p.path=='/v1.0/me/messages' and not p.query
            updating=method.upper()=='PATCH' and re.fullmatch(r'/v1.0/me/messages/[A-Za-z0-9_%=-]+',p.path) and not p.query
            if p.scheme!='https' or p.netloc!='graph.microsoft.com' or not ((method.upper()=='GET' and p.path=='/v1.0/me') or drafting or updating):
                raise Blocked('Unsupported Outlook operation; production sending and tracking are unavailable')
            if drafting or updating:
                from .db import Session
                from .models import ActionAttempt,Operation
                with Session() as current:
                    attempt=current.get(ActionAttempt,active_delivery.get()) if active_delivery.get() else None
                    op=current.get(Operation,attempt.operation_id) if attempt else None
                    if not attempt or not attempt.authorized or attempt.status!='running' or not op or op.kind!='mailbox_draft':raise Blocked('Draft requires a durable mailbox-draft reservation')
        if self.cfg.mail_provider!='gmail' and method.upper()=='POST' and url.endswith('/sendMail'):
            raise Blocked('Outlook production sending is not implemented')
        if method.upper()=="POST" and (url.endswith("/messages/send") or url.endswith("/sendMail")) and not active_delivery.get():
            raise Blocked("Delivery requires a policy-authorized ledger reservation")
        if self.cfg.mail_provider=='gmail':
            from urllib.parse import urlsplit
            p=urlsplit(url)
            if p.scheme!='https' or p.netloc!='gmail.googleapis.com' or not p.path.startswith('/gmail/v1/users/me/'):
                raise Blocked('Unsupported Gmail endpoint')
            import re
            path=p.path.removeprefix('/gmail/v1/users/me/')
            verb=method.upper()
            read=verb=='GET' and re.fullmatch(r'(profile|history|messages|messages/[A-Za-z0-9_-]+|threads/[A-Za-z0-9_-]+)',path)
            sending=verb=='POST' and path=='messages/send'
            drafting=(verb=='POST' and path=='drafts') or (verb=='PUT' and re.fullmatch(r'drafts/[A-Za-z0-9_-]+',path))
            if not (read or sending or drafting):raise Blocked('Unsupported Gmail operation; draft sends and raw mutations are prohibited')
            if sending or drafting:
                if not active_delivery.get():raise Blocked('Delivery requires a policy-authorized ledger reservation')
                from .db import Session
                from .models import ActionAttempt,Operation
                with Session() as current:
                    attempt=current.get(ActionAttempt,active_delivery.get())
                    op=current.get(Operation,attempt.operation_id) if attempt else None
                    allowed=('company_send','self_test') if sending else ('mailbox_draft',)
                    if not attempt or not attempt.authorized or attempt.status!='running' or not op or op.kind not in allowed:
                        raise Blocked('Provider mutation requires a matching durable authorized operation')
                    if sending:
                        from .services.envelope import validate
                        validate(current,attempt,op,kwargs.get('json') or {},self.cfg.sender_email)
                    if sending and op.job_id:
                        from .services.jobs import active_job,require_owner
                        ownership=active_job.get()
                        if not ownership or ownership[0]!=op.job_id:raise Blocked('Delivery job ownership required')
                        require_owner(current,*ownership)
                    if drafting:
                        from .gmail_oauth import require_connection,COMPOSE
                        if COMPOSE not in require_connection(current,self.generation).scopes:raise Blocked('Reconnect with explicit Gmail draft permission')
            self.ensure_authorized()
        async with httpx.AsyncClient(timeout=25,follow_redirects=False) as client:
            r = await client.request(method,url,headers={"Authorization":"Bearer "+self.token,**kwargs.pop("headers",{})},**kwargs)
        from .services.contracts import MailboxFailure
        if r.status_code==404 and url.endswith('/history'):
            raise MailboxFailure('cursor_invalid', definite=True)
        if r.status_code==401 or (r.status_code==403 and 'rateLimitExceeded' not in r.text and 'userRateLimitExceeded' not in r.text):
            if self.managed:
                from .gmail_oauth import invalidate
                invalidate('provider_rejected')
            raise MailboxFailure('authorization_rejected', definite=True)
        if r.status_code==404:raise MailboxFailure('not_found', definite=True)
        if r.status_code in (429,403):raise MailboxFailure('rate_limited', definite=True, retryable=True)
        if r.status_code>=500:raise MailboxFailure('provider_unavailable', retryable=True)
        if r.status_code>=400:raise MailboxFailure('provider_rejected', definite=True)
        if len(r.content)>1_000_000:raise MailboxFailure('payload_limit')
        return r.json() if r.content else {}

    async def send(self, db, row, contact, original):
        from .services.ledger import active_delivery
        if not active_delivery.get():
            raise Blocked("Delivery requires a policy-authorized ledger reservation")
        self.ensure_authorized(db)
        s = self.cfg
        if s.mail_provider!='gmail':raise Blocked('Company delivery requires Gmail')
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
        raise Blocked('Outlook production sending is not implemented')

async def sync_mailbox(db, mailbox=None):
    """Compatibility name for the one bounded response/reconciliation reader."""
    from .responses import sync_session
    result = await sync_session(db, mailbox)
    if result['status'] not in ('ok', 'idle'):
        raise Blocked('Mailbox sync incomplete; inspect Responses before sending')
    return result.get('messages', 0)

async def send_one(db, row, mailbox=None):
    """Compatibility entry point; all company delivery now uses the same service."""
    from .services.delivery import send_company
    from .services.email_provider import MailboxProvider
    return await send_company(db,row.id,mode='worker',provider=MailboxProvider(mailbox or Mailbox()))
