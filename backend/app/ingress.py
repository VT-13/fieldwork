"""Bound requests before parsing; fixed hosts/origins and DB-backed sensitive limits."""
import json
from datetime import timedelta
from sqlalchemy import delete
from .auth import digest
from .config import settings
from .core import aware
from .db import Session
from .models import RateBucket,now
from .services.ledger import lock


def bucket(path,method):
    if path=='/auth/login':return ('login',5,300)
    if '/integrations/' in path:return ('oauth',12,300)
    if method not in ('GET','HEAD','OPTIONS'):
        if any(x in path for x in ('send','self-test','mailbox')):return ('send',10,60)
        if any(x in path for x in ('policy','automation','campaign','privacy')):return ('control',10,60)
        return ('mutation',30,60)
    return ('read',240,60)


def rate_limit(client,path,method):
    kind,limit,seconds=bucket(path,method)
    key=digest(client+':'+kind)
    with Session() as db:
        lock(db)
        at=now();row=db.get(RateBucket,key)
        db.execute(delete(RateBucket).where(RateBucket.window_start<at-timedelta(hours=1)).execution_options(synchronize_session=False))
        if not row:row=RateBucket(key=key,window_start=at,count=0);db.add(row)
        if aware(row.window_start)<=at-timedelta(seconds=seconds):row.window_start=at;row.count=0
        row.count+=1;allowed=row.count<=limit;db.commit()
    return allowed,seconds


class Ingress:
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        cfg=settings();headers={k.decode().lower():v.decode() for k,v in scope['headers']}
        async def fail(status,detail):
            body=json.dumps({'detail':detail}).encode()
            await send({'type':'http.response.start','status':status,'headers':[(b'content-type',b'application/json'),(b'cache-control',b'no-store'),(b'x-content-type-options',b'nosniff')]})
            await send({'type':'http.response.body','body':body})
        if len(scope['path'])>512 or len(scope['query_string'])>4096:return await fail(414,'Request target too long')
        if headers.get('content-encoding') not in (None,'identity'):return await fail(415,'Encoded request bodies are unsupported')
        try:
            if int(headers.get('content-length','0'))>cfg.max_request_bytes:return await fail(413,'Request too large')
        except ValueError:return await fail(400,'Invalid content length')
        if scope['method']=='OPTIONS':return await fail(403,'Cross-origin access is unsupported')
        if headers.get('origin') and headers['origin']!=cfg.app_origin:return await fail(403,'Origin check failed')
        if scope['path']!='/health':
            try:allowed,seconds=rate_limit((scope.get('client') or ('unknown',0))[0],scope['path'],scope['method'])
            except Exception:return await fail(503,'Security state unavailable')
            if not allowed:return await fail(429,'Rate limit reached; retry later')
        chunks=[];size=0
        while True:
            event=await receive()
            if event['type']=='http.disconnect':return
            part=event.get('body',b'');size+=len(part)
            if size>cfg.max_request_bytes:return await fail(413,'Request too large')
            chunks.append(part)
            if not event.get('more_body'):break
        body=b''.join(chunks)
        if body and headers.get('content-type','').split(';')[0].strip()!='application/json':return await fail(415,'Use application/json')
        delivered=False
        async def bounded_receive():
            nonlocal delivered
            if not delivered:delivered=True;return {'type':'http.request','body':body,'more_body':False}
            return await receive()
        async def secure_send(event):
            if event['type']=='http.response.start':
                event['headers']+= [(b'cache-control',b'no-store'),(b'x-content-type-options',b'nosniff'),(b'x-frame-options',b'DENY'),(b'referrer-policy',b'no-referrer'),(b'permissions-policy',b'camera=(), microphone=(), geolocation=()')]
                if cfg.environment=='production':event['headers'].append((b'strict-transport-security',b'max-age=31536000'))
            await send(event)
        return await self.app(scope,bounded_receive,secure_send)
