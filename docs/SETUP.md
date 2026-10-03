# Personal-first setup (canonical Module 2 source; not yet deployed)

The installed app is deliberately unchanged. Follow MIGRATION_PLAN.md before replacing it. Current recurring outreach stays paused. No setup instruction is permission to send, purchase provider access or start a worker.

Use Python 3.11+ and a maintained PostgreSQL 17 instance for production, Node22+, and private storage with disk encryption. Development tests may use disposable SQLite. Install the pinned backend requirements in a new environment; never patch the installed environment in place during release preparation.

From backend, `python scripts/security_setup.py --output /private/path/fieldwork-secrets.env` prompts for a new Fieldwork operator password and creates mode0600 configuration containing its scrypt hash, a random CLI API key and an external credential-encryption key. It never asks for a Gmail password. Keep this file/keys separately from database backups. Merge its values into private backend environment configuration without printing them. Use dotenv loading or a secret manager; do not shell-source a hash-containing dotenv file. `.env` must be a regular file, mode0600. Never use NEXT_PUBLIC variables for secrets.

Copy `.env.example` as a starting point. For production set ENVIRONMENT=production, a PostgreSQL DATABASE_URL, an absolute private DATA_DIRECTORY, explicit TRUSTED_HOSTS, HTTPS APP_ORIGIN and matching OAUTH_REDIRECT_URI. Generate actual API_KEY/OPERATOR_PASSWORD_HASH/CREDENTIAL_KEYS as above. Configure TLS at the private ingress and protect database networking/storage. Defaults do not satisfy production validation. Backend migrations must run before service startup; Docker worker is opt-in via its `worker` profile.

Frontend configuration only needs BACKEND_URL and APP_ORIGIN. It no longer needs API_KEY or DASHBOARD_PASSWORD and never forwards a bearer key on behalf of a browser. Start the separately staged API with access logging disabled, serve the built frontend privately, then sign in at `/login`. Restart services when changing external application secrets; a new password hash invalidates prior sessions. Server sessions expire after SESSION_HOURS (default12); Settings provides sign-out and Gmail lifecycle controls. CLI requests use the separate operator bearer key.

## Gmail

Create a Google OAuth web client with the exact OAUTH_REDIRECT_URI registered. Set OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET externally. Verify the student profile and its own email, then Settings → Connect / reconnect Gmail. Browser consent opens Google's official page and returns through the authenticated callback. Default scopes are send and read-only; enable GMAIL_DRAFTS_ENABLED and reconnect only if own-account provider draft saving is desired. Tokens are stored encrypted in the database. SENDER_EMAIL, when configured, must agree with profile and provider identity. The existing connected identity cannot transfer silently.

Disconnect removes local authorization immediately, attempts upstream revocation and preserves send history. Reconnect does not resume outreach. Old plaintext OAUTH_REFRESH_TOKEN files are preserved in the installed runtime until a separately authorized migration; the new Gmail implementation never reads them. Production rejects legacy refresh-token settings. For migration, pause, set up encryption/session secrets, run schema003 on a disposable backup first, then reconnect through the app; remove retired plaintext tokens only in that later controlled deployment. Do not run the old bootstrap or historical drivers.

Google testing-mode expiration, app-verification requirements and restricted-scope approval remain provider-side requirements; a fake-provider test does not certify a real registration. Outlook remains a compatibility contract, with no production OAuth/send rollout in this module.

Provider API keys remain optional and external. Manual mode and explicit paid-service prohibition block billed calls; no subscription-to-ChatGPT connection is implemented. For all quota/pause/dry-run distinctions read ARCHITECTURE.md. See SECURITY.md, DATA_LIFECYCLE.md and BACKUP_RESTORE.md for current implemented controls.
