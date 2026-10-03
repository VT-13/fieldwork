> Historical MVP instructions. Current security/OAuth setup is in [SETUP.md](SETUP.md) and [../SECURITY.md](../SECURITY.md); release ordering is in [MIGRATION_PLAN.md](MIGRATION_PLAN.md). Basic authentication, browser bearer forwarding and plaintext Gmail bootstrap described below are retired in canonical source. No deployment is authorized by this document.

# Integration coverage

| Source | Implemented route | Requirements / scope |
|---|---|---|
| Google Maps | Official Places API (New), Text Search | API key and enabled billing. Coordinates plus Haversine distance filter; one bounded query, at most 20 results. |
| Tavily | Official basic search API | Paid key. Returns company-site candidates; geography must be confirmed before delivery. |
| Apollo | Official organization search | API entitlement; unknown distances remain unverified. People contact enrichment is not implemented. |
| Firecrawl | Official v2 single-page scrape | Fixed priority paths, bounded content, cache. No full-domain crawling. |
| Hunter | Domain search, email verifier | Public professional contacts; prioritizes founder, CEO/CTO, engineering, product, recruiting and operations roles. Only valid/non-catch-all addresses pass. |
| Company websites | Firecrawl evidence, manual public contact entry | Contact pages are researched. This version does not automatically scrape arbitrary email lists. |
| LinkedIn | Authorized manual/licensed-export import | No session scraping or private profile access. |
| Crunchbase | Authorized manual/licensed-export import | No licensed API access assumed. |
| Wellfound | Public company website discovery via search, manual import | No direct authenticated Wellfound integration. |
| Local directories, startup/software databases | Web discovery or normalized batch import | Use official company domain; retain source attribution; confirm location. |
| OpenAI | Responses API with Pydantic structured outputs | Configurable extraction, writer and reviewer models. Independent review with bounded attempts. |
| Gmail | OAuth refresh, send, list/full-message polling | Identity check, MIME reply headers, thread IDs, sent-message reconciliation. |
| Outlook | OAuth refresh, Graph MIME sendMail and messages polling | Delegated scopes. Preserve RFC reply headers, capture conversation IDs during sync. |

Not every source exposes an unrestricted, stable API. Imported leads go through the same research, evidence, scoring, verification and sending gates as automatically discovered leads. The UI labels configured credentials honestly; it does not claim an integration is live merely because a key exists.

## Provider documentation used

- [OpenAI structured output](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Google Places Text Search](https://developers.google.com/maps/documentation/places/web-service/text-search)
- [Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search)
- [Firecrawl Scrape](https://docs.firecrawl.dev/api-reference/endpoint/scrape)
- [Apollo Organization Search](https://docs.apollo.io/reference/organization-search)
- [Hunter API](https://hunter.io/api-documentation)
- [Gmail thread handling](https://developers.google.com/workspace/gmail/api/guides/threads)
- [Microsoft Graph sendMail](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0)

## Import a CSV without spreadsheet dependencies

Save columns `name,website,industry,distance_miles,source` in UTF-8 CSV. Convert locally:

```sh
python backend/scripts/csv_to_json.py leads.csv > leads.json
```

Review `leads.json`, then POST it to `/companies/import` using an authenticated local API client. The converter caps each batch at 50 records and keeps absent distances null. APIs may require licensed plans; this repository does not purchase accounts or consume real quotas during tests.
