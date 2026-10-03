import asyncio
import re
from datetime import timedelta
from sqlalchemy import select
from . import providers
from .models import Company, Contact, Evidence, Outreach, Profile, now
from .schemas import ResearchResult, DraftResult, ReviewResult, ProfileInput
from .config import settings
from .core import Blocked, score_company, public_url, aware, STOP_STAGES, profile_fingerprint

async def research(db, company):
    if company.demo:
        raise Blocked("Demo companies never use live research")
    if company.researched_at and aware(company.researched_at)>now()-timedelta(days=14):
        return
    cfg = settings()
    pages = []
    async with asyncio.timeout(cfg.research_seconds):
        # Discover a contact once; a missing Hunter key does not block research-only use.
        if cfg.hunter_api_key and not db.scalar(select(Contact).where(Contact.company_id==company.id)):
            for c in (await providers.hunter_contacts(db,company))[:3]:
                if not db.scalar(select(Contact).where(Contact.email==c["value"].lower())):
                    db.add(Contact(company_id=company.id,email=c["value"].lower(),name=" ".join(filter(None,[c.get("first_name"),c.get("last_name")])),title=c.get("position") or "",source="Hunter"))
            db.commit()
        contact = db.scalar(select(Contact).where(Contact.company_id==company.id))
        root = "https://"+company.domain
        urls = [root,root+"/about",root+"/careers",root+"/contact",root+"/blog",root+"/news"][:cfg.max_pages]
        extracted = None
        for i,url in enumerate(urls):
            try:
                content = await providers.scrape(db,company,url)
            except (providers.httpx.HTTPStatusError, Blocked):
                if i == 0:
                    raise
                continue
            pages.append({"url":url,"text":content[:9000]})
            # Extract after homepage and once more after priority pages; never after every page.
            if i == 0 or i == len(urls)-1 or (i == 3):
                extracted = await providers.llm(db,company.id,ResearchResult,
                    "Extract company facts with exact short quotes from the supplied pages. Each fact needs its exact page URL. Use unknown/empty values for absent information. size must be 1-10, 11-50, 51-200, 201+, or unknown. Do not infer student friendliness or internship history from generic careers content. Limit to 6 high-value facts.",
                    {"company":company.name,"pages":pages})
                valid = [f for f in extracted.facts if any(p["url"]==f.url and f.quote.strip() and f.quote in p["text"] for p in pages)]
                extracted.facts = valid
                if extracted.description and contact and len(valid)>=2:
                    break
        if not extracted or len(extracted.facts)<2:
            raise Blocked("Insufficient source-backed facts; add sources or review this company manually")
        company.research = extracted.model_dump()
        company.description = extracted.description
        company.industry = extracted.industry
        for fact in extracted.facts:
            if not db.scalar(select(Evidence).where(Evidence.company_id==company.id,Evidence.quote==fact.quote)):
                db.add(Evidence(company_id=company.id,**fact.model_dump()))
        company.researched_at = now()
        company.stage = "researched"
        profile = db.get(Profile,1)
        score_company(company,bool(contact), (profile.data if profile else ProfileInput().model_dump())["interests"])
        db.commit()

