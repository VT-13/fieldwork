# Module 1 source reconciliation

All 27 Phase 0 discrepancies were reviewed. Runtime source hashes still match the handoff. These are intentional source behaviors, not operational state. Production depends on the campaign/inbox/send controls; tests and docs support their preservation. No database, credentials, receipts, installed binary, caches or historical driver was imported. Runtime remains unchanged; schema/source rollout is separately gated by the migration plan.

| Path | Decision and behavior | Proof |
|---|---|---|
| `backend/app/mail.py` | Preserve runtime behavior; route execution/state through canonical policy, ledger and provider boundaries | Architecture + workflow + scheduled + response/self-test/campaign tests |
| `backend/app/worker.py` | Preserve runtime behavior; route execution/state through canonical policy, ledger and provider boundaries | Architecture + workflow + scheduled + response/self-test/campaign tests |
| `backend/app/responses.py` | Preserve runtime behavior; route execution/state through canonical policy, ledger and provider boundaries | Architecture + workflow + scheduled + response/self-test/campaign tests |
| `backend/app/config.py` | Preserve runtime behavior; route execution/state through canonical policy, ledger and provider boundaries | Architecture + workflow + scheduled + response/self-test/campaign tests |
| `backend/app/scheduled_send.py` | Preserve runtime behavior; route execution/state through canonical policy, ledger and provider boundaries | Architecture + workflow + scheduled + response/self-test/campaign tests |
| `backend/app/core.py` | Preserve runtime behavior; route execution/state through canonical policy, ledger and provider boundaries | Architecture + workflow + scheduled + response/self-test/campaign tests |
| `backend/app/campaign.py` | Preserve runtime behavior; route execution/state through canonical policy, ledger and provider boundaries | Architecture + workflow + scheduled + response/self-test/campaign tests |
| `backend/app/self_test.py` | Preserve runtime behavior; route execution/state through canonical policy, ledger and provider boundaries | Architecture + workflow + scheduled + response/self-test/campaign tests |
| `backend/app/main.py` | Preserve runtime behavior; route execution/state through canonical policy, ledger and provider boundaries | Architecture + workflow + scheduled + response/self-test/campaign tests |
| `backend/tests/conftest.py` | Import regression suite; align fixtures with centralized policy where necessary | Isolated pytest suite |
| `backend/tests/test_scheduled.py` | Import regression suite; align fixtures with centralized policy where necessary | Isolated pytest suite |
| `backend/tests/test_self_test.py` | Import regression suite; align fixtures with centralized policy where necessary | Isolated pytest suite |
| `backend/tests/test_workflow.py` | Import regression suite; align fixtures with centralized policy where necessary | Isolated pytest suite |
| `backend/tests/test_worker.py` | Import regression suite; align fixtures with centralized policy where necessary | Isolated pytest suite |
| `backend/tests/test_responses.py` | Import regression suite; align fixtures with centralized policy where necessary | Isolated pytest suite |
| `backend/tests/test_campaign.py` | Import regression suite; align fixtures with centralized policy where necessary | Isolated pytest suite |
| `backend/scripts/oauth_setup.py` | Preserve existing OAuth setup source; no credentials copied or OAuth run | Exact runtime SHA-256 match |
| `frontend/app/Campaign.tsx` | Import existing campaign/inbox/review UI unchanged; no redesign | Typecheck and production build |
| `frontend/app/ResponseInbox.tsx` | Import existing campaign/inbox/review UI unchanged; no redesign | Typecheck and production build |
| `frontend/app/ReviewDesk.tsx` | Import existing campaign/inbox/review UI unchanged; no redesign | Typecheck and production build |
| `frontend/app/page.tsx` | Import existing campaign/inbox/review UI unchanged; no redesign | Typecheck and production build |
| `desktop/local.vihaan.fieldwork.api.plist` | Preserve personal launch templates/shell unchanged; not installed or executed | Exact runtime SHA-256 match |
| `desktop/local.vihaan.fieldwork.web.plist` | Preserve personal launch templates/shell unchanged; not installed or executed | Exact runtime SHA-256 match |
| `desktop/README.md` | Preserve personal launch templates/shell unchanged; not installed or executed | Exact runtime SHA-256 match |
| `desktop/Fieldwork.swift` | Preserve personal launch templates/shell unchanged; not installed or executed | Exact runtime SHA-256 match |
| `README.md` | Merge personal response-inbox instructions; retain canonical handoff and add release caveat | Document reconciliation |
| `start-personal.sh` | Preserve personal launch templates/shell unchanged; not installed or executed | Exact runtime SHA-256 match |

## Intentional changes

Unknown delivery now blocks every communication path; fresh unthreaded contact replies stop follow-ups; accepted receipts persist before confirmation. Shared database claims replace disconnected send locks. The worker follows one final follow-up, never its old 7/14/30 loop. Invalid transitions fail explicitly. Self-tests remain independent own-account actions but count toward total quota. These safety corrections preserve intended operation rather than preserving known defects.

The canonical manifest records every tracked application/test/desktop/script artifact. CI rejects drift; source-only bundle creation requires committed source. Regression tests reject changed, missing and newly added auto-discovered modules/routes. Future deployment verifies the same manifest; manual edits to installed code are not canonical source.

Existing operational JSON/SQLite/credential files remain outside Git and source bundles. Historical State/file receipts are read as evidence, never used as replay instructions. Migration 002 adds records without rewriting old tables. Preservation evidence is recorded as hashes/counts, not private message contents.
