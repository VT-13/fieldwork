# Package6E final release verification — READY

Personal-first, single operator, private installation. This decision permits a separately authorized production cutover package to begin; it does not authorize deployment, migration, production OAuth, worker activation or communication. The live personal schema001 database, services, credentials and recurring pause remain unchanged.

Canonical baseline was `66f4fbb`, clean and matching origin/main. Final verified application source is `b02457c`; subsequent changes are release documentation/evidence only. Canonical and Railway staging schema are006. Actual deployed API/worker file hashes match the verified application source. Frontend source is unchanged from the Node22 Linux/hosted evidence; staging runs Node22.23.3, Python3.13.16 and PostgreSQL17.11. Four staging services remain online and communication paused.

## Current executed gates

The initial full regression passed282 tests. A concrete accepted-RFC assumption discovered in the normal company path was fixed narrowly: immutable accepted API/thread receipts and exact full SENT envelope permit provider RFC normalization, while preserving the reserved identifier and holding ambiguous/unknown evidence without resend. Nine new regression cases and210 affected tests pass. The final full backend suite passes291 tests, zero failures/skips, with two existing upstream TestClient deprecation warnings. Contracts, fixture check and Ruff pass. No separate backend formatter/typechecker is configured.

Clean frontend npm ci, lint, TypeScript, format check and production build pass on local Node24.18.0. The unchanged production frontend retains actual Linux Node22 build evidence from6B/6C; current deployed runtime is22.23.3. Focused real hosted Chromium smoke passes login/reload/dashboard/campaign/prospect/detail/review/settings/Gmail integration/logout at desktop/mobile sizes, with zero page/console/critical API errors or mixed content and no form/send mutation. This does not claim a new exhaustive cross-browser suite.

Current trusted TLS, authenticated private routes, Secure/HttpOnly/SameSite cookies, hostile-Origin rejection, logout invalidation, untrusted Host rejection and canonical redirect pass. Railway resolved configuration still has debug disabled, safe manual/dry-run defaults, recurring mail polling/auto approval/paid APIs disabled, private API/worker/PG with no public database proxy, and only public frontend configuration in browser-facing variables. Actual runtime secrets are absent from tracked source, sampled service logs and fetched browser assets. Runtime Python/npm audits report zero known vulnerabilities; five existing high dev-tool entries are the braces lint chain, excluded from runtime and using repository-controlled patterns, classified P2.

Gmail6D evidence is retained without repeating draft/send/reply/consent. Identity/authentication/current history cursor pass; bounded incremental read sync is fresh and deduplicated. The new shared RFC helper passed against the existing accepted test message using reads only. Totals remain one unsent draft, one controlled test send and one owner reply; no extra transmission, company send or duplicate reply Event. Worker/scheduler/heartbeat and duplicate-leader rejection pass; zero queued communication or unknown retry activity.

Final PG17 regression revalidates fresh/forward001→006 migrations, constraints/concurrency and full-record private backup/restore. Prior installed read-only preflight, actual Linux restart/persistence and hosted restart/cursor evidence remain valid. Affected delivery/reconciliation/reply/worker/recovery suites were rerun after the narrow fix; no full soak or live-company test was repeated.

## Executed commands and scope

All test commands ran in a sanitized isolated source copy with empty provider credentials, fake HOME and a disposable loopback PG17 target. Canonical checks, exact command arrays and exit statuses are in backend-checks.json and frontend-checks.json:

```sh
python scripts/frontend_contracts.py --check
python scripts/module3_fixture.py --check
python -m pytest -q -ra
python -m ruff check app scripts tests
npm ci --ignore-scripts
npm run lint
npm run typecheck
npm run format:check
npm run build
pip-audit -r backend/requirements.runtime.lock.txt --no-deps --disable-pip --format json
npm audit --omit=dev --json
npm audit --json
python scripts/source_manifest.py verify
```

Hosted smoke used the existing6C Playwright helper, limited to Chromium, with actual HTTPS/API and normal certificate verification. Railway reads used `railway environment config -e staging --json`, `railway variable list -s <service> -e staging --json`, and owner-only SSH probes. Secret-bearing outputs were captured in memory/private files and never committed or printed. `railway ssh -s worker -e staging -i <private-key> -- python -m app.worker --health` passes after bounded read-only Gmail sync. Only the existing staging API/worker were redeployed from source for the narrow fix; no frontend/production/DB/OAuth project was created.

## Decision and separate cutover

No P0/P1 remains. FW-026 migration and FW-030 RFC handling are resolved with executed evidence. P2: bounded CRM N+1 and existing dev lint advisories. P3: upstream test-client deprecation warnings. These do not block the current personal-first release. A live company send is deliberately unverified, not silently claimed by synthetic validation.

DEPLOYMENT.md and RUNBOOK.md now identify the separate production environment/private PG target/stable HTTPS origin/runtime secrets/dedicated OAuth, sender retirement, writer freeze, private backup and restore rehearsal, schema006 transfer, paused worker health/smoke and receipt-preserving rollback. Production identifiers must be concretely selected and authorized in that later package. Recurring activation is separately authorized afterward.

Fieldwork personal-first release is READY for a separate production cutover package. No production cutover was performed.
