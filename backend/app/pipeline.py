import asyncio
import re
from datetime import timedelta
from sqlalchemy import select
from . import providers
from .services.contracts import IntelligenceProvider
from .services.intelligence import ConfiguredIntelligence
from .models import Company, Contact, Evidence, Outreach, Profile, now
from .schemas import ResearchResult, DraftResult, ReviewResult, ProfileInput
from .config import settings
from .core import Blocked, score_company, public_url, aware, STOP_STAGES, profile_fingerprint

async def research(db, company, *, gateway: IntelligenceProvider | None=None):
    from .intelligence.evidence import research as bounded_research
    return await bounded_research(db,company,gateway or ConfiguredIntelligence())

async def generate(db, company, sequence=0, replace=False, *, gateway: IntelligenceProvider | None=None, job_id=None):
    from .intelligence.personalization import generate as bounded_generate
    return await bounded_generate(db,company,sequence,replace,gateway or ConfiguredIntelligence(),job_id)

def learning(db):
    # Observational evidence, not a causal assertion or automatic model retraining.
    from .models import Event
    rows = list(db.scalars(select(Outreach).where(Outreach.sequence==0,Outreach.status=="sent")))
    events = list(db.scalars(select(Event)))
    groups = {}
    for row in rows:
        company = db.get(Company,row.company_id)
        key = company.industry+" / "+row.strategy
        g = groups.setdefault(key,{"sent":0,"replies":0,"positive":0,"subjects":[]})
        g["sent"]+=1
        kinds = {e.kind for e in events if e.company_id==row.company_id}
        g["replies"]+=bool(kinds & {"reply","positive","negative","interview","offer"})
        g["positive"]+=bool(kinds & {"positive","interview","offer"})
        if len(g["subjects"])<3:
            g["subjects"].append(row.subject)
    return [{"segment":k,**v,"smoothed_reply_rate":round((v["replies"]+1)/(v["sent"]+5),3),"usable_signal":v["sent"]>=10} for k,v in groups.items()][:20]
