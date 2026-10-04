from functools import lru_cache
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    database_url: str = Field("sqlite:///./local.db", repr=False)
    api_key: str = Field("", repr=False)
    operator_password_hash: str = Field("", repr=False)
    credential_keys: str = Field("", repr=False)
    app_origin: str = "http://localhost:3000"
    trusted_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    response_preview_retention_days: int = Field(30, ge=1, le=90)
    session_hours: int = Field(12, ge=1, le=24)
    max_request_bytes: int = Field(100_000, ge=10_000, le=500_000)
    oauth_redirect_uri: str = "http://localhost:3000/api/integrations/gmail/callback"
    gmail_drafts_enabled: bool = False
    allow_legacy_oauth: bool = False
    environment: str = "development"
    dry_run: bool = True
    manual_mode: bool = True
    response_poll_enabled: bool = False
    worker_poll_seconds: int = Field(15, ge=1, le=60)
    worker_lease_seconds: int = Field(120, ge=60, le=300)
    job_timeout_seconds: int = Field(600, ge=60, le=900)
    mailbox_poll_seconds: int = Field(300, ge=300, le=3600)
    mailbox_max_requests: int = Field(60, ge=10, le=100)
    mailbox_max_messages: int = Field(40, ge=5, le=100)
    mailbox_lookback_days: int = Field(30, ge=7, le=90)
    data_directory: str = ""
    auto_approve: bool = False
    daily_send_limit: int = Field(25, ge=1, le=30)
    send_interval_seconds: int = Field(120, ge=60)
    timezone: str = "America/Los_Angeles"
    daily_budget_usd: float = Field(5, gt=0)
    daily_generation_budget_usd: float = Field(3, gt=0)
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
    discovery_seconds: int = Field(60, ge=10, le=60)
    max_contacts: int = Field(5, ge=1, le=10)
    max_provider_requests: int = Field(16, ge=1, le=30)
    max_job_tokens: int = Field(24000, ge=2000, le=40000)
    max_input_chars: int = Field(12000, ge=2000, le=20000)
    max_output_tokens: int = Field(1800, ge=500, le=2400)
    daily_token_limit: int = Field(60000, ge=2000, le=200000)
    max_generation_attempts: int = Field(2, ge=1, le=2)
    max_job_retries: int = Field(2, ge=0, le=2)
    model_allowlist: list[str] = ['gpt-4.1-mini','gpt-4.1']
    discovery_batch_limit: int = Field(30, ge=1, le=50)
    company_size_preference: list[str] = ['1-10','11-50','51-200']
    search_cooldown_days: int = 14
    openai_api_key: str = Field("", repr=False)
    cheap_model: str = "gpt-4.1-mini"
    writing_model: str = "gpt-4.1"
    review_model: str = "gpt-4.1"
    tavily_api_key: str = Field("", repr=False)
    firecrawl_api_key: str = Field("", repr=False)
    google_maps_api_key: str = Field("", repr=False)
    apollo_api_key: str = Field("", repr=False)
    hunter_api_key: str = Field("", repr=False)
    mail_provider: Literal["gmail", "outlook"] = "gmail"
    sender_email: str = ""
    oauth_client_id: str = ""
    oauth_client_secret: str = Field("", repr=False)
    oauth_refresh_token: str = Field("", repr=False)
    microsoft_tenant: str = "common"
    @model_validator(mode="after")
    def production(self):
        if any(m not in self.model_allowlist for m in (self.cheap_model,self.writing_model,self.review_model)):
            raise ValueError('Extraction, writing and review models must be in MODEL_ALLOWLIST')
        from zoneinfo import ZoneInfo
        ZoneInfo(self.timezone)
        from pathlib import Path
        env=Path('.env')
        if env.exists() and (env.is_symlink() or env.stat().st_mode&0o077):
            raise ValueError('Private .env must be a regular owner-only file (chmod 600)')
        from urllib.parse import urlsplit
        origin=urlsplit(self.app_origin)
        if origin.scheme not in ('http','https') or origin.path not in ('','/') or origin.query or origin.fragment or origin.username or origin.password:
            raise ValueError('APP_ORIGIN must be an exact HTTP(S) origin')
        if self.operator_password_hash or self.credential_keys:
            if len(self.api_key)<32 or self.api_key.startswith(('local-','replace-with-')):
                raise ValueError('Operator/OAuth setup requires a strong separate API_KEY even in local development')
        if self.environment == "production":
            if self.mail_provider!='gmail':raise ValueError('Production release supports Gmail only')
            if len(self.api_key) < 32 or self.api_key.startswith(("local-","replace-with-")):
                raise ValueError("Production requires a random API_KEY of at least 32 characters")
            from urllib.parse import urlsplit
            from cryptography.fernet import Fernet
            if not self.credential_keys:raise ValueError("Production requires CREDENTIAL_KEYS")
            for key in self.credential_keys.split(","):Fernet(key.strip().encode())
            if not self.operator_password_hash.startswith("scrypt$"):
                raise ValueError("Production requires OPERATOR_PASSWORD_HASH")
            if urlsplit(self.app_origin).scheme != 'https':
                raise ValueError("Production requires HTTPS APP_ORIGIN")
            if any('*' in h for h in self.trusted_hosts) or 'testserver' in self.trusted_hosts:
                raise ValueError("Set explicit production TRUSTED_HOSTS")
            if not self.data_directory or not Path(self.data_directory).is_absolute():raise ValueError('Production requires an absolute private DATA_DIRECTORY')
            if self.allow_legacy_oauth or self.oauth_refresh_token:
                raise ValueError("Production requires encrypted OAuth storage, not legacy tokens")
            if not self.database_url.startswith("postgresql"):
                raise ValueError("Production requires PostgreSQL")
        return self

@lru_cache
def settings():
    return Settings()
