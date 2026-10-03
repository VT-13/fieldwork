# Module 3 — frontend verification and handoff

This directory records implementation and isolated QA only. Nothing was deployed, no real email was sent, and the installed runtime remains paused and unchanged. All browser screenshots use explicit fictional companies, public `.example` source URLs, and a QA profile. Demo company records do not contribute to production outcome metrics.

The visual identity is encoded in `.codex/skills/fieldwork-product-design/references/design-system.md`. `critique.md` records the first actual render and the required workflow refinement. The final four flagship screenshots exist at wide desktop, laptop, tablet and mobile widths.

## Reproduce

Backend dependencies: the repository lockfile plus pytest and ruff in a separate development virtual environment. Generate/check the contracts with `python scripts/frontend_contracts.py [--check]`; generate/check fictional browser fixtures with `python scripts/module3_fixture.py [--check]`. The shared state enum is independent of runtime imports; neither command imports application settings, opens the personal database, or contacts a provider.

In `frontend`: `npm ci --ignore-scripts`, `npm run lint`, `npm run typecheck`, `npm run format:check`, `npm run build`, then `npm run test:browser`. On this Mac, set `FIELDWORK_BROWSER_EXECUTABLE` to `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`; CI installs Playwright Chromium. Typecheck generates Next route types before tsc. Run typecheck and build sequentially because build replaces `.next/types`. The test server uses the standalone production output on localhost:13030. All private APIs are intercepted by fictional fixtures; external sending/connection/discovery operations fail closed in the fixture. This browser fixture is not an authorization test.

Authentication, private reads, database-authoritative pause, review edits/transitions, attempted-message immutability, PostgreSQL concurrency, OAuth and other backend regressions run separately in a sanitized snapshot through `scripts/module3_check.py`. Supply only `FIELDWORK_DISPOSABLE_POSTGRES_URL` pointing to an explicitly disposable database. The current Mac convenience runner uses the existing Module 2 test virtualenv/tool paths; use normal `python -m pytest -q -ra` with the locked dependencies on other hosts. No schema migration is needed for Module 3.

## Scope of the UI

URL parameters preserve navigation, selected prospect/message, campaign section, search, stage and sort. The resource cache deduplicates concurrent reads, polls campaign and visible pipeline/metrics/reply views every 30 seconds, skips polling in hidden tabs, and refreshes relevant resources after mutations. It contains no credentials. Page-local form state stays separate from server state; unsaved edits have navigation/unload protection.

Pydantic read contracts in `backend/app/ui_contracts.py` generate both TypeScript and runtime JSON Schema. Existing additional review, settings, metrics, Gmail-status and campaign fields are preserved. The client validates incoming records before using them. There is no public OpenAPI route. All existing cookie/origin/OAuth/send-policy boundaries remain server-side.

The two new review operations are narrow: edit an unattempted draft (clears prior review/approval), and reject/return-to-draft using existing transitions under the shared database lock. Approval also acquires that lock. Sent, sending, uncertain and attempted records are immutable through these operations. Editing does not claim that a fresh quality check has happened; it stays blocked for approval until the existing generation/review worker produces a quality-passed version. Implementing new generation capability belongs to its later module.

Recurring pause is always returned from `/campaign`, even without an active scoped batch. Pause/stop UI waits for the database response; it does not offer a resume toggle. Current batch membership uses actual outreach IDs, not company-stage guesses. Approval does not authorize delivery. Reply handling changes the local CRM attention flag without marking Gmail read or sending a reply.

## Tooling and limits

Inspected available official skills/tools: repo design/frontend skills, native browser control, local Playwright/Chrome, image generation, visualization and Sites. This existing Next.js project benefits from code-native styling and real browser renders; no raster asset or external design plugin was needed. Sites is not applicable to development in this existing project. Reference setup: [Next ESLint](https://nextjs.org/docs/app/api-reference/config/eslint), [Playwright accessibility](https://playwright.dev/docs/accessibility-testing).

Automated axe scans cover the configured WCAG A/AA rules and are supplemented by keyboard checks. They do not establish complete WCAG compliance or a full screen-reader audit. Chromium is tested; Safari/WebKit and real Google provider behavior are not claimed here. Lint uses the full Next core-web-vitals + TypeScript presets, with warnings rejected and hooks/unused variables/explicit `any` enforced; no meaningful rule is disabled.

## Recorded results

Final source: comprehensive lint (zero warnings), Next route typecheck, formatting and production build pass. Twelve Playwright tests pass, including 16 flagship viewport combinations and additional secondary-screen axe scans. Intentional HTTP 503 failures are injected in failure-path tests; successful screenshot flows report no page exceptions or horizontal document overflow. Node's NO_COLOR/FORCE_COLOR message is a test-runner terminal warning, not a browser error. Production dependency audit has zero known advisories; the upstream dev-only lint advisory is documented in BUG_AUDIT.md. Backend snapshot: 133 passed, no skips, two dependency deprecation warnings, including PostgreSQL concurrency and restore tests. Preservation hashes confirm installed source, recurring pause and historical record counts unchanged.
