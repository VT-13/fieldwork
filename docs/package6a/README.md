# Package6A — FW-026 lossless State migration

Scope: only FW-026. Canonical source remains undeployed; installed schema001, credentials, services and recurring pause are unchanged. No production workers, provider calls, email, OAuth, service installation or production migration. Module6 container/hosted/live-provider gates remain outstanding; Package6B has not started.

## Diagnosis without private contents

Read-only installed inventory found exactly one State key over100:111 characters, `self-test:` (10) + UUID (36) + `:` (1) + SHA-256 hex digest (64). Installed `backend/app/self_test.py:15` constructed this exact key from a saved desk packet and its draft hash. Its associated JSON records a historical sent self-test with original acceptance receipt and timestamp. The linked desk packet exists and its current draft hash still matches. No job contains the full key; the only stored full-key match is its own State row. No schema001–006 foreign key targets State.key.

The receipt is historical, but its identity remains active as a duplicate-send guard: canonical self_test.send explicitly looks up both the newer digest key and the original111-character key before connecting to any provider. Schema002 must also import this exact key into Operation.idempotency_key, the packet UUID into entity_id and `state:<original key>` into ActionAttempt.receipt.source. Dropping, renaming, truncating or rebuilding the key would lose that identity/provenance or permit a resend.

The100-character limit originated in the generic legacy State model and its frozen001 snapshot. No repository decision gives it a semantic/security meaning. SQLite ignored the VARCHAR length; the creator combined111 characters. PostgreSQL enforced the physical100-character bound. FW-025 prevents newly generated self-tests from exceeding the old bound, but cannot remove historical receipts.

## Chosen design

Schema006 widens only State.key to VARCHAR(255), matching the existing operation idempotency-key capacity. Preserve the primary key, every character/case, JSON value and all linked history. No alias, hash conversion, decomposition, normalization or collision resolution is needed. Distinct keys sharing their first100 characters remain distinct; exact duplicates remain rejected. All installed keys fit255. Values beyond255 or an unrecognized State column definition fail safely for explicit future reconciliation; this is not an unbounded import guarantee.

`backend/app/migration_v6.py` is the frozen versioned widening helper. On normal SQLite/PG upgrades Alembic006 follows005. SQLite uses batch column alteration; PG uses ALTER COLUMN TYPE without discarding its primary key. Narrowing downgrade is refused. Existing001–005 and their frozen helper artifacts remain byte-identical.

A cross-engine transfer cannot insert111 characters into PG001 before upgrading: nor may it upgrade002 before importing, because002 backfills legacy receipt history. The explicit empty-target transfer therefore runs, in one transaction: create001 → apply only006's widening helper → insert ALL frozen001 records → run002–006 in order → compare EVERY original table exactly → commit. No revision is skipped or prematurely stamped. The final006 helper sees255 and is idempotent. Any DDL/import/backfill/comparison failure rolls the entire target back to empty. Reapplying transfer to a populated target is refused; repeated Alembic head upgrades are no-ops.

Production API/worker schema checks now require006. This is source compatibility only; no installed process is started or updated. Fresh installations migrate normally through001–006 and ORM metadata agrees on both engines.

## Evidence / reproduce

- `failing-migration-test.log`: sanitized111-character fixture reproduced original pre-write rejection.
- `migration-suite.log`, `backend-regressions.log`, `checks.json`: isolated checks, blank credentials, disabled polling, fake HOME, disposable SQLite and native PostgreSQL17.11.
- `migration-rehearsal.json`:001→006 transfer, mode0600 SQLite/PG backups and PG restore into a new disposable database. Exact old records AND all current ORM tables match the pre-backup snapshot, including original self-test provenance, uncertain operations and synthetic integration ciphertext/generation/scopes.
- `installed-migration-preflight.json`, `identifier-structure.json`, `preservation*.json`: real installed DB inspected with mode=ro/query_only and no target connection. Metadata/count/digest evidence only; no real key/value/UUID/draft/credentials exported. Full-table row digests, DB file digest, source/credential/service-definition hashes and pause compare unchanged.

Run `FIELDWORK_DISPOSABLE_POSTGRES_URL=<disposable PG17 URL> FIELDWORK_TEST_PG_TOOLS=<PG17 bin> <clean-python> scripts/package6a_check.py`. The current local test interpreter is `/private/tmp/fieldwork-module6/venv/bin/python`; provision an equivalent locked clean environment if it is removed. Never supply the personal DB as TEST_POSTGRES_URL or a fixture.

For source-only inspection from sanitized backend with PYTHONPATH=., use `python scripts/transfer_legacy.py --source-backup <explicit SQLite001 path> --preflight-only`. This mode does not need/connect to a target, rejects --apply/stopped-confirmation and outputs counts/digests only. Preflight is not permission to migrate. A later authorized transfer still requires a consistent private backup, stopped senders, empty target, validated source manifest and all remaining release gates. No production backup was exported for this rehearsal.
