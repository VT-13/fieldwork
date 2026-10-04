# Fieldwork operations — paused personal release candidate

Release decision: **NOT READY**. Read RELEASE_CHECKLIST.md and RELEASE_CANDIDATE.md before any cutover. These instructions do not authorize deployment, provider access or communication. Keep the installed system unchanged and paused until a separately authorized rollout passes every gate.

## Processes and signals

The private Next server proxies authenticated operator sessions to FastAPI. One dedicated `python -m app.worker` process owns PostgreSQL leadership, runs the scheduler and executes bounded jobs. There is no cron sender, scheduled AI agent or API mailbox loop. Start web/API separately from the worker; web health never proves worker health. Native Mac execution requires awake hardware and network.

Run commands from the staged release's `backend` with explicit external configuration, never from the old installation's working directory. `/health` reports API/database liveness only. Authenticated `/runtime` reports schema006, worker and scheduler timestamps/status, Gmail state, stale sync, communication holds, recent communication jobs, shared daily attempts/cap and daily bounce stop. `/jobs` shows bounded queued/running/failed/blocked/interrupted work; `/outreach` shows acceptance, Sent confirmation and uncertainty separately. `python -m app.worker --health` checks schema/worker heartbeat without provider I/O and exits nonzero when stale. PostgreSQL readiness additionally needs the authenticated schema check.

Worker SIGTERM/SIGINT stops new claims and allows the bounded current job to finish. Use a supervisor grace interval longer than JOB_TIMEOUT_SECONDS (Compose uses 16 minutes, maximum job timeout is 15 minutes). Forced termination expires leases and holds reserved communication; it never authorizes retransmission. Another worker process cannot concurrently claim the same job or reserve the same communication. Scheduler dedupe keys are persistent. Offline return evaluates current buckets/policy; it does not replay missed days or add quota.

Logs use generated request IDs and operation/job/outreach/provider/status identifiers. Inspect `X-Request-ID` on private API responses to correlate requests. Logs omit query strings, Authorization, request bodies, resume/email contents and provider traceback locals. API access logging stays disabled. Collect stderr with private access and bounded retention/rotation (for example 10 MiB × 3 files per service); no hosted log collector/rotation is claimed installed. Monitor worker staleness, reconnect state, stale sync, unknown operations and blocked jobs. Quiet healthy polling does not need user notifications.

## Failures and safe actions

| Signal | Diagnose | Safe action |
|---|---|---|
| API liveness fails | DB reachable? pool exhausted? correct private target? | Pause/stop sender, restore connectivity; public error stays generic. Inspect sanitized category and database metrics privately. Never expose SQL/credentials through health. |
| Schema differs from006 | Compare stopped-target migration revision and source manifest | Stop new processes; do not start old source against partial migrations. Rehearse forward repair or backup restore. |
| Worker offline/stale | Heartbeat vs WORKER_LEASE_SECONDS; supervisor status; running Job owner/lease | Stop duplicate legacy executors, restore one worker. Check interrupted/unknown outcomes before any new communication. |
| Scheduler waiting/offline | Current long-running Job vs last scheduler heartbeat | A healthy processing worker may report waiting_for_current_job. Do not launch a second scheduler or replay past dates. |
| Gmail reconnect_required/identity_mismatch | Private integration state and verified profile email | Keep paused, reconnect through Settings only under authorized account consent. Reconnect never resumes campaigns. |
| Sync stale/failed | Last successful sync, bounded cursor recovery/backoff, sync job category | Queue Responses → Check replies when permitted. One scanner/lease; no unbounded mailbox download or AI reply. |
| Unknown/sending or confirmation pending | Operation/attempt and original RFC/provider/thread identity | Use the private **Check Sent evidence** action. Exact positive evidence can resolve; absent/mismatching evidence stays held. Do not send a replacement. |
| Queued backlog | Worker availability, capability/mode, due time, retry bounds | Fix the cause. Retry only a safe, never-attempted bounded Job through the app. Preserve owner/token fences. |
| Two distinct new bounces today | Runtime bounce_stop, immutable Events/suppression | Stop introductions/follow-ups; investigate sourced contacts. Never remove suppressions to fill quota. |
| Provider429/401/403/5xx | Sanitized category and durable attempt outcome | 401/403 authorization rejection is definite;429 is definite rate rejection;5xx/transport ambiguity holds communication. No blind company retry.403 handling is conservatively authorization-based. |
| Legacy transfer rejects a field width | Read-only preflight and explicit frozen-schema limits | **Stop cutover.** Package6A safely widens known State keys to255 in006. A future out-of-bound/unknown field still requires explicit lossless reconciliation. No truncation/guessed aliases. |

Pause in Campaign disables pending company delivery/preparation; authorized sync/reconciliation can still run. STOP is stronger and cancels continuing campaign work. A provider request reserved before pause may finish; wait for its persisted receipt/unknown state. Do not automatically respond to inbound messages or commit the student to an interview/task.

## Backups and rollback

Use BACKUP_RESTORE.md and MIGRATION_PLAN.md. Explicit targets only: SQLite backup API for the stopped legacy data; pg_dump17 custom format for PostgreSQL; private0600 outputs, encrypted storage and separate encryption-key backup. Restore to an **empty disposable** target first and verify old records, pause, suppressions, jobs, integration metadata and attempts/receipts. Preserve immutable receipt files separately. Record digest/revision/restore date; an untested dump is not a healthy backup.

