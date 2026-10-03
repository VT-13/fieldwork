# Phase 0 baseline — October 3, 2026

## Scope and safety

Both the workspace and newer installed runtime were copied into sanitized temporary directories. `.env*`, databases, logs, receipt/data directories, dependencies and generated output were excluded. Provider credentials were empty, polling disabled, HOME redirected to a temporary location, SQLite disposable, and production web/API bound to separate loopback ports. No worker, historical batch, mailbox sync, live send or paid research/generation call was run. The final read-only personal CRM check found `outreach_policy.enabled=false` and zero unresolved sends.

Development files were not deployed. Local Git was initialized without a commit/remote. Skills/docs/isolated audit scripts and ignore patterns are the Phase 0 changes. Next phases must reconcile the 27 source differences in `baseline/source-drift.json`.

## Actual results

| Check | Workspace | Runtime | Evidence / limits |
|---|---|---|---|
| Backend dependency consistency | Pass | Pass | `python -m pip check`; existing installed venv reused |
| Backend lock install resolution | Pass | Pass | `pip install --dry-run --no-index -r requirements.lock.txt`; not a fresh environment install |
| Backend pytest | 48 passed, 1 skipped | 73 passed, 1 skipped | `*-pytest-corrected.log`; PostgreSQL requires disposable URL |
| SQLite migration | Pass | Pass | `python -m alembic upgrade head`; initial schema only |
| Python compile | Pass | Pass | `python -m compileall -q app scripts` |
| Frontend install | Pass | Pass | `npm ci --ignore-scripts --no-audit --no-fund` in snapshots; scripts deliberately disabled |
| Lint | Missing command; exit 1 | Missing command; exit 1 | `npm run lint`; no configured backend lint/typecheck either |
| Typecheck | Pass | Pass | `npm run typecheck` |
| Production build | Pass | Pass | `npm run build`; does not prove provider functionality |
| Frontend dependency audit | Fail; 1 critical advisory | Fail; 1 critical advisory | `npm audit --omit=dev --json`; Next 16.3.5 |
| Python dependency audit | Fail | Same lockfile | pip-audit 2.10.1: seven cryptography records, four unique IDs; no app exploitability assertion |
| Local API/web startup | Pass | Pass | Uvicorn and production `next start`, isolated ports 18010/13010 and 18011/13011 |
| Browser smoke | Pass | Pass | Six views visited; no JS page errors; unauthenticated API 401 and cross-origin mutation 403 |
| Visual observation | Screenshots saved | Screenshots inspected | 1440px desktop and 390px mobile; mobile document width 390px in both; no horizontal overflow on tested desk |
| Project skill validation | Six pass | N/A | Bundled `quick_validate.py`, `skill-validation.log` |
| Extra uncertainty regression probe | N/A | Expected safety assertion fails | `runtime-global-uncertainty-probe.log`: guard did not block while an unknown send existed |
| PostgreSQL / Docker / hosted release | Not run | Not run | No disposable PostgreSQL URL or Docker daemon/CLI; no deployment requested |
| Live Gmail/Outlook / detector contracts | Not run | Not run | Outside this audit's mutation scope; previous Gmail repair is not provider E2E for this phase |

First pytest runs failed because the audit harness supplied a nondefault fake API key while the existing API test hard-codes the development key. Correcting the harness key produced the passing counts above; original logs are retained. This was not an application bug fix.

First browser run completed workspace checks but timed out on runtime because its initial view is Outreach rather than the email desk. The runner now explicitly navigates to the desk; both pass. `next start` warns that standalone builds should run `node .next/standalone/server.js`; the tested server nevertheless served successfully. The existing Dockerfile uses the standalone entrypoint. No production launch command was changed.

Browser external requests were blocked, including Google Fonts; screenshots show fallback fonts and do not certify external-font layout. The runtime desktop/mobile screenshots were visually inspected: forms and actions fit, mobile sidebar collapses to icons, and vertical reading length is substantial. This is a smoke/visual baseline, not a complete WCAG, keyboard, E2E or performance audit.

## Dependency evidence

The verified [Next.js advisory](https://github.com/advisories/GHSA-vcvr-r3jv-pc5j) covers attacker-controlled SVG content/styles in Node `next/og` ImageResponse; 16.3.6 is patched. Search found no application ImageResponse/next/og imports in either source tree. Record the affected pin and failing dependency gate without calling the current app remotely exploitable.

`baseline/python-audit.json` is the raw pinned-requirements response; `python-audit-summary.json` removes descriptions and exposes duplicate records. cryptography is pinned at 46.0.7 and constrained below 47 in pyproject. Remediation requires reviewing applicability and the bound, not blindly substituting a version during baseline. Audits do not verify application security.

## Reproduce

From this repository root, using the existing installed Python environment:

```sh
python3 scripts/phase0_baseline.py
python3 scripts/phase0_browser.py
```

The first script prints exact commands and saves `baseline/results.json`/logs; it runs four independent checks concurrently, without agents. The browser runner requires the installed Python Playwright module and Google Chrome executable. Snapshot paths are transient; source/logs/hashes/screenshots here are durable. Rerunning replaces baseline artifacts; preserve them separately when comparing a later phase.

Security tooling was installed into `/tmp/fieldwork-phase0-security-venv`, leaving production dependencies unchanged:

```sh
/tmp/fieldwork-phase0-security-venv/bin/pip-audit -r backend/requirements.lock.txt --no-deps --disable-pip --format json --output docs/baseline/python-audit.json
```

PyYAML was added only to that temporary venv to run the skill validator; its first invocation lacked that dependency, then all six validations passed. This tooling directory is disposable, not an application requirement.

## Remaining verification gaps

Fresh backend install, PostgreSQL behavior, container builds, multi-process send races, full provider contracts, comprehensive accessibility and browser regressions, rollback/restore and hosted deployment remain explicit next-phase work. Existing unit tests mostly exercise mocks and SQLite. No command that was skipped/missing is counted as passing.
