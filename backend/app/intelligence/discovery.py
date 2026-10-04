"""Candidates are a review buffer, never permission to join an outreach campaign."""

from sqlalchemy import select
from ..core import public_url, Blocked
from ..models import Candidate, Company, Contact, ContactObservation, now
from .schemas import DiscoveredCompany, ContactRecord, Observation
from .bounds import IntelligenceFailure, checkpoint


def ingest_candidates(db, rows, context):
    accepted = 0
    invalid = 0
    from ..config import settings

    for raw in rows[: settings().discovery_batch_limit]:
        checkpoint()
        try:
            data = DiscoveredCompany.model_validate(raw)
            domain = public_url(str(data.website))
        except (ValueError, Blocked):
            invalid += 1
            continue
        candidate = db.scalar(select(Candidate).where(Candidate.domain == domain))
        if not candidate:
            candidate = Candidate(
                domain=domain,
                name=data.name,
                website="https://" + domain,
                industry=data.industry,
                distance_miles=data.distance_miles,
            )
            db.add(candidate)
            db.flush()
            accepted += 1
        stamp = data.retrieved_at
        items = []
        for field, value in [
            ("name", data.name),
            ("website", str(data.website)),
            ("industry", data.industry),
            ("location", data.location),
            (
                "distance_miles",
                str(data.distance_miles) if data.distance_miles is not None else "",
            ),
        ]:
            if not value:
                continue
            source_url = data.source if data.source.startswith("https://") else ""
            if source_url:
                try:
                    public_url(source_url)
                except Blocked:
                    source_url = ""
            item = Observation(
                field=field,
                value=value,
                provider=data.source[:30] if not source_url else "search",
                external_id=data.provider_id,
                source_url=source_url,
                retrieved_at=stamp,
                confidence="provider-confirmed" if data.provider_id else "unknown",
            ).model_dump(mode="json")
            # Repeated identical observations refresh time without growing unbounded history.
            old = next(
                (
                    o
                    for o in candidate.observations
                    if (o["field"], o["value"], o["provider"], o.get("external_id"))
                    == (field, value, item["provider"], data.provider_id)
                ),
                None,
            )
            items.append(
                item if not old else {**old, "retrieved_at": stamp.isoformat()}
            )
        keys = {
            (o["field"], o["value"], o["provider"], o.get("external_id")) for o in items
        }
        candidate.observations = (
            [
                o
                for o in candidate.observations
                if (o["field"], o["value"], o["provider"], o.get("external_id"))
                not in keys
            ]
            + items
        )[-40:]
        candidate.contexts = list(dict.fromkeys([*candidate.contexts, context]))[-8:]
        candidate.updated_at = now()
        # Same provider identity with different domains remains separate and visibly ambiguous.
        if data.provider_id:
            for other in db.scalars(
                select(Candidate).where(Candidate.domain != domain)
            ):
                if any(
                    o.get("external_id") == data.provider_id
                    and o.get("provider") == items[0]["provider"]
                    for o in other.observations
                ):
                    candidate.status = "ambiguous"
                    other.status = "ambiguous"
        db.commit()
    return {
        "candidates_added": accepted,
        "invalid_skipped": invalid,
        "candidates_seen": min(len(rows), settings().discovery_batch_limit),
    }


def accept(db, candidate, *, source="Candidate accepted by operator", commit=True):
    if candidate.status == "dismissed":
        raise Blocked("Dismissed candidate must be deliberately restored first")
    from ..services.ledger import lock

    lock(db)
    db.refresh(candidate)
    company = db.scalar(select(Company).where(Company.domain == candidate.domain))
    if not company:
        company = Company(
            domain=candidate.domain,
            name=candidate.name,
            website=candidate.website,
            industry=candidate.industry,
            distance_miles=candidate.distance_miles,
            source=source,
            stage="discovered",
        )
        db.add(company)
        db.flush()
    candidate.company_id = company.id
    candidate.status = "accepted"
    if commit:
        db.commit()
    return company


