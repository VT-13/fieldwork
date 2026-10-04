# Production cutover paused — Package6F

PRODUCTION CUTOVER PAUSED: Package 6E passed. Package 6F is intentionally paused because the current Railway plan cannot provision the full production architecture. Before public/always-on production deployment, upgrade Railway and resume Package 6F from docs/PRODUCTION_CUTOVER_PAUSED.md.

## Release and current environments

Canonical repository: VT-13/fieldwork, branch main. Package6E PASS / personal-first single-operator release READY. The exact verified application release is **b68a84fb7d5426a30a54aab650a0715493c9533e** (`b68a84f`). Later pause/checkpoint documentation commits do not change or invalidate that application source; production must initially deploy the verified commit, not silently use a newer main HEAD.

Package6F encountered only Railway's concrete free-plan resource provisioning limit before cutover. It is now intentionally PAUSED, not an instruction to bypass the limit. No plan upgrade, alternate architecture, service consolidation or staging repurposing is authorized. The original architecture remains public frontend, private API/backend, private deterministic worker/integrated scheduler and private persistent PostgreSQL17.

Staging: **fieldwork-staging / staging**, https://fieldwork-staging.up.railway.app. It remains intact and available for private single-operator use with its existing Gmail connection, PostgreSQL, worker, data and security configuration. Recurring outreach remains PAUSED; private use does not automatically authorize company outreach. It is a reference environment, not the production database or a rollback copy of personal records.

Production: **fieldwork-production / production**. Project ID `8cc02692-cbca-41e1-b2f9-1c95f822a113`, environment ID `c4979de7-1d82-40d8-be9c-ad260ac735d5`. Partial Postgres service ID `31451c8f-bf83-4804-ad75-48890adac960`, image `ghcr.io/railwayapp-templates/postgres-ssl:17`. Its idle deployment was stopped during this pause because it was running without persistent storage; service/project/environment configuration remains preserved. No Fieldwork production schema/personal-state import was performed. No frontend/API/worker was provisioned; no production hostname or OAuth client was configured. Staging was not modified.

## Completed steps

- Verified canonical main/remote at b68a84f, clean checkout and passing source manifest.
- Read-only source preflight verified schema001, all communication paused and no in-flight outreach status.
- Used canonical `backend/scripts/backup_database.py` SQLite backup API to create a private consistent backup; checked SQLite integrity, SHA256 and exact legacy-row equality against source.
- Canonical schema001→006 migration preflight PASS, including the over-width State identity; no transfer applied.
- Preserved original external configuration, exact historical receipt-file bytes and local service definitions privately for rollback. Original personal database/source/credentials were not modified.
- Created the separate production project/environment and partial Postgres service. Railway rejected the API/frontend/worker provisioning attempts with “Free plan resource provision limit exceeded. Please upgrade to provision more resources!” No workaround was attempted.
- Stopped the partial idle production deployment without deleting its service/project/checkpoint; left staging operational.

Backup/reference location (private, never committed):
`/Users/vihaantirumala/.local/share/fieldwork-production/cutover-2026-10-04/`

Files: `personal-schema001.sqlite`, `backup-verification.json`, `installed-before.json`, `external-originals/`, and resumable `checkpoint.json`. Backup verification records digest/timestamp/counts privately. Baseline aggregate counts:1 profile,46 companies,46 contacts,83 evidence records,46 outreach records,6 events,2 suppressions,1 job and13 State records. Backup integrity was rechecked at pause. Original personal data remains at its original location. No personal content, credentials or message bodies are included in this document.

## Incomplete steps and exact continuation

Production persistent storage/PG initialization and fresh secrets; exact-release builds; actual-data restored-backup migration rehearsal; canonical transactional lossless import/001→006 migration and parity checks; production hostname/TLS; dedicated production OAuth/client/consent and minimal Gmail read-only health; paused worker startup/health/leadership; focused production security/UI/privacy smoke; secret/log review; legacy-runtime ownership transition; verified initial production backup and final cutover report are all incomplete. No production worker has started. Legacy autostart/configuration is unchanged; data and rollback capability remain preserved.

Production migration: **NOT performed**. Production OAuth: **NOT configured**. Company outreach during cutover: **0**. Self-test messages: **0**. Recurring outreach: **PAUSED**.

Only when the operator explicitly resumes:

1. Upgrade the existing Railway workspace to a plan capable of the required separate services and persistent storage; owner approves billing.
2. Reopen the existing fieldwork-production project/environment and reuse the recorded partial Postgres service. Do not recreate them or alter staging.
3. Verify canonical repository, exact b68a84f commit, remote containment and source manifest. Later documentation-only HEADs do not replace the verified deployment revision. Application changes require affected release re-verification.
4. Verify whether original personal records/policy/receipts changed since the saved backup. Keep all communication paused; freeze writers as the runbook requires. Create and verify a fresh canonical backup if necessary; retain the previous backup.
5. Resume at **remaining production service/storage provisioning**, then the canonical restored-backup rehearsal and lossless transfer. Follow the existing migration/runbook ordering: transfer requires an empty explicit PG target and applies001→006 transactionally. Do not first populate the target with a separate schema initialization that would cause empty-target refusal.
6. Complete the remaining original Package6F gates. Do not restart the whole release process unless actual source changes require re-verification. No company sending is a health check; recurring activation stays separately authorized.

Rollback references: docs/RUNBOOK.md, docs/BACKUP_RESTORE.md and docs/MIGRATION_PLAN.md, plus the private pre-cutover backup and preserved original configuration/source. No personal migration occurred, so there is currently nothing to roll back. Future production backup and worker-stop instructions must be recorded before declaring cutover complete. After any new attempt, preserve receipts and uncertain holds; never restore older history to authorize a resend.

No automated reminders were created. No further production provisioning/migration/OAuth/communication work is authorized while paused.
