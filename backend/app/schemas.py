from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl

class ProfileInput(BaseModel):
    name: str = Field("", max_length=120)
    email: str = ""
    grade: str = "High school freshman"
    location: str = "Rocklin / Roseville, California"
    resume: str = Field("", max_length=20000)
    linkedin_url: str = ""
    portfolio_links: list[str] = []
    projects: list[str] = ["Built websites for local businesses"]
    awards: list[str] = ["VEX Robotics World Championship competitor"]
    skills: list[str] = ["Software development", "Web development", "Robotics"]
    interests: list[str] = ["Software", "AI", "Robotics", "Finance", "Startups", "Business"]
    cover_letter_snippets: list[str] = []
    background: str = "Strong academic profile"
    voice_notes: str = Field("Direct, curious, friendly. No corporate praise. Sound like a real high-school student, not a sales pitch.", max_length=2000)
    writing_samples: list[str] = Field(default_factory=list, max_length=3)
    verified: bool = False

class CompanyInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    website: HttpUrl
    industry: str = Field("Unknown", max_length=100)
    distance_miles: float | None = Field(None, ge=0)
    source: str = "manual"

class ContactInput(BaseModel):
    email: EmailStr
    name: str = Field("", max_length=255)
    title: str = Field("", max_length=255)
    source: str = "manual"

class DiscoveryInput(BaseModel):
    area: str = Field("Rocklin / Roseville, California", max_length=120)
    latitude: float = Field(38.7907, ge=-90, le=90)
    longitude: float = Field(-121.2358, ge=-180, le=180)
    radius_miles: int = Field(50, ge=1, le=300)
    industry: str = Field("software AI robotics engineering finance startups", max_length=120)
    provider: Literal["maps", "tavily", "apollo"] = "maps"
    limit: int = Field(30, ge=1, le=50)

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")
class Fact(Strict):
    url: str
    quote: str
    fact: str
    category: Literal["product", "service", "news", "founder", "technology", "internship", "size", "growth", "description", "careers", "student"]
class ResearchResult(Strict):
    description: str
    industry: str
    size: str
    technologies: list[str]
    founder: str
    careers_url: str
    internship_history: str
    growth_indicators: list[str]
    student_friendly: bool
    startup_friendly: bool
    facts: list[Fact]
class DraftResult(Strict):
    subject: str
    body: str
    evidence_ids: list[str]
    strategy: Literal["project-match", "product-curiosity", "practical-help"]
class ReviewResult(Strict):
    personalization_score: int
    grounded: bool
    names_correct: bool
    claims_supported: bool
    non_generic: bool
    non_spammy: bool
    adds_new_value: bool
    issues: list[str]
class EventInput(BaseModel):
    kind: Literal["reply", "positive", "negative", "bounce", "opt_out", "interview", "offer", "open", "closed"]
    detail: str = Field("", max_length=2000)
