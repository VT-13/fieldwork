# Testing strategy and validation

## Checks run during this build

- Backend: **48 tests passed, 1 PostgreSQL test skipped** locally using SQLite and fake provider boundaries.
- Next.js: optimized production build and TypeScript checks passed.
- Frontend dependency audit: zero reported vulnerabilities after upgrading to the installed patched release.
- Alembic initial migration applied successfully to a fresh local SQLite database.
- Browser smoke check: dashboard, fictional demo seeding, company brief/source display and disabled demo actions.

No real messages were sent. No paid company research or real model calls were performed. Docker, PostgreSQL server, cloud deployment, and real Gmail/Outlook delivery were not available for runtime validation in this environment.

## Local automated suite

```sh
cd backend
python -m pip install -e '.[test]'
python -m pytest -q
cd ../frontend
npm ci
npm run build
npm audit --omit=dev
```

Coverage includes authentication, company deduplication, demo isolation, nonpublic URL rejection, geographic calculation, unknown-factor scoring, budgets/cache, event idempotency, suppression across outcome types, dry-run delivery, duplicate sends, timeouts, unknown-send reconciliation, bounce matching, stale/catch-all validation, strict quality threshold, changed-profile protection and bounded draft regeneration.

## PostgreSQL acceptance test

Run migrations against a **disposable test database** and enable the optional database test:

```sh
TEST_POSTGRES_URL='postgresql+psycopg://user:password@localhost/testdb' python -m pytest tests/test_postgres.py -q
```

The optional test uses a temporary schema and checks foreign keys, unique campaign sequences, rollback behavior and advisory-lock exclusion across connections. It is skipped when no test URL is supplied. Do not point it at a production database.

Also start two worker containers in a disposable deployment, enqueue the same workflow and verify only one leader processes it. Simulate a worker crash after the outbox changes to sending; restart and confirm the row becomes unknown rather than being delivered twice.

## Provider contract tests with your sandbox credentials

1. Discovery: one Maps search, assert all returned coordinates are within the configured radius; compare a few distances independently. Repeat and ensure no extra reservation because of the query cache.
2. Firecrawl: verify a homepage and two priority pages; compare exact quotes to stored evidence. Test inaccessible pages and a site containing instructions to the agent—the output must treat those as untrusted content.
3. OpenAI: use a company with known evidence, assert schema parsing and evidence IDs. Include deliberate unsupported student claims and wrong contact names and require reviewer rejection. Sample reviews manually; AI scoring alone is not a correctness proof.
4. Hunter: validate a mailbox you own, a catch-all result and a known invalid result. Confirm only the first can send.
5. Gmail and Outlook separately: verify identity, send to a second controlled mailbox, inspect RFC Message-ID / thread headers, reply and sync, confirm no follow-up.
6. Sending failures: inject a definite 429 and confirm delayed bounded retry; inject a timeout after successful provider acceptance and confirm unknown, then reconciliation from Sent.
7. Notifications: test supported delivery-status messages. For unmatched formats, record a bounce manually and verify suppression. Ensure automatic replies stop follow-ups.
8. Scheduling: simulate days 7, 14 and 30 in a test database, with an outage spanning multiple due dates. Confirm predecessor and six-day spacing prevent a burst.

## UI / operational acceptance

- Mobile viewport and 200% text scaling: all actions accessible, table can scroll deliberately without clipping forms.
- Profile editing and verification; stale drafts require regeneration.
- Search/add/import, detail evidence, contacts, validation job, drafts and approval.
- Missing credential / provider failure surfaced as blocked work, not fake success.
- Real metrics exclude demo data and count distinct initial-contact companies.
- API endpoints reject missing bearer keys; hosted dashboard challenges unauthenticated users; cross-origin mutation requests fail.
- Database backup/restore and OAuth credential rotation work before live automation is enabled.

For future development, add provider fixtures from your own redacted sandbox responses and integration tests for any new endpoint contract. Keep the dry-run default and delivery uncertainty tests as release blockers.


Personal desk update: additional tests cover paid-call blocking in manual mode, stored real detector results, stale result/sign-off invalidation, self-only unsent MIME export, header injection, Gmail/Outlook draft-only endpoints, idempotent draft saving, uncertain-write quarantine, and wrong-mailbox rejection. The updated desk and saved detector result were verified in Safari. No mailbox is connected yet, so real provider draft saving still needs account authorization and live verification.
