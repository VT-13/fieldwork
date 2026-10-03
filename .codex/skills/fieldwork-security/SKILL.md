---
name: fieldwork-security
description: Audit or change Fieldwork authentication, authorization, OAuth, credentials, externally supplied content, logging, privacy, or deployment security.
---

Use `BUG_AUDIT.md` to distinguish confirmed defects from unverified exposure. Current private operator sessions and separate CLI bearer access are personal installation boundaries, not tenant isolation. Require ownership checks and fail-closed authorization before any shared deployment; a loopback hostname is not authentication.

Keep OAuth state, PKCE, exact redirect validation, minimum scopes and mailbox identity checks. Store secrets outside source, artifacts and logs; encrypted durable credential storage is required for hosted accounts. Test rotation and revocation without printing tokens. Keep CSRF/origin defenses on mutations; render untrusted text safely and use appropriate security headers.

Use parameterized database operations. Validate URLs at the actual fetching boundary, including resolved addresses and redirects where direct fetching is introduced. Verify signed webhooks and dedupe delivery IDs. Validate upload size/type/content and isolate storage before enabling uploads. Bound body sizes, rate limits and expensive operations; sanitize provider exceptions and redact logs.

Student profiles and reply previews are private data. Minimize collection, define retention/deletion/export and account ownership, avoid unnecessary tracking, and do not send private drafts to external detectors without applicable user authorization. Verify backups and filesystem permissions. Audit dependency advisories without silently upgrading production.
