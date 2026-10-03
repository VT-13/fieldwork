# Module 3 visual critique — first rendered pass

Inspected the first dashboard and review renders in the chat (subsequent smoke runs refreshed those initial filenames) from production Next.js in Chromium (1440px). All company/contact/reply records are fictional QA fixtures; demo companies are excluded from metrics.

What works: the field-note identity is distinctive without decorative images; the dark green navigation, warm canvas and ruled ledgers establish clear hierarchy. The dashboard answers the next action and separates replies from aggregate outcomes. Company evidence and actual student experience are adjacent to the message on a wide desktop.

Problems to refine:

1. The review queue behaves like a second sidebar. At laptop widths it takes the space needed for evidence, forcing the central email and sources apart. Change its information architecture to a compact horizontal message rail, keeping email and evidence together at 1280px.
2. Approval is below a long message and competes with footer notes. Give the review decision a contained, persistent desktop action bar, with quality state and unsaved state beside the actions. Keep it in normal flow on mobile so it cannot cover the editor.
3. Fixed-height email text can hide the final paragraph and the QA label. Size the textarea to the actual text on load and edits; retain manual resizing. Long messages should expand the document, not hide important content in a small nested scroll area.
4. The prospect sidebar describes batch membership as unknown even when a database scope could establish it. Expose only the current scope's exact outreach IDs as an authenticated read field; show membership only when an ID matches.
5. The manual practice workflow has a second API helper and a handwritten response type. Preserve its operations but use the shared validated contract and protect newly written unsaved content too.

These are workflow and hierarchy changes, not a decorative spacing pass. Final screenshots and browser assertions will verify the revised layout at wide desktop, laptop, tablet and mobile widths.

Second inspection: the first persistent decision bar obscured the middle of the email in a full-page laptop capture. Moved the bar above the reading surface and retained sticky positioning at the top on desktop; it remains in normal flow on small screens. The editor now observes width changes as well as content, so narrowing an open page cannot hide its final lines. Axe also caught low contrast in the decorative sidebar note and a missing accessible name after the mobile search text disappeared; both were fixed in code, without suppressing rules.

Final mobile inspection: moved company relevance before evidence in the mobile document order, rather than leaving it after the communication/outcome forms. A shared FitContext provides the same data in the desktop side context and primary mobile flow; the duplicate presentation is CSS-hidden. Authentication transitions perform a full same-origin navigation so private in-memory resource data is not retained across sign-out/sign-in.
