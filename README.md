> Module 2 account/security setup supersedes legacy authentication/token examples below. Read [SECURITY.md](SECURITY.md) and [docs/SETUP.md](docs/SETUP.md). Canonical source has not been deployed; recurring outreach remains paused.

> Canonical Module 1 source: see [architecture](ARCHITECTURE.md), [reconciliation](docs/module1/RECONCILIATION.md), and [migration plan](docs/MIGRATION_PLAN.md). No Module 1 changes have been deployed; recurring outreach remains paused. Older deployment examples below are not authorization to start workers.

# Fieldwork

**Phase 0 audit (October 3, 2026):** Start with [CODEBASE_MAP](docs/CODEBASE_MAP.md), [BASELINE](docs/BASELINE.md), [BUG_AUDIT](BUG_AUDIT.md), and [PHASE_PLAN](docs/PHASE_PLAN.md). This workspace differs from the newer installed Mac app; reconcile the recorded source drift before deployment. Older workflow/deployment descriptions below are historical and do not supersede the active CRM policy. Six project skills and repository instructions now live in `.codex/skills/` and `AGENTS.md`. Phase 1 has not begun.

A private, single-student internship outreach workspace for Rocklin / Roseville. FastAPI + PostgreSQL + Next.js, with a separate durable worker. It discovers companies, saves evidence, drafts and reviews grounded introductions, controls delivery, stops follow-ups after responses, and tracks outcomes.

**Default: personal manual mode, dry-run, automation paused.** Open **My email desk** to write and review emails without paid API calls. See [the personal email workflow](docs/PERSONAL_EMAIL_DESK.md). Set `MANUAL_MODE=false` only if you intentionally want the optional paid research/model pipeline.

**Mailbox connection is required for automatic unsent-draft saving.** No API credentials are included. Fictional demo companies are visibly labeled, excluded from real metrics, and impossible to send to. This implementation does not promise higher response rates; it measures them.

## Quick start with Docker

Prerequisites: Docker Engine / Desktop with Compose.

```sh
cp .env.example .env
# Edit .env: set a random API_KEY, DASHBOARD_PASSWORD and POSTGRES_PASSWORD.
# Update DATABASE_URL to use exactly the same database password.
docker compose up --build -d
```

Open http://localhost:3000. Sign in with username `student` and your `DASHBOARD_PASSWORD`. The database migration runs before the API and worker. PostgreSQL is not published to the host. The API and web ports bind to loopback by default.

1. Open **My profile**, enter your real name, email, links, resume text, project details, and availability/background. Verify the facts.
2. Open **Opportunities → Explore demo** to inspect clearly fictional examples without paid API calls, or add a real company.
3. For the optional automated research pipeline only, set `MANUAL_MODE=false`. Keep it true for the personal email desk. Configure provider secrets in `.env`; restart with `docker compose up -d` after changes.
4. Use **Discover companies**. For Google Places enable Places API (New) and billing; Tavily and Apollo are alternative sources.
5. Open a company → **Research & draft**. Firecrawl and OpenAI are required; Hunter finds contacts if configured. You can add a public contact manually.
6. Review the source quotes and email. Confirm unverified distance and validate the email. Approve the draft.
7. Connect a mailbox using [mail setup](docs/SETUP.md). Keep dry-run on until the sandbox-mailbox acceptance checks pass.
8. Set `DRY_RUN=false` to permit actual sends. **Settings → Start** enables scheduled processing. `AUTO_APPROVE=true` is a separate opt-in for fully automatic approval after the quality gate.

## What is implemented

- Google Places text search with geographic distance filtering; Tavily web search; Apollo organization search; deduplicated manual/batch imports.
- Bounded Firecrawl research, shared page cache, exact quote checks, cheap-model fact extraction, structured company profiles, explainable 0–100 fit scores.
- Hunter domain contacts and deliverability verification; manually sourced public contacts are also supported.
- OpenAI structured generation and independent review, score strictly above 80, at most two candidate drafts, hard call caps, explicit evidence references, profile-version checks.
- Gmail and Microsoft Graph OAuth refresh, plain-text threaded messages, inbox sync, matching replies / opt-outs / delivery notifications, durable sending states, uncertainty reconciliation, 429 handling.
- Day 7 / 14 / 30 follow-up planning from the initial send, new-value review, suppression on conversation outcomes, no catch-up burst after downtime.
- Private dashboard, student profile database, company CRM, evidence inspection, outcome tracking, budget reservations, queued jobs, and observed response patterns.
- Alembic migration, PostgreSQL schema, Docker services, automated tests, deployment and operational guides.

