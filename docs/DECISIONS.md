# Fieldwork decisions

## ADR 001 — Audit first; preserve live operation (accepted, Phase 0)

**Decision:** Phase 0 creates skills, evidence and plans; it does not refactor/deploy or send email. Baselines run in sanitized temporary snapshots.
**Reason:** The installed app holds real credentials and irreversible send history.
**Alternatives:** Test the installed services or rewrite first.
**Consequences:** Mocked tests cannot prove provider contracts. No live mailbox/provider mutation occurs during audit; pause and historical records remain authoritative.

## ADR 002 — Explicit source reconciliation (accepted)

**Decision:** This Git root is the development repository; the installed runtime is authoritative evidence for newer existing behavior. Keep both intact in Phase 0 and use the hash manifest to reconcile deliberately in Phase 1.
**Reason:** Reply tracking, campaigns and guard tests are missing from workspace source.
**Alternatives:** Blind copy of runtime or deploy stale workspace.
**Consequences:** Source drift is a P1 and a first Phase 1 task; no new feature development or deployment before reconciliation and regression checks. No remote/publish is implied by local git initialization.

## ADR 003 — Modular monolith and deterministic orchestration (proposed for Phase 1)

**Decision:** Keep FastAPI/Next.js/SQLAlchemy; establish profile, prospecting, evidence, outreach and mailbox boundaries with provider interfaces. Move scheduling and execution decisions into durable application jobs.
**Reason:** Current app is small; AI is useful for research/writing but unnecessary for quotas, retries, dedupe and clocks.
**Alternatives:** Microservices, agent-owned execution, separate queue cluster immediately.
**Consequences:** Shared send state/ledger and database locking come first. Preserve existing model capability without requiring a model to keep routine processing alive. Do not turn on paid APIs or legacy automation as part of this change.

## ADR 004 — Personal-first scope; shared deployment gated (accepted)

**Decision:** Preserve personal workspace use for now; phase planning may prepare ownership boundaries without launching a multi-user product.
**Reason:** User explicitly prioritized their own outreach; current schema/auth are single-user.
**Alternatives:** Immediate SaaS rewrite or exposing Basic-auth prototype.
**Consequences:** A shared deployment requires account/tenant ownership, secure OAuth storage, privacy lifecycle and corresponding authorization tests. Local no-auth mode cannot be a hosted default.

## ADR 005 — One send-policy boundary (proposed)

**Decision:** All company send adapters ultimately use one transactional attempt ledger, policy service, suppression and reconciliation logic; explicit self-tests have a separately labeled, bounded policy.
**Reason:** Legacy and scheduled helpers have different limits, locks, retries and follow-up schedules.
**Alternatives:** Maintain parallel senders and rely on agent discipline.
**Consequences:** Delivery uncertainty is retained, never blindly resent. Preserve user-authorized manual overrides but make their scope inspectable. A generic dry-run flag currently does not govern all send paths; the replacement mode model must be explicit.

## ADR 006 — Advisory detector results and bounded intelligence (accepted)

**Decision:** Use verified evidence and student facts; record real detector results as advisory, with version fingerprints. Keep bounded research and at most one writing revision.
**Reason:** Authenticity and useful company-specific proposals matter more than detector scores.
**Alternatives:** Fabricated scores, unlimited rewrites or long crawls.
**Consequences:** No claims of guaranteed human detection or delivery. Provider expenses remain unauthorized in current personal mode. Credentials configured is distinct from connection health.

## ADR 007 — Lockfiles and honest release gates (accepted)

**Decision:** Record actual isolated checks and advisories; upgrade only in a later scoped change with regression evidence. Treat skips/missing commands as gaps.
**Reason:** A build passing is not a security, PostgreSQL, or E2E pass.
**Alternatives:** Silent dependency upgrades during baseline or assuming old docs are current.
**Consequences:** Baseline artifacts remain durable; Phase 1 can start, but production release remains blocked by audit gates. Docker/PostgreSQL capability setup belongs to the phase that uses it.

## Module 1: personal-first modular monolith

One local primary operator/profile/Gmail account is the first release boundary. Public/shared SaaS, billing and tenant isolation are out of scope. Keep existing entities and add provider seams, database-serialized policy/attempt claims and explicit transitions. Future ownership/account keys must be added before shared access. See ../ARCHITECTURE.md and MIGRATION_PLAN.md. No deployment or campaign resume is authorized.

## Module 2: personal operator sessions and encrypted OAuth

Preserve the single operator boundary: hashed revocable server sessions for browsers and a separate CLI bearer key. Browser proxy forwards cookies, never a backend bearer secret. Store Google tokens/verifiers encrypted with an externally managed keyring. Connect requires session-bound PKCE/state and canonical Gmail identity; disconnect fences later sends and keeps receipts. Database-serialized ingress buckets reuse the existing lock. Explicit privacy content erasure retains delivery/suppression history. PostgreSQL validation is now local disposable evidence, not just CI intent.