def ingest_contact(db, company, raw):
    data = ContactRecord.model_validate(raw)
    for url in (data.source_url, data.profile_url):
        if url:
            public_url(url)
    email = str(data.email).lower()
    contact = db.scalar(select(Contact).where(Contact.email == email))
    if contact and contact.company_id != company.id:
        raise IntelligenceFailure(
            "Contact email belongs to another company; inspect conflicting identity"
        )
    identities = list(
        db.scalars(
            select(ContactObservation).where(
                ContactObservation.company_id == company.id
            )
        )
    )
    if not contact:
        linked = next(
            (
                o
                for o in identities
                if (
                    data.external_id
                    and o.provider == data.provider
                    and o.external_id == data.external_id
                )
                or (
                    data.profile_url
                    and o.field == "profile_url"
                    and o.value == data.profile_url
                )
            ),
            None,
        )
        if linked:
            contact = db.get(Contact, linked.contact_id)
    if not contact:
        contact = Contact(
            company_id=company.id,
            email=email,
            name=data.name,
            title=data.title,
            source=data.source_url or data.provider,
        )
        db.add(contact)
        db.flush()
    stamp = data.retrieved_at
    for field in ("email", "name", "title", "profile_url", "location"):
        value = email if field == "email" else getattr(data, field)
        if not value:
            continue
        old = [o for o in identities if o.contact_id == contact.id and o.field == field]
        if any(o.value != value for o in old):
            confidence = "conflicting"
        else:
            confidence = data.confidence
        exact = next(
            (
                o
                for o in old
                if o.value == value
                and o.provider == data.provider
                and o.source_url == data.source_url
            ),
            None,
        )
        if exact:
            exact.retrieved_at = stamp
            exact.confidence = confidence
        else:
            db.add(
                ContactObservation(
                    company_id=company.id,
                    contact_id=contact.id,
                    field=field,
                    value=value,
                    provider=data.provider,
                    external_id=data.external_id,
                    source_url=data.source_url,
                    confidence=confidence,
                    retrieved_at=stamp,
                )
            )
    db.commit()
    return contact


def role_fit(title, size):
    title = title.lower()
    if size == "201+" and any(
        x in title for x in ("ceo", "founder", "chief executive")
    ):
        return 0
    if any(
        x in title
        for x in (
            "intern",
            "recruit",
            "engineering",
            "engineer",
            "team lead",
            "product",
            "department",
        )
    ):
        return 10
    if size in ("1-10", "11-50") and any(x in title for x in ("founder", "cto", "ceo")):
        return 10
    if "operations" in title:
        return 6
    return 0


def contact_confidence(db, contact):
    from datetime import timedelta
    from ..core import aware

    observations = list(
        db.scalars(
            select(ContactObservation).where(
                ContactObservation.contact_id == contact.id
            )
        )
    )
    if any(o.confidence == "conflicting" for o in observations):
        return "conflicting"
    if observations and any(
        aware(o.retrieved_at) < now() - timedelta(days=30)
        for o in observations
        if o.field in ("email", "title")
    ):
        return "stale"
    if contact.validation == "valid" and contact.validated_at:
        return (
            "provider-confirmed"
            if aware(contact.validated_at) > now() - timedelta(days=7)
            else "stale"
        )
    email = next((o for o in observations if o.field == "email"), None)
    return email.confidence if email else "unknown"


def best_contact(db, company):
    contacts = list(db.scalars(select(Contact).where(Contact.company_id == company.id)))
    eligible = [
        c
        for c in contacts
        if contact_confidence(db, c) not in ("conflicting", "stale")
        and not (
            company.research.get("size", "unknown") not in ("1-10", "11-50")
            and any(t in c.title.lower() for t in ("ceo", "founder", "chief executive"))
        )
    ]
    return max(
        eligible,
        key=lambda c: (
            role_fit(c.title, company.research.get("size", "unknown")),
            contact_confidence(db, c) == "provider-confirmed",
        ),
        default=None,
    )
