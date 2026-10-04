# Fieldwork deployment

The canonical personal release uses PostgreSQL17, a private FastAPI process, a production Next.js server and one dedicated worker with its integrated scheduler. Deployment has **not** occurred; Module6 currently says **NOT READY**.

Follow [the deployment guide](docs/DEPLOYMENT.md), [operational runbook](docs/RUNBOOK.md) and [release checklist](docs/RELEASE_CHECKLIST.md). FW-026 is resolved by Package6A and the runtime-container gate passes Package6B. Intended hosted HTTPS/private staging and live-provider gates still require separate verification before cutover. Source/template availability is not an installed desktop service or an always-on hosted deployment.

## Verified Linux staging — Package6B

Linux ARM64 Docker builds and actual production Python3.13.16/Node22.23.3/PG17.11 runtime pass, including separate API/web/worker, integrated scheduler, schema006, non-root app users, injected secrets, layer/asset scan, concurrency, fake-provider HTTP E2E and restart/private backup/restore. Only loopback web ingress was published; API/worker/DB stayed private. See [executed commands and limits](docs/package6b/README.md) and [verification](docs/package6b/verification.json). Production source/DB/credentials/services and pause were not changed. Temporary staging was removed; this is not a hosted deployment or production activation.

## Package6C hosting access check — BLOCKED

No intended staging project/server, stable HTTPS hostname or usable hosting access is configured. Railway opens at sign-in. No hosted deployment or certificate/proxy/session/browser/worker validation occurred. See [access findings and resume boundary](docs/package6c/README.md) and [verification](docs/package6c/verification.json). Package6B remains PASS; hosted TLS stays unchecked and Package6D is NOT READY. Production is unchanged.
