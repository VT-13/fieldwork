# Fieldwork repository

Read `docs/CODEBASE_MAP.md` and the relevant phase entry in `docs/PHASE_PLAN.md` before substantial changes. Read `BUG_AUDIT.md` for known risks; update it when evidence changes. Record architectural choices in `docs/DECISIONS.md`.

Repository-scoped skills live in `.codex/skills/`; select the relevant skill for design, frontend, architecture, security, outreach, or testing. Frontend changes must also follow `frontend/AGENTS.md` and installed Next.js documentation.

This workspace and the installed app differ. `docs/baseline/source-drift.json` lists the source differences. Do not deploy this workspace over the installed app without reconciling them. Phase 0 performs no product rewrite; Phase 1 has not begun.

Baseline tests use isolated temporary copies, fake HOME, empty provider/mail credentials, disposable SQLite, and disabled polling. Never use the personal database as a test fixture. Preserve historical receipts, suppressions, uncertain attempts, and the current pause. Engineering work alone does not authorize email sends, provider purchases, or starting the legacy worker. Existing explicit user authorization remains authoritative for actual outreach tasks.

Use search → targeted read → decision → patch → verification. Keep provider calls and runtime scheduling bounded and deterministic. Do not require an AI agent for ordinary scheduling, retries, quotas, or state transitions.
