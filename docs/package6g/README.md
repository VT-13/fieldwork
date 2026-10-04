# Package6G — explicit initial-message Autopilot

PASS in canonical source; Autopilot defaults OFF. Existing Railway staging recurring outreach and Package6F production cutover remain PAUSED. Exact candidate identity is the Package6G commit on VT-13/fieldwork main. b68a84f remains the historical Package6E verified release. This new candidate is ready for focused release re-verification before any separately requested6F resume, not for automatic production activation.

## Implementation

Existing State JSON stores explicit Autopilot policy and a revision. Schema remains006; no007 DDL or migration-time rewrite is needed. Missing fields mean OFF. Authenticated same-origin precheck/confirmation checks verified profile/resume, matching Gmail, configured discovery/research/generation/contact capabilities, authorized bounded provider spending, reply polling, schema/worker/scheduler and unresolved delivery. Provider configuration is not a guarantee of live provider health. Activation does not resume recurring outreach.

Scheduler admission uses the remaining configured1–25 introductions and shared25 attempts, a min(50,2×remaining) inventory buffer including review drafts and active work, three active intelligence pipelines maximum, one acceptance/pipeline per tick, and the existing daily discovery dedupe/cooldown. Source-confirmed candidates require current name/domain/location/distance observations. Terminal failures never automatically retry. Weak evidence/contact/location goes to review; targets never justify invented facts or extra API calls.

The canonical worker researches, finds/verifies contacts, generates and independently reviews. Initial auto-approval requires current immutable generation/review hashes, verified profile facts, correct current public contact provenance, research/evidence, explicit official allowed-city statement, all quality booleans and score>80, no responses/suppression/uncertainty, valid content and opt-out language. Domain transitions preserve approval audit metadata without copying message bodies to logs. Edited/returned drafts require explicit regeneration. Disable/reconfiguration invalidates automatic approvals and fences queued/running work; profile/account/discovery changes require deliberate reactivation.

The existing scheduler only creates send intent. policy.company rechecks automatic authority and all existing reply/bounce/pause/quota/spacing rules at reservation. delivery.py remains the sole transmitter. Introductions, follow-ups, self-tests and uncertain attempts share25 daily units; no burst, account rotation or new send path. Bounded reply sync, fresh Gmail conversation checks, immutable receipts, unknown reconciliation and suppression are preserved. No automatic inbound replies.

Follow-up automatic approval is intentionally unsupported and rejected. Follow-ups remain manual-review gated, one maximum, at least168 hours, original thread/subject, current sources and distinct new value. The Campaign UI clearly exposes both independent modes, metrics, provider/budget state, prerequisites, confirmation, disable and emergency pause. It validates server response contracts, preserves unsaved input and never optimistically reports successful activation/pause.

## Executed verification

- Full Python3.13 backend:360 passed,0 failed,0 skipped;69 added Autopilot cases. Ruff, generated contracts and generated fixtures pass. Two upstream TestClient deprecation warnings remain.
- Disposable PostgreSQL17.11: fresh/repeat006 OFF preservation, existing forward migrations, transactional representative SQLite001→006 lossless transfer, full-record private backup/restore, concurrent ledger/job/quota/reply reservations and failure rollback pass in the full suite. No installed data is used as a test fixture.
- Actual deterministic fake-provider E2E: scheduler discovery → sourced acceptance → worker research/contact verification → grounded generation/review → automatic domain approval → canonical scheduled fake send/receipt → reply cancellation. Duplicate ticks/replay do not duplicate work/transmission. New tests also cover post-approval reply/ack/bounce/opt-out/profile/discovery changes, target boundaries, shared quota, backpressure, budget stop, activation/auth/CSRF/confirmation and inactive-job fencing. Existing follow-up/crash/reconciliation/worker-leader regressions are rerun.
- Clean frontend npm ci, lint/typecheck/format/production build pass. Native Node24.18.0 is the actual test runtime; production remains declared Node22. Historical Linux/container evidence is retained, not claimed as a fresh6G container pass.
-75 Chromium/WebKit/Firefox cases pass with0 failures/skips/flakes. Axe WCAG A/AA, keyboard focus/confirmation, server failure states,1–25 target bounds, manual/ON/OFF/pause controls and1280/768/390 responsiveness pass. Campaign laptop/mobile screenshots are visually inspected. This is automated accessibility coverage, not WCAG certification or physical Safari certification.
- Read-only existing staging checks: schema006, healthy worker/scheduler, Gmail connection still connected, AutopilotOFF, recurringPAUSED, safe manual/dry-run flags, paid provider keys absent, zero company transmissions. The historical6D self-test/reply counts remain1/1. No mailbox provider calls in the6G staging state check. TLS/session/CSRF/private networking and source secret checks pass; staging was not activated. These read-only checks describe the pre-publication hosted runtime; pushing main may trigger the existing staging Git integration. That does not certify the new candidate on hosted runtime or authorize outreach.
- Installed read-only preservation matches the private6F checkpoint for source, DB/policy/counts/schema, credentials and service definitions. Production project, live DB, OAuth, worker and recurring pause are untouched. Company/prospect outreach in6G:0.

