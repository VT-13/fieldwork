# Railway staging setup — READY

The existing `VT-13/fieldwork` repository/main and Railway project were reused. The project is now `fieldwork-staging`, with a clean `staging` environment; the original cloud environment was not used as a secret/data source. Existing `fieldwork` service identity is retained as the frontend. Required separate `api`, `worker` and dedicated `Postgres` services were added only in staging.

Stable ingress: https://fieldwork-staging.up.railway.app. Frontend `/frontend` and API/worker `/backend` use the existing Dockerfiles (Node22/Python3.13). Worker starts `python -m app.worker`; API uses its standard IPv4 listener, no access logs or trusted proxy headers. Railway environments created after October2025 have private IPv4/IPv6 DNS. Frontend readiness uses its existing `/favicon.svg` static asset because Railway health requests use a different Host; the app's exact Host check is unchanged. API `/health` has an explicit Railway health hostname allowlist. Application connectivity is separately verified through authenticated `/api/runtime`.

PostgreSQL17.11 uses `ghcr.io/railwayapp-templates/postgres-ssl:17` and its persistent staging volume. The default empty18 cluster was not downgraded in place:17 initialized a separate `PGDATA=/var/lib/postgresql/data/fieldwork17` directory. `POSTGRES_DB=fieldwork_staging`. API pre-deploy runs `alembic upgrade head` only against this dedicated database, yielding006. API/worker database URLs use Railway variable references with the psycopg driver; no DB password was manually copied. Only frontend has a public HTTP domain; API/worker/Postgres have no public domain or TCP proxy.

New operator password/hash, internal API key and encryption key were generated privately and injected as runtime service variables. Frontend receives only APP_ORIGIN, BACKEND_URL, PORT and HOSTNAME. Owner-only local staging credentials are outside Git, under `~/.local/share/fieldwork-staging/railway/`; never paste their contents into documentation/chat. A separate registered staging verification SSH key is there too. No production secrets were reused. Existing Dockerfile COPY/context exclusions were reviewed; no credential files entered the build context. Runtime variables are not Dockerfile ARG/ENV layers. All fetched build/deployment logs and7 browser JS assets were scanned against staging secret values with zero matches.

Basic HTTPS frontend/login, health, operator login and authenticated runtime checks passed. API and worker independently reached17.11/schema006. Worker/scheduler heartbeat available, no unresolved delivery, zero daily attempts, Gmail disconnected, recurring policy absent (fail-closed paused). DRY_RUN=true, MANUAL_MODE=true, RESPONSE_POLL_ENABLED=false, AUTO_APPROVE=false, production mode, debug/QA off; real provider and OAuth keys empty. No profile/company/mail fixtures or real sends were created. Read-only installed-state baseline comparison and source manifest verification passed.

## Actual commands

Official Railway CLI5.63.1, authorized to the existing project, was used for exact scoped configuration and runtime-only secret injection after UI creation/rename. Sensitive patches and HTTP login scripts stayed in owner-only files outside Git.

```sh
railway link --project 803f24c5-8e9e-4a88-9c84-7909136f4524 --environment staging --json
railway domain --service fieldwork --environment staging --port 3000 --json
railway redeploy --service Postgres --environment staging --from-source --yes --json
railway redeploy --service api --environment staging --from-source --yes --json
railway redeploy --service fieldwork --environment staging --from-source --yes --json
railway redeploy --service worker --environment staging --from-source --yes --json
railway ssh --service worker --environment staging -- python -m app.worker --health
curl --fail https://fieldwork-staging.up.railway.app/api/health
python3 scripts/source_manifest.py verify
```

Use `--from-source` to deploy current service configuration: ordinary redeploy reuses the previous deployment's configuration. Do not export Railway variable/config JSON to terminals; it contains secrets. Runtime PostgreSQL/schema/settings probes asserted the exact staging environment ID before read-only queries.

This closes **staging provisioning only**. Full Package6C certificate/proxy/CSRF/session/browser/restart verification has not begun; its previous access blocker is removed. Package6D/live Google and production cutover remain unauthorized and unverified. Trial hosting may expire/run out of credits; no paid upgrade was performed.
