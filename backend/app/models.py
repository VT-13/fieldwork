from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Text, DateTime, JSON, ForeignKey, UniqueConstraint, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def now():
    return datetime.now(timezone.utc)
def uid():
    return str(uuid4())

class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Company(Base):
    __tablename__ = "companies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    domain: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    website: Mapped[str] = mapped_column(Text)
    industry: Mapped[str] = mapped_column(String(100), default="Unknown")
    distance_miles: Mapped[float | None]
    description: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(Text, default="manual")
    research: Mapped[dict] = mapped_column(JSON, default=dict)
    score: Mapped[int] = mapped_column(default=0)
    score_factors: Mapped[dict] = mapped_column(JSON, default=dict)
    stage: Mapped[str] = mapped_column(String(40), default="discovered", index=True)
    demo: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    researched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    url: Mapped[str] = mapped_column(Text)
    quote: Mapped[str] = mapped_column(Text)
    fact: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(60))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    source_kind: Mapped[str] = mapped_column(String(30), default='unknown')
    confidence: Mapped[str] = mapped_column(String(30), default='unknown')
    content_hash: Mapped[str] = mapped_column(String(64), default='')
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    title: Mapped[str] = mapped_column(String(255), default="")
    source: Mapped[str] = mapped_column(Text, default="")
    validation: Mapped[str] = mapped_column(String(40), default="unverified")
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class Outreach(Base):
    __tablename__ = "outreach"
    __table_args__ = (UniqueConstraint("company_id", "sequence"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("contacts.id"))
    sequence: Mapped[int] = mapped_column(default=0)
    subject: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    review: Mapped[dict] = mapped_column(JSON, default=dict)
    strategy: Mapped[str] = mapped_column(String(80), default="project-match")
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_id: Mapped[str] = mapped_column(Text, default="")
    thread_id: Mapped[str] = mapped_column(Text, default="")
    message_id: Mapped[str] = mapped_column(String(255), default="")
    attempts: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Event(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[str] = mapped_column(String(255), unique=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Suppression(Base):
    __tablename__ = "suppressions"
    email: Mapped[str] = mapped_column(String(320), primary_key=True)
    reason: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    dedupe_key: Mapped[str] = mapped_column(String(255), unique=True)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    error: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class Usage(Base):
    __tablename__ = "usage"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id"), index=True)
    service: Mapped[str] = mapped_column(String(80))
    reserved_usd: Mapped[float]
    tokens: Mapped[int] = mapped_column(default=0)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)

class Cache(Base):
    __tablename__ = "cache"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class State(Base):
    __tablename__ = "state"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)

Index("outreach_due", Outreach.status, Outreach.due_at)

# Operations contain identifiers and policy metadata, never message bodies or tokens.
class Operation(Base):
    __tablename__ = 'operations'
    __table_args__ = (CheckConstraint("status in ('pending','running','succeeded','failed','unknown','blocked','skipped')",name='operation_status'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True)
    kind: Mapped[str] = mapped_column(String(60), index=True)
    entity_id: Mapped[str] = mapped_column(String(100), default='')
    outreach_id: Mapped[str | None] = mapped_column(ForeignKey('outreach.id'), index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey('jobs.id'))
    provider: Mapped[str] = mapped_column(String(40), default='local')
    status: Mapped[str] = mapped_column(String(20), default='pending', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ActionAttempt(Base):
    __tablename__ = 'action_attempts'
    __table_args__ = (UniqueConstraint('operation_id','number'),
        CheckConstraint("status in ('running','succeeded','failed','unknown','blocked','skipped')",name='attempt_status'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    operation_id: Mapped[str] = mapped_column(ForeignKey('operations.id'), index=True)
    number: Mapped[int]
    retry_of: Mapped[str | None] = mapped_column(ForeignKey('action_attempts.id'))
    status: Mapped[str] = mapped_column(String(20), index=True)
    authorized: Mapped[bool] = mapped_column(default=False)
    network_units: Mapped[int] = mapped_column(default=0)
    policy: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(String(160), default='')
    receipt: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class DomainTransition(Base):
    __tablename__ = 'domain_transitions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    domain: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(100), index=True)
    from_state: Mapped[str] = mapped_column(String(40))
    to_state: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(String(120), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ExecutionLock(Base):
    __tablename__ = 'execution_lock'
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(default=0)


# Private personal-operator security state; never returned by generic API serializers.
class OperatorSession(Base):
    __tablename__ = 'operator_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    operator_id: Mapped[str] = mapped_column(String(40), default='personal')
    auth_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("operator_id = 'personal'", name='session_personal_operator'),)

class Integration(Base):
    __tablename__ = 'integrations'
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default='gmail')
    operator_id: Mapped[str] = mapped_column(String(40), default='personal')
    email: Mapped[str] = mapped_column(String(320), default='')
    status: Mapped[str] = mapped_column(String(40), default='disconnected')
    generation: Mapped[int] = mapped_column(default=0)
    encrypted_tokens: Mapped[str] = mapped_column(Text, default='')
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint("operator_id = 'personal'", name='integration_personal_operator'),
        CheckConstraint("status in ('connected','disconnected','reconnect_required','identity_mismatch')",name='integration_status'))

class OAuthGrant(Base):
    __tablename__ = 'oauth_grants'
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_hash: Mapped[str] = mapped_column(ForeignKey('operator_sessions.token_hash'))
    verifier_ciphertext: Mapped[str] = mapped_column(Text)
    expected_email: Mapped[str] = mapped_column(String(320))
    generation: Mapped[int]
    requested_scopes: Mapped[list] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class RateBucket(Base):
    __tablename__ = 'rate_buckets'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    count: Mapped[int] = mapped_column(default=0)

class Candidate(Base):
    __tablename__ = 'candidates'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    domain: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    website: Mapped[str] = mapped_column(Text)
    industry: Mapped[str] = mapped_column(String(100), default='Unknown')
    distance_miles: Mapped[float | None]
    status: Mapped[str] = mapped_column(String(30), default='candidate')
    company_id: Mapped[str | None] = mapped_column(ForeignKey('companies.id'))
    observations: Mapped[list] = mapped_column(JSON, default=list)
    contexts: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ContactObservation(Base):
    __tablename__ = 'contact_observations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id'), index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey('contacts.id'), index=True)
    field: Mapped[str] = mapped_column(String(40))
    value: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(30))
    external_id: Mapped[str] = mapped_column(String(255), default='')
    source_url: Mapped[str] = mapped_column(Text, default='')
    confidence: Mapped[str] = mapped_column(String(30), default='unknown')
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class StudentFact(Base):
    __tablename__ = 'student_facts'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey('profiles.id'))
    profile_hash: Mapped[str] = mapped_column(String(64), index=True)
    field: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(Text)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Generation(Base):
    __tablename__ = 'generations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id'), index=True)
    outreach_id: Mapped[str | None] = mapped_column(ForeignKey('outreach.id'), index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey('jobs.id'))
    prompt_version: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    student_fact_ids: Mapped[list] = mapped_column(JSON, default=list)
    subject: Mapped[str] = mapped_column(String(200), default='')
    body: Mapped[str] = mapped_column(Text, default='')
    review: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
