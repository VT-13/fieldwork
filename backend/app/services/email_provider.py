"""Existing Gmail/Graph transport adapted to a provider-neutral delivery contract."""
from ..config import settings
from ..core import Blocked
from .contracts import DeliveryReceipt
BASE='https://gmail.googleapis.com/gmail/v1/users/me/'

class MailboxProvider:
    def __init__(self, mailbox):
        self.mailbox=mailbox
        cfg=getattr(mailbox,'cfg',settings())
        self.name=cfg.mail_provider;self.sender=cfg.sender_email

    async def connect(self):
        if not getattr(self.mailbox,'token',''):
            await self.mailbox.connect()

    async def check_conversation(self,db,row,contact,original):
        from ..mail import sync_mailbox
        # Includes contact-matched unthreaded replies, opt-outs and bounce events.
        await sync_mailbox(db,self.mailbox)
        if self.name!='gmail':
            # First production release is Gmail-only; do not imply Graph parity.
            raise Blocked('Company delivery requires Gmail in the personal-first release')
        bounce=await self.mailbox.call('GET',BASE+'messages',params={'q':f'in:anywhere "{contact.email}" {{from:mailer-daemon from:postmaster}}','maxResults':1})
        if bounce.get('messages'):raise Blocked('Delivery notice exists; inspect and suppress before continuing')
        # Fresh unthreaded check regardless of background-sync cursor.
        query=f'in:anywhere from:{contact.email}' if original else f'in:anywhere {{to:{contact.email} from:{contact.email}}}'
        prior=await self.mailbox.call('GET',BASE+'messages',params={'q':query,'maxResults':1})
        if prior.get('messages'):raise Blocked('Existing Gmail conversation or reply; stopped pending review')
        if original:
            thread=await self.mailbox.call('GET',BASE+'threads/'+original.thread_id,params={'format':'metadata'})
            if any('SENT' not in m.get('labelIds',[]) for m in thread.get('messages',[])):
                raise Blocked('Incoming response in original thread; stopped')

    async def deliver(self,db,row,contact,original):
        pid,tid=await self.mailbox.send(db,row,contact,original)
        return DeliveryReceipt(pid,tid)

    async def confirm(self,receipt):
        if self.name!='gmail':return None
        result=await self.mailbox.call('GET',BASE+'messages/'+receipt.provider_id,params={'format':'minimal'})
        return 'SENT' in result.get('labelIds',[])
