# Fieldwork — personal-first architecture

Module 1 establishes canonical source, not a deployed release. One operator, one student profile, one connected Gmail account, and one private local installation are supported. No public signup, shared-account deployment, tenant isolation, billing, or unattended agent-based authorization is supported. Module 2 verifies migrations and concurrency on disposable PostgreSQL; production PostgreSQL17/container/TLS rollout remains gated.

## Modular monolith and ownership

| Domain | Owner / canonical state |
|---|---|
| Operator / integration | Existing authenticated API, settings and private OAuth configuration; credentials stay outside source and ledger |
| Student facts | Profile and its structured evidence; review hashes bind messages to the reviewed profile |
| Prospects / research | Company, Contact, Evidence and existing pipeline; published URLs and extraction provenance support claims |
| Personalization | Pipeline structured schema validation; `IntelligenceProvider` supplies bounded research, verification and LLM output |
| Campaign authorization | Database State `outreach_policy` and explicit scoped `manual_batch`; `services/policy.py` is the decision boundary |
| Communications | Outreach stores exact message/thread linkage; `services/delivery.py` is the sole company-send entrypoint |
| Execution evidence | Operation + ActionAttempt + DomainTransition; legacy receipts remain immutable evidence |
| Scheduling | Durable Job records and deterministic worker; scheduling never authorizes a send by itself |
| Replies / CRM | Existing response tracker, events, suppressions and opportunity status; provider evidence stops future sends |
| Usage | ActionAttempt for operational history; existing usage records retain token/cost accounting, not separate send authority |

FastAPI, SQLAlchemy, existing providers and Next.js remain one application. The desktop shell is a client, not another scheduler. No additional database or distributed infrastructure is introduced. Most existing entities remain intact; only four additive ledger/transition tables are introduced.

## Provider contracts

`services/contracts.py` defines EmailProvider, ProspectProvider, ResearchProvider, LLMProvider and their combined IntelligenceProvider. Existing adapters implement these seams. Provider-specific Gmail checks live in EmailAdapter; business authorization and reservation do not. Company-send support in this first release is Gmail; existing Graph drafts remain compatible but full Outlook tracking is deferred. No speculative free/subscription adapter is claimed.

The bounded pipeline retrieves canonical facts, calls intelligence when needed, validates structured output, then persists it. The deterministic job runner owns retries and dispatch. LLM text cannot change quotas, pause, identity, approval or suppression. Direct paid provider reservation also respects manual mode and explicit paid-service prohibition. Module 1 does not replace the external research workflow with a complete autonomous research product (FW-005/006).

## State and execution semantics

`domain/states.py` centralizes transitions for messages, jobs and operations. Invalid transitions raise Blocked; accepted transitions append DomainTransition. A draft can become approved/rejected/cancelled; approved can return to draft or reserve sending. Sending becomes sent, unknown or failed. Sent is terminal. Unknown requires evidence-based resolution to sent/failed; it cannot blindly retry. Job queued → running → done/failed/blocked/interrupted; only failed/blocked/interrupted jobs may requeue. Operations distinguish pending, blocked, skipped, running, succeeded, failed and unknown. Campaign pause/stop changes are audited.

Reply/bounce/opt-out facts remain immutable events and suppression records rather than overwriting a successful send as a different delivery state. `sent` means provider acceptance, not inbox delivery. Receipt `confirmation_pending` holds later sends until a matching Sent message resolves it. Automatic acknowledgments also hold contact outreach. Follow-up is a separate Outreach row with sequence 1, original threading IDs, a due date at least 168 hours later, and reviewed new value. Existing uniqueness constraints and send reservation prevent duplicate follow-ups.

## Shared ledger and idempotency

Operation uniquely identifies a logical action. ActionAttempt records each authorized or denied attempt, policy version/hash, timestamps, provider, linkage, retry predecessor, network units and minimal receipts. Exact message bodies remain in Outreach, not duplicated into the ledger. Reasons are bounded and provider errors are redacted. DomainTransition records state changes in the same database.

A singleton ExecutionLock row serializes claims, current-policy rechecks, quota reads and reservation across connections. Unique operation keys are a second guard. Policy and message fingerprints are rechecked after mailbox preflight under that lock. The transaction commits before network I/O. This prevents another worker from claiming the same operation. A crash after reservation leaves running/unknown state and blocks communication; it is never treated as permission to resend. Pause commits before reservation prevent that send; a transmission already reserved may complete.

