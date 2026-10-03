from contextlib import contextmanager
from fastapi.testclient import TestClient
from app.main import app
from app.db import session
from app.models import State, DomainTransition
from app.ui_contracts import CONTRACTS
from app import campaign
from sqlalchemy import select

HEADERS={'Authorization':'Bearer local-development-key-change-me'}

def test_private_read_contracts_normalize_defaults_and_remain_authenticated(db,ready,monkeypatch):
    @contextmanager
    def connection():yield db
    monkeypatch.setattr(campaign,'Session',connection)
    monkeypatch.delenv('LIVE_BATCH_DIRECTORY',raising=False)
    app.dependency_overrides[session]=lambda:db
    try:
        with TestClient(app) as client:
            for path in ('profile','companies','outreach','settings','metrics','responses','campaign','integrations/gmail'):
                assert client.get('/'+path).status_code==401
                response=client.get('/'+path,headers=HEADERS)
                assert response.status_code==200,response.text
            draft=client.get('/outreach',headers=HEADERS).json()[0]
            assert draft['review']['issues']==[]
            assert draft['review']['passed'] is True
            assert client.get('/campaign',headers=HEADERS).json()['ongoing_policy']['enabled'] is True
            assert client.get('/openapi.json',headers=HEADERS).status_code==404
    finally:app.dependency_overrides.clear()

def test_edits_clear_review_and_approval_then_block_reapproval(db,ready):
    row=ready[2];app.dependency_overrides[session]=lambda:db
    try:
        with TestClient(app) as client:
            body={'subject':'A specific project idea','body':'An edited message, still requiring quality review.'}
            assert client.patch('/outreach/'+row.id,json=body).status_code==401
            response=client.patch('/outreach/'+row.id,json=body,headers=HEADERS)
            assert response.status_code==200,response.text
            assert response.json()['status']=='draft'
            assert response.json()['review']['passed'] is False
            assert client.post('/outreach/'+row.id+'/approve',headers=HEADERS).status_code==409
            assert client.post('/outreach/'+row.id+'/review/reject',headers=HEADERS).json()['status']=='rejected'
            assert client.post('/outreach/'+row.id+'/review/draft',headers=HEADERS).json()['status']=='draft'
            assert db.scalar(select(DomainTransition).where(DomainTransition.reason=='operator_edit'))
    finally:app.dependency_overrides.clear()

def test_delivery_records_cannot_be_edited_or_returned_to_draft(db,ready):
    row=ready[2];row.status='unknown';row.attempts=1;db.commit()
    app.dependency_overrides[session]=lambda:db
    try:
        with TestClient(app) as client:
            assert client.patch('/outreach/'+row.id,json={'subject':'Changed','body':'Changed'},headers=HEADERS).status_code==409
            assert client.post('/outreach/'+row.id+'/review/draft',headers=HEADERS).status_code==409
            assert row.body=='Example draft' and row.status=='unknown'
    finally:app.dependency_overrides.clear()

def test_inactive_campaign_still_exposes_authoritative_pause(db,monkeypatch):
    @contextmanager
    def connection():yield db
    monkeypatch.setattr(campaign,'Session',connection);monkeypatch.delenv('LIVE_BATCH_DIRECTORY',raising=False)
    db.add(State(key='outreach_policy',value={'enabled':False}));db.commit()
    assert campaign.status()=={'active':False,'ongoing_policy':{'enabled':False}}
    db.get(State,'outreach_policy').value={'enabled':True};db.commit()
    assert campaign.status()['ongoing_policy']['enabled'] is True

def test_contract_schema_generation_is_deterministic():
    assert all(model.model_json_schema() for model in CONTRACTS)
