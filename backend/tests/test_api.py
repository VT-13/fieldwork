from fastapi.testclient import TestClient
from app.main import app
from app.db import session


def test_auth_profile_import_and_demo(db):
    app.dependency_overrides[session]=lambda:db
    try:
        with TestClient(app) as client:
            assert client.get('/companies').status_code==401
            headers={'Authorization':'Bearer local-development-key-change-me'}
            assert client.get('/profile',headers=headers).json()['grade']=='High school freshman'
            data={'name':'Acme','website':'https://example.com'}
            first=client.post('/companies',json=data,headers=headers)
            again=client.post('/companies',json=data,headers=headers)
            assert first.status_code==200 and first.json()['id']==again.json()['id']
            assert client.post('/demo',headers=headers).json()['seeded']
            assert not client.post('/demo',headers=headers).json()['seeded']
            assert client.get('/metrics',headers=headers).json()['companies']==1
    finally:
        app.dependency_overrides.clear()
