> Historical MVP instructions. Current security/OAuth setup is in [SETUP.md](SETUP.md) and [../SECURITY.md](../SECURITY.md); release ordering is in [MIGRATION_PLAN.md](MIGRATION_PLAN.md). Basic authentication, browser bearer forwarding and plaintext Gmail bootstrap described below are retired in canonical source. No deployment is authorized by this document.

# Deployment guide

The repository is ready to configure for deployment, but no hosted resources or mail credentials are provisioned. Use one PostgreSQL database, one API service, one persistent worker, and one Next.js service. A browser-only static export cannot run this system.

## Railway

1. Create a project and a PostgreSQL service with private networking, backups and an appropriate region.
2. Add an API service from this repository, root directory `backend`, Dockerfile `Dockerfile`. Configure the production environment variables from `.env.example`, using Railway's PostgreSQL credentials and the `postgresql+psycopg://` scheme. Set `ENVIRONMENT=production`.
3. Configure a pre-deploy command `alembic upgrade head`. Start the API using `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (Railway shell command setting, not JSON exec). Health path `/health`.
4. Add a separate worker service from `backend`, same secrets/database, start `python -m app.worker`. Keep it running; serverless request-only functions cannot run the scheduler.
5. Deploy the Next.js frontend on Railway (`frontend` root, included Dockerfile) or Vercel. Set `BACKEND_URL` to the API address reachable from the frontend server, the same `API_KEY`, a separate `DASHBOARD_PASSWORD`, and `APP_ORIGIN` equal to the HTTPS dashboard origin.
6. Test authentication and origin checks on the actual hosted domain, then follow the acceptance checks below.

## Render

1. Provision managed PostgreSQL with backups enabled.
2. Add a Docker web service rooted at `backend`. Environment and pre-deploy migration command as above. Start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`; health path `/health`.
3. Add a background worker from the same backend with `python -m app.worker`, sharing the database and secrets. Choose a plan that runs continuously; a suspended free web instance cannot provide autonomous follow-ups.
4. Use a second Docker web service for Next.js or Vercel for the frontend. Keep API access private where possible; otherwise require HTTPS and the bearer key.

## Vercel frontend

- Import `frontend` as the project root. Install `npm ci`, build `npm run build`.
- Configure `BACKEND_URL`, `API_KEY`, `DASHBOARD_PASSWORD`, `APP_ORIGIN` as server-side variables. Never use `NEXT_PUBLIC_` for these.
- The API proxy only performs short CRUD/enqueue calls. All long-running research, LLM and email work stays on the persistent Python worker.
- Set the exact production origin before enabling forms. Preview domains need their own matching origin/environment and should connect to a separate test backend/database.
- Do not enable `ALLOW_LOCAL_NO_AUTH` on a hosted deployment. Prefer an identity-aware proxy / MFA in addition to Basic Auth for Internet-facing access.

## Release and operation

1. Build and test a pinned revision. `package-lock.json` pins Node packages; `requirements.lock.txt` records the tested Python dependency set.
2. Back up the database before migrations. Apply migrations once before starting new workers.
3. Keep automation paused and `DRY_RUN=true` during initial release.
4. Review `/health`, Settings integration configuration, a successful inbox sync and worker job completion. Credential presence is not a live service health check.
5. Complete your profile and verify one real company's sources and recipient manually.
6. In a **separate sandbox mailbox and database**, enable live sending and send one message to another mailbox you control. Confirm the provider accepted it, it appears in Sent, the recipient receives it, and replying prevents a follow-up.
7. Test a rejection/opt-out outcome and uncertain delivery handling. Never reset an unknown email to approved just because it does not immediately appear in Sent.
8. Only then configure production live sending and automation. Keep the cap at 20–25 initially; the hard ceiling is 30 total messages/day.

### Monitoring

Monitor API availability, worker process restarts, job error counts, `unknown` / `failed` outreach, mailbox authorization failures, and budget consumption. A scheduled discovery job is deduplicated daily and identical query results stay cached for the cooldown. A blocked company moves to `needs_attention` so the next company can proceed. Some states intentionally require manual intervention rather than generating API charges forever.

Use provider-side cost caps and alerts. Reservations are approximate. Back up PostgreSQL daily and rehearse restore. Restrict database/network access and encrypt storage. Avoid logging message bodies, access tokens, refresh tokens, or contact lists in centralized logs. Configure reverse-proxy rate limits for sign-in attempts. Use distinct secrets across development and production.

### Recovery

- **Research/LLM/provider failure:** inspect sanitized job error and provider console. Fix configuration; use Settings → Retry. No autonomous infinite job retries.
- **429 sending rejection:** bounded retry after 15 minutes, maximum three attempts on that outreach. Other 4xx errors are failed and require review.
- **Timeout/5xx/worker crash while sending:** status is unknown. Queue an inbox sync. An exact RFC Message-ID match in Sent reconciles it to sent. If missing, check the provider manually; absence alone is not proof of non-delivery. This release intentionally exposes no one-click unknown resend.
- **Mailbox backlog exceeds polling page limit:** sync blocks sending. Narrow the mailbox backlog or extend the implementation with provider-specific persistent pagination/delta cursors before live use. Do not skip the unread interval.
- **Rollback:** stop the worker, deploy the previous compatible build, restore a tested backup if needed. Do not erase the outbox to clear failures; it carries deduplication history.

## Runtime acceptance still required

This build was tested locally with SQLite and mocked external adapters. Docker/PostgreSQL and live cloud resources were not available in the build environment. Execute Compose and the PostgreSQL-specific test on your deployment environment before calling the deployment production-verified. Verify current plan restrictions, OAuth app permissions and model availability with your own accounts.
