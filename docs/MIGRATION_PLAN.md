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

A later rollout must supply new external operator/encryption configuration, use a maintained PostgreSQL17 client/server and exact private HTTPS origin, migrate a restored backup first, and require an authenticated Gmail reconnect. Do not copy the legacy refresh token into the new table by hand or restore an old token after disconnect. Setup/backup/key scripts have explicit application/disposable targets; no script was run on live credentials/database in Module2. Any previously plaintext token remains intact in the unchanged installed runtime until a controlled deployment handles it. Source manifests now cover the security modules and changed dependency locks. The desktop templates no longer carry the unauthenticated local flag; installation is still a later operation.

003 also refuses destructive downgrade. After restore, run the explicit post_restore_safety fence before startup to pause campaigns, invalidate sessions and clear credential access while retaining receipts/unknown operations. Stop APIs/workers before external encryption-key changes; restart with the intended keyring after verification. External encryption rotation uses a new,old keyring and validate-only `rotate_credentials.py`; --apply rewrites ciphertext with the active key, after a verified backup. Preserve the old key until all required encrypted backups are retired. Module2 tests verified rotation with fake credentials; no live key changed.
