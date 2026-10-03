---
name: fieldwork-frontend-quality
description: Implement or review Fieldwork React/Next.js components, frontend state, API clients, accessibility, performance, and browser behavior.
---

Follow `frontend/AGENTS.md`; use installed Next.js docs for version-specific APIs. Keep strict TypeScript; validate untrusted API data instead of relying on casts. Extract reusable components and typed API contracts when behavior repeats, without building an unused component framework.

Handle pending, success, empty, stale, validation and network-error states. Cancel obsolete requests, prevent overlapping polling and duplicate mutations, preserve unsaved edits, and avoid all-screen refreshes for unrelated changes. Keep secrets server-side; mutations retain origin checks and authorization.

Use semantic controls, associated labels, visible focus, accessible status announcements, keyboard dialogs with focus restoration, and responsive layouts. Measure unnecessary requests, render work and asset costs before optimizing.

Run typecheck and production build for frontend changes; use relevant browser regressions and desktop/mobile screenshots for interaction/layout changes. Record failures honestly. Never click real send or mutate the personal profile during QA; use a disposable API and provider mocks. Coordinate substantial visual work with `fieldwork-product-design`.
