# Personal release checklist — NOT READY

Checked entries have executed evidence. Unchecked gates block cutover or need separately authorized provider/production action.

- [x] **Source:** baseline cc43165 manifest verified from an isolated committed archive (`module6/source-baseline.json`); Module6 changes classified in BUG_AUDIT.md; final committed manifest/bundle gate recorded in verification.json.
- [x] **Dependencies:** clean backend/test and separate runtime-only installs, pip check, clean frontend npm ci (`module6/*clean-install.log`, runtime-pip-check.log).
- [x] **Dependency audit:** fresh pip/production npm zero known; five high dev-tool entries classified as the existing non-runtime braces chain (`python-audit.json`, frontend-audit-*.json, BUG_AUDIT.md).
- [x] **Database:** maintained official-source PostgreSQL17.11/checksum, fresh/forward005, parity, constraints/indexes, independent claims/locks/quota/reply races (`runtime-environment.json`, backend-tests.log).
- [x] **Compatible migration rehearsal:** sanitized installed schema001 shape backed up, exact typed SQLite→PG transfer,005 upgrade, private backup/mutation/restore, duplicate refusal/failure rollback (`migration-rehearsal.json`, test_release_migration.py, test_release.py).
- [x] **Actual installed migration compatibility (Package6A):** schema006 retains the111-character self-test identity/value/provenance;001→006 SQLite/PG17.11 and full-record backup/restore pass. Installed read-only preflight recognizes one safely migratable key; no production migration (`package6a/verification.json`, installed-migration-preflight.json).
- [x] **Backup/restore:** actual disposable PG17 dump/restore preserves pause, receipts/unknowns, jobs, suppression and integration metadata; private mode0600 and source unchanged (migration-rehearsal.json).
- [x] **Rollback:** concrete pre-attempt backup+compatible-source restore and post-attempt forward repair; restore fences/credentials/privacy covered (RUNBOOK.md, BACKUP_RESTORE.md, security/runtime tests).
- [x] **Security/config:** private sessions/origin/CSRF/host/body/rate/ownership/SSRF/prompt scope, startup/schema and safe defaults; allowlisted IDs/traceback redaction tests (backend-tests.log, E2E and BUG_AUDIT.md).
- [x] **OAuth/Gmail live (Package6D):** PASS. Dedicated OAuth/state/PKCE/identity/encrypted storage/natural refresh, exact unsent draft, one A-to-B self-test, Gmail IDs/SENT/reconciliation replay, B reply/deduplication/cancellation, incremental sync/restart and safe disconnect/reconnect verified live. Final Gmail connected; see package6d/verification.json. Existing personal production OAuth is unchanged.
- [x] **Worker:** actual process, SIGTERM/SIGINT/restart/stale lease/duplicate leader tests; fake-provider forced termination/no resend;181-second60-sample bounded soak (`e2e-results.json`, backend-tests.log).
- [x] **Scheduler:** persistent dedupe/one current bucket/offline no-catchup/current pause/rollover tests (test_runtime.py, e2e-results.json).
- [x] **Delivery:** real HTTPS→production Next proxy→authenticated API→actual worker→PG17→fake provider; explicit approval, initial/follow-up, receipt/replay/unknown/own-test/shared cap (e2e-results.json).
- [x] **Replies:** threaded/unthreaded correlation, fresh preflight, cancellation/suppression/race, bounded cursor recovery (backend-tests.log, e2e-results.json).
- [x] **Follow-ups:**168-hour controlled clock, current contact/research/new proposal, original subject/thread, separate review and replay hold (e2e-results.json, test_release.py).
- [x] **Frontend:** clean lint/typecheck/format/production build (frontend-*.log, runtime-environment.json build ID).
- [x] **Accessibility/browsers:**20 tests per Chromium/WebKit/Firefox,0 skips/flakes; axe at four sizes, keyboard/dialog/labels/locked states; inspected campaign laptop and review mobile screenshots (`browsers/browser-results.json`). This is not WCAG or physical Safari certification.
- [x] **Performance:** measured500-row PG read and500-company production-built Chromium campaign, low observed layout shift/no long tasks; bounded N+1 recorded asP2 (performance-*.json).
- [x] **Observability:** independent private worker/scheduler/schema/sync/Gmail/unknown/job/shared daily cap/bounce-stop visibility; request/operation IDs, sanitized failures and health tests (backend-tests.log, E2E).
- [x] **Privacy:** disconnect/local credential clear, resume/personal deletion/export, retention preserves receipts and suppression; disposable encryption/session rotation tests (test_security.py/full suite).
- [x] **Documentation:** exact current architecture/processes/TLS host handling/secrets/migration/rollback/retirement/provider limits (RUNBOOK.md, DEPLOYMENT.md, PROVIDER_CAPABILITIES.md).
- [x] **Preservation:** before/after read-only comparison; no deployment/live DB/OAuth/service/automation/mail changes (`preservation.json`).
- [x] **Containers (Package6B):** actual Linux ARM64 Docker Python3.13.16/Node22.23.3/PG17.11 clean builds; locked runtime/no test packages, non-root app users, injected-secrets/layer scan, private networking, separate worker/scheduler, fake-provider E2E, duplicate fences, graceful shutdown/restarts and exact DB persistence/backup/restore pass (`package6b/verification.json`). Intended hosted deployment remains separate.
- [x] **Hosted TLS/private staging (Package6C):** actual Railway trusted TLS/hostname/HTTP redirect, safe forwarded/Host behavior, session/login/expiry/revocation, CSRF/origin/CORS, public headers, private infrastructure, Chromium/WebKit/Firefox, safe profile mutation, log/asset secret review and worker restart/leadership pass on schema006/PG17.11. No live Google exchange; see package6c/verification.json.
- [ ] **Production activation:** later explicit rollout authorization; retire old external sender first, verified backup/migration/worker health and own-account canary while paused. Later recurring activation is separate. Nothing activated here.

