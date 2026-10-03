# Fieldwork repository

Read `docs/CODEBASE_MAP.md` and the relevant phase entry in `docs/PHASE_PLAN.md` before substantial changes. Read `BUG_AUDIT.md` for known risks; update it when evidence changes. Record architectural choices in `docs/DECISIONS.md`.

Repository-scoped skills live in `.codex/skills/`; select the relevant skill for design, frontend, architecture, security, outreach, or testing. Frontend changes must also follow `frontend/AGENTS.md` and installed Next.js documentation.

This repository is canonical after Module 1 reconciliation; the installed app remains the older, intentionally undeployed runtime. Read ARCHITECTURE.md and docs/MIGRATION_PLAN.md before release work. Verify scripts/source_manifest.py before packaging; never edit installed source as the canonical implementation. Module 2 security work is now authorized by its prompt; it does not authorize Module 3 or deployment. Read SECURITY.md for current session/OAuth/retention controls.

Module 1 tests use isolated temporary copies, an explicit DATA_DIRECTORY, empty provider/mail credentials, disposable SQLite, and disabled polling. Never use the personal database as a test fixture. Preserve historical receipts, suppressions, uncertain attempts, and the current pause. Engineering work alone does not authorize email sends, provider purchases, or starting the legacy worker. Existing explicit user authorization remains authoritative for actual outreach tasks.

Use search → targeted read → decision → patch → verification. Keep provider calls and runtime scheduling bounded and deterministic. Do not require an AI agent for ordinary scheduling, retries, quotas, or state transitions.
