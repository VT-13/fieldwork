# Module 5 — durable communication runtime

Canonical schema005 source only, built from Module 4 revision `cf37cbf`. No deployment, live migration, real OAuth change, paid provider call, real company email or installed worker activation occurred. The installed personal runtime remains older source/schema with recurring outreach paused. Module 6 requires its own user prompt and owns release verification; do not casually install this revision.

## Runtime and ownership

The API queues work; `python -m app.worker` runs a deterministic scheduler and executor against the same database. `services/jobs.py` owns due times, stable dedupe, serialized claim, owner tokens/leases, recovery and explicit retries. Existing Job/Operation/ActionAttempt/Usage remain the only queue/operation/cost architecture. Scheduling writes intent, never permission. Existing policy remains authoritative at execution and reservation.

One worker leader is supported for the first personal release. PostgreSQL advisory leadership covers each processing tick; database ExecutionLock and unique operation keys independently protect competing claims and send reservations. Development SQLite uses a local file lock, but release concurrency evidence is disposable PostgreSQL. Consequential network I/O starts only after reservation commit and does not hold the database execution lock. Read sync uses an additional database-scoped lease.

Defaults: worker ticks15 s; lease120 s, renewed every40 s; job execution600 s (configurable maximum 900 s). SIGTERM/SIGINT stops new claims and finishes the bounded current job. Compose worker remains opt-in and grants16 min shutdown grace; the Mac worker template is not installed. `python -m app.worker --health` reads DB/schema/heartbeats without provider calls and exits nonzero for unavailable worker/schema. Authenticated `/runtime` distinguishes database, schema, worker, scheduler, Gmail stored connection, stale sync, communication holds and actual job state. A long job may show scheduler waiting for that current job; web/API liveness is separate from worker execution or provider health.

## One company delivery path

API send jobs, worker sends and scheduled compatibility helpers converge on `services/delivery.send_company`. `mail.send_one` is a compatibility delegate, not a second sender. Gmail transport rejects naked sends/draft-send/batch mutations and verifies the MIME against the exact saved reservation: own sender, exact recipient, subject/body/fingerprint, RFC Message-ID and original threading. Query-suffixed Graph send endpoints fail closed. Self-tests and unsent own-account drafts retain their separately labeled narrow policies and ledger claims.

At reservation, current policy rechecks approval/review/profile/contact/evidence hashes, due time, configured timezone/business hours, scope, stop/pause, suppression/events, account authorization, global uncertainty, spacing and shared quotas. Production worker business hours and the explicitly scoped manual initial-only exception remain canonical. Defaults: daily total25 including self-tests/unknown attempts, scheduled introductions10 per weekday, two distinct daily bounced companies stop sending, one follow-up. An approved message or queued job cannot bypass these checks.

Provider acceptance is Sent, not inbox delivery or readership. Minimal receipts retain account, operation/outreach IDs, provider/thread/RFC IDs and acceptance/reservation timestamps. Confirmation failure keeps a durable accepted receipt and communication hold. Known-success replay returns the stored result without connection or another transmission. Definite provider rejection records Failed and consumed attempt history; it does not automatically retry. Network/timeout/5xx ambiguity remains Unknown. Raw provider responses, credentials and bodies are not duplicated into the ledger.

## Crash and race semantics

| Window / race | Durable outcome / recovery |
|---|---|
| Before reservation commit | Rollback; no transmission; later eligible processing is safe. |
| After reservation, before request | Reserved/running or interrupted becomes Unknown; conservatively require evidence, never assume no send. |
| During request / forced cancellation | Unknown/held, never requeued for send. |
| Provider success before local success commit | Durable reservation survives; exact Sent evidence reconciles to Sent without another request. |
| After final commit / duplicate job | Saved receipt replay, no duplicate transmission. |
| Reply/pause committed before reservation | Fresh locked state wins; no send. |
| Reply/pause after reservation | Already reserved I/O may complete; retain receipt and preserve reply/stop CRM state. |
| Lease lost | Stale ownership cannot authorize a new send; recovery retains uncertainty. |

Reconciliation verifies the configured account and searches only the reserved RFC ID. A match needs own sender, exact recipient without Cc/Bcc, exact subject/body/RFC, SENT label and reserved-time window (−2 min/+1 h). Exactly one match without additional pages resolves the hold. Absence, duplicates or mismatches remain held; they do not prove non-transmission. Conflicting recorded provider/thread identity is never overwritten. Positive resolution adds minimal reconciliation linkage, not a fabricated historical authorization. Historical file receipts stay unchanged.

## One reply scanner

`responses.sync_session` owns bounded Gmail history sync; both API sync routes enqueue the same operator bucket, and legacy `sync_mailbox` delegates here. The API lifespan has no reply loop. With RESPONSE_POLL_ENABLED, the worker creates five-minute sync intents while company outreach is paused. No page render performs provider scans.

