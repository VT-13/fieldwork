---
name: fieldwork-architecture
description: Design or change Fieldwork backend boundaries, persistence, provider interfaces, state transitions, jobs, scheduling, and deployment architecture.
---

Read `docs/CODEBASE_MAP.md` and `docs/DECISIONS.md`; resolve workspace/runtime drift before deployment. Prefer a modular monolith with explicit profile, prospecting, evidence, outreach, mailbox and outcome services. Introduce infrastructure only for demonstrated requirements.

Define provider interfaces around typed inputs/results/errors and inject mocks. Keep orchestration, deadlines, budgets, quotas, retry decisions and scheduling in deterministic application code. AI extracts or writes bounded evidence-backed content; it must not own the durable delivery ledger.

Express outreach/job state transitions explicitly. Reserve attempts before external sends; retain uncertain outcomes; reconcile without automatic resend. Make dedupe, global quota, stop conditions and ownership transactional across every send entry point. Emit idempotent domain events that cancel follow-ups on replies, opt-outs and bounces.

Separate service logic from FastAPI handlers and CLI adapters. Use schema validation and typed actionable errors; preserve migration history. Jobs need leases, bounded retries, crash recovery and observability. Machine-local locks alone are insufficient for multi-process/multi-host correctness. Record alternatives and consequences when changing architecture.
