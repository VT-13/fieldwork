# Fieldwork — implemented design language (Module 3)

Fieldwork is a personal field notebook for making useful professional connections. Warm paper, forest-green actions, precise ruled ledgers, a restrained serif display face and monospaced annotations distinguish it from a generic analytics dashboard. Hierarchy comes from type, alignment, whitespace and rules. Avoid gradients, decorative charts, tiled metric cards, school motifs, stock illustrations or imitations of another product.

## Tokens and type

The single token source is `frontend/app/globals.css`; shared components consume it.

| Role | Token | Implemented value |
|---|---|---|
| Canvas | `--canvas` | `#f4f3ee` |
| Reading paper | `--paper` | `#fffefa` |
| Secondary surface | `--surface` | `#ecece5` |
| Primary text | `--ink` | `#222c27` |
| Secondary text | `--muted` | `#606b63` |
| Rules | `--line` | `#d8dbd2` |
| Action / identity | `--forest` | `#234c3b` |
| Calm highlight | `--forest-soft` | `#e6eee4` |
| Held / pending | `--ochre`, `--ochre-soft` | `#856027`, `#f7eedc` |
| Failure | `--danger`, `--danger-soft` | `#9b3931`, `#fbefeb` |
| Keyboard focus | `--focus` | `#245f89` |
| Normal control shape | `--radius` | `5px` |
| Spacing | `--space-1` through `--space-8` | `4, 8, 12, 16, 24, 32, 48, 64px` |

System UI body at 14px/1.55; 13–14px email copy with generous leading; compact task labels 11–12px. Georgia display headings at 30–43px, 400 weight, restrained negative tracking; section headings 17–20px in system UI. SFMono/Consolas annotations at 9–10px, modest letter spacing. Fonts are local/system fallbacks: no Google Fonts import, remote request or font download. Do not set long paragraphs in the display or mono face.

Standard controls use 5px radius, statuses 3px, dialogs 8px; circles only for avatars/dots. Ruled sections are the default surface. Borders establish email paper and dialogs; soft elevation is reserved for the paper, persistent review decision and native dialogs. Standard spacing uses the shared scale; a few optical and viewport frame measurements remain explicit in CSS. Lucide icons are typically 14–18px; decorative icons are hidden from assistive technology, icon-only actions require an accessible name.

## Shell and hierarchy

216px quiet sidebar on wide screens; 195px on smaller desktops. Content max-width 1440px with 38px desktop gutters, 28px laptop, 19–22px mobile. At 800px the sidebar becomes a horizontally scrollable navigation rail. This rail may scroll locally; the page must never overflow horizontally. A persistent header offers Cmd/Ctrl+K search with actual navigation and prospect results. URL parameters retain view, selected company/message, campaign tab, query, stage and sort. Native links/controls preserve keyboard semantics.

Overview: one dominant next action, then conversations, then a ranked prospect register; a quieter side context explains pause/attention and factual progression. No fabricated performance charts. Rates need a real confirmed denominator; demo companies are excluded.

Prospect: identity/contact → relevance → sourced observations → communication → recorded outcome/next action. Desktop places relevance in side context near identity; mobile places the same shared FitContext before evidence. Quotes, source links and collection dates accompany claims. Unverified names, roles, distance, internship history and research details stay explicitly unknown/reported. Scores guide research, not eligibility or predicted hiring. Batch membership uses exact scope IDs.

Campaign: an authoritative pause banner precedes compact pipeline counts and task sections (targets/messages/responses/follow-ups). Distinguish recurring policy from independent scoped batch authorization. Pause/stop waits for server state, and failed updates retain the prior state. There is no cosmetic resume switch. Target rows provide URL-backed search/filter/sort and accessible detail links; mobile rows retain distance.

Review: a compact horizontal message rail replaces a second sidebar. One email paper sits beside company evidence and actual student experience at desktop/laptop widths. The decision bar precedes the reading surface and is sticky at the top on desktop; normal flow on small screens. It must not cover the editor. Textarea height follows both text and width so no final paragraph is hidden. Editing clears review/approval; attempted/sent/uncertain records stay locked. Review does not send, resume, or imply a fresh quality check. A separate practice desk labels self-tests and unsent exports clearly; external detector results are advisory and version-bound.

## States, access and motion

Status text and dots communicate the state together: “Approved · unsent”, “Sent receipt recorded”, “Delivery uncertain”, “Acknowledgment · held”, etc. Do not equate provider configuration, approval, accepted transmission, receipt reconciliation, inbox delivery or a reply. Uncertain delivery prohibits retry language. Show actionable errors near the affected section with Retry where appropriate; preserve form input on failed writes. Loading uses localized skeletons and accessible status announcements. Empty states explain the missing prerequisite and a useful next step.

Semantic headings, persistent input labels, native validation, associated form/sign-in errors, visible 3px focus rings and a skip link are required. Native `<dialog>` supplies modal focus containment/Escape, with explicit focus restoration, a named close action and background scroll lock. Search results are real links navigable by Tab/Enter. Unsaved forms warn on link navigation/unload; in-page anchors do not discard edits. Authentication transitions reload the private workspace to clear in-memory resources.

Interactions use 140ms color/border transitions; skeleton breathing is the only loading animation. `prefers-reduced-motion: reduce` removes animation/transitions and smooth scrolling. No decorative animation or new motion dependency.

## Verification and extension

Module 3 production renders are in `docs/module3/` at 1728×1117, 1280×900, 768×1024 and 390×844. The critique and refinement are recorded in `critique.md`. Chromium/Playwright tests include WCAG A/AA axe scans, keyboard dialogs/navigation, source context, review transitions, pause failures, responsive overflow and textarea resizing. Secondary profile/settings/responses/practice screens use the same language. This is tested coverage, not a claim of a complete screen-reader audit, Safari/WebKit coverage or provider end-to-end validation.

Reuse `components/ui.tsx`, the resource client and generated contracts. Prefer a new row/section within this language over a new visual framework. New API data must be validated against shared/generated contracts. Keep policy and authorization authoritative on the backend. No deployment, real provider mutation, campaign resume or real send is implied by a visual change.
