# Fieldwork deployment

The canonical personal release uses PostgreSQL17, a private FastAPI process, a production Next.js server and one dedicated worker with its integrated scheduler. Deployment has **not** occurred; Module6 currently says **NOT READY**.

Follow [the deployment guide](docs/DEPLOYMENT.md), [operational runbook](docs/RUNBOOK.md) and [release checklist](docs/RELEASE_CHECKLIST.md). Resolve the legacy State-key transfer blocker and validate the chosen container/HTTPS environment before cutover. Source/template availability is not an installed desktop service or an always-on hosted deployment.
