"""Explicit post-restore fence; preserve uncertain attempts and all delivery receipts."""
import argparse
from sqlalchemy import select,delete
from app.db import Session
from app.models import Integration,OperatorSession,OAuthGrant,DomainTransition,now
from app.privacy import pause
from app.gmail_oauth import change
from app.services.ledger import lock
p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');args=p.parse_args()
with Session() as db:
    lock(db)
    if args.apply:
        pause(db)
        for row in db.scalars(select(Integration)):change(db,row,'disconnected','post_restore_fence',clear=True)
        db.execute(delete(OAuthGrant))
        for row in db.scalars(select(OperatorSession)):row.revoked_at=now()
        db.add(DomainTransition(domain='restore',entity_id='personal',from_state='restored',to_state='paused',reason='explicit_post_restore_fence'))
        db.commit()
    else:db.rollback()
print('Post-restore pause, credential invalidation and session revocation applied:',args.apply,'No delivery attempts changed')
