# Fieldwork repository

Read `docs/CODEBASE_MAP.md` and the relevant phase entry in `docs/PHASE_PLAN.md` before substantial changes. Read `BUG_AUDIT.md` for known risks; update it when evidence changes. Record architectural choices in `docs/DECISIONS.md`.

Repository-scoped skills live in `.codex/skills/`; select the relevant skill for design, frontend, architecture, security, outreach, or testing. Frontend changes must also follow `frontend/AGENTS.md` and installed Next.js documentation.

This repository is canonical after Module 1 reconciliation; the installed app remains the older, intentionally undeployed runtime. Read ARCHITECTURE.md and docs/MIGRATION_PLAN.md before release work. Verify scripts/source_manifest.py before packaging; never edit installed source as the canonical implementation. Modules 1–3 are implemented in canonical source. Module 3 frontend work was authorized by its prompt; it does not authorize Module 4 or deployment. Read SECURITY.md for current session/OAuth/retention controls.

Module 1 tests use isolated temporary copies, an explicit DATA_DIRECTORY, empty provider/mail credentials, disposable SQLite, and disabled polling. Never use the personal database as a test fixture. Preserve historical receipts, suppressions, uncertain attempts, and the current pause. Engineering work alone does not authorize email sends, provider purchases, or starting the legacy worker. Existing explicit user authorization remains authoritative for actual outreach tasks.

Use search → targeted read → decision → patch → verification. Keep provider calls and runtime scheduling bounded and deterministic. Do not require an AI agent for ordinary scheduling, retries, quotas, or state transitions.

## Module 3 handoff

Use the final product-design reference, frontend-quality skill and `docs/module3/README.md`. Four flagship views, generated/validated API contracts and lint/typecheck/build/browser gates are implemented. The installed runtime remains intentionally undeployed and recurring outreach paused. Module 4 needs a separate user prompt; it should build against these existing UI/policy/security patterns rather than start another audit or design system.

## Module 4 handoff

Module4 is implemented and verified in canonical source only. Read docs/module4/README.md and verification.json for bounded candidate/research/evidence/ranking/generation ownership and limits. Keep the shared job/operation/usage/policy boundaries, deliberate candidate acceptance, exact evidence/profile references, review gate and immutable history. The installed personal runtime, receipts and recurring pause are unchanged. Module5 requires its own user prompt; Module4 does not authorize deployment, real provider calls, worker activation or mail.
