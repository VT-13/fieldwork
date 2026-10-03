# Fieldwork phase handoff

Phase 0 complete after baseline evidence and skill validation are recorded. **Do not start Phase 1 in this task.** The supplied attachment defines Phase 0 only; the following 1–6 sequence is a proposed handoff, subject to the user's subsequent phase prompts.

| Phase | Focus | Entry conditions | Exit conditions |
|---|---|---|---|
| 1 | Source reconciliation and architecture | Read map, decisions, baseline, drift hashes and P1s; preserve active DB/receipts/credentials/pause; determine personal-first release boundary. | Runtime behavior reconciled into versioned source; provider/service boundaries and explicit state machines defined; single policy/attempt ledger designed and tested; migration/deploy plan; FW-001 resolved. |
| 2 | Security, accounts and persistence | Phase 1 source and ownership decision accepted; disposable DB available. | OAuth/secret storage and revocation flow; tested auth/ownership for chosen scope; ingress/rate limits; privacy lifecycle; safe migrations/backups; dependencies reviewed/patched; no unresolved applicable P0. |
| 3 | Product design and frontend foundation | Stable contracts/mode semantics from 1–2; product-design skill/reference loaded. | Final design system stored in skill reference; reusable accessible components, responsive task flows, typed API boundary; lint/typecheck/build and desktop/mobile/keyboard QA pass. |
| 4 | Discovery, evidence and bounded personalization | Provider contracts and permitted costs defined; secrets handled; UI foundation ready. | Cached bounded discovery/research, contact provenance and scoring; evidence-grounded writing/review with real profile; early stop/call limits; detector claims honest; no unsupported provider/subscription promises. |
| 5 | Unified delivery, responses and scheduling | Previous phases pass; delivery policy and provider mocks complete. | All send paths enforce authorization, caps, dedupe and uncertainty; durable jobs/follow-ups; fresh threaded/unthreaded reply checks; suppression/cancellation; Gmail/Outlook capabilities explicit; legacy contradictions retired; FW-002–005 addressed. |
| 6 | Production verification and release readiness | Core product coherent; applicable P0/P1s fixed or explicitly excluded by accepted scope; disposable PostgreSQL/container environment available. | Meaningful unit/integration/provider/browser/E2E regressions; accessibility/visual QA; failure/crash/concurrency tests; restore/rollback and credential rotation verified; operational metrics; accurate deployment/runbook and release evidence. Any requested publish/deploy uses established authorization. |

## Next phase input

Use `AGENTS.md`, `.codex/skills/fieldwork-architecture/SKILL.md`, `docs/CODEBASE_MAP.md`, `docs/DECISIONS.md`, `BUG_AUDIT.md`, `docs/BASELINE.md`, and `docs/baseline/source-drift.json`. Read only relevant source/tests after that. Do not repeat the full audit or run historical campaign drivers.

Phase 1 is ready to begin engineering, **not ready for deployment**. Its first task is reconciling workspace/runtime drift. Baseline failures and skips are preserved as release gates, not hidden. The active user's recurring outreach pause remains authoritative.

## Module 1 handoff

Architecture and reconciliation implementation completed in canonical source, without live deployment. Module 2 should consume ARCHITECTURE.md provider/policy/ledger contracts and docs/MIGRATION_PLAN.md. FW-005/006 remain product work; PostgreSQL/container/security release gates remain. Do not begin Module 2 without the user request.

## Module 2 handoff

Personal operator authentication, encrypted Gmail lifecycle, ingress/rate controls, privacy and PostgreSQL semantics are implemented and tested in canonical source. No deployment/live OAuth/outreach occurred. Module3 must preserve these API/provider/policy contracts; no frontend bearer fallback or unauthenticated local shortcut may return. Follow SECURITY.md, DATA_LIFECYCLE.md and MIGRATION_PLAN.md; this handoff does not start Module3.
