import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db import Base
from app import models
from app.config import settings

@pytest.fixture
def db():
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(engine,expire_on_commit=False)() as session:
        yield session
    engine.dispose()

@pytest.fixture(autouse=True)
def clean_settings(monkeypatch):
    settings.cache_clear()
    monkeypatch.setenv("ENVIRONMENT","development")
    monkeypatch.setenv("DRY_RUN","true")
    monkeypatch.setenv("MANUAL_MODE","false")
    yield
    settings.cache_clear()

@pytest.fixture
def ready(db):
    from app.models import Company,Contact,Profile,Outreach,now
    from app.schemas import ProfileInput
    p=ProfileInput(name="Student Example",email="student@example.com",verified=True)
    db.add(Profile(id=1,data=p.model_dump()))
    c=Company(name="Example Robotics",domain="example.com",website="https://example.com",distance_miles=12,stage="drafted")
    db.add(c);db.flush()
    contact=Contact(company_id=c.id,email="founder@example.com",validation="valid",validated_at=now())
    db.add(contact);db.flush()
    from app.core import profile_fingerprint
    row=Outreach(company_id=c.id,contact_id=contact.id,subject="Robotics project idea",body="Example draft",status="approved",review={"passed":True,"personalization_score":91,"profile_hash":profile_fingerprint(p.model_dump())})
    db.add(row);db.commit()
    return c,contact,row
