"""Write an unsent draft addressed only to the student. Never call sendMail/messages.send."""
import base64
from urllib.parse import quote
from .config import settings
from .mail import Mailbox
from .models import now
from .core import Blocked
from .desk import get_packet,mailbox_address,eml

async def save_mailbox_draft(db,id,draft_hash,mailbox=None):
    row=get_packet(db,id)
    if row.value['draft_hash']!=draft_hash:
        raise Blocked('Draft changed after queueing; save the current version instead')
    address=mailbox_address(db)
    previous=row.value.get('mailbox_draft') or {}
    if previous.get('status') in {'saving','unknown'}:
        raise Blocked('Previous draft save is uncertain. Check Drafts before retrying; no duplicate created')
    if previous.get('status')=='saved' and previous.get('draft_hash')==draft_hash:
        return previous
    box=mailbox or Mailbox()
    if not box.token:
        await box.connect()
    if address.lower()!=getattr(box,'cfg',settings()).sender_email.lower():raise Blocked('Connect the mailbox that matches your profile email before saving a draft')
    db.refresh(row)
    if row.value['draft_hash']!=draft_hash:
        raise Blocked('Draft changed while connecting; save the current version instead')
    if previous.get('provider_id') and settings().mail_provider=='outlook':
        current=await box.call('GET','https://graph.microsoft.com/v1.0/me/messages/'+quote(previous['provider_id'],safe='')+'?$select=isDraft')
        if not current.get('isDraft'):
            raise Blocked('The saved Outlook message is no longer a draft; it will not be modified')
    from .services import ledger,policy
    def authorize():
        if hasattr(box,'ensure_authorized'):box.ensure_authorized(db)
        if get_packet(db,id).value['draft_hash']!=draft_hash:raise Blocked('Draft changed after queueing')
        return policy.own_mailbox(db,mailbox_address(db),getattr(box,'cfg',settings()).sender_email,'mailbox_draft')
    def reserve(attempt):
        row.value={**row.value,'mailbox_draft':{**previous,'status':'saving','draft_hash':draft_hash,'to':address}}
    attempt,replay=ledger.claim(db,'mailbox-draft:'+id+':'+draft_hash,'mailbox_draft',settings().mail_provider,authorize,entity_id=id,reserve=reserve)
    if replay:return {**attempt.receipt,'status':'saved','to':address}
    try:
        old_id=previous.get('provider_id')
        if settings().mail_provider=='gmail':
            payload={'message':{'raw':base64.urlsafe_b64encode(eml(db,id).encode()).decode()}}
            path='https://gmail.googleapis.com/gmail/v1/users/me/drafts'
            if old_id:
                path+='/'+quote(old_id,safe='');payload['id']=old_id
            with ledger.permit(attempt):
                result=await box.call('PUT' if old_id else 'POST',path,json=payload)
        else:
            path='https://graph.microsoft.com/v1.0/me/messages'+('/'+quote(old_id,safe='') if old_id else '')
            label='FICTIONAL PRACTICE — not a researched opportunity.\n\n' if row.value.get('fictional') else ''
            result=await box.call('PATCH' if old_id else 'POST',path,json={
                'subject':'[DRY RUN] '+row.value['subject'],'body':{'contentType':'Text','content':label+row.value['body']},
                'toRecipients':[{'emailAddress':{'address':address}}]})
        saved={'status':'saved','provider_id':result['id'],'draft_hash':draft_hash,'to':address,'at':now().isoformat(),'provider':settings().mail_provider}
        db.refresh(row)
        row.value={**row.value,'mailbox_draft':saved}
        ledger.finish(db,attempt,'succeeded',receipt={k:v for k,v in saved.items() if k!='to'},reason='draft_saved')
        return saved
    except Exception:
        db.refresh(row)
        row.value={**row.value,'mailbox_draft':{**row.value['mailbox_draft'],'status':'unknown'}}
        ledger.finish(db,attempt,'unknown',reason='draft_save_uncertain')
        raise Blocked('Mailbox draft save failed or is uncertain. Check provider permissions and Drafts; no message was sent by this operation')