## Honest boundaries

- This is a **single-user platform**, not a multi-tenant SaaS. Deploy privately behind HTTPS. Dashboard authentication is a simple server-side Basic Auth gate; add an identity proxy with MFA for broader exposure.
- LinkedIn, Crunchbase, Wellfound and licensed directory exports are **import sources**, not unofficial scrapers or pretend live integrations. Their access conditions and paid API entitlements differ. The exact source coverage is in [integrations](docs/INTEGRATIONS.md).
- Google Places returns at most 20 results in this single bounded query. A 100-mile search still filters at 100 miles, but Google's circle bias caps at 50 km. It is discovery, not exhaustive geographic coverage.
- Research checks the homepage and a small set of conventional paths. Unknown or inaccessible facts remain unknown; an unusual site structure may need manual work. Quotes verify provenance, not factual truth; the AI review is fallible.
- Cost limits enforce configured **reservations**, call counts, page counts and time limits. Reservations are not provider invoices. Set provider-side spending limits too; adjust reservation values to your models and subscriptions.
- Mailbox sync uses bounded, overlapping polling, not webhooks. Delivery notifications with unrecognized formats require manual CRM recording. Uncertain sends never auto-retry. Microsoft Graph acceptance is not proof of delivery.
- No automatic tracking pixels or reliable open-rate claims. Manual open observations are separate from reply / interview / offer rates.
- Real provider requests, real email delivery, and hosted deployment require your accounts and credentials. Local tests mock those boundaries. Docker/PostgreSQL runtime acceptance is separately documented.

## Repository map

```text
internship-platform/
├── backend/
│   ├── app/
│   │   ├── main.py             # authenticated API and CRM endpoints
│   │   ├── models.py           # SQLAlchemy schema
│   │   ├── migration_v1.py     # frozen initial schema
│   │   ├── schemas.py          # validation + structured AI output types
│   │   ├── config.py           # environment and bounds
│   │   ├── core.py             # scoring, budgets, cache, suppression
│   │   ├── providers.py        # Maps, Tavily, Apollo, Firecrawl, Hunter, OpenAI
│   │   ├── pipeline.py         # evidence extraction, generation, independent review
│   │   ├── mail.py             # Gmail/Graph, sync, delivery state machine
│   │   ├── worker.py           # database-leased durable queue + automation
│   │   └── seed.py             # fictional demo fixtures
│   ├── alembic/versions/001_initial.py
│   ├── scripts/oauth_setup.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.lock.txt
├── frontend/
│   ├── app/page.tsx            # workspace, CRM, review, profile, settings
│   ├── app/globals.css
│   ├── app/api/[...path]/route.ts # server-only authenticated API proxy
│   ├── proxy.ts               # dashboard authentication
│   ├── package-lock.json
│   └── Dockerfile
├── docs/
│   ├── ARCHITECTURE.md
│   ├── SCHEMA.sql
│   ├── SETUP.md
│   ├── INTEGRATIONS.md
│   ├── DEPLOYMENT.md
│   ├── TESTING.md
│   └── EXAMPLE_WORKFLOW.md
├── .env.example
└── compose.yaml
```

See [architecture](docs/ARCHITECTURE.md), [setup and environment variables](docs/SETUP.md), [deployment](docs/DEPLOYMENT.md), [testing](docs/TESTING.md), and [example workflow](docs/EXAMPLE_WORKFLOW.md).

## Personal Gmail response inbox

Set `RESPONSE_POLL_ENABLED=true` in backend/.env to check outreach responses every five minutes while the API is running. The personal installation has this enabled. Gmail send/read-only OAuth access is sufficient. The tracker reads known outreach threads and searches for unthreaded contact replies and delivery failures; it does not change Gmail labels or read status. Human replies appear under Replies needing attention, with company, preview, direct Gmail link, and a reversible Mark handled control. Automatic replies, opt-outs, and bounces are shown separately and stop outreach. Use Check now for an immediate check. Last successful check and connection failures are displayed. This monitors the connected account only, and needs the Mac awake and backend running.

For scheduled runs use `SSL_CERT_FILE=/etc/ssl/cert.pem ../.venv/bin/python -m app.responses` from backend and confirm status ok. Tests in backend/tests/test_responses.py cover reply matching, deduplication, automatic acknowledgments, bounce evidence, quoted text, and safe previews.
