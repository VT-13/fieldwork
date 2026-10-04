# Fieldwork

A private internship outreach workspace for one student, one Gmail account and one operator. FastAPI, PostgreSQL, Next.js and a deterministic database-backed worker support sourced prospects, reviewed messages, guarded delivery, response tracking and one final follow-up.

Modules 1–5 are implemented in this canonical repository. They have **not been deployed** to the personal installation. Its credentials, historical records and recurring pause remain unchanged. Module 6 needs a separate user request for release verification; these instructions do not authorize deployment or mail.

## Setup and operation

Read [setup](docs/SETUP.md), [security](SECURITY.md), [deployment](docs/DEPLOYMENT.md) and [migration ordering](docs/MIGRATION_PLAN.md). Production is private HTTPS with PostgreSQL, hashed operator sessions and encrypted Gmail authorization; legacy Basic Auth and plaintext token setup are retired. Generate external application secrets with the documented security setup tool. Never commit credentials or use a personal database as a test fixture.

The API serves authenticated CRM and queues durable work. The separate `python -m app.worker` process executes jobs and creates bounded scheduling intents. Web availability alone does not mean jobs execute. The opt-in Compose worker and Mac service template are source configuration, not an installed or activated service. A sleeping/offline Mac cannot provide continuous execution.

Default manual mode, dry-run and paused policy prevent recurring company sends. Optional existing research/model APIs require configuration and explicit paid-policy authorization. A ChatGPT subscription is not an API connection; no free model or AI-detector automation is advertised. Opening a page does not initiate mailbox scans or paid research.

## Outreach workflow

1. Verify the student profile and real experience.
2. Import known companies without provider calls, or run explicitly permitted bounded discovery. Inspect candidates and deliberately accept suitable companies.
3. Save a current public contact and source observations; investigate conflicts rather than guessing an address.
4. Research a small set of priority pages. Generation selects supported company/student facts and a relevant practical proposal, then passes independent quality review.
5. Inspect the exact draft, sources and recipient. Operator approval is separate from permission to deliver.
6. An eligible send job rechecks current policy, account, review, evidence, replies, suppression, quota and uncertainty before atomic reservation. Provider acceptance is recorded; it does not guarantee inbox delivery.
7. Bounded Gmail history sync records replies, acknowledgments, bounces and opt-outs. These hold or cancel further outreach; no automatic reply or read-state change occurs.
8. One follow-up may be prepared at least 168 hours after confirmed initial transmission. It keeps the original subject/thread, adds a distinct proposal, requires review and is checked again before sending. Historical messages without a known proposal remain held for manual research.

All applicable sends share the total daily cap 25, including own-account tests and uncertain attempts; scheduled introductions are capped at 10 per weekday. Two daily bounces stop company sending. Missed schedules never increase today's quota. Explicit scoped manual batches retain the narrower canonical exception. Unknown sends remain held until positive exact Sent evidence; absence of evidence never authorizes resend.

## Source and verification

- [Architecture](ARCHITECTURE.md), [codebase map](docs/CODEBASE_MAP.md), [decisions](docs/DECISIONS.md), [bug audit](BUG_AUDIT.md).
- [Intelligence handoff](docs/module4/README.md), [communication runtime handoff](docs/module5/README.md), [actual provider capabilities](docs/PROVIDER_CAPABILITIES.md).
- `backend/app/services/{policy,delivery,ledger,jobs,scheduler,reconciliation}.py`: authorization, transport lifecycle, durable execution and evidence resolution.
- `backend/app/responses.py`: one bounded incremental scanner. `worker.py`: lifecycle, scheduling and claims. Alembic001→005 is the schema authority.
- `frontend/components/` and `frontend/app/`: notebook UI and authenticated workflows. Backend Pydantic contracts generate frontend TypeScript/runtime schema.
- `scripts/module5_check.py` and `module5_frontend_check.py`: sanitized disposable backend/PostgreSQL and browser gates; [verification](docs/module5/verification.json) records actual results and limitations.

Gmail capabilities are implemented and fake-tested; live OAuth/delivery, maintained PostgreSQL17/container/TLS/hosted operation and Safari remain release checks. Outlook production sending/tracking and SMTP are not implemented. No tracking pixels, calibrated open-rate claims, autonomous inbound replies, SaaS tenancy or response-rate guarantee are provided.
