"""Adapters for configured bounded intelligence; business callers use contracts."""
from .. import providers

class ConfiguredIntelligence:
    async def contacts(self,db,company):return await providers.hunter_contacts(db,company)
    async def scrape(self,db,company,url):return await providers.scrape(db,company,url)
    async def llm(self,db,company_id,schema,instruction,data,purpose='extract'):
        return await providers.llm(db,company_id,schema,instruction,data,purpose)
    async def verify(self,db,contact):return await providers.verify(db,contact)

class ConfiguredProspects:
    async def discover(self,db,spec):return await providers.discover(db,spec)