Package6A supersedes only the migration-width gate: canonical head006 and startup checks are verified with the isolated backend suite. Module6 browser/HTTP E2E proofs above remain historical005 evidence; no UI/container/hosted/live-provider suites were rerun or claimed for006. Installed schema001, source, credential/service definitions and pause compare unchanged. Other unchecked gates remained open at Package6A; Package6B now closes only the container gate, as recorded below.

Package6B supersedes the container gap:16 targeted Linux regressions and actual container fake-provider E2E/recovery, plus one browser-to-Linux smoke pass. Full historical design/browser suites were not rerun. Original Module6 native evidence remains historical; package6b/verification.json supplies schema006 container proof. Source/source-manifest and preservation checks pass. Temporary staging is removed; actual production migration/activation, hosted TLS/private staging and live Gmail remain unchecked. Package6C attempted hosting access discovery and is BLOCKED; no hosted runtime/security/browser result is claimed.

## Railway staging setup update

Isolated staging provisioning is READY; see [setup evidence](railway-staging/README.md) and [smoke results](railway-staging/verification.json). Stable origin is https://fieldwork-staging.up.railway.app; private API/worker/PG17.11 run schema006 with communication paused and no real provider keys. The historical Package6C access blocker is superseded. Its full hosted verification gate remains unchecked; production activation and live Google remain separate. Do not enable outreach or use production data/secrets in staging.

## Package6C superseding evidence

The previous access blocker is resolved and actual hosted gate PASS. Package6D is ready to begin only on separate user request; real providers remain disconnected. Historical Module6 native/container evidence remains unchanged; no production cutover, personal DB/OAuth/sender/service/pause change occurred.

## Package6D superseding evidence

Live Google gate PASS on the existing dedicated staging client and designated A/B identities.167 targeted regressions pass, privacy/source/preservation checks pass, and all four staging services are online on schema006 with Gmail connected and recurring paused. Live synthetic communication totals remain one unsent draft, one initial self-test and one owner reply, with no duplicate transmissions/events or company sends. Package6E is READY for a separate request and remains unstarted; production activation/cutover remains unchecked.