async def generate(db, company, sequence=0, replace=False):
    if company.stage in STOP_STAGES:
        raise Blocked("Conversation stopped; no further outreach")
    existing = db.scalar(select(Outreach).where(Outreach.company_id==company.id,Outreach.sequence==sequence))
    if existing and not replace:
        return existing
    if existing and existing.status not in {"draft","approved","rejected"}:
        raise Blocked("Only unsent drafts may be replaced")
    profile = db.get(Profile,1)
    if not profile or not profile.data.get("verified") or not profile.data.get("name"):
        raise Blocked("Complete and verify your profile before generating real outreach")
    if company.demo:
        raise Blocked("Demo draft is a fixture; it cannot be regenerated or sent")
    contacts = list(db.scalars(select(Contact).where(Contact.company_id==company.id)))
    if not contacts:
        raise Blocked("No contact found")
    contact = next((c for c in contacts if c.validation=="valid"),contacts[0])
    facts = list(db.scalars(select(Evidence).where(Evidence.company_id==company.id)))
    if len(facts)<2:
        raise Blocked("Research needs at least two sourced facts")
    prior = list(db.scalars(select(Outreach).where(Outreach.company_id==company.id,Outreach.sequence<sequence).order_by(Outreach.sequence)))
    # Keep premium-model context compact even when the stored resume is long.
    compact_profile={k:str(profile.data.get(k,""))[:500] for k in ("name","grade","location","background","linkedin_url")}
    for key in ("projects","awards","skills","interests","cover_letter_snippets","portfolio_links"):
        compact_profile[key]=[str(x)[:240] for x in profile.data.get(key,[])[:6]]
    compact_profile["voice_notes"]=profile.data.get("voice_notes","")[:2000]
    compact_profile["writing_samples"]=[x[:1500] for x in profile.data.get("writing_samples",[])[:3]]
    compact_profile["resume_excerpt"]=profile.data.get("resume","")[:1500]
    payload = {"profile":compact_profile,"company":{"name":company.name,"description":company.description},
               "contact":{"name":contact.name,"title":contact.title},
               "facts":[{"id":f.id,"fact":f.fact,"quote":f.quote,"url":f.url} for f in facts],
               "prior":[{"subject":d.subject,"body":d.body} for d in prior],"sequence":sequence,
               "learning": [g for g in learning(db) if g["usable_signal"]][:5]}
    instruction = "Write a concise 90-170 word outreach email from this high school freshman. Open with 1-3 specific supported company observations. Match real profile experience to one feasible proposed contribution; phrase proposed work as an offer, not completed work. End with a low-friction question. Be candid about grade. Avoid generic praise, exaggerated skills, tracking links and claims about hiring eligibility. Use only supplied evidence for company claims. Cite the used evidence IDs in evidence_ids (not in the email body). Include a natural opt-out sentence. If sequence > 0, reference the prior email, keep the same subject and add a distinct useful idea without inventing new achievements. Do not repeat previous value propositions. Sign with the profile name."
    instruction += " Match the student's writing samples and voice notes if present. Be curious, direct and a little informal; use natural contractions. Ask one genuine company-specific question where useful. Avoid corporate praise, inflated adjectives, rehearsed enthusiasm and stock openings. Do not invent a personal anecdote, add fake typos, or optimize to fool a detector. A modest, concrete proposal is enough."
    last = None
    for attempt in range(2):
        draft = await providers.llm(db,company.id,DraftResult,instruction,payload,"generate")
        report = await providers.llm(db,company.id,ReviewResult,
            "Independently check this email against the supplied evidence and student profile. Score personalization 0-100. Reject generic praise, unsupported company statements, wrong recipient names, exaggerated student claims, spam tone and follow-ups that add no new value. For initial outreach adds_new_value=true. All factual claims must be supported; an evidence ID alone is not proof. Return specific issues.",
            {**payload,"draft":draft.model_dump()},"review")
        issues = list(report.issues)
        if not draft.evidence_ids or not set(draft.evidence_ids)<=set(f.id for f in facts):
            issues.append("Missing or invalid evidence references")
        if "\n" in draft.subject or "\r" in draft.subject or len(draft.subject)>180:
            issues.append("Invalid subject")
        if not 60<=len(draft.body.split())<=220:
            issues.append("Email length outside bounds")
        passed = report.personalization_score>80 and all(getattr(report,k) for k in ["grounded","names_correct","claims_supported","non_generic","non_spammy","adds_new_value"]) and not issues
        last = Outreach(company_id=company.id,contact_id=contact.id,sequence=sequence,
                        subject=prior[0].subject if prior else draft.subject,body=draft.body,evidence_ids=draft.evidence_ids,strategy=draft.strategy,
                        status="approved" if passed and settings().auto_approve else "draft" if passed else "rejected",
                        review={**report.model_dump(),"issues":issues,"passed":passed,"attempts":attempt+1,"profile_hash":profile_fingerprint(profile.data)})
        if passed:
            break
        payload["revision_feedback"] = issues
    if existing:
        from .models import Event, uid
        db.add(Event(company_id=company.id,kind="draft_revision",source_id="revision:"+uid(),detail=existing.subject+"\n"+existing.body))
        for field in ("subject","body","evidence_ids","strategy","status","review"):
            setattr(existing,field,getattr(last,field))
        last=existing
    else:
        db.add(last)
    company.stage = "drafted" if sequence==0 else company.stage
    db.commit()
    return last

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
