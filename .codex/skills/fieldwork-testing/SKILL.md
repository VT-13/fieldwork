---
name: fieldwork-testing
description: Baseline or verify Fieldwork changes with isolated unit/integration tests, provider mocks, browser/visual QA, end-to-end flows, and regression evidence.
---

Read `docs/BASELINE.md` and relevant audit IDs. Use disposable databases, empty provider credentials, disabled response polling, and fake HOME for file locks. Never execute tests against the personal mailbox or database. The Phase 0 runner is `scripts/phase0_baseline.py`.

Definition of done scales to the change: unit tests for business rules; integration tests for ownership, migrations and transactional boundaries; provider mocks for identity, errors, retries and delivery uncertainty; browser tests for user-visible interactions; visual QA for substantial layout changes; isolated E2E for core workflows; focused regression coverage for fixed audit items. Do not add tests that merely echo implementation.

Email release gates cover all send paths: authorization, dry-run semantics, duplicate prevention, concurrent quota reservation, pause, uncertain sends, bounce stop, fresh threaded/unthreaded replies and follow-up cancellation. Provider acceptance is distinct from confirmed Sent and actual delivery.

Run backend tests, frontend typecheck/build, relevant lint and dependency checks. PostgreSQL must use a disposable test URL; skipped database/provider/browser checks remain explicit gaps. Record exact commands, results, skips and evidence. Do not call a mocked or static review an E2E pass. Preserve baseline failures until fixed and verified.
