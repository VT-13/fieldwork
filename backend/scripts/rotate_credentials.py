"""Offline encrypted-data rewrap; external keyring must contain new,old keys."""
import argparse
from sqlalchemy import select
from app.db import Session
from app.models import Integration,OAuthGrant,DomainTransition
from app.credentials import rotate
from app.services.ledger import lock
p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');args=p.parse_args()
with Session() as db:
    lock(db)
    values=[(r,'encrypted_tokens',rotate(r.encrypted_tokens)) for r in db.scalars(select(Integration)) if r.encrypted_tokens]
    values += [(r,'verifier_ciphertext',rotate(r.verifier_ciphertext)) for r in db.scalars(select(OAuthGrant)) if r.verifier_ciphertext]
    if args.apply:
        for row,column,value in values:setattr(row,column,value)
        db.add(DomainTransition(domain='integration',entity_id='personal',from_state='encrypted',to_state='rewrapped',reason='external_key_rotation'));db.commit()
    else:db.rollback()
print('Credential ciphertexts validated:',len(values),'Applied:',args.apply,'No secrets printed')
