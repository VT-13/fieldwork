# Fieldwork codebase map — Phase 0, October 3, 2026

## Source and runtime

Development root: `outputs/internship-platform/` within the original workspace. A local Git repository was initialized here during Phase 0; there is no commit or configured remote. Installed app: `/Users/vihaantirumala/.local/share/fieldwork`. It contains newer product features. **27 source paths differ or exist only in runtime**; exact paths and SHA-256 values are in `baseline/source-drift.json`. Do not overwrite the runtime from this workspace. Phase 1 must reconcile this drift without copying `.env`, databases, receipts, logs, dependencies or generated assets into source.

## Stack and directories

- `frontend/`: Next.js 16.3.5, React/React DOM 19.3.0 and TypeScript 5.9.3 resolved by lockfile, strict TypeScript; Lucide icons; `output: standalone`. Verify locked versions in `package-lock.json` rather than dependency ranges.
- `backend/`: Python 3.13 in the installed venv; FastAPI, SQLAlchemy 2, Pydantic, Alembic, HTTPX and OpenAI SDK. Locked dependency file and pyproject both exist.
- `backend/app/`: application handlers, business rules, research/generation, mailbox and worker. No separate domain/service layer yet.
- `backend/tests/`: pytest; in-memory SQLite fixtures and mocked providers. Runtime has additional campaign, scheduled-send, self-test and response tests.
- `backend/alembic/`: initial frozen migration `001`; `migration_v1.py` is its schema snapshot. `docs/SCHEMA.sql` is documentation, not the migration authority.
- `docs/`: original setup/architecture/deployment docs plus Phase 0 map, ADRs, plan and baseline. Older docs describe now-superseded scheduling and connection behavior.
- `.codex/skills/`: six project skills. `AGENTS.md` routes future work.
- `scripts/`: safe Phase 0 snapshot/baseline and browser runners.
- Runtime-only `desktop/`: Swift/WebKit shell, launchd definitions and local instructions. `~/Applications/Fieldwork.app` is the installed personal app.

## Domains and persistence

`models.py`: `Profile` singleton (id 1, structured JSON); `Company` (unique domain, research, score, stage); `Contact` (globally unique email); `Evidence` (source/quote/fact); `Outreach` (unique company+sequence, message, review, attempt and provider/thread identifiers); `Event` (unique source_id); `Suppression`; `Job` (unique dedupe_key); `Usage`; `Cache`; generic JSON `State`.

Active local storage is SQLite at `~/.local/share/fieldwork/data/fieldwork.sqlite`. Container/hosted design uses PostgreSQL; production settings require PostgreSQL and a non-default bearer key. No account or tenant ownership columns exist. SQLite foreign keys are enabled by an engine hook. JSON State currently holds desk packets, detector records, policies, manual batches, reply previews and polling cursors. It is a flexible prototype store, not a validated durable workflow schema.

## Authentication and API

`backend/app/main.py`: constant-time shared bearer key on private endpoints; `/health` is public. `frontend/proxy.ts`: Basic auth or explicitly enabled localhost no-auth mode. `frontend/app/api/[...path]/route.ts`: same-origin mutation check, approximate 100KB body limit, private server-side API key forwarding, 15-second fetch timeout. No sessions, per-user authorization, credential ownership, or authorization roles.

Frontend routes: `/` client workspace with six main views (email desk, opportunities, outreach, insights, profile, settings); catch-all `/api/*` proxy. Runtime adds response inbox and campaign summary. Most screens/state live in one `page.tsx`; `ReviewDesk.tsx` is the main separate editor.

Backend route groups: `/profile`; `/companies` import/detail/actions/contacts/events; `/contacts/{id}/verify`; `/discover`; `/outreach` approve/regenerate/send; `/jobs` retry; `/automation`; `/settings`; `/metrics`; `/mail/sync`; `/demo`; `/desk` edit/detector/signoff/MIME/mailbox draft. Runtime adds `/desk/{id}/self-test`, `/campaign`, `/campaign/stop`, `/outreach-policy`, `/responses`, `/responses/sync`, `/responses/{id}`. Read OpenAPI for exact request shapes.

## Integrations and AI

