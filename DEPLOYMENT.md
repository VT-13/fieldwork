# Fieldwork deployment

> PRODUCTION CUTOVER PAUSED: Package 6E passed. Package 6F is intentionally paused because the current Railway plan cannot provision the full production architecture. Before public/always-on production deployment, upgrade Railway and resume Package 6F from docs/PRODUCTION_CUTOVER_PAUSED.md.

See [pause checkpoint](docs/PRODUCTION_CUTOVER_PAUSED.md).

The canonical personal release uses PostgreSQL17, a private FastAPI process, a production Next.js server and one dedicated worker with its integrated scheduler. Personal production deployment has **not** occurred; Package6E verifies the release **READY for a separately authorized production cutover**. Isolated Railway staging is now provisioned.

Follow [the deployment guide](docs/DEPLOYMENT.md), [operational runbook](docs/RUNBOOK.md) and [release checklist](docs/RELEASE_CHECKLIST.md). FW-026 is resolved by Package6A and the runtime-container gate passes Package6B. Package6C hosted HTTPS/private staging and Package6D scoped live Google gates pass; see docs/package6e/verification.json for current final verification. Source/template availability is not an installed desktop service or an always-on hosted deployment.

## Verified Linux staging — Package6B

Linux ARM64 Docker builds and actual production Python3.13.16/Node22.23.3/PG17.11 runtime pass, including separate API/web/worker, integrated scheduler, schema006, non-root app users, injected secrets, layer/asset scan, concurrency, fake-provider HTTP E2E and restart/private backup/restore. Only loopback web ingress was published; API/worker/DB stayed private. See [executed commands and limits](docs/package6b/README.md) and [verification](docs/package6b/verification.json). Production source/DB/credentials/services and pause were not changed. Temporary staging was removed; this is not a hosted deployment or production activation.

## Railway hosted staging — Package6C PASS

The existing `fieldwork-staging` project, clean `staging` environment, has stable HTTPS [Fieldwork staging](https://fieldwork-staging.up.railway.app), private API/worker/PG17.11 and schema006. Trusted TLS, real ingress/session/origin/headers/browser/private-network/worker checks pass; see [actual hosted verification](docs/package6c/README.md) and [evidence](docs/package6c/verification.json). Public Next now carries the same HSTS/Permissions-Policy as the API. Communication remains paused; the dedicated staging Gmail connection is verified and connected. Its callback is `https://fieldwork-staging.up.railway.app/api/integrations/gmail/callback`. Scoped live Google verification passes; production activation remains separately authorized and unperformed; no personal production change occurred.
