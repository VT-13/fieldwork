# Module 1 migration plan — NOT executed on the personal installation

## Current and target

The installed runtime has 27 documented source discrepancies relative to the Phase 0 checkout. Module 1 reconciles those behaviors into this Git repository and introduces central policy/ledger execution. The installed runtime remains unchanged. Its SQLite database, private `.env`, receipts, suppressions, profile and active pause remain authoritative until a separately authorized deployment.

Target schema: Alembic 002 adds operations, action_attempts, domain_transitions, execution_lock, plus unique/check/foreign-key constraints and indexes. No legacy column/table is dropped or rewritten. Backfill preserves existing Outreach IDs, provider/thread IDs, RFC identifiers, times and known outcomes. Historical authorization is explicitly unknown, not fabricated. Ambiguous historical attempts become unknown. Existing self-test history is linked into the ledger. The migration is frozen rather than importing mutable current ORM definitions.

## Deployment ordering (future authorization required)

1. Verify source integrity and tests. Create a committed source-only bundle with `python scripts/source_manifest.py bundle --output /private/tmp/fieldwork-release.tar.gz`. Never package `.env`, database files, caches or credentials. Retain the previous source release.
2. Record policy, pause, counts, unresolved attempts, schema version and receipt digests. Stop API/background processes during migration; do not enable the historical worker. Verify no transmission is in flight. Preserve recurring `enabled=false`, manual stop state and all suppressions.
3. Create a private consistent SQLite backup using SQLite backup API (not a raw copy during WAL writes), and separately back up immutable receipt files and private credentials with original permissions. Confirm the backup opens and record its digest. For PostgreSQL use a verified consistent database backup.
4. Stage source separately from the installed release. Configure the existing private data/credential locations explicitly; do not overwrite or rotate credentials. Run `alembic upgrade head` with the intended database only after confirming backup and target path. First exercise the migration on a disposable restored backup, then compare all old-table records and IDs.
5. Historical `scheduled-receipts.jsonl` and `historical-batch/receipts.json` retain their original bytes. The additive migration covers database receipts; use `backend/scripts/import_receipts.py --help` for explicit file import. Default is validation only. Review exact linkage and unmatched entries before `--apply`. Import is idempotent by source digest/index. Do not delete originals or treat acceptance as Sent/inbox verification. Manual batch/progress State remains byte-equivalent and is not regenerated.
6. Verify migration version, old records, receipt linkage, suppression state, unresolved holds and `enabled=false`. Run offline policy/route checks before starting the API. Source verifier must pass against the staged release. Install/restart only under a later explicit deployment task. Preserve polling policy; never start the legacy worker by default.
7. Confirm app health, read-only CRM and connection status. No send is a migration test. Resuming outreach is a separate operator decision after all holds are understood.

## Rollback and failure

002 deliberately refuses destructive downgrade: evidence may represent real external actions. Before any new activity, stop processes and restore the verified pre-migration backup plus previous source as a unit. After any new attempts exist, do not roll the database back and erase those attempts; keep it paused and use a forward repair retaining all receipts. Never reset unknown/running to queued just to make the system proceed. A provider acceptance receipt is preserved before confirmation; reconcile it with matching provider Sent evidence.

Never replay historical drivers, batch manifests, send receipt files, missed schedules or provider requests. Never restore source over runtime state. Desktop plist paths are personal-machine templates, not a portable deployment installer. Docker/PostgreSQL/hosted release checks remain later gates; Module 1 local verification does not certify them.

## Verification performed

Disposable SQLite migration tests compare every old table before/after, preserve pause, profile, suppression and provider IDs, and compare resulting schema against ORM metadata. Source integrity tests alter/delete/add source and require rejection. Tests cover two independent database connections claiming one operation, pause races, uncertain delivery and preserved acceptance receipts. See `docs/module1/checks.json` and logs. No production migration, send, OAuth mutation or deployment was executed.

## Module 2 additive security migration

003 adds operator_sessions, integrations, oauth_grants and rate_buckets with explicit personal ownership/status constraints and indexes. It neither imports plaintext secrets nor modifies existing rows/receipts/pause. PostgreSQL fresh and representative001→003 migrations were exercised on disposable schemas, with metadata comparison and exact old-table equality. Concurrent ExecutionLock claims and quota reservation also passed on PostgreSQL; SQLite results are no longer the only evidence.

A later rollout must supply new external operator/encryption configuration, use a maintained PostgreSQL17 client/server and exact private HTTPS origin, migrate a restored backup first, and require an authenticated Gmail reconnect. Do not copy the legacy refresh token into the new table by hand or restore an old token after disconnect. Setup/backup/key scripts have explicit application/disposable targets; no script was run on live credentials/database in Module 2. Any previously plaintext token remains intact in the unchanged installed runtime until a controlled deployment handles it. Source manifests now cover the security modules and changed dependency locks. The desktop templates no longer carry the unauthenticated local flag; installation is still a later operation.

