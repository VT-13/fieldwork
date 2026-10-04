# Module6 production verification — NOT READY

Canonical implementation remains undeployed. The installed schema001 personal app, credentials, LaunchAgent definitions, receipts, CRM counts and recurring pause are unchanged. Source baseline cc43165 verifies from an isolated committed archive; the new candidate's source is verified and bundled using the same manifest tooling. Git/application revision, schema005, build ID, UTC timestamp and configuration identity are in RELEASE_CANDIDATE.md and verification.json.

## Executed evidence

Clean Python3.13.3 locked test/runtime environments and clean npm ci on Node24.18.0/npm11.16.0 succeeded. PostgreSQL17.11 was compiled under a private temporary prefix from the official tarball with SHA256 `dd27f2b3c59e73ed14aa3324901242bf69a032a6347805f274e6260322d42979`; a UTF8 cluster listened only on127.0.0.1:55436. Initial SQL_ASCII fixture was rejected and replaced; this was harness setup, not a passed production configuration. Official source and maintenance policy: [17.11 source](https://www.postgresql.org/ftp/source/v17.11/), [versioning](https://www.postgresql.org/support/versioning/). Local build excluded server SSL/ICU/readline/zlib; it verifies database semantics, not production DB TLS/storage hardening.

Final full suite:250 passed,0 skipped, two upstream TestClient deprecation warnings; contracts/fixture checks and Ruff pass. Maintained-target migrations/parity/constraints/indexes, ExecutionLock/quota/reply/worker races, lifecycle/scheduling/failure/privacy/security/restore are included. `backend-checks.json` captures actual commands and exit statuses. Compatible sanitized SQLite001 transfer/private backup/005 migration/mutate/PG17 restore preserves every old row and uncertain history; injected005 transaction failure remains004 and retry/repetition succeeds.

Production-built Chromium/WebKit/Firefox each pass20 browser tests (60 total,0 skipped/flaky), including axe at four viewport sizes, keyboard/dialogs/forms/loading/error/locked messages and overflow. Browser APIs are synthetic fixtures and do not prove authentication/provider behavior. That separate evidence is `e2e-results.json`: real HTTPS with an explicitly trusted ephemeral CA → production Next proxy → authenticated API → actual dedicated worker process → PG17 → fixed fake provider seams. It proves initial discovery/accept/contact/research/evidence/ranking/generation/independent review/approval/send/receipt, reviewed distinct follow-up with original subject/thread, reply linkage/cancellation, forced termination→unknown→absent evidence hold→exact Sent reconciliation with no resend, reply race, shared cap across follow-up/unknown/self-test/initial and configured timezone rollover. It used a production-only dependency venv, no browser API interception and no real provider network.60 RSS/CPU samples over181 seconds show no extra transmissions, three deduplicated read jobs and no obvious short-term memory/CPU runaway. This is not long-term host reliability.

Fresh pip audit and production npm audit return zero known findings. Full npm audit still reports five high dev-tool entries for the existing lint/braces chain; BUG_AUDIT.md classifies reachability. No blind major upgrades. Runtime-only lock/image exclude pytest and fixtures. Clean frontend asset scan found no configured private/fake secret matches; source/private .env never enters build context. Safe defaults/production startup validation, request/operation identifiers and logger-handler traceback filtering are regression-tested.

500-row PG read timing: median70.67ms and501 queries; private runtime median6.65ms/18 queries. Bounded N+1 is P2 for the current46-record personal workload.500-company Chromium production-build campaign measured135–343ms to ready, CLS~0.00205, no observed long tasks and one read per resource; local/unthrottled/intercepted API, not hosted Lighthouse scoring. No speculative index/UI redesign.

## Open gates

**FW-026 P1 (historical, resolved by Package6A):** read-only actual installed schema/count/width inventory found one State key exceeding100. SQLite permits it, frozen PostgreSQL schema does not. The strict transfer refuses oversized values before writes. Passing a compatible sanitized fixture is not proof the actual installation can cut over. Needs a versioned lossless identifier/schema migration plus exact-history rehearsal; no truncation/guessing/frozen migration rewrite was performed.

Docker CLI/daemon is absent. Python3.13-slim/Node22-alpine/postgres17-alpine images and their actual runtime remain unbuilt/unrun. Native production-only proof does not clear this declared deployment gate; CI image/browser/PG17-tool checks are source changes only, not a remotely executed pass. Intended hosted private TLS/certificate/proxy/network/callback remains unverified; the isolated CA is not a hosted certificate.

**NOT VERIFIED LIVE:** no authorized disposable encrypted Google connection existed for this candidate. Unchanged installed plaintext credentials were deliberately not reused. Real OAuth refresh/identity/consent/reconnect, own-account draft/self-test, RFC retention, actual Sent/thread/history require a separately authorized safe account test. Mock acceptance does not prove recipient inbox placement. No company emails, purchases or real OAuth changes occurred.

## Reproduce locally / later staging

- `python scripts/source_manifest.py verify`; source-only bundle requires a clean committed manifest. Final bundle/check evidence is in verification.json. Test artifacts are in the repository; source-only bundle intentionally omits runtime data/private keys.
- `FIELDWORK_DISPOSABLE_POSTGRES_URL=<isolated PG17 URL> <clean-python> scripts/module6_check.py`. The native harness currently expects test tool paths under `/private/tmp/fieldwork-module6`; provision the clean venv/PG17 tools first or parameterize only the test paths for another host. Never substitute the live DB.
- Clean frontend: `npm ci --ignore-scripts`, `npm run lint`, `npm run typecheck`, `npm run format:check`, `npm run build`; install Playwright Chromium/WebKit/Firefox and run `npx playwright test`. Browser artifact directory is FIELDWORK_BROWSER_ARTIFACT_DIR; Playwright cache may use PLAYWRIGHT_BROWSERS_PATH.
- `<runtime-only-python> scripts/module6_e2e.py`: hard-fenced disposable named DBs on loopback55436, fake student@example.com account and ephemeral CA; fixed QA ports only. It resets those dedicated temporary DBs. Do not port it to real recipients/credentials or turn it into a runtime fixture endpoint. Production-only bootstrap stays in backend/tests, outside the packaged app/Docker.
- `scripts/module6_frontend_perf.py`: production standalone timing with fictional intercepted API. Backend timing methodology/measurements are recorded in performance-backend.json/log (five500-row and five private-runtime samples, query-event counts).
- `python scripts/module6_preserve.py`: read-only installed before/after comparison, never updates the baseline. All production mutation flags stay false.

RUNBOOK.md, RELEASE_CHECKLIST.md, DEPLOYMENT.md and MIGRATION_PLAN.md define later exact retirement/backup/staging/rollback/activation ordering. Module6 gives no permission to activate any of it.

## Package6A superseding migration evidence

FW-026 is RESOLVED in canonical head006: exact111-character historical self-test identity/JSON/provenance survives transactional001→006 import and full-record SQLite/PG17.11 backup/restore. Installed read-only preflight passes with no source/DB/credential/service/pause changes. See ../package6a/verification.json and README.md. Original Module6 build/UI/E2E/test results above remain historical005 evidence; no such suite was rerun for this narrow package. All other open release gates remain; no Package6B or production activation.

## Package6B superseding container evidence

The previous Docker absence/native-only gap is superseded by ../package6b/verification.json: actual Linux ARM64/Python3.13/Node22/PG17 production images pass the runtime-container gate, including private networking, runtime secrets/layer scans, separate processes, fake-provider E2E, restart and full-record persistence/backup/restore. Original Module6 evidence remains historical. Intended hosted/live Google/activation gates remain, production unchanged, Package6C not begun.
