"""Compatibility CLI for one authorized message. No discovery/generation/replays."""
import asyncio,json,sys
from .db import Session
from .services.policy import company as guards
from .services.delivery import send_company

async def run(id):
    with Session() as db:
        result=await send_company(db,id,mode='scheduled')
        print(json.dumps(result))
        return result

if __name__=='__main__':asyncio.run(run(sys.argv[1]))
