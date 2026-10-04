# Fieldwork Module6 candidate — NOT READY

Identifier: `fieldwork-module6-rc1` (local Git reference; no remote publication).
Application commit: recorded after committing the reviewed implementation in `docs/module6/verification.json`.
Schema/migration head: `005` (unchanged frozen migrations001–005).
Configuration: personal-v2 communication policy, bounded deterministic worker/scheduler; current verified profile and database pause remain authoritative.
Runtime tested: Python3.13.3, Node24.18.0, npm11.16.0, PostgreSQL17.11, native macOS ARM64; runtime-only dependency environment, production Next standalone build, disposable fake providers.
Frontend build identity: `3W_xTGOAvedGHON6GFX9O`.
Timestamp: generated UTC in `docs/module6/verification.json`; build artifacts are reproducible from locked source where intended; Next BUILD_ID itself is generated per build.

Code fixes, tests and classified evidence are committed before the final evidence-only identity update. The final local Git reference includes the runbook/checklist/evidence update; those updates do not change application code. Source integrity/bundle verification must pass on that checkout. Do not use the old installed app as the candidate or silently overlay it.

**NOT READY TO CUT OVER:** FW-026 installed historical State key width needs a versioned lossless migration. Declared Docker runtime and intended hosted TLS remain unverified. Live Google safe validation remains an authorized-provider condition. See RELEASE_CHECKLIST.md, RUNBOOK.md and module6/README.md. Nothing was deployed, migrated or activated.
