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
- [ ] **OAuth/Gmail live:** NOT VERIFIED LIVE. No authorized disposable Google integration available; unchanged legacy plaintext authorization is not a new release test credential. Safe own-account consent/draft/test and actual RFC/Sent/history proof required before enabling supported Gmail operations.
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
- [ ] **Containers:** builds/runtime/env/health/nonroot/persistent storage must execute in Docker-enabled staging; source and native runtime proof are insufficient for declared Compose targets. CI checks added but not remotely run.
- [ ] **Hosted TLS/private staging:** intended trusted certificate, ingress/network/header/cookie/callback behavior still need verification. Ephemeral private test CA passed; no hosted endpoint supplied/deployed.
- [ ] **Production activation:** later explicit rollout authorization; retire old external sender first, verified backup/migration/worker health and own-account canary while paused. Later recurring activation is separate. Nothing activated here.

Package6A supersedes only the migration-width gate: canonical head006 and startup checks are verified with the isolated backend suite. Module6 browser/HTTP E2E proofs above remain historical005 evidence; no UI/container/hosted/live-provider suites were rerun or claimed for006. Installed schema001, source, credential/service definitions and pause compare unchanged. Other unchecked gates remain open; Package6B has not started.