Before any new external attempt, a failed cutover may restore the verified old DB **and compatible old source** as a unit while all senders remain stopped. After any reservation/provider request, preserve the failed release's DB, logs and receipts; prefer forward repair. Do not erase attempt history by restoring an earlier database. Restore fencing clears local OAuth grants/tokens, revokes sessions and reasserts pause; reconnection is deliberate. Reapply privacy deletion performed since the backup.

Credential rotation is offline and paused: stage new application/session secret (restart both services; old sessions invalidate); stage new,old CREDENTIAL_KEYS, validate and `python scripts/rotate_credentials.py --apply` on the explicit target, verify decryption, then remove old key. Google client/provider/DB secret rotation requires provider-authorized new credentials, both process configurations updated and private verification; no automatic purchase or consent. Retain old encryption keys for protected backups until their retention expires. Disposable encryption/session rotation regressions pass; actual provider/DB secrets were not rotated.

## Never do these recovery actions

Do not reset Unknown to queued, delete ledger/reservation rows, manually replay provider requests/send Jobs, bypass current policy/review, restart historical batches or enable the legacy worker. A response, opt-out, bounce, acknowledgment or uncertain send stops/holds its conversation. No quota catches up missed days. Unmatched historical receipts remain unmatched.

## Separately authorized cutover order

1. FW-026 is resolved by Package6A; close the remaining release gates. Verify the exact committed manifest/RC and reversible staged source installation. Keep PostgreSQL17 private, TLS and storage protections configured.
2. Verify recurring/manual/automation pause. Retire `rocklin-internship-outreach` in the Codex automation UI/tool and any external scheduled prompt. Inventory cron, shell loops and previous scheduled-send/batch processes; verify none remain. Stop legacy API/web LaunchAgents using their exact recorded labels only under cutover authorization; no installed worker exists. Retain plist/source copies. See module6/legacy-inventory.json; no entries were changed in this phase.
3. Confirm no in-flight mail; snapshot counts/schema/policy/receipts/credentials permissions. Back up and rehearse restore; preserve previous source and private credentials separately. Never copy plaintext tokens into a new table.
4. Stage separately. The validate-first transfer helper accepts only exact schema001 SQLite backups and empty PostgreSQL targets; **Package6A read-only installed preflight now passes with lossless006 widening**. This does not authorize production application. For already compatible PG staging targets, run `alembic upgrade head` with every sender stopped; validate006 and exact old records.
5. Configure strong external secrets, exact HTTPS APP_ORIGIN/callback and explicit TRUSTED_HOSTS (public host, private API host, localhost health host). Keep DRY_RUN=true, MANUAL_MODE=true, RESPONSE_POLL_ENABLED=false, paid permission false, recurring/manual/automation disabled. Build/start API/web only; verify read-only authenticated CRM and source/schema.
6. Start one new worker while communication remains paused and old sender is retired. Verify independent worker/scheduler health. Authorize Gmail reconnect and safe read/reconciliation explicitly; keep unknowns held. Authorized own-account draft/self-test is a separate canary, never company outreach.
7. Record zero company transmissions and preservation. Recurring activation requires a **later explicit operator decision**, current profile/reviews, permitted geography and unchanged daily limits. Module6 does not authorize it.

## Package6B verified container operations (disposable only)

Runtime-container PASS: Python3.13 production image and Node22 production image built cleanly; PG17.11 migrated006. Explicit Compose worker profile passed health, scheduler, graceful SIGTERM0, duplicate process/leader/intent protections and restart. Stage API/web were separate; web alone had an edge bridge, while API/worker/PG had only an internal network and no published backend/database port. Secrets were runtime-only; layer/decompressed-file/asset scan was clean. The actual production image was used unchanged with a copied, fenced fake-provider bootstrap only in test containers.

Actual commands/reproduction are package6b/README.md and scripts/package6b_tools.py, package6b_staging.py, package6b_recovery.py. Recovery stops staging writers, snapshots all ORM tables, invokes pg_dump17 custom format with0600 output, restores transactionally into a fresh named staging DB and compares every row, restarts PG and compares again, then restarts app processes and checks durable domain data/no duplicate fake transmissions. Heartbeat/lease and nondecreasing ExecutionLock.version are runtime coordination changes, not lost history. Do not copy these named test-target commands onto the personal database.

Communication was paused at initial startup and returned to paused after isolated fake E2E. Five fake transmissions, no real ones. Containers/VM are removed after evidence capture; no installed LaunchAgent/service/automation/pause/OAuth change. The container gate is closed; intended hosted TLS/private networking/live Google/production activation remain unverified. Package6C attempted access discovery and is BLOCKED; see package6c/verification.json.

## Package6C blocked hosting handoff

Read package6c/README.md and verification.json before resuming hosted verification. An existing authorized isolated staging project/server plus stable HTTPS hostname/access is missing; do not infer this gate from local TLS or source controls. No hosted commands/tests were executed. Keep the installed personal DB and credentials outside staging. No exact Google callback is ready to register, and Package6D has not started.
