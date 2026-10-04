# Fieldwork Module6 candidate — NOT READY

Identifier: `fieldwork-module6-rc1` (local Git reference; no remote publication).
Application commit: `b3b23f6e9336c32286ff92a6af6bd6ad5202a666`.
Original Module6 candidate schema/migration head: `005` (unchanged frozen migrations001–005). Current canonical migration head: `006`; Package6A verification is `docs/package6a/verification.json`. The recorded Module6 build/E2E identities remain historical.
Configuration: personal-v2 communication policy, bounded deterministic worker/scheduler; current verified profile and database pause remain authoritative.
Runtime tested: Python3.13.3, Node24.18.0, npm11.16.0, PostgreSQL17.11, native macOS ARM64; runtime-only dependency environment, production Next standalone build, disposable fake providers.
Frontend build identity: `3W_xTGOAvedGHON6GFX9O`.
Timestamp: `2026-10-04T02:53:47.864019+00:00`; build artifacts are reproducible from locked source where intended; Next BUILD_ID itself is generated per build.

Code fixes, tests and classified evidence are committed before the final evidence-only identity update. The final local Git reference includes the runbook/checklist/evidence update; those updates do not change application code. Source integrity/bundle verification must pass on that checkout. Do not use the old installed app as the candidate or silently overlay it.

**NOT READY TO CUT OVER:** FW-026 is resolved by Package6A schema006 with representative/PG17/backup/installed read-only evidence; no production migration occurred. Declared Docker runtime passes Package6B; intended hosted TLS remains unverified. Live Google safe validation remains an authorized-provider condition. See RELEASE_CHECKLIST.md, RUNBOOK.md and module6/README.md. Nothing was deployed, migrated or activated.

Current runtime-container verification: `fieldwork-package6b-container` (local source/evidence reference), Linux ARM64 production Python3.13/Node22/PG17, schema006. Exact runtime image IDs and commands are docs/package6b/verification.json and README.md. Original Module6 frontend build/commit identities remain historical and are not overwritten by container proof. Production remains undeployed and Package6C access discovery BLOCKED; no hosted checks executed (package6c/verification.json).
