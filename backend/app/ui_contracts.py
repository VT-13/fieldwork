"""Private workspace read contracts. Generate frontend types from these, not copies.

These views normalize existing persistence; they do not authorize an operation.
"""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from .domain.states import MessageState
from .schemas import ProfileInput

class CompanyView(BaseModel):
    id: str
    name: str
    domain: str
    website: str
    industry: str
    distance_miles: float | None
    description: str
    source: str
    research: dict[str, Any]
    score: int
    score_factors: dict[str, float]
    stage: str
    demo: bool
    created_at: datetime
    researched_at: datetime | None

class ContactView(BaseModel):
    id: str
    company_id: str
    email: str
    name: str
    title: str
    source: str
    validation: str
    validated_at: datetime | None

class EvidenceView(BaseModel):
    id: str
    company_id: str
    fact: str
    quote: str
    url: str
    category: str
    fetched_at: datetime

class EventView(BaseModel):
    id: str
    company_id: str
    kind: str
    detail: str
    source_id: str
    created_at: datetime

class CompanyDetail(CompanyView):
    contacts: list[ContactView]
    evidence: list[EvidenceView]
    events: list[EventView]

class ReviewView(BaseModel):
    model_config = ConfigDict(extra="allow")
    passed: bool = False
    personalization_score: int | None = None
    issues: list[str] = []
    profile_hash: str = ''
    grounded: bool | None = None
    names_correct: bool | None = None
    claims_supported: bool | None = None

class OutreachView(BaseModel):
    id: str
    company_id: str
    contact_id: str
    sequence: int
    subject: str
    body: str
    evidence_ids: list[str]
    review: ReviewView
    strategy: str
    status: MessageState
    due_at: datetime
    sent_at: datetime | None
    provider_id: str
    thread_id: str
    message_id: str
    attempts: int
    created_at: datetime

class PolicyView(BaseModel):
    enabled: bool = False
    new_companies_per_weekday: int | None = None
    followup_after_days: int | None = None

class CampaignView(BaseModel):
    model_config = ConfigDict(extra="allow")
    active: bool
    batch_name: str = ''
    status: str = 'inactive'
    detail: str = ''
    can_stop: bool = False
    stop_requested: bool = False
    limit: int = 25
    planned: int = 0
    sent: int = 0
    verified: int = 0
    skipped: int = 0
    validation_policy: str = ''
    outreach_ids: list[str] = []
    ongoing_policy: PolicyView = Field(default_factory=PolicyView)

class ReplyView(BaseModel):
    id: str
    company_id: str
    company: str
    kind: str
    sender: str
    subject: str
    preview: str
    received_at: datetime
    handled: bool
    gmail_url: str

class SyncView(BaseModel):
    status: str
    last_success: str | None = None
    error: str | None = None

class InboxView(BaseModel):
    enabled: bool
    needs_attention: int
    responses: list[ReplyView]
    sync: SyncView

class MetricsView(BaseModel):
    model_config = ConfigDict(extra="allow")
    companies: int
    sent: int
    replies: int
    interviews: int
    offers: int
    response_rate: float
    interview_rate: float
    conversion_rate: float
    sent_today: int
    learning: list[dict[str, Any]]

class SettingsView(BaseModel):
    model_config = ConfigDict(extra="allow")
    manual_mode: bool
    dry_run: bool
    daily_send_limit: int
    auto_approve: bool
    max_pages: int
    research_seconds: int
    mail_provider: str
    mail_connected: bool
    demo_allowed: bool
    integrations: dict[str, bool]
    automation: dict[str, Any]

class ConnectionView(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    email: str
    connected: bool

# Only unsent content can be edited. Review must run again afterward.
class OutreachEdit(BaseModel):
    subject: str = Field(min_length=1, max_length=180)
    body: str = Field(min_length=1, max_length=8000)


class StyleView(BaseModel):
    words: int
    generic_phrases: list[str]
    long_sentences: int
    has_question: bool
    note: str

class DetectorView(BaseModel):
    model_config = ConfigDict(extra="allow")
    provider: str
    ai_probability: float | None
    result: str
    checked_at: datetime
    report_url: str | None = None

class MailboxDraftView(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    to: str
    at: str | None = None

class PacketView(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    company: str
    subject: str
    body: str
    evidence: str
    fictional: bool
    draft_hash: str
    status: str
    updated_at: datetime
    style: StyleView
    detector: DetectorView | None
    signoff: dict[str, Any] | None
    mailbox_draft: MailboxDraftView | None
    history: list[dict[str, Any]]

class EmlView(BaseModel):
    filename: str
    content: str

class SelfTestView(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: str
    to: str

CONTRACTS = [ProfileInput, CompanyView, CompanyDetail, OutreachView, CampaignView,
             InboxView, MetricsView, SettingsView, ConnectionView, OutreachEdit, PacketView, EmlView, SelfTestView]
