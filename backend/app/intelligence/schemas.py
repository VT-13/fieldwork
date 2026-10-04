from typing import Literal
from datetime import datetime, timezone
from pydantic import Field, EmailStr
from ..schemas import Strict, CompanyInput, DiscoveryInput

Confidence = Literal[
    "provider-confirmed",
    "source-observed",
    "inferred",
    "unknown",
    "stale",
    "conflicting",
]


class Observation(Strict):
    field: str = Field(max_length=40)
    value: str = Field(max_length=500)
    provider: str = Field(max_length=30)
    external_id: str = Field("", max_length=255)
    source_url: str = Field("", max_length=2000)
    retrieved_at: datetime
    verified_at: datetime | None = None
    confidence: Confidence = "unknown"


class DiscoveredCompany(CompanyInput):
    provider_id: str = Field("", max_length=255)
    location: str = Field("", max_length=240)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ContactRecord(Strict):
    email: EmailStr
    name: str = Field("", max_length=255)
    title: str = Field("", max_length=255)
    provider: str = Field("manual", max_length=30)
    external_id: str = Field("", max_length=255)
    source_url: str = Field("", max_length=2000)
    profile_url: str = Field("", max_length=2000)
    location: str = Field("", max_length=240)
    confidence: Confidence = "unknown"
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CandidateImport(Strict):
    companies: list[DiscoveredCompany] = Field(min_length=1, max_length=50)
    context: str = Field("Personal internship search", max_length=160)


class SearchSpec(DiscoveryInput):
    context: str = Field("Personal internship search", max_length=160)


class ExtractedFact(Strict):
    url: str = Field(max_length=2000)
    quote: str = Field(min_length=3, max_length=280)
    category: Literal[
        "product",
        "service",
        "news",
        "founder",
        "technology",
        "internship",
        "size",
        "growth",
        "description",
        "careers",
        "student",
    ]


class Extraction(Strict):
    facts: list[ExtractedFact] = Field(max_length=6)


class Plan(Strict):
    evidence_ids: list[str] = Field(min_length=1, max_length=3)
    student_fact_ids: list[str] = Field(min_length=1, max_length=2)
    proposal_id: str
    voice: Literal["curious", "direct"]


class GeneratedClaims(Strict):
    """No free-form factual prose from a model can bypass the reference validator."""

    plan: Plan
