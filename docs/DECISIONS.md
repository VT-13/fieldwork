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

## Module 3: field notebook and shared private read contracts

Use ruled task views, local/system typography and one semantic token source, refined from actual production browser renders. Preserve one personal operator. Keep URL navigation/filter state separate from form state and validated cached server data. Generate TypeScript and runtime schema from private Pydantic response contracts; normalize defaults while preserving existing additional contract fields. Do not expose HTTP OpenAPI. A narrow serialized unsent-message edit clears review; reject/return use existing transitions. Pause is returned from the database even without a current batch and UI actions await it. Approval never authorizes transport. No new generation system, provider purchase, deployment, real mail or campaign resume occurs.

## Module 4 — candidates, exact observations and grounded writing plans

Keep one personal operator/profile and existing Job/Operation/ActionAttempt/Usage boundaries. Add a domain-deduplicated candidate buffer, ContactObservation, profile-hashed StudentFact and immutable Generation history; extend Evidence and Usage additively in schema004. Accept candidates deliberately; no discovery adapter imports directly into communications. Model work is bounded and subordinate to deterministic limits, current policy, source ownership and human review.

Choose structured fact/task selection plus source-attributed rendering over arbitrary prose validated only by another model. This makes unknown IDs, invented numbers/names and injected actions rejectable without claiming a perfect semantic fact checker. Independent quality review still matters. Tradeoff: a small proposal catalog and less creative variation; editing always clears review. Prompt identity hashes the instructions/catalog/renderer, and exact generation versions survive replacement. Reuse original source timestamps on cache hits; otherwise caching could falsely refresh roles or careers evidence. Never auto-resolve identity conflict or substitute a guessed mailbox. Existing private read-contract/cache/URL patterns and design tokens remain authoritative.

Use conservative token/cost reservations in the existing Usage ledger and a personal campaign daily generation cap. No speculative free/subscription adapter or paid service activation. Capability-aware actions fail before enqueue when unavailable and show actual existing job states on dedupe. Explicit retries are bounded/backed off; stopped/uncertain work cannot become silent retries. This module changes no scheduler, pause, OAuth account or production runtime.


## Module 5 — one deterministic communication runtime

Extend existing Job with due time and lease ownership, and Event with optional contact/outreach links and the personal campaign identity. Keep one queue, one scanner, one central policy and one delivery ledger. The worker also creates scheduling intents; no external AI/cron executor is needed. First release supports one active worker leader, while atomic database claims/reservations guard accidental concurrency. Safe read-only jobs can retry twice; paid interrupted work requires explicit bounded retry; uncertain sends never retry.

A reserved transmission cannot be recalled by pause or a subsequent reply. Preserve the reply CRM state if it arrives during provider I/O. Resolve uncertainty only with one exact own-account Sent match; no matching message is not proof of non-transmission. Follow-up preparation and operator approval remain separate from later transport, with a fixed minimum168 h due time and one distinct proposal. Bounded incremental Gmail history is sufficient for personal-first use; no Pub/Sub infrastructure or autonomous response agent is added. Production Graph sending/tracking is excluded honestly. Source service definitions are deployable later but this module leaves the personal runtime untouched.

## Module6 release verification

Keep schema005 frozen and the installed personal system unchanged. Use private native PostgreSQL17.11 from checksum-verified official source because no Docker engine is available; actual production-build/authenticated API/dedicated-worker E2E uses a private TLS test CA and fake provider seams only. This is executable native evidence, not container/hosted/live-Google certification. Split runtime dependency pins from test pins so production images exclude pytest. Fix only observed release failures (startup schema/config, original follow-up reference, PostgreSQL self-test State key, shared policy cap, idle rate bucket, public Host validation, WebKit keyboard/resize and responsive wrap) and narrow observability gaps. No new service/provider/SaaS feature or production activation.

Introduce an explicit validation-first stopped-sender SQLite001→empty-PG transfer with exact old-record comparison and transactional forward migration. It refuses unrecognized schemas, non-paused source, nonempty target, oversized fields and missing stopped-sender confirmation. Count-only installed preflight found one over-width State key; do not fabricate its compatibility. A versioned lossless migration is a remaining P1; keep release NOT READY rather than truncating history or editing frozen migrations. Runbook retirement and rollback are defined but not executed.

## Package6A — widen exact State identity in versioned006

Decision: widen State.key100→255, the existing operation-idempotency capacity. Installed read-only structural inspection confirms one111-character legacy self-test receipt composed from packet UUID+draft hash. Its current packet still matches; canonical fallback lookup and002 original-key receipt backfill require exact identity. The100 limit was a generic legacy declaration, not a semantic rule. Preserve the original primary key/JSON/history; no alias, normalization or irreversible hashing.