003 also refuses destructive downgrade. After restore, run the explicit post_restore_safety fence before startup to pause campaigns, invalidate sessions and clear credential access while retaining receipts/unknown operations. Stop APIs/workers before external encryption-key changes; restart with the intended keyring after verification. External encryption rotation uses a new,old keyring and validate-only `rotate_credentials.py`; --apply rewrites ciphertext with the active key, after a verified backup. Preserve the old key until all required encrypted backups are retired. Module 2 tests verified rotation with fake credentials; no live key changed.

## Module 4 additive intelligence migration — not deployed

004 adds Candidate, ContactObservation, StudentFact and Generation records, four evidence provenance/freshness columns and Usage.details. Its frozen `app/migration_v4.py` does not import mutable ORM definitions. Existing evidence becomes explicitly unknown with empty content hashes; historical message approvals, receipts, suppressions, source dates and pause state are not rewritten or promoted. See module4/schema004.sql for documentation, not an alternative migration runner.

The same backup/stopped-sender/source-integrity ordering applies: test 001→004 on a restored disposable backup first; compare historical rows and pause before installing source. SQLite and disposable PostgreSQL schema/row-preservation tests passed; this is not permission to migrate the personal database. 004 refuses destructive downgrade because source/claim history must remain available. Module 4 does not start the installed worker or alter OAuth.


## Module 5 runtime migration/release ordering — NOT executed

005 extends existing jobs with nullable available_at/lease_until and owner_token, plus nullable Event contact/outreach foreign keys and personal campaign_id. The frozen Alembic migration is authoritative; it creates no replacement queue, rewrites no history and invents no legacy due time/ownership or contact/outreach linkage. Historical jobs default to no owner; stale legacy running jobs are interrupted safely on the new runtime. SQLite/PostgreSQL schema comparisons, forward old-row/pause preservation and disposable backups/restores cover this target. Downgrade refuses destructive history removal.

For a later explicitly authorized rollout:

1. Record current source/policy/pause, counts, receipts, unresolved operations, schema and credentials configuration. Back up consistently and verify restoration to a disposable target, retaining original receipt files and private key configuration separately.
2. Stop all existing API/worker/scheduled-send/batch executors and retire the external scheduled AI outreach task. Confirm no in-flight transmission. Do not replay old batch files or enable the legacy worker. This source phase changes none of those installed services/automations.
3. Verify the committed canonical source manifest and source-only release bundle. Stage a new release/venv independently; preserve the previous source and installed credentials. Verify recurring paused/stop/suppression policy on the intended target and disposable rehearsal.
4. Rehearse 001→005 on the restored disposable data; compare old records, IDs, receipt fields, suppressions and policy. Under release authorization, run Alembic on the exact intended stopped production database. Do not start the old API/worker against partially migrated data.
5. Stage the API/web and dedicated `python -m app.worker` service with the same explicit private configuration/database. Scheduler is inside that worker; no cron/LLM executor or API response loop is needed. A service file does not grant permission to install/start it. Production requires maintained PostgreSQL17, private HTTPS, sessions and encrypted Gmail configuration. A Mac service requires awake hardware; jobs are portable to an always-on private worker.
6. Validate schema005, manifest, authenticated CRM and separate worker/scheduler health without company sends, with recurring/manual delivery still paused. Preserve unknown operations; never reset them to queued. A test worker must use only disposable DB/config.
7. Validate/import historical receipt files via the existing validate-first importer. Inspect unmatched/ambiguous records. Reconcile existing attempts through exact positive Sent evidence; missing/mismatching mail remains held. Existing file receipts and acceptance outcomes are immutable evidence.
8. Verify the actual connected Gmail/profile identity through the approved account lifecycle. An authenticated reconnect may be required by the security migration, but is a separate concrete release action, not a reason to copy an old plaintext refresh token. No OAuth is changed in Module 5.
9. Complete Module 6 container/maintained-PostgreSQL17/TLS/hosted/Safari and authorized safe provider release checks, health/monitoring, crash recovery and restore/key rotation gates. Own-account provider checks require existing policy authorization; company sending is not a health check.
10. Enable eligible communication only under explicit release authorization after all holds/current reviews are resolved. Preserve caps, current city scope and current policy. There is no missed-day catch-up or historical batch restart. Do not resume simply because migration/worker startup succeeded.

After new attempts occur, do not restore an older DB and erase their reservations/receipts. Stop/pause and forward-repair; any source rollback must remain compatible with retained schema/history. See DEPLOYMENT.md and BACKUP_RESTORE.md for safe shutdown, restore fencing and external credential rotation.
