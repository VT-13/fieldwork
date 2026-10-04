# Fieldwork deployment

The canonical personal release uses PostgreSQL17, a private FastAPI process, a production Next.js server and one dedicated worker with its integrated scheduler. Personal production deployment has **not** occurred; the overall release remains **NOT READY**. Isolated Railway staging is now provisioned.

Follow [the deployment guide](docs/DEPLOYMENT.md), [operational runbook](docs/RUNBOOK.md) and [release checklist](docs/RELEASE_CHECKLIST.md). FW-026 is resolved by Package6A and the runtime-container gate passes Package6B. Intended hosted HTTPS/private staging and live-provider gates still require separate verification before cutover. Source/template availability is not an installed desktop service or an always-on hosted deployment.

## Verified Linux staging — Package6B

Linux ARM64 Docker builds and actual production Python3.13.16/Node22.23.3/PG17.11 runtime pass, including separate API/web/worker, integrated scheduler, schema006, non-root app users, injected secrets, layer/asset scan, concurrency, fake-provider HTTP E2E and restart/private backup/restore. Only loopback web ingress was published; API/worker/DB stayed private. See [executed commands and limits](docs/package6b/README.md) and [verification](docs/package6b/verification.json). Production source/DB/credentials/services and pause were not changed. Temporary staging was removed; this is not a hosted deployment or production activation.

## Railway staging provisioned — ready for Package6C

The existing project is now `fieldwork-staging`, clean environment `staging`, with stable HTTPS [Fieldwork staging](https://fieldwork-staging.up.railway.app). Existing frontend service plus separate private API/worker/PostgreSQL17.11 are online on schema006, communication paused, real providers disconnected. See [actual setup and smoke commands](docs/railway-staging/README.md) and [verification](docs/railway-staging/verification.json). The earlier Package6C access blocker is removed; full hosted TLS/security verification remains outstanding and was not run by this setup task. No installed personal production change occurred.
