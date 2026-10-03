import os
from uuid import uuid4
import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db import Base
from app.models import Company,Contact,Outreach

@pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'),reason='No disposable PostgreSQL test URL')
def test_postgres_constraints_and_leader_lock():
    engine=create_engine(os.environ['TEST_POSTGRES_URL'])
    schema='test_'+uuid4().hex
    with engine.connect() as a,engine.connect() as b:
        assert a.scalar(text('SELECT pg_try_advisory_lock(987640921)'))
        assert not b.scalar(text('SELECT pg_try_advisory_lock(987640921)'))
        a.execute(text('SELECT pg_advisory_unlock(987640921)'))
        a.execute(text(f'CREATE SCHEMA {schema}'))
        a.execute(text(f'SET search_path TO {schema}'))
        a.commit()
        try:
            Base.metadata.create_all(a)
            a.commit()
            with Session(a) as db:
                c=Company(name='Test',domain='example.com',website='https://example.com')
                db.add(c);db.flush()
                contact=Contact(company_id=c.id,email='test@example.com')
                db.add(contact);db.flush()
                db.add(Outreach(company_id=c.id,contact_id=contact.id,sequence=0))
                db.commit()
                db.add(Outreach(company_id=c.id,contact_id=contact.id,sequence=0))
                with pytest.raises(IntegrityError): db.commit()
                db.rollback()
                db.add(Contact(company_id=str(uuid4()),email='missing@example.com'))
                with pytest.raises(IntegrityError): db.commit()
                db.rollback()
        finally:
            a.rollback()
            a.execute(text(f'DROP SCHEMA {schema} CASCADE'))
            a.commit()
    engine.dispose()
