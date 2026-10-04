# Fieldwork phase handoff

Phase 0 complete after baseline evidence and skill validation are recorded. **Do not start Phase 1 in this task.** The supplied attachment defines Phase 0 only; the following 1–6 sequence is a proposed handoff, subject to the user's subsequent phase prompts.

| Phase | Focus | Entry conditions | Exit conditions |
|---|---|---|---|
| 1 | Source reconciliation and architecture | Read map, decisions, baseline, drift hashes and P1 s; preserve active DB/receipts/credentials/pause; determine personal-first release boundary. | Runtime behavior reconciled into versioned source; provider/service boundaries and explicit state machines defined; single policy/attempt ledger designed and tested; migration/deploy plan; FW-001 resolved. |
| 2 | Security, accounts and persistence | Phase 1 source and ownership decision accepted; disposable DB available. | OAuth/secret storage and revocation flow; tested auth/ownership for chosen scope; ingress/rate limits; privacy lifecycle; safe migrations/backups; dependencies reviewed/patched; no unresolved applicable P0. |
| 3 | Product design and frontend foundation | Stable contracts/mode semantics from 1–2; product-design skill/reference loaded. | Final design system stored in skill reference; reusable accessible components, responsive task flows, typed API boundary; lint/typecheck/build and desktop/mobile/keyboard QA pass. |
| 4 | Discovery, evidence and bounded personalization | Provider contracts and permitted costs defined; secrets handled; UI foundation ready. | Cached bounded discovery/research, contact provenance and scoring; evidence-grounded writing/review with real profile; early stop/call limits; detector claims honest; no unsupported provider/subscription promises. |
| 5 | Unified delivery, responses and scheduling | Previous phases pass; delivery policy and provider mocks complete. | All send paths enforce authorization, caps, dedupe and uncertainty; durable jobs/follow-ups; fresh threaded/unthreaded reply checks; suppression/cancellation; Gmail/Outlook capabilities explicit; legacy contradictions retired; FW-002–005 addressed. |
| 6 | Production verification and release readiness | Core product coherent; applicable P0/P1 s fixed or explicitly excluded by accepted scope; disposable PostgreSQL/container environment available. | Meaningful unit/integration/provider/browser/E2E regressions; accessibility/visual QA; failure/crash/concurrency tests; restore/rollback and credential rotation verified; operational metrics; accurate deployment/runbook and release evidence. Any requested publish/deploy uses established authorization. |

## Next phase input

Use `AGENTS.md`, `.codex/skills/fieldwork-architecture/SKILL.md`, `docs/CODEBASE_MAP.md`, `docs/DECISIONS.md`, `BUG_AUDIT.md`, `docs/BASELINE.md`, and `docs/baseline/source-drift.json`. Read only relevant source/tests after that. Do not repeat the full audit or run historical campaign drivers.

Phase 1 is ready to begin engineering, **not ready for deployment**. Its first task is reconciling workspace/runtime drift. Baseline failures and skips are preserved as release gates, not hidden. The active user's recurring outreach pause remains authoritative.

## Module 1 handoff

Architecture and reconciliation implementation completed in canonical source, without live deployment. Module 2 should consume ARCHITECTURE.md provider/policy/ledger contracts and docs/MIGRATION_PLAN.md. FW-005/006 remain product work; PostgreSQL/container/security release gates remain. Do not begin Module 2 without the user request.

## Module 2 handoff

Personal operator authentication, encrypted Gmail lifecycle, ingress/rate controls, privacy and PostgreSQL semantics are implemented and tested in canonical source. No deployment/live OAuth/outreach occurred. Module 3 must preserve these API/provider/policy contracts; no frontend bearer fallback or unauthenticated local shortcut may return. Follow SECURITY.md, DATA_LIFECYCLE.md and MIGRATION_PLAN.md; this handoff does not start Module 3.

## Module 3 handoff

The final field-notebook design system, four flagship surfaces and consistent secondary views are implemented and browser-tested in canonical source. Shared Pydantic/generated TypeScript+runtime contracts, deduplicated resources and comprehensive frontend lint/browser CI resolve FW-009. See `docs/module3/README.md`, `critique.md` and verification artifacts. The installed runtime and pause remain preserved. Module 4 is ready to consume the stable prospect/evidence/review patterns, but has not started and requires the user's prompt.

## Module 4 handoff

Bounded company candidates/contact provenance, first-class current evidence, transparent research ranking, strict supported-fact/task generation and private UX are implemented in canonical source. Read docs/module4/README.md and its verification before Module 5. Continue using the same Job/Operation/ActionAttempt/Usage, generated contracts, resource client and notebook primitives. Delivery/reply/follow-up scheduling and permanent runtime rollout remain Module 5/later release work; this phase does not enable them or deploy source. The recurring pause and installed historical records remain authoritative.


## Module 5 handoff

Canonical delivery/ledger, one bounded Gmail scanner, durable reply cancellation, one reviewed168 h follow-up, deterministic scheduler/worker ownership/recovery/health and source service configuration are implemented and verified with isolated regressions and disposable PostgreSQL. See module5/README.md and verification.json. The installed source/schema/OAuth/pause remain unchanged; no company mail or paid calls occurred. Module 6 is ready for separately requested release verification, not automatically started or authorized to deploy. Follow the schema005 migration/release ordering and explicit provider limits; do not repeat the repository audit or replace this queue/policy design.

## Module6 verification outcome

Production verification performed in canonical source only. Fresh clean pins, maintained PG17.11,250 backend tests,60 Chromium/WebKit/Firefox browser tests, production-build/private TLS/actual-worker/fake-provider E2E, shared quota/rollover, forced-crash uncertainty, reply race, bounded soak and compatible migration/restore passed. Observed release defects were fixed and regression-covered. Actual installed State key width is incompatible with frozen PG schema and remains P1 FW-026. Docker/intended hosted TLS/live authorized Google gates remain unverified. Release is **NOT READY**; installed source/schema/credentials/services, receipts and recurring pause are preserved. No automatic next phase or campaign activation is authorized.

## Package6A verification outcome

Only FW-026 is resolved: versioned006 exact State widening, representative001→006 on SQLite/PG17.11, full-record backup/restore and installed read-only compatibility/preservation. Historical Module6 evidence remains dated005; package6a/verification.json is the current migration evidence. Container/hosted/live Gmail gates remain unverified and release NOT READY. No production migration, worker/service/automation/OAuth/pause/mail changes; Package6B has not started.

## Package6B verification outcome

Runtime-container PASS only: actual Linux ARM64 clean Python3.13/Node22 builds, PG17/schema006, paused startup, non-root/runtime-injected secrets/layer scans/private network, separate worker/scheduler,16 target regressions, container fake E2E/recovery, full-record backup/restore and one host-browser smoke. Temporary staging removed; installed source/schema001/credentials/services/pause unchanged. Intended hosted/live-provider/activation gates stay unverified. Package6C not begun.
