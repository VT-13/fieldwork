from functools import lru_cache
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./local.db"
    api_key: str = "local-development-key-change-me"
    environment: str = "development"
    dry_run: bool = True
    manual_mode: bool = True
    auto_approve: bool = False
    daily_send_limit: int = Field(25, ge=1, le=30)
    send_interval_seconds: int = Field(120, ge=60)
    timezone: str = "America/Los_Angeles"
    daily_budget_usd: float = Field(5, gt=0)
    company_budget_usd: float = Field(.75, gt=0)
    # Conservative per-call reservations, NOT provider invoice estimates.
    search_reserve_usd: float = Field(.03, gt=0)
    scrape_reserve_usd: float = Field(.02, gt=0)
    contact_reserve_usd: float = Field(.05, gt=0)
    extract_reserve_usd: float = Field(.03, gt=0)
    generate_reserve_usd: float = Field(.15, gt=0)
    review_reserve_usd: float = Field(.10, gt=0)
    max_pages: int = Field(5, ge=1, le=10)
    research_seconds: int = Field(120, ge=20, le=300)
    max_llm_calls: int = Field(7, ge=3, le=10)
    search_cooldown_days: int = 14
    openai_api_key: str = ""
    cheap_model: str = "gpt-4.1-mini"
    writing_model: str = "gpt-4.1"
    review_model: str = "gpt-4.1"
    tavily_api_key: str = ""
    firecrawl_api_key: str = ""
    google_maps_api_key: str = ""
    apollo_api_key: str = ""
    hunter_api_key: str = ""
    mail_provider: Literal["gmail", "outlook"] = "gmail"
    sender_email: str = ""
    oauth_client_id: str = ""
    oauth_client_secret: str = ""
    oauth_refresh_token: str = ""
    microsoft_tenant: str = "common"
    @model_validator(mode="after")
    def production(self):
        if self.environment == "production":
            if len(self.api_key) < 32 or self.api_key.startswith("local-"):
                raise ValueError("Production requires a random API_KEY of at least 32 characters")
            if not self.database_url.startswith("postgresql"):
                raise ValueError("Production requires PostgreSQL")
        return self

@lru_cache
def settings():
    return Settings()