Each run verifies mailbox/profile identity, obtains a database lease and persists history/page/pending-message checkpoints. Defaults: up to 40 messages,60 requests,120 s,25 history/list entries per request; a history page with more than250 message IDs is held. Checkpoints advance only after ingestion commits. Initial/expired-cursor recovery uses a30-day recent backfill, captures a history boundary before listing and resumes partial pages. There is no mailbox-wide recurring scan. In-memory CRM linkage reads existing outreach/contact records; provider I/O is bounded. Failure retains committed pagination, records a safe category and backs off up to an hour. Safe interrupted sync/reconciliation jobs automatically recover at most twice with30/60 s delay; fresh later polling intents are normal read work, not send retries.

Correlation prefers exact thread or RFC references with the own account among recipients and timing after reserved send. Unthreaded fallback needs the exact known sender/own recipient, no contradictory RFC linkage, one company and a30-day context. Subject similarity never links unrelated mail. Supported DSNs use deterministic sender/content-type plus recipient/RFC evidence. Human reply, automatic acknowledgment, bounce and explicit unquoted opt-out become immutable source-ID-deduplicated Events linked to Contact, Outreach and the personal campaign. Replayed ingestion has no duplicate effects.

Inbound plain text is bounded; HTML scripts/styles are removed and React escapes previews. No remote HTML/resource execution, LLM response classifier, automatic inbound reply, Gmail read/label modification or inferred offer commitment is added. Mark handled only updates local attention. Human responses cancel future outreach, automatic acknowledgment holds it, and bounce/opt-out persist suppression independent of campaign state.

## Follow-ups and scheduling

An initial confirmed send gets one deduplicated preparation intent at initial timestamp+168 h. Existing attempted-operation records require positive Sent confirmation; legacy linked rows remain subject to original thread/contact/evidence policy and receipt review. Preparation rechecks original confirmation, current policy/contact, reply/suppression and global uncertainty, then performs fresh mailbox preflight and rechecks again. Module 4 generation keeps the original subject, demands a distinct practical proposal and preserves evidence/profile/review guarantees. Historical messages lacking a known prior proposal are held for manual research.

Preparation creates a draft for operator review, never auto-approves or sends. Later delivery must be independently approved and pass every current send guard. Reply/acknowledgment/bounce/opt-out cancels queued messages and related jobs durably. Pause blocks queued sends/preparation and requires deliberate requeue; read sync/reconciliation remain available. Campaign STOP retains the stronger canonical terminal behavior. Unknown/attempted/cancelled work cannot become retryable just by resetting browser state or changing campaigns.

Scheduler creates current polling/reconciliation buckets and at most five send intents per tick, prioritizing approved follow-ups. It excludes existing send/preparation intents before limiting, so blocked/history rows do not hide later work. Reconciliation rotates up to five operations within a bounded100-operation selection to avoid an oldest hold starving the next one. Follow-up selection is bounded100 originals per tick. Already authorized configured discovery uses the current local day only; accepted-company research remains bounded and provider/mode constrained. No historical-day replay or accumulated quotas after sleep/offline. A laptop cannot execute while asleep; reliable continuous scheduling needs an authorized always-on runtime.

## Verification and preservation

From repository root on this Mac:

```sh
FIELDWORK_DISPOSABLE_POSTGRES_URL=postgresql+psycopg://fieldwork_test@127.0.0.1:55432/postgres /private/tmp/fieldwork-module2-venv/bin/python scripts/module5_check.py
/private/tmp/fieldwork-module2-venv/bin/python scripts/module5_frontend_check.py
/private/tmp/fieldwork-module2-venv/bin/python scripts/module5_preserve.py
python3 scripts/source_manifest.py verify
```

The paths/port above are disposable test tooling, not production requirements. CI uses pinned requirements and PostgreSQL17. Runners sanitize temporary source/config with empty mail/research credentials and no personal DB. Backend tests cover canonical delivery, MIME fences, recovery, response/currentness/suppression, quota/day boundaries, migration old-row preservation and backup/restore, real worker subprocess startup/SIGTERM/restart/SIGINT, and two actual competing workers/claims/quota/sync readers on PostgreSQL. Frontend lint/typecheck/format/build and browser gates use fictional intercepted APIs, not live-provider E2E.

See verification.json, backend/frontend-checks.json, browser-results.json, logs and critique.md. Preservation compares installed source hashes, credential-file hashes, launch-agent definitions, policy hash/pause and historical counts before/after. It is not a full row-by-row live DB audit or live service deployment check. Runtime records were never used as test fixtures. No active launch agent/automation was modified; future release must retire the old external sender before starting this deterministic runtime.

## Release limits

Live Google registration/consent/token refresh/API throttling/RFC preservation/deliverability are unverified here; fakes prove application behavior only. Outlook has no production OAuth/send/tracking/reconciliation/self-test; legacy development draft compatibility is explicitly partial. SMTP and Gmail watch/push are absent. No free/ChatGPT-subscription model adapter or detector automation is implied. Docker builds, maintained PostgreSQL17 server, TLS/hosted operation and Safari remain Module 6 release gates. Dependency pins did not change; Module 3's development-only lint advisory remains recorded, not claimed rescanned clean. Follow MIGRATION_PLAN.md and PROVIDER_CAPABILITIES.md. Module 6 can verify/release this architecture without another queue or scheduler rewrite.
