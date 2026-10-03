# Fieldwork for this Mac

Open ~/Applications/Fieldwork.app or its Desktop shortcut. The app is a native WebKit window for the personal local workspace. Gmail links open in the default browser.

The API and production Next.js server run through LaunchAgents:
- local.vihaan.fieldwork.api
- local.vihaan.fieldwork.web

Both start at sign-in and restart after process exit. Closing Fieldwork only closes the window. Reply checks run every five minutes. The Mac must be logged in, awake and online. No sleep or security settings were changed. Sending remains the existing weekday Codex automation and caps; keeping the server alive does not independently discover or send new email.

Service definitions: ~/Library/LaunchAgents/local.vihaan.fieldwork.*.plist
Logs: ~/.local/share/fieldwork/logs/*-service.log
Launch services: ~/.local/share/fieldwork/start-personal.sh
Pause outreach using Pause ongoing outreach in the app. This leaves response tracking running.

To disable background services intentionally:
launchctl bootout gui/$(id -u)/local.vihaan.fieldwork.api
launchctl bootout gui/$(id -u)/local.vihaan.fieldwork.web

Remove or move the two LaunchAgent plist files if they should not load at next sign-in. Keep the app's data and backend/.env private. This is a locally built, ad-hoc signed personal app, not a notarized public distribution.

My email desk now offers Send test to myself. It sends a saved draft only to the authenticated Gmail/profile address, requires no LLM API key, and sends each saved version at most once. Unknown sends are held rather than retried. AI generation inside the editor is still manual/chat-assisted; no Gemini or ChatGPT plan connection was added.