`providers.py`: fixed HTTP endpoints for Google Places, Tavily, Apollo, Firecrawl and Hunter; configurable OpenAI Responses structured output. LinkedIn/Crunchbase/Wellfound are not autonomous integrations; search excludes directory domains, and import/manual research bridges gaps. Gmail and Microsoft Graph share `Mailbox` in `mail.py`; identity is checked after refresh. `scripts/oauth_setup.py` uses state and PKCE, localhost callback and private `.env` persistence. OAuth is environment-wide, not per account.

`pipeline.py`: bounded page list, cache, exact-quote validation, early stop at two usable facts plus contact, compact profile/evidence inputs; up to two generation/review attempts. Reservations count failures and bound provider usage; they are not invoice costs. Manual mode blocks paid providers. `desk.py` stores manual drafts and actual external detector results; it does not automate detector access or AI writing.

No Astra runtime SDK/orchestrator was found in application code. OpenAI calls supply intelligence, but current personal research and orchestration depend on a scheduled Codex task and campaign scripts outside this repository (`../ongoing-outreach/`). Ordinary discovery sequencing and follow-up preparation therefore still depend on a conversational agent. The app has no direct connection to a ChatGPT subscription and no free Gemini integration.

## Jobs, sending and runtime

`worker.py`: SQL jobs, PostgreSQL advisory-lock leader or local flock, 15-second ticks, crash → interrupted/unknown; legacy follow-ups at 7/14/30 days. It is intentionally disabled for the current personal workflow. `/send` queues into this worker, so manual-mode sending requests can be queued then blocked.

Runtime `scheduled_send.py`: separate explicit CLI, policy/manual-batch guards, local flock, quota checks, Gmail history/thread checks, pre-send reservation and JSONL receipts. It permits one 7-day follow-up, matching current personal policy. `self_test.py` separately sends an idempotent saved draft to the authenticated student's own Gmail. These paths do not yet share one attempt ledger or lock.

Runtime `responses.py`: read-only Gmail scan, thread history cache, contact/bounce searches, idempotent events/State previews; five-minute loop owned by the API lifespan. It changes CRM state and cancels pending outreach, without marking Gmail read. Outlook lacks this response inbox implementation. Local API/web LaunchAgents start at sign-in and restart on exit; sleep/offline interrupts operation. Sending is still driven by the authorized Codex task, not launchd alone. Current recurring policy is paused.

## Verification and deployment

See `BASELINE.md` and `baseline/results.json`: workspace 48 tests pass, runtime 73 pass; each skips PostgreSQL. Both typecheck/build; no configured lint. Isolated browser smoke covers startup, six views, API auth and origin rejection; full E2E/visual/accessibility coverage remains incomplete. CI runs backend tests/migrations with disposable PostgreSQL and frontend build/npm audit. No frontend/browser test suite exists.

`compose.yaml`: PostgreSQL, migration, API, legacy worker and web. Dockerfiles are non-root and include context ignores, but images were not built in this environment. `Makefile` wraps Docker/tests/build. Railway/Render/Vercel guidance exists; no deployment was executed. Docker, PostgreSQL CLI, gh and hosted deployment CLIs are unavailable here. GitHub tools are available, but this project has no remote.

Main risks: source drift; three sending paths; local locks and hard-coded HOME paths; inconsistent policy/state machines; no tenant authorization; plaintext OAuth storage for a personal app; rate-limit/retention gaps; missing frontend lint/E2E; outdated dependency advisories and stale deployment docs. See `../BUG_AUDIT.md` for evidence and priorities.

## Module 1 canonical additions

Canonical source now includes the runtime campaign, responses, self-test, scheduled helper, desktop shell and UI. backend/app/services/{policy,ledger,delivery,email_provider,contracts,intelligence,receipt_import}.py own authorization, attempts, provider boundaries and historical evidence import; domain/states.py owns transitions. migration_v2.py and alembic/versions/002_operations.py implement additive migration. tests/test_architecture.py and test_migration_v2.py cover contracts. scripts/source_manifest.py verifies/packages committed source; scripts/module1_check.py runs isolated checks. Installed runtime is deliberately unchanged.
