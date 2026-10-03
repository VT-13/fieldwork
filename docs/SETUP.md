# Setup and configuration

## Local development without Docker

Python 3.11+ and Node 22+ are required. SQLite can demonstrate the application; production requires PostgreSQL.

```sh
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.lock.txt
pip install -e '.[test]'
cp ../.env.example .env
```

For local SQLite set `DATABASE_URL=sqlite:///./local.db` and `ENVIRONMENT=development` in `backend/.env`. Set a random API key. Then:

```sh
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
# Separate terminal, same backend directory and virtual environment:
python -m app.worker
```

In `frontend/.env.local`:

```dotenv
BACKEND_URL=http://127.0.0.1:8000
API_KEY=the-same-random-api-key-as-backend
DASHBOARD_PASSWORD=a-separate-long-password
APP_ORIGIN=http://localhost:3000
```

```sh
cd frontend
npm ci
npm run dev
```

Use `http://localhost:3000`, username `student`. API OpenAPI schema is at `http://127.0.0.1:8000/docs`; authenticated endpoints require `Authorization: Bearer <API_KEY>`.

## Mailbox connection

The app uses one personally controlled mailbox. It sends plain text from the configured address; it does not impersonate contacts or attach unverified resumes. OAuth credentials live in your secret manager / private `.env`. Do not paste tokens into the chat or browser profile form.

### Gmail

1. Create a Google Cloud project, enable Gmail API, configure OAuth consent, and add your mailbox as an allowed test user if the app is in testing.
2. Create a web OAuth client with redirect URI `http://localhost:8765/callback` for the local bootstrap script. Configure client ID and secret.
3. Set `MAIL_PROVIDER=gmail`, `SENDER_EMAIL`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET` in `backend/.env`.
4. From the backend directory, run `python -m scripts.oauth_setup`. It opens consent using state and PKCE. Live mode requests `gmail.send` and `gmail.readonly`; manual mode requests `gmail.compose` and `gmail.readonly`.
5. The script saves `OAUTH_REFRESH_TOKEN` in `backend/.env` with owner-only permissions and does not print it. Restart API / worker. Use your deployment secret manager when hosting.
6. Queue **Outreach → Sync inbox**. Check the job result and verify the mailbox identity matches `SENDER_EMAIL`.

Google OAuth testing mode and restricted scopes can limit token lifetime / require app verification depending on app configuration. Follow the provider console's requirements for your use; do not assume the initial token remains valid indefinitely.

### Microsoft Outlook

1. Register an app in Microsoft Entra, choosing the supported account types appropriate for the mailbox. Configure a web redirect URI `http://localhost:8765/callback` and a client secret.
2. Add delegated `User.Read`, `Mail.Read`, `Mail.Send` and `offline_access` permissions. Tenant policy may require administrator consent.
3. Set `MAIL_PROVIDER=outlook`, `MICROSOFT_TENANT` (tenant ID, or `common` for an appropriately registered multitenant app), client ID, client secret and sender address.
4. Run the same bootstrap script; it saves the refresh token privately to `backend/.env`.
5. Test inbox sync before enabling sending. The worker refreshes access tokens per connection. If the refresh token is revoked or expires, repeat consent. Rotated refresh-token values are not automatically persisted by this version; plan reauthorization / secret-manager rotation.

The Graph endpoint accepts MIME and returns acceptance without a delivery receipt. The app records that separately from a recipient response and later captures mailbox thread identifiers when available. Both providers preserve Message-ID / reply headers for conversation matching.

## Environment variables

| Variable | Default / purpose |
|---|---|
| `ENVIRONMENT` | development; production requires PostgreSQL and a random API key ≥32 chars |
| `DATABASE_URL` | local SQLite fallback; use `postgresql+psycopg://...` in production |
| `POSTGRES_PASSWORD` | Docker PostgreSQL password; keep in sync with the URL |
| `API_KEY` | Server-to-server authentication secret, same in frontend/backend |
| `DASHBOARD_PASSWORD` | Private browser gate; username student |
| `APP_ORIGIN` | Exact browser origin, no trailing slash; required for mutation CSRF checks |
| `BACKEND_URL` | Next server-only API URL; Compose supplies http://api:8000 |
| `MANUAL_MODE` | true; blocks paid provider calls and live sending; personal review desk stays available |
| `DRY_RUN` | true; false explicitly enables network delivery |
| `AUTO_APPROVE` | false; true lets quality-passed generated drafts enter approved state |
| `DAILY_SEND_LIMIT` | 25, hard bound 1–30; all sequences / uncertain attempts share quota |
| `SEND_INTERVAL_SECONDS` | 120, minimum 60 |
| `TIMEZONE` | America/Los_Angeles; daily sending / reservation accounting boundary |
| `DAILY_BUDGET_USD` | 5 in reserved costs |
| `COMPANY_BUDGET_USD` | 0.75 reserved per company per calendar day |
| `SEARCH_RESERVE_USD` | 0.03 per discovery call |
| `SCRAPE_RESERVE_USD` | 0.02 per uncached page |
| `CONTACT_RESERVE_USD` | 0.05 per contact search / validation |
| `EXTRACT_RESERVE_USD` | 0.03 per extraction |
| `GENERATE_RESERVE_USD` | 0.15 per draft generation |
| `REVIEW_RESERVE_USD` | 0.10 per review |
| `MAX_PAGES` | 5, configurable 1–10; implemented path list contains six pages |
| `RESEARCH_SECONDS` | 120, hard maximum 300 |
| `MAX_LLM_CALLS` | 7 per company per rolling 24 hours, hard maximum 10 |
| `SEARCH_COOLDOWN_DAYS` | 14; also avoid identical searches with superficial query changes |
| `OPENAI_API_KEY` | Extraction, writing and reviewer calls |
| `CHEAP_MODEL` | gpt-4.1-mini, configurable |
| `WRITING_MODEL`, `REVIEW_MODEL` | gpt-4.1, configurable; account/model availability must be checked |
| `TAVILY_API_KEY` | Search discovery alternative |
| `FIRECRAWL_API_KEY` | Website research |
| `GOOGLE_MAPS_API_KEY` | Google Places New discovery |
| `APOLLO_API_KEY` | Organization search (plan access required) |
| `HUNTER_API_KEY` | Domain search and verification |
| `MAIL_PROVIDER` | gmail or outlook |
| `SENDER_EMAIL` | Must match OAuth identity and verified student profile |
| `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `OAUTH_REFRESH_TOKEN` | Mailbox OAuth credentials |
| `MICROSOFT_TENANT` | common or your tenant ID |
| `ALLOW_LOCAL_NO_AUTH` | Optional frontend-only loopback preview bypass; never enable on a hosted app |

Models are configurable because availability, price and performance vary. Structured Responses output follows the [official OpenAI documentation](https://developers.openai.com/api/docs/guides/structured-outputs). Do not tune limits by assuming per-call reservations equal actual billed spend.

## Importing authorized source exports

Normalize a licensed directory export into an array of up to 50 records:

```json
[
  {
    "name": "Verified company name",
    "website": "https://company.example.com",
    "industry": "Robotics",
    "distance_miles": 12.5,
    "source": "Licensed directory export, 2026-09-21"
  }
]
```

POST this JSON to `/companies/import` with the bearer API key. Do not populate a guessed distance: omit it until verified. For a company found through LinkedIn, Crunchbase or Wellfound, use its official company website as `website`, and the original listing URL as `source`.
