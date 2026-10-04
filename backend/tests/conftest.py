import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db import Base
from app import models
from app.config import settings

@pytest.fixture
def db(monkeypatch):
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    import app.ingress as ingress
    import app.gmail_oauth as oauth
    monkeypatch.setattr(ingress,'Session',sessionmaker(engine,expire_on_commit=False))
    monkeypatch.setattr(oauth,'Session',sessionmaker(engine,expire_on_commit=False))
    with sessionmaker(engine,expire_on_commit=False)() as session:
        yield session
    engine.dispose()

@pytest.fixture(autouse=True)
def clean_settings(monkeypatch):
    settings.cache_clear()
    # Unit tests must never inherit the personal mailbox or paid provider credentials.
    for key in ["OAUTH_CLIENT_ID", "OAUTH_CLIENT_SECRET", "OAUTH_REFRESH_TOKEN", "SENDER_EMAIL", "OPENAI_API_KEY", "TAVILY_API_KEY", "FIRECRAWL_API_KEY", "GOOGLE_MAPS_API_KEY", "APOLLO_API_KEY", "HUNTER_API_KEY"]:
        monkeypatch.setenv(key, "")
    monkeypatch.setenv("API_KEY","local-development-key-change-me")
    monkeypatch.setenv("ENVIRONMENT","development")
    monkeypatch.setenv("DRY_RUN","true")
    monkeypatch.setenv("RESPONSE_POLL_ENABLED","false")
    monkeypatch.setenv("MANUAL_MODE","false")
    monkeypatch.setenv("OPERATOR_PASSWORD_HASH","")
    monkeypatch.setenv("CREDENTIAL_KEYS","")
    monkeypatch.setenv("ALLOW_LEGACY_OAUTH","false")
    yield
    settings.cache_clear()

@pytest.fixture
def ready(db):
    from app.models import Company,Contact,Profile,Outreach,Evidence,State,now
    from app.schemas import ProfileInput
    p=ProfileInput(name="Student Example",email="student@example.com",verified=True)
    db.add(Profile(id=1,data=p.model_dump()))
    c=Company(name="Example Robotics",domain="example.com",website="https://example.com",distance_miles=12,stage="drafted")
    db.add(c);db.flush()
    contact=Contact(company_id=c.id,title="Engineering Lead",email="founder@example.com",validation="valid",validated_at=now())
    db.add(contact);db.flush()
    from app.core import profile_fingerprint
    row=Outreach(company_id=c.id,contact_id=contact.id,subject="Robotics project idea",body="Example draft",status="approved",review={"passed":True,"personalization_score":91,"profile_hash":profile_fingerprint(p.model_dump())})
    c.research={'city':'Rocklin'};contact.source='https://example.com/contact'
    evidence=Evidence(company_id=c.id,url=c.website,quote='An example service',fact='An example service',category='service')
    db.add(evidence);db.flush();row.evidence_ids=[evidence.id]
    row.review={**row.review,'grounded':True,'claims_supported':True,'non_generic':True,'names_correct':True,'non_spammy':True}
    db.add(State(key='outreach_policy',value={'enabled':True,'max_followups_per_company':1}))
    db.add(row);db.commit()
    from app.intelligence.discovery import ingest_contact
    from app.intelligence.schemas import ContactRecord
    ingest_contact(db,c,ContactRecord(email=contact.email,title=contact.title,source_url=contact.source,confidence='source-observed').model_dump());db.commit()
    return c,contact,row
