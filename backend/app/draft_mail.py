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
    if address.lower()!=settings().sender_email.lower():
        raise Blocked('Connect the mailbox that matches your profile email before saving a draft')
    previous=row.value.get('mailbox_draft') or {}
    if previous.get('status') in {'saving','unknown'}:
        raise Blocked('Previous draft save is uncertain. Check Drafts before retrying; no duplicate created')
    if previous.get('status')=='saved' and previous.get('draft_hash')==draft_hash:
        return previous
    box=mailbox or Mailbox()
    if not box.token:
        await box.connect()
    db.refresh(row)
    if row.value['draft_hash']!=draft_hash:
        raise Blocked('Draft changed while connecting; save the current version instead')
    if previous.get('provider_id') and settings().mail_provider=='outlook':
        current=await box.call('GET','https://graph.microsoft.com/v1.0/me/messages/'+quote(previous['provider_id'],safe='')+'?$select=isDraft')
        if not current.get('isDraft'):
            raise Blocked('The saved Outlook message is no longer a draft; it will not be modified')
    # Persist intent before the external write. There is no automatic create retry.
    row.value={**row.value,'mailbox_draft':{**previous,'status':'saving','draft_hash':draft_hash,'to':address}}
    db.commit()
    try:
        old_id=previous.get('provider_id')
        if settings().mail_provider=='gmail':
            payload={'message':{'raw':base64.urlsafe_b64encode(eml(db,id).encode()).decode()}}
            path='https://gmail.googleapis.com/gmail/v1/users/me/drafts'
            if old_id:
                path+='/'+quote(old_id,safe='');payload['id']=old_id
            result=await box.call('PUT' if old_id else 'POST',path,json=payload)
        else:
            path='https://graph.microsoft.com/v1.0/me/messages'+('/'+quote(old_id,safe='') if old_id else '')
            label='FICTIONAL PRACTICE — not a researched opportunity.\n\n' if row.value.get('fictional') else ''
            result=await box.call('PATCH' if old_id else 'POST',path,json={
                'subject':'[DRY RUN] '+row.value['subject'],'body':{'contentType':'Text','content':label+row.value['body']},
                'toRecipients':[{'emailAddress':{'address':address}}]})
        saved={'status':'saved','provider_id':result['id'],'draft_hash':draft_hash,'to':address,'at':now().isoformat(),'provider':settings().mail_provider}
        db.refresh(row)
        row.value={**row.value,'mailbox_draft':saved};db.commit()
        return saved
    except Exception:
        db.refresh(row)
        row.value={**row.value,'mailbox_draft':{**row.value['mailbox_draft'],'status':'unknown'}};db.commit()
        raise Blocked('Mailbox draft save failed or is uncertain. Check provider permissions and Drafts; no message was sent by this operation')
