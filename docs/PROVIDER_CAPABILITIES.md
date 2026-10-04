# Actual communication capabilities — canonical schema006, paused staging

SUPPORTED means implemented and regression-tested with fakes; it does not imply live registration, mailbox delivery or hosted readiness.

| Capability | Gmail | Outlook / Graph | SMTP |
|---|---|---|---|
| OAuth/account identity | SUPPORTED encrypted personal account lifecycle; NOT VERIFIED LIVE here | PARTIAL legacy development credential path only; no production account lifecycle | NOT IMPLEMENTED |
| Company send | SUPPORTED sole guarded delivery service, durable reservation/receipts; NOT VERIFIED LIVE | NOT IMPLEMENTED; transport mutations that could send are fenced | NOT IMPLEMENTED |
| Own-account self-test | SUPPORTED, explicit saved-version idempotency/shared total quota; NOT VERIFIED LIVE | NOT IMPLEMENTED | NOT IMPLEMENTED |
| Own-account drafts | SUPPORTED with explicit compose scope; no send receipt/quota; NOT VERIFIED LIVE | PARTIAL existing development draft contract, durable reservation; not supported in production configuration or verified live | NOT IMPLEMENTED |
| RFC/thread IDs | SUPPORTED RFC Message-ID, original thread/subject, References/In-Reply-To | PARTIAL draft/MIME compatibility; no company-send receipt/thread rollout | NOT IMPLEMENTED |
| Reply/bounce/opt-out sync | SUPPORTED bounded history/checkpoints/recovery and deterministic correlation; NOT VERIFIED LIVE | NOT IMPLEMENTED | NOT IMPLEMENTED |
| Send reconciliation | SUPPORTED unique exact positive Sent evidence; absence stays held; NOT VERIFIED LIVE | NOT IMPLEMENTED | NOT IMPLEMENTED |
| Follow-ups | SUPPORTED deterministic168-hour preparation, review, policy/preflight, cancellation; NOT VERIFIED LIVE | NOT IMPLEMENTED | NOT IMPLEMENTED |
| Watch/webhooks/push | NOT IMPLEMENTED; bounded polling/history is used | NOT IMPLEMENTED | NOT IMPLEMENTED |

Gmail capabilities use the authenticated connected identity, not a plaintext token setting. Provider acceptance is not guaranteed inbox delivery. No read/label mutation, automatic reply, calibrated sentiment/hiring classifier or AI-detector integration is introduced. Historical Graph sending helpers are not a supported release path and cannot transmit through the canonical Mailbox transport, including query-suffixed send URLs.

API behavior is based on Google's primary [history synchronization](https://developers.google.com/workspace/gmail/api/guides/sync), [message search](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list) and [threading requirements](https://developers.google.com/workspace/gmail/api/guides/threads). Live OAuth, actual API plans, throttling and Gmail's retention of a supplied RFC identifier still require release verification. Bounded backfill intentionally does not claim full historical-mailbox coverage.

Module6 proved the full authenticated production-build/actual-worker workflow with a fake transport on PostgreSQL17.11, including self-tests, thread continuity, reply cancellation, exact Sent reconciliation, shared quota and rollover. Direct simulated401/403/429/500/503 responses map to safe failures;403 is conservatively treated as authorization rejection. The native soak was181 seconds, not proof of long-term hosting or delivery. **OAuth, own-account draft/send, real Google RFC retention/thread behavior and live history remain NOT VERIFIED LIVE.** Existing installed plaintext authorization was deliberately not reused or changed. Container/platform and lossless installed-data migration gates remain open. No deliverability/inbox-placement claim follows from these tests.

## Package6D live-validation preflight

Historical preflight: hosted Package6C passed, while Gmail live statuses were then NOT VERIFIED LIVE. Dedicated OAuth pre-flight is READY: separate staging project/client, exact callback, minimum send/read/compose scopes, server-side credentials and explicit A/B identities are configured. Live Package6D is paused at owner Google account selection/consent; no draft/send/reply/scan has occurred. The retired exposed client credential is independently rejected by Google as invalid_client. See package6d/verification.json. Existing production OAuth was neither reused nor changed. Draft compose permission and a separate controlled reply identity are needed to test those capabilities honestly; self-tests themselves do not create Outreach records. Outlook status is unchanged.

## Package6D current live evidence (supersedes preflight-only status)

Railway staging only; company outreach remains unverified and paused. The opt-in expiring two-account validation reuses the normal self-test ledger/transport and cannot authorize company recipients. Public verification excludes private IDs/credentials; exact receipts remain in staging.

| Gmail capability | Actual status |
|---|---|
| OAuth, state, PKCE, hosted callback/token exchange | VERIFIED LIVE |
| Google-derived Account A identity | VERIFIED LIVE |
| Authenticated Gmail API | VERIFIED LIVE; profile and exact synthetic messages |
| Canonical encrypted token storage | VERIFIED LIVE |
| Token refresh | VERIFIED LIVE; naturally expired credentials refreshed through canonical access and encrypted storage; no forced expiry |
| Own-account unsent draft | VERIFIED LIVE; exactly one |
| Authorized scoped A-to-B test send | VERIFIED LIVE; exactly one |
| Provider message ID | VERIFIED LIVE |
| RFC Message-ID | VERIFIED LIVE; Gmail rewrote supplied identifier; reserved and observed identities both retained |
| Gmail thread ID / SENT label | VERIFIED LIVE |
| Sent reconciliation / replay | VERIFIED LIVE against existing accepted receipt; zero duplicate transmissions |
| Controlled reply synchronization | VERIFIED LIVE; owner-authorized existing reply, correct thread/test packet, one immutable test_reply Event, deduplication and held-to-cancelled state |
| History cursor / checkpoint | VERIFIED LIVE; bounded incremental sync and persisted checkpoint; replay two requests |
| Worker restart continuation | VERIFIED LIVE; exact receipt/Event/cursor preserved across new worker process and incremental continuation |
| Disconnect/reconnect | VERIFIED LIVE; upstream revocation/local fail-closed, exact history preservation, same A identity and one Integration after owner reconnect, incremental sync resumed |

Default own-account self-tests, unknown-delivery holds and company delivery policy are unchanged. Observed RFC rewriting is normalized only with an exact accepted API message/thread receipt and full matching Sent evidence; subject similarity cannot authorize reconciliation. No live company delivery, bounce, follow-up send or inbox-placement assertion follows from this synthetic test.

Package6D final result: **PASS**. The current live evidence table above supersedes the historical preflight/Module6-only claims. Owner reconnect completed and current Gmail identity/storage/connection were reverified. Exactly one draft remains unsent, one original self-test remains Sent and one owner reply Event remains immutable. No company communication was authorized or tested; company delivery/bounce/follow-up status must not be promoted to live-verified from this protocol. Final recurring outreach is PAUSED; Package6E has not begun.
