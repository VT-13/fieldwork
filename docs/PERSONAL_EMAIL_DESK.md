# Your personal email desk

This is a single-person workflow. **MANUAL_MODE=true** is now the default. It blocks all paid research, contact verification and model calls, and disables live sending regardless of DRY_RUN. The app does not add a drafting charge or require a paid research subscription to use the desk. Your existing chat/service plan and any independently chosen external service still have their own limits.

The primary page is **My email desk**. You and the assistant write the email in the current conversation, save it locally, check the company claims, obtain a real detector result, and make your own final decision. This is a manual agent workspace, not a fake autonomous background AI. A copied agent brief contains your voice notes, saved draft and evidence so you can ask the assistant to work on a specific email without configuring a paid API.

## Voice

In My profile, add your tone preferences and a short paragraph or email that you actually wrote. The writing prompt favors a genuine company-specific question, a modest contribution, contractions, and direct language. It does not invent anecdotes or insert deliberate errors to game a detector.

## Central review

1. Save the email and its company facts/source links.
2. Use **Copy agent brief** to hand the draft to the assistant in this task.
3. Read the local style checklist. It detects a few stock phrases and long sentences; it is **not an AI detector** and supplies no AI probability.
4. Open GPTZero, paste the saved email body and scan it. Record the actual result. Private contact details should be omitted from the detector input; note any redactions in the result.
5. Read the email aloud. Confirm facts, your voice, the intended recipient, and that you considered the detector feedback. Mark reviewed.
6. An edit to subject/body/company/evidence/fictional status invalidates the old result and sign-off. Previous versions are kept locally (last ten).

Detector scores are advisory, not a proof of authorship. The [GPTZero FAQ](https://gptzero.me/faq) explains its limitations. A short email can be assessed differently by different tools. There is no pass-score laundering and no automatic rewrite loop that keeps scanning until a desired percentage appears.

## Dry-run mailbox workflow

The recipient is always **your own profile email**, never the company. Subject begins `[DRY RUN]`. Fictional examples include a visible fictional-practice label.

- **Download unsent email**: creates an `.eml` with `X-Unsent: 1`, addressed to you. Opening behavior varies by mail client; this operation itself does not send.
- **Open Gmail compose**: opens an editable compose window in Gmail, addressed to you. You sign in if necessary. It is not marked as automatically saved by this app.
- **Save to connected mailbox**: the worker calls only Gmail draft creation/update or Graph draft creation/update. It does not call a send endpoint. Requires this app's OAuth credentials; a Codex connector does not automatically hand OAuth tokens to a separate local app.

The create intent is saved before the provider write. A timeout becomes uncertain; no blind retry creates duplicate drafts. Saving the same version twice is idempotent; a changed version updates the existing provider draft when a known draft ID is available.

### OAuth scopes for automatic draft saving

- Gmail needs `gmail.compose` to create drafts, plus `gmail.readonly` for the existing mailbox identity/sync workflow. Gmail's compose scope also permits sending at the provider level; this app's manual-mode gates still block sending.
- Outlook needs `User.Read`, `Mail.ReadWrite` and `offline_access`. `Mail.Send` is needed only if you later opt into live delivery.
- Granting these scopes must be done in the provider's consent screen. Having browser/computer access does not make this app connected. No tokens are copied from browser storage.

Provider references: [Gmail drafts.create](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.drafts/create), [Microsoft Graph create draft](https://learn.microsoft.com/en-us/graph/api/user-post-messages?view=graph-rest-1.0).

## Current sample check

A fictional robotics email was checked in GPTZero through the browser during this update. The displayed model was **4.10b**; the result was **100% AI, 0% mixed, 0% human**, on 135 words / 798 characters. This is recorded as observed feedback, not presented as a successful human-authorship test. It was not sent to a company. The detector flagged several polished, generic closing sentences; a real writing sample from you remains the best input for voice editing.
