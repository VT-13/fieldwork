from sqlalchemy import select
from .models import Company, Contact, Evidence, Outreach

def seed(db):
    if db.scalar(select(Company).where(Company.demo==True)):
        return {"seeded":False}
    examples=[("Sierra Robotics Lab","Robotics",12,91,"Builds inspection robots for small manufacturing teams.","Inspection robots combine camera feeds with operator dashboards."),
              ("Granite Cloud Studio","Software",8,86,"Develops scheduling software for local service businesses.","The scheduling dashboard helps teams manage repeat appointments."),
              ("Oakline Analytics","Finance",23,78,"Creates reporting tools for independent financial teams.","Reporting tools turn recurring spreadsheets into reusable workflows.")]
    for i,(name,industry,miles,score,description,fact) in enumerate(examples):
        c=Company(name=name,domain=f"fictional-{i}.example.com",website=f"https://fictional-{i}.example.com",industry=industry,distance_miles=miles,score=score,description=description,source="Fictional demo fixture",demo=True,stage="drafted" if i==0 else "researched",research={"size":"11-50","technologies":[],"facts":[]},score_factors={"proximity":14,"technology_alignment":20,"contact_availability":10})
        db.add(c);db.flush()
        contact=Contact(company_id=c.id,email=f"demo{i}@example.com",name="Demo founder",title="Founder",source="Fictional fixture",validation="demo")
        db.add(contact);db.flush()
        e=Evidence(company_id=c.id,url=c.website,quote=fact,fact=fact,category="product")
        db.add(e);db.flush()
        if i==0:
            db.add(Outreach(company_id=c.id,contact_id=contact.id,subject="A small dashboard idea for your inspection robots",body="Hi,\n\nYour focus on inspection robots for small manufacturing teams caught my attention, especially the connection between camera feeds and operator dashboards.\n\nI’m a high school freshman in the Rocklin/Roseville area and a VEX Robotics World Championship competitor. I’ve also built websites for local businesses. I’d be interested in helping prototype a simple dashboard view that makes inspection results easier for an operator to review.\n\nWould you be open to a short conversation about whether a small, supervised project could be useful to your team? I’m happy to start with a clearly scoped task.\n\nIf this isn’t a fit, let me know and I won’t follow up.\n\n[Your name]",evidence_ids=[e.id],review={"passed":False,"personalization_score":92,"issues":["Fictional demo. Complete profile and generate a real draft before sending."]},status="demo"))
    db.commit()
    return {"seeded":True}