Initial browser failures exposed an async dialog-trigger focus bug plus an ambiguous test status selector. Explicit trigger-ref restoration and named status fixed both without disabling lint/a11y rules. A later visual check applied the existing primary-button/buttons classes. The final review also exposed that a blocked-approval reason was stored but not visible in the review UI; an explicit response-contract field, review status and browser regression now expose the required action. Delivery-hold metrics also count a company represented in both legacy outreach and the ledger once, retaining separate uncertain self-tests. All final gates below are rerun on final source. One extra HTTP-auth test initially used the intentionally weak development fixture key; its isolated fixture now supplies a separate strong fictional key. No runtime configuration check was weakened.

## Actual commands and safe reproduction

The ephemeral runners used repository `scripts/module1_check.py`'s `isolated()` to copy only source to a temporary root, strip private/provider credentials, disable sending/polling, and give tests disposable DATA_DIRECTORY and HOME. Python3.13 test venv was `/private/tmp/fieldwork-module6/venv/bin/python`; PG17 tools were `/private/tmp/fieldwork-module6/pg17/install/bin`. Test PostgreSQL was an explicitly disposable loopback cluster at127.0.0.1:55436, database fieldwork_6d_tests. Never substitute the personal/staging/production database for that URL.

Executed wrappers:

```
python3 /private/tmp/fieldwork-package6g/backend_check.py
python3 /private/tmp/fieldwork-package6g/frontend_check.py
python3 /private/tmp/fieldwork-package6g/browser_check.py
```

They executed these repository commands inside the sanitized copies:

```
python scripts/frontend_contracts.py --check
python scripts/module3_fixture.py --check
# backend/ with disposable TEST_POSTGRES_URL and FIELDWORK_TEST_PG_TOOLS;
# FIELDWORK_RELEASE_MIGRATION_REPORT points to this package's rehearsal artifact.
python -m pytest -q -ra
python -m ruff check app scripts tests
# frontend/ with empty secrets and fake browser API routes
npm ci --ignore-scripts
npm run lint
npm run typecheck
npm run format:check
npm run build
PLAYWRIGHT_BROWSERS_PATH=/private/tmp/fieldwork-module6/browsers npm run test:browser
```

Use a fresh isolated copy/environment when reproducing; tests set only fictional provider credentials at mocked seams. Check backend-checks.json, frontend-checks.json, browsers/browser-results.json and the corresponding logs for exact paths/elapsed times. Existing test_release_migration.py invokes real disposable PG17 backup/restore; migration-rehearsal.json records exact preservation results. Read-only staging used Railway SSH to the existing staging worker with explicit staging environment ID, querying aggregate State/ledger counts only; source secrets were scanned in memory and never printed. Read-only installed preservation compares scripts/module6_preserve.capture() with the private saved6F baseline and publishes only equality/safety booleans.

Final source integrity:

```
python scripts/source_manifest.py create
python scripts/source_manifest.py verify
python scripts/source_manifest.py bundle --output /private/tmp/fieldwork-package6g/release-source.tar.gz
```

Manifest generation includes tracked new source/docs deliberately; bundle verification is performed only after committing. No database/credentials are packaged.

## Remaining release scope

No applicable source P0/P1 blocker remains. Existing P2: FW-028 bounded N+1 and the documented five dev-tool advisory entries; P3: two upstream TestClient deprecations. Follow-up auto-approval remains explicitly manual. Focused new-candidate Linux/Node22/hosted staging verification must occur while paused before a separately requested6F resume. Railway production resource limits remain the intentionally paused6F checkpoint. Do not provision production, migrate live data, activate recurring or send real prospects under this package.
