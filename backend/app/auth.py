"""Single-operator authorization: private bearer CLI or revocable browser session."""
import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session as DBSession
from .config import settings
from .db import session
from .models import OperatorSession, now
from .core import aware
COOKIE='fieldwork_session'


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password):
    if len(password)<16 or len(password)>1024:
        raise ValueError('Use a unique operator password of 16–1024 characters')
    salt=secrets.token_bytes(16)
    hashed=hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1,dklen=32)
    return 'scrypt$'+base64.urlsafe_b64encode(salt).decode()+'$'+base64.urlsafe_b64encode(hashed).decode()


def verify_password(password,stored):
    try:
        kind,salt,expected=stored.split('$')
        if kind!='scrypt' or len(password)>1024:return False
        result=hashlib.scrypt(password.encode(),salt=base64.urlsafe_b64decode(salt),n=16384,r=8,p=1,dklen=32)
        return secrets.compare_digest(result,base64.urlsafe_b64decode(expected))
    except (ValueError,TypeError):return False


@dataclass(frozen=True)
class Operator:
    id: str='personal'
    session_hash: str=''
    mechanism: str='bearer'


def require_operator(operator):
    if operator.id!='personal':raise HTTPException(403,'Operator access required')
    return operator


def origin_check(request):
    if request.headers.get('origin')!=settings().app_origin or request.headers.get('sec-fetch-site') not in (None,'same-origin'):
        raise HTTPException(403,'Origin check failed')


def authorize(request:Request,db:Annotated[DBSession,Depends(session)]):
    supplied=request.headers.get('authorization','')
    if supplied:
        if not settings().api_key or not secrets.compare_digest(supplied,'Bearer '+settings().api_key):raise HTTPException(401,'Authentication required')
        # Browser cross-origin requests never gain authority through a bearer header.
        if request.headers.get('origin'):origin_check(request)
        return require_operator(Operator())
    token=request.cookies.get(COOKIE,'')
    row=db.get(OperatorSession,digest(token)) if token else None
    if not row or row.revoked_at or aware(row.expires_at)<=now() or row.auth_version!=digest(settings().operator_password_hash):
        raise HTTPException(401,'Authentication required')
    if request.method not in ('GET','HEAD','OPTIONS'):origin_check(request)
    return require_operator(Operator(id=row.operator_id,session_hash=row.token_hash,mechanism='session'))


def browser_operator(request:Request,db:Annotated[DBSession,Depends(session)]):
    op=authorize(request,db)
    if op.mechanism!='session':raise HTTPException(403,'Sign in with an operator session')
    return op


def create_session(db,password):
    cfg=settings()
    if not cfg.operator_password_hash:raise HTTPException(503,'Configure operator authentication before signing in')
    if not verify_password(password,cfg.operator_password_hash):raise HTTPException(401,'Authentication required')
    token=secrets.token_urlsafe(48)
    row=OperatorSession(token_hash=digest(token),operator_id='personal',auth_version=digest(cfg.operator_password_hash),expires_at=now()+timedelta(hours=cfg.session_hours))
    db.add(row);db.commit()
    return token


def set_cookie(response,token):
    cfg=settings()
    response.set_cookie(COOKIE,token,httponly=True,secure=cfg.environment=='production',samesite='lax',max_age=cfg.session_hours*3600,path='/')
