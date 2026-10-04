# Fieldwork repository

Read `docs/CODEBASE_MAP.md` and the relevant phase entry in `docs/PHASE_PLAN.md` before substantial changes. Read `BUG_AUDIT.md` for known risks; update it when evidence changes. Record architectural choices in `docs/DECISIONS.md`.

Repository-scoped skills live in `.codex/skills/`; select the relevant skill for design, frontend, architecture, security, outreach, or testing. Frontend changes must also follow `frontend/AGENTS.md` and installed Next.js documentation.

This repository is canonical after Module 1 reconciliation; the installed app remains the older, intentionally undeployed runtime. Read ARCHITECTURE.md and docs/MIGRATION_PLAN.md before release work. Verify scripts/source_manifest.py before packaging; never edit installed source as the canonical implementation. Modules 1–3 are implemented in canonical source. Module 3 frontend work was authorized by its prompt; it does not authorize Module 4 or deployment. Read SECURITY.md for current session/OAuth/retention controls.

Module 1 tests use isolated temporary copies, an explicit DATA_DIRECTORY, empty provider/mail credentials, disposable SQLite, and disabled polling. Never use the personal database as a test fixture. Preserve historical receipts, suppressions, uncertain attempts, and the current pause. Engineering work alone does not authorize email sends, provider purchases, or starting the legacy worker. Existing explicit user authorization remains authoritative for actual outreach tasks.

Use search → targeted read → decision → patch → verification. Keep provider calls and runtime scheduling bounded and deterministic. Do not require an AI agent for ordinary scheduling, retries, quotas, or state transitions.

## Module 3 handoff

Use the final product-design reference, frontend-quality skill and `docs/module3/README.md`. Four flagship views, generated/validated API contracts and lint/typecheck/build/browser gates are implemented. The installed runtime remains intentionally undeployed and recurring outreach paused. Module 4 needs a separate user prompt; it should build against these existing UI/policy/security patterns rather than start another audit or design system.

## Module 4 handoff

Module 4 is implemented and verified in canonical source only. Read docs/module4/README.md and verification.json for bounded candidate/research/evidence/ranking/generation ownership and limits. Keep the shared job/operation/usage/policy boundaries, deliberate candidate acceptance, exact evidence/profile references, review gate and immutable history. The installed personal runtime, receipts and recurring pause are unchanged. Module 5 requires its own user prompt; Module 4 does not authorize deployment, real provider calls, worker activation or mail.


## Module 5 handoff

Read docs/module5/README.md, verification.json and PROVIDER_CAPABILITIES.md. Canonical schema005 has one delivery/policy/ledger, durable owner-fenced Jobs, one bounded incremental Gmail scanner and one reviewed168 h follow-up workflow. Source-only worker/service configuration exists; installation/production migration/OAuth/send/automation changes remain unperformed. Module 6 requires its own user prompt. Keep exact unknown-send holds, current policy/review, suppression and installed preservation; release must stop/retire the old external sender before any authorized worker activation. Do not add another queue/scanner/agent scheduler.

## Module6 handoff

Read docs/module6/README.md, verification.json, RELEASE_CHECKLIST.md and RUNBOOK.md. Release is NOT READY: FW-026 was the installed State width blocker; Package6A resolves it with lossless schema006 and read-only installed preflight. Read docs/package6a/README.md and verification.json; no production migration occurred. No truncation/guessed migration or frozen schema rewrite. Maintained PG17/native production-build/fake-provider/worker/browser evidence does not certify containers, hosted TLS or live Gmail. Installed runtime/schema001, credentials/services and recurring pause remain unchanged. No deployment, OAuth, worker activation or communication is authorized by this verification. Keep the sole policy/ledger and current review/unknown/suppression guarantees; resolve only concrete remaining release gates.

## Package6A handoff

Current canonical head006 preserves exact legacy State identities with a255-character column. Do not change frozen001–006 or skip002 receipt backfill. The empty-target transfer uses006's idempotent widening before001 copy, then002–006 in one transaction. Installed runtime/schema001/credentials/services and recurring pause remain unchanged. FW-026 is resolved only for the verified migration/preflight; all other Module6 gates persist. No Package6B, deployment, worker activation, OAuth, automation or email is authorized by this task.

## Package6B handoff

Read docs/package6b/README.md and verification.json. The runtime-container gate passes actual Linux ARM64 production images, schema006, private networking, runtime-only secrets, separate API/web/worker/scheduler, fake E2E/recovery and full-record PG17 persistence/backup/restore. No product/Dockerfile redesign or installed production change. Fakes remain test-only and outside runtime images; scripts require isolated named staging targets. Hosted/private TLS/live Google/production activation remain separate gates. Package6C requires its own user request. Keep the personal schema001/source/credentials/services/pause unchanged.

## Canonical GitHub remote

This existing local repository and its intact history are canonical. Its permanent private collaboration/deployment remote is `origin`, `https://github.com/VT-13/fieldwork.git`; `main` tracks `origin/main`. Future work should edit this repository, verify, commit and push here. Reuse this GitHub repository for staging/Railway workflows; do not create another project, reset history, clone into new working directories or change origin without an explicit reason. Production databases, mail/resumes and credentials stay outside Git. GitHub connection alone never authorizes deployment, worker activation, OAuth changes or communication.
