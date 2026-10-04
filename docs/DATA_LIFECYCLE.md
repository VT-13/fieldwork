# Personal data lifecycle

Only the authenticated operator can export or delete application data. These operations do not remove messages already sent from Gmail or a recipient's mailbox.

| Category | Use / storage | Removal / retention |
|---|---|---|
| Profile and resume text | Structured Profile facts used in reviewed messages; no binary upload | `/privacy/delete` scope `resume`, confirmation `DELETE RESUME`, removes resume and derived cover snippets, marks facts unverified and cancels pending approvals |
| Generated unsent messages and desk copies | Outreach / State | Scope `generated`, confirmation `DELETE GENERATED DATA`, cancels pending messages, erases unsent content, deletes desk artifacts and cached content; accepted receipt rows remain |
| Personal content | Profile, sent/unsent bodies, response previews, derived cache/desk | Scope `personal`, confirmation `DELETE PERSONAL CONTENT`, erases student profile and message bodies, clears previews, removes local OAuth access, revokes browser sessions and pauses all queued communication |
| OAuth credentials/verifiers | Encrypted Integration/OAuthGrant | Disconnect deletes local tokens and outstanding grants; expired grants pruned; upstream revocation attempted and failure reported |
| Inbound previews | State response record, at most 3000 characters | Hourly maintenance clears preview/subject after RESPONSE_PREVIEW_RETENTION_DAYS (default30, maximum90); no mailbox labels/read status are changed |
| Cache | Bounded provider data | Hourly maintenance deletes expired entries; personal/generated deletion clears all caches |
| Sessions/rate state | Hashed tokens and minimal counters | Expired grants/sessions and old rate buckets are pruned; logout/password change invalidate authorization |
| Research/contact data | Company/Contact/Evidence provenance | Retained for the active opportunity history; deleting generated messages does not erase company/contact records |
| Delivery/audit/suppression | Provider IDs, original linkage, status, times, reviewed fingerprints | Retained through deletion and disconnect so prior outreach/opt-outs cannot silently become eligible again; no credentials or duplicated message bodies are stored in the ledger |

Deletion requires exact confirmation and fails while communication is in flight/unknown or provider acceptance is awaiting confirmation. It pauses recurring/manual outreach, cancels queued jobs and preserves receipt linkage. Personal deletion records a content fingerprint before erasing bodies; it retains contact/prospect IDs and minimal historical metadata. This is intentional content erasure, not a claim of physical database/backup erasure or deleting all operational history. For complete installation disposal, first archive needed receipts, disconnect/revoke access, then retire the encrypted data volume and its separately protected keys/backups according to the operator's retention policy. No remote account signup/deletion exists.

`GET /privacy/export` returns personal profile, research, message, policy, job and operational records as authenticated JSON. It excludes integration ciphertext, OAuth grants, session tokens and rate buckets. Treat the downloaded export as private. Privacy changes are audited with DomainTransition; nothing is transmitted to external detectors during deletion/export.

New drafts and profile facts stay until the operator removes them; no speculative automatic deletion of current opportunities is enabled. Hourly maintenance runs with the API, independent of the outreach pause, and does only the bounded retention tasks above. If the API is stopped, maintenance resumes on its next start. Backups can contain older deleted content; follow BACKUP_RESTORE.md before restoring and expire copies according to the configured rotation. External provider retention is outside this application's local deletion guarantees.

Immutable historical receipt files and minimal campaign-progress State are preserved separately; the deletion API does not rewrite these artifacts. They may contain older personal content, so complete disposal also requires the explicit archive/retire and encrypted-backup expiration procedure. The Integration email remains as an identity fence after disconnect; its tokens are erased. No API claims to delete a remote Google account or all physical audit history.

## Module 4 derived intelligence

Candidate observations and ContactObservation rows retain reported values, provider/source provenance, retrieval times and conflicts; accepted candidates link to canonical companies. Evidence stores short source quotations, dates, quality and hashes, rather than whole web pages. The existing bounded provider cache can contain transient page text and follows the cache retention/deletion rules above.

StudentFact text and Generation exact subject/body/review are personal derived content. Export includes these records; generated/personal deletion erases their content while preserving minimal generation/reference/linkage metadata. Resume deletion marks facts unverified; current-profile-hash validation prevents prior facts approving new messages. No third-party detector export is added. Historical provider receipts, suppressions and uncertain-delivery holds remain intact.
