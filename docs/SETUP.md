# Personal-first setup (canonical source; not yet deployed)

The installed app is deliberately unchanged. Follow MIGRATION_PLAN.md before replacing it. Current recurring outreach stays paused. No setup instruction is permission to send, purchase provider access or start a worker.

Use Python 3.11+ and a maintained PostgreSQL 17 instance for production, Node22+, and private storage with disk encryption. Development tests may use disposable SQLite. Install the pinned backend requirements in a new environment; never patch the installed environment in place during release preparation.

From backend, `python scripts/security_setup.py --output /private/path/fieldwork-secrets.env` prompts for a new Fieldwork operator password and creates mode0600 configuration containing its scrypt hash, a random CLI API key and an external credential-encryption key. It never asks for a Gmail password. Keep this file/keys separately from database backups. Merge its values into private backend environment configuration without printing them. Use dotenv loading or a secret manager; do not shell-source a hash-containing dotenv file. `.env` must be a regular file, mode0600. Never use NEXT_PUBLIC variables for secrets.

Copy `.env.example` as a starting point. For production set ENVIRONMENT=production, a PostgreSQL DATABASE_URL, an absolute private DATA_DIRECTORY, explicit TRUSTED_HOSTS, HTTPS APP_ORIGIN and matching OAUTH_REDIRECT_URI. Generate actual API_KEY/OPERATOR_PASSWORD_HASH/CREDENTIAL_KEYS as above. Configure TLS at the private ingress and protect database networking/storage. Defaults do not satisfy production validation. Backend migrations must run before service startup; Docker worker is opt-in via its `worker` profile.

Frontend configuration only needs BACKEND_URL and APP_ORIGIN. It no longer needs API_KEY or DASHBOARD_PASSWORD and never forwards a bearer key on behalf of a browser. Start the separately staged API with access logging disabled, serve the built frontend privately, then sign in at `/login`. Restart services when changing external application secrets; a new password hash invalidates prior sessions. Server sessions expire after SESSION_HOURS (default 12); Settings provides sign-out and Gmail lifecycle controls. CLI requests use the separate operator bearer key.

## Gmail

Create a Google OAuth web client with the exact OAUTH_REDIRECT_URI registered. Set OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET externally. Verify the student profile and its own email, then Settings → Connect / reconnect Gmail. Browser consent opens Google's official page and returns through the authenticated callback. Default scopes are send and read-only; enable GMAIL_DRAFTS_ENABLED and reconnect only if own-account provider draft saving is desired. Tokens are stored encrypted in the database. SENDER_EMAIL, when configured, must agree with profile and provider identity. The existing connected identity cannot transfer silently.

Disconnect removes local authorization immediately, attempts upstream revocation and preserves send history. Reconnect does not resume outreach. Old plaintext OAUTH_REFRESH_TOKEN files are preserved in the installed runtime until a separately authorized migration; the new Gmail implementation never reads them. Production rejects legacy refresh-token settings. For migration, pause, set up encryption/session secrets, run the current schema005 on a disposable backup first, then reconnect through the app; remove retired plaintext tokens only in that later controlled deployment. Do not run the old bootstrap or historical drivers.

Google testing-mode expiration, app-verification requirements and restricted-scope approval remain provider-side requirements; a fake-provider test does not certify a real registration. Outlook remains a compatibility contract, with no production OAuth/send rollout in this module.

Provider API keys remain optional and external. Manual mode and explicit paid-service prohibition block billed calls; no subscription-to-ChatGPT connection is implemented. For all quota/pause/dry-run distinctions read ARCHITECTURE.md. See SECURITY.md, DATA_LIFECYCLE.md and BACKUP_RESTORE.md for current implemented controls.

## Bounded intelligence configuration

Read module4/README.md for supported provider capabilities, the no-provider import path, explicit candidate acceptance, research/generation bounds and verification commands. Optional external keys: GOOGLE_MAPS_API_KEY, TAVILY_API_KEY, APOLLO_API_KEY, FIRECRAWL_API_KEY, HUNTER_API_KEY and OPENAI_API_KEY. Keys alone do not authorize paid calls: MANUAL_MODE and the persisted paid-services policy still govern them. `.env.example` lists model allowlists, page/request/time/token budgets, generation reservations and explicit retry ceilings. Generation always requires review regardless of legacy AUTO_APPROVE. A separately running authorized worker executes durable research/import jobs; merely opening the UI does not run them. No worker was installed or activated in Module 4.


## Durable communication runtime

Read module5/README.md and DEPLOYMENT.md before any later authorized installation. From a separately staged backend, `python -m app.worker` runs the scheduler and job executor; `python -m app.worker --health` reports database/schema/worker health without provider calls. `RESPONSE_POLL_ENABLED=true` enables bounded sync intents in that worker even while recurring sends are paused. The API has no reply polling loop. Use the documented worker environment bounds in `.env.example`; no cron/AI prompt is required. Follow schema005 backup/migration/paused validation ordering before worker startup. None of this activates the installed worker.
