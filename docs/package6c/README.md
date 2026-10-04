# Package6C — hosted TLS gate PASS

Actual target: https://fieldwork-staging.up.railway.app, existing Railway project `fieldwork-staging`, isolated `staging` environment, canonical `VT-13/fieldwork` main. Schema006, PG17.11, separate private API/worker and public production Next. This supersedes the earlier access-only BLOCKED artifact; full native/container evidence was not repeated or substituted for hosted checks.

## Executed hosted verification

- Python SSL default trusted CA context with hostname validation: TLS1.3, valid chain/hostname, Let's Encrypt YE2 issuer, SAN and validity dates in verification.json. No trust bypass. HTTP returns301 to exact HTTPS URL. Chromium/WebKit/Firefox used normal certificate checks and no HTTPS ignore flag. Browser requests contained no mixed-content, localhost or private Railway hostname URLs.
- Public canonical Host works; unexpected Host safely fails at Railway ingress. Direct private frontend probe using raw node:http separately confirms400 for hostile Host. Spoofed X-Forwarded-Host/Proto/Forwarded cannot change the configured HTTPS redirect, Origin rejection or stable callback. API starts with `--no-proxy-headers`; configured origin, not client forwarding metadata, owns cookies/absolute URLs.
- Actual HTTPS login cookie: Secure, HttpOnly, SameSite=Lax, Path=/, host-only,43200 seconds. Authenticated page/read/refresh work. Forged/malformed sessions fail401, logout revokes copied prior cookie, and a separate synthetic session expired in the staging DB fails401. No cookie/password values are exported. Active bearer cookies are not claimed to be non-transferable.
- Unauthenticated profile/runtime/jobs/integration/export/session reads reject401. Valid-origin synthetic profile PUT persists; hostile/null/missing Origin and spoofed origin reject403. Form body rejects415. Next OPTIONS returns204 with no CORS allow headers; it does not grant browser cross-origin access. No credentialed wildcard CORS. Public health is only `{status:ok}`; detailed status is authenticated. Debug/docs/fixtures/signup/fake endpoints do not expose data (404, or400 for dotted proxy paths).
- One narrow confirmed fix: public Next omitted the API's existing HSTS and Permissions-Policy. Commit `0cc379c1892958742e086e7625df146368d8e495` applies the same one-year HSTS and denied camera/microphone/geolocation policy globally. Actual Railway Docker production build/redeploy and HTTP recheck passed. nosniff, DENY and no-referrer also verified. CSP is intentionally not implemented; no arbitrary new CSP was introduced.
- Chromium, WebKit and Firefox completed real hosted login/refresh, overview, campaign, prospects/detail, outreach review, settings/Gmail connection display, synthetic profile form save, dialog keyboard open/Escape/focus restoration, desktop/mobile overflow checks, authenticated runtime and logout. No mocked API responses, provider clicks, approval or send. Final runs had zero unexpected page/console/API errors. Initial WebKit rapid-refresh prefetch cancellations were traced to the harness reloading before initial requests settled; waiting for networkidle resolved them without an application change. Expected navigation cancellations remain separately counted.
- Railway config confirms frontend only public; API/worker/PG have no public HTTP/custom domain/TCP proxy. Frontend variables contain no private keys. Fetched1000-line build/deployment log windows and current browser JS assets were scanned in memory against staging credentials and sensitive markers: zero matches, no stack traces, no exposed source-map directives. Existing Docker secret exclusions and runtime injection are unchanged.
- Real hosted worker health/scheduler/current heartbeat/schema/database reachability pass. Concurrent PG connections verify duplicate leadership refusal. `railway restart -s worker -e staging --yes --json` passes recovery; synthetic company/message records persist. Communication has no jobs, zero attempts/network units/Usage rows, Gmail disconnected and policy explicitly paused/stopped with paid permission false. No real provider keys exist.

The staging-only synthetic profile, one `.example` demo company/contact/evidence and one unapproved draft remain for later testing. Profile edits invalidate the draft review; company demo/pause/manual/dry-run/no credentials independently prevent real mail. No QA/test runtime fallback was enabled. Session-expiry mutation touched only the verifier's own synthetic staging session. No real Google authorization was started.

## Actual commands and evidence

Private helpers/scripts and synthetic screenshots reside under `/private/tmp/fieldwork-package6c/`; they read owner-only staging credentials in memory and never print them. Test scripts are verification artifacts, not runtime services.

```sh
/private/tmp/fieldwork-module6/venv/bin/python /private/tmp/fieldwork-package6c/http_verify.py
python3 /private/tmp/fieldwork-package6c/runtime_check.py
PLAYWRIGHT_BROWSERS_PATH=/private/tmp/fieldwork-module6/browsers node /private/tmp/fieldwork-package6c/browsers.cjs chromium
PLAYWRIGHT_BROWSERS_PATH=/private/tmp/fieldwork-module6/browsers node /private/tmp/fieldwork-package6c/browsers.cjs webkit firefox
python3 /private/tmp/fieldwork-package6c/proxy_check.py
python3 /private/tmp/fieldwork-package6c/privacy_check.py
railway restart -s worker -e staging --yes --json
python3 /private/tmp/fieldwork-package6c/final_runtime.py
npm run lint # frontend
npm run typecheck # frontend
python3 scripts/source_manifest.py verify
```

First typecheck encountered ignored duplicate generated `* 2.ts` files from the local build cache; moving them outside `.next/types` restored a clean typecheck without changing source. Initial probe expectations for Next OPTIONS204/openapi400 and explicit Host via Node fetch were corrected transparently. Rate limits were neither disabled nor reset; checks waited for their normal window. The seed helper intentionally accepts only an empty named staging target; do not rerun it over historical data. Do not print Railway variables/config JSON or private helpers' credential file.

Safe public results are consolidated in verification.json. Installed production preservation uses module6_preserve.capture() before/after, read-only: source/schema/counts/credential/service definitions and recurring pause unchanged. Source manifest verified after the fix and handoff docs. No live DB migration, installed worker change, old sender change, OAuth change, company email or paid provider call.

## Boundary

Hosted TLS gate PASS; Package6D is ready for a separately requested live-Google validation. Exact callback: `https://fieldwork-staging.up.railway.app/api/integrations/gmail/callback`. This verification did not begin6D. Overall production release/cutover remains NOT READY until the remaining live-provider/activation gates and explicit rollout authorization. Trial hosting expiry/credits remain a hosting lifecycle limitation, not a certificate or access-control failure.