Rejected: truncation/deletion loses replay protection/provenance; rename/hash mapping adds unnecessary lookup/migration ambiguity; unbounded Text adds no value for installed/key-producer semantics and outgrows the existing operation bound; rewriting001–005 invalidates frozen history. Beyond255/unknown schema must fail explicitly.

Consequence: the empty-target transfer applies only the frozen006 widening helper before copying001, then runs002–006 after the full copy so historical ledger backfill remains intact. One PG transaction rolls all stages back together. Normal fresh/in-place upgrades use Alembic006; downgrade refuses. Installed schema/source/pause/credentials/services are untouched. Exact identity, same-prefix uniqueness, replay/unknown holds, full-row preservation and SQLite/PG17.11 restore are verified; Package6B and remaining release gates are not started.

## Package6D — bounded two-account provider validation

The authorized live protocol requires one exact-subject A→A draft, one A→B self-test, and a controlled B→A reply. Existing default desk self-tests/drafts prepend DRY RUN and self-tests cannot target B; company reply/reconciliation previously require Outreach rows. Do not bypass the transport fence or fabricate a company send. Add an explicit disabled-by-default live_gmail_validation_enabled setting plus a server-provisioned expiring State scope usable only in the named Railway staging environment with dry-run/manual safeguards and polling off. Bind two known accounts, separate packet IDs, immutable hashes, fixed synthetic content, and a maximum24-hour send/draft window; reject scope changes at the transport fence. There is no public scope-grant endpoint. Existing self_test/mailbox_draft operations, shared quota, uncertainty holds, exact Sent envelope matcher and bounded history reader remain the sole paths. No schema change or new sender/queue is introduced.

A test reply Event has kind test_reply and campaign gmail-validation; its mandatory company FK uses the already-existing synthetic demo audit fixture only. No Contact/Outreach or company-recipient record is created, no Company state changes, and test_reply is excluded from real response metrics/policy classification. The scope State explicitly links the reply to its originating test packet and marks its non-sending follow-up state cancelled. While the scope is active, history fetches metadata first and full bodies only for the exact controlled thread/accounts, retaining the current cursor without an unrelated bootstrap. Historical test receipts remain durable. This is a protocol capability gap, not an already-observed Gmail wire discrepancy; actual live semantics must still pass.

### Package6D real Gmail RFC identifier normalization

The single authorized live staging self-test returned an immutable Gmail message/thread receipt, but reading that exact Sent message showed a different RFC Message-ID generated by Gmail. Never infer a match from subject alone or resend the accepted message. For the scoped validation record, canonical reconciliation reads the exact accepted API ID, verifies that ID/thread, sender, sole recipient, subject, complete body, SENT label and bounded acceptance time, then confirms a unique search by the observed RFC ID. Store both original reserved and actual provider RFC identities. Without an accepted provider receipt, strict reserved-ID matching remains unchanged. Replay rejects subsequent identifier changes. This bounded adapter normalization does not change company sending or unknown-attempt retry policy. Google's message resource documents immutable message IDs and parsed MIME headers; the rewrite is observed live evidence, not an asserted provider guarantee: https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages .

### Package6D owner reply text amendment

The owner sent the existing same-thread controlled reply with “It is working” instead of the original proposed phrase, then explicitly authorized using it and prohibited another reply. The scoped State carries that exact expected opening line; canonical ingestion keeps the same authenticated A/B/thread/receipt/time checks and accepts Gmail's appended quoted original without accepting changed opening text. No outbound envelope/policy changes. A regression verifies the original expectation rejects it, the exact owner amendment creates one deduplicated test Event/cancellation, and changed text is rejected without additional sending.

### Package6E accepted Gmail RFC identity normalization

Final verification found company confirmation used only the SENT label and retained the reserved RFC ID, while Package6D proved Gmail can rewrite that ID. The smallest fix extends exact receipt-bound normalization to canonical company confirmation, reconciliation and own-Sent ingestion. An alias requires a succeeded durable Operation/ActionAttempt with matching immutable API message/thread IDs plus exact account, sole recipient, subject, body, Sent label and bounded timestamp. The ledger rechecks the reservation/receipt under its existing lock, preserves reserved_message_id and stores the provider RFC ID for subsequent threading. Unknown attempts without accepted receipts retain strict reserved-ID search and cannot resend. Provider acceptance is committed before confirmation; failed or conflicting confirmation remains pending. No schema, queue, policy, approval or sender redesign; all new test network is fake/read-only. Live company communication remains unauthorized and unverified.
