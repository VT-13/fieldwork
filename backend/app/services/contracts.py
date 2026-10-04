"""Stable seams for the existing providers; no speculative provider integrations."""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, TypeVar
from pydantic import BaseModel
T = TypeVar('T', bound=BaseModel)

@dataclass(frozen=True)
class ScrapedPage:
    text: str
    source_url: str
    retrieved_at: datetime

@dataclass(frozen=True)
class DeliveryReceipt:
    provider_id: str
    thread_id: str = ''
    sent_verified: bool | None = None

class EmailProvider(Protocol):
    name: str
    sender: str
    async def connect(self) -> None: ...
    def authorize(self, db) -> None: ...
    async def check_conversation(self, db, row, contact, original) -> None: ...
    async def deliver(self, db, row, contact, original) -> DeliveryReceipt: ...
    async def confirm(self, receipt: DeliveryReceipt) -> bool | None: ...

class ResearchProvider(Protocol):
    async def scrape(self, db, company, url: str) -> ScrapedPage | str: ...
    async def contacts(self, db, company) -> list[dict]: ...

class LLMProvider(Protocol):
    async def llm(self, db, company_id: str, schema: type[T], instruction: str,
                  data: dict, purpose: str = 'extract') -> T: ...

class ProspectProvider(Protocol):
    async def discover(self, db, spec: dict) -> list[dict]: ...

class IntelligenceProvider(ResearchProvider, LLMProvider, Protocol):
    async def verify(self, db, contact) -> str: ...
