# Available engineering capabilities — Phase 0

| Capability | Availability and decision |
|---|---|
| Codex skills | Bundled skill-creator used; other available document, design, OpenAI docs, plugin and hosting skills can be selected when needed. Six Fieldwork skills now exist under `.codex/skills/`. |
| Browser/computer | CUA browser/native-app tools available; Python Playwright already installed. Installed Google Chrome used headlessly for isolated smoke/screenshots. No browser download required. Safari remains available for user OAuth tasks. |
| Git | `/usr/bin/git`; local project repo initialized; no commits/remote created. |
| GitHub | Connector tools available; `gh` CLI unavailable; no project remote to inspect or publish. No extra installation needed for Phase 0. |
| JavaScript | Node v24.18.0 and npm; Next/TS lockfiles available. CI/Docker use Node 22; cross-version parity not validated locally. |
| Python | Python 3.13; installed Fieldwork venv includes pinned app dependencies, pytest and Alembic. Reused for sanitized snapshot checks; no live package changes. |
| Current docs | Installed Next.js documentation under `frontend/node_modules/next/dist/docs/`; web tools for authoritative upstream references; existing setup/integration docs require reconciliation. |
| Security | npm audit available; official PyPI pip-audit installed in isolated tooling venv, with PyYAML for bundled skill validation. No paid service or unrelated plugin installed. |
| Database | SQLite CLI and SQLAlchemy/Alembic available; psycopg installed. No psql executable/disposable PostgreSQL server or test URL. PostgreSQL CI configuration exists. |
| Deployment | Docker/compose, Railway, Render and Vercel CLIs unavailable. Dockerfiles/compose and launchd/macOS runtime exist. No container/hosted deployment tested. Desktop services were not restarted in this audit. |
| Other tools | GitHub PR check tools and connected Google apps available. Not invoked because this task needs local audit, not account changes. |

Missing optional CLIs are not Phase 0 blockers: existing connectors cover repository access, and Docker/hosted tooling must be installed/configured in the phase that actually tests a disposable deployment. Installing a system container daemon or publishing resources is not necessary to this baseline. Source reconciliation and release scope should precede that environment setup.

No Astra orchestrator package was found; expensive/free model choice is configuration for intelligence, while current agent scheduling is external to this repository. No paid provider/API usage occurred.