- Company send key: stable Outreach ID (initial/follow-up have distinct rows); completed replay returns the existing receipt only.
- Self-test: saved message version and own-mailbox identity; provider draft: saved content fingerprint. Both use this ledger; self-tests count toward total send quota.
- Jobs: stable Job ID, with explicitly linked retries. Interrupted/uncertain external operations do not automatically replay.
- Provider research/generation: existing bounded cache plus job identity, budget reservation and structured results. Deliberate regeneration is a distinct job; failed work requires an explicit retry. Not every HTTP subrequest is a separate Operation: job attempt owns those calls and existing usage records retain request accounting.
- Reply/preflight scans: distinct bounded read executions; provider event IDs and existing event deduplication prevent duplicate CRM effects.
- Historical receipt import: file digest + entry index, requiring exact Outreach/RFC linkage; unmatched evidence is reported, never guessed.
- Webhooks/callback ingestion is not implemented. A later endpoint must claim `(provider, account, external_event_id)` before applying transitions; no unaudited callback path exists now.

Global unknown/running communication, pending confirmation, suppression, replies, bounces, invalid approval/evidence, stale contact validation, identity mismatch, quota exhaustion, and stop state block delivery. Authorization counts ledger attempts plus legacy attempts without double counting. Maximum daily total is 25 including self-tests/unknown sends; scheduled new-company limit is 10. Explicit scoped manual batches retain their narrower, expiring initial-only exception. Two daily bounces stop sends. No catch-up quota exists.

## Exact pause matrix

| Work | Recurring policy paused |
|---|---|
| Company introductions / queued sends / follow-ups | Blocked |
| Exact explicitly enabled, unexpired manual batch | Initial messages explicitly listed in its scope only; stop_requested always blocks |
| Explicit self-test / provider draft to own account | Allowed independently, with identity/idempotency and uncertainty guards; test sends count toward quota |
| Discovery / research / generation | Pause alone does not cancel; manual mode or explicit prohibition on paid services blocks paid calls; budgets still apply |
| Reply synchronization / read-only CRM / analytics | Allowed |

Missing campaign policy fails closed. Worker DRY_RUN/MANUAL_MODE remain additional controls; the explicitly authorized scheduled helper uses database policy, not those worker flags. Use database pause/stop as authoritative communication control. No browser state, prompt, temporary file or chat memory overrides it. The legacy filesystem STOP fallback is compatibility-only for historical batch display/stop, never an alternative authorization source.

## Release and expansion

The canonical Git source is checked by `scripts/source_manifest.py`; CI detects changed, missing, or added source. Source-only bundles require a committed matching manifest. Installed drift is detectable with the same verifier. Deployment must follow `docs/MIGRATION_PLAN.md`; it is not automated or performed here. Multi-user expansion requires operator ownership keys, account-scoped policies/uniqueness, real authentication and authorization tests before any shared deployment. Existing provider contracts and explicit entity references allow this later without pretending today's singleton is tenant-safe.

## Module 2 security boundary

auth.py owns operator sessions/authorization; gmail_oauth.py and credentials.py own encrypted integration lifecycle. Integration.generation fences stale connections after disconnect/profile identity changes. ingress.py bounds requests and shares database rate buckets. privacy.py owns content deletion/export and hourly minimization. Schema003 is additive; no existing operator/profile/prospect/receipt row is reassigned. Next forwards authenticated cookies rather than holding browser-facing bearer authority. See SECURITY.md and docs/BACKUP_RESTORE.md. No source changes were deployed.

## Module 4 intelligence boundary

`app/intelligence/` owns normalized candidates/contacts, request bounds, evidence extraction/freshness/ranking and grounded personalization. `providers.py` retains fixed external endpoint adapters; `services/contracts.py` adds dated ScrapedPage results. The existing worker executes scoped durable jobs; discovery writes Candidate only, and operator acceptance creates Company. Research commits useful exact evidence before later pages can fail. Queuing is separate from execution and authorization.

Schema004 adds Candidate, ContactObservation, StudentFact and Generation, Evidence source/freshness fields and Usage metadata. No raw site dump goes into these domain records or premium writing context. Contact/student/company ownership is checked before generation and application; generation references bind to current source/profile/contact hashes. A deterministic renderer accepts only a validated model selection over supplied references and relevant supervised task IDs. Independent quality review is required; generated records remain unsent drafts. Prompt/version/model/input identity and prior versions persist. Existing send policy calls the narrow current-generation guard without introducing another transport or changing scheduling.

Privacy export includes new domain records; content erasure removes student/generation text while preserving minimal linkage/history. Operational records/logs use IDs, hashes, counts and sanitized codes. Read-only capability endpoints describe actual configured adapters and disabled policy, never connection health. New private contracts feed the Module3 generated frontend client. See docs/module4/README.md for exact limits, provider coverage, testing and production constraints.
