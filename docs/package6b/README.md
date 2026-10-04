# Package6B — runtime-container gate PASS

Package6A/FW-026 was verified RESOLVED before this work. Canonical migration head is006. Only the runtime-container gate is closed. No application redesign or product feature, production installation/database migration, real provider access, real outreach, paid API use, recurring-policy change or Package6C work occurred.

## Actual target runtime

An isolated Colima0.10.3/Lima2.2.1 VZ profile ran Ubuntu24.04.4 LTS, kernel6.8.0-117-generic, Linux ARM64, two CPUs and4GiB RAM. Docker Engine29.5.2, private Docker CLI29.8.2, Compose5.6.0 and Buildx0.37.2 were used. No login service was installed or existing Docker context activated. Official [Colima installation](https://colima.run/docs/installation/) and [Lima releases](https://github.com/lima-vm/lima/releases) supplied tools; Colima/Lima/Compose downloads were checksum-verified. No existing personal Fieldwork service was stopped or replaced.

Both declared Dockerfiles built from a sanitized clean context, without node_modules, private .env, SQLite databases, caches or installed source. `docker build --no-cache` used python:3.13-slim and node:22-alpine. Runtime versions are Python3.13.16, Node22.23.3, Next16.3.8 and PostgreSQL17.11. Production backend pins installed successfully, pip check passed, pytest/Playwright were absent. API/web run as UID1000; PostgreSQL server runs as postgres. Build-stage npm development dependencies are not production browser/test requirements. Image IDs are in image-scan.json; tags are staging-only. ARM64 is the executed architecture; amd64 is not claimed.

The original compose.yaml was used from a clean temporary copy with a **staging-only** override: the same migrate/API/web/worker commands/images, isolated `fieldwork6b_e2e` database, named PostgreSQL volume, no published API/database port, and web bound to127.0.0.1:13066. Web alone has an edge bridge plus the internal network; API/worker/PG are internal only. Starting web on only an internal network provided no ingress in this Docker runtime, so a separate edge network was added to the test override. No production network/firewall change occurred.

Initial production-configured startup had DRY_RUN=true, MANUAL_MODE=true, RESPONSE_POLL_ENABLED=false, AUTO_APPROVE=false, no profile/integration/jobs/attempts and no QA flags/provider keys. Schema readiness, API health, separate worker health and integrated scheduler heartbeats passed. Starting containers neither seeded data nor resumed communication. The worker remains an explicit Compose profile.

## Container E2E and durability

Existing Module6 fake-provider logic was reused. Only the test bootstrap gained strict Linux fences: `/staging/fieldwork6b`, host `db:5432`, exact database `fieldwork6b_e2e`, explicit disposable-only flags and student@example.com. It is **copied into test containers**, never loaded or included in production images. No QA application endpoint or production fixture switch was added. API and worker have no external network route; provider seams are fixed fakes. Synthetic connection/client/model values are injected only at runtime. Enabling the isolated fake campaign for E2E is not a production pause change; it is returned to paused afterward.

Actual production Node container → Python API container → separate worker container → PG17 passed profile/discovery/acceptance/contact/evidence/ranking/personalization/review/approval/fake-send, distinct168-hour follow-up and reply cancellation. Forced worker termination preserved unknown; missing evidence held; exact Sent evidence reconciled without resend. A reply immediately before follow-up reservation canceled it with zero transmission. Shared daily quota and timezone rollover passed. Five total **fake** transmissions, zero real ones.

Two worker containers competing on the same database executed one newly queued safe-read job once. Independent Linux processes verified the PG advisory leader fence. Duplicate scheduler ticks retained exact job IDs. SIGTERM exited0, worker health/restart passed, and web/API/worker/PG restarts added no fake transmissions. App restart comparisons exclude only volatile process heartbeat/identity, safe-read Job lease state and the monotonically advancing ExecutionLock.version coordination counter; durable domain/history tables match. PG restart and backup/restore comparisons included **every ORM table exactly**, including coordination state, schema006, policy, sessions, integration ciphertext, messages, receipts, unknown history and provenance. pg_dump17/pg_restore17 restored into a fresh disposable database; dump mode0600 and digest were checked.

A separate disposable QA image supplies pytest, leaving runtime images untouched. Sixteen targeted Linux schema/configuration/concurrency/worker/scheduler regressions pass with zero skips. One host Chromium smoke through the actual Linux stack passes login, Secure session and authenticated profile/runtime; only the ephemeral leaf SPKI is permitted, without changing system trust. This is not another visual/design/browser suite or hosted certificate validation.

Full saved production images were scanned, including **decompressed file contents of every layer**, image configuration and app paths. No synthetic runtime secret/canary match, baked secret variable, QA bootstrap/test tree or personal SQLite/.env path was found. This includes browser assets. Secrets were never build arguments and never copied from the personal runtime. Exact image IDs, layer counts and scan scope are recorded.

## Reproduce the executed steps

Use a separately provisioned isolated Docker daemon. The actual Mac tooling was in `/private/tmp/fieldwork-package6b/tooling`; these are test-tool paths, **not production runtime requirements**. No Homebrew/Desktop service is required by the app. The staging VM/data is disposable and was removed after verification.

```sh
export FIELDWORK_STAGING_ROOT=/private/tmp/fieldwork-package6b
export FIELDWORK_DOCKER_BIN=/private/tmp/fieldwork-package6b/tooling/bin/docker
export DOCKER_HOST=unix:///Users/vihaantirumala/.colima/fieldwork6b/docker.sock
export DOCKER_CONFIG=/private/tmp/fieldwork-package6b/docker
```

The daemon was started using the private tool PATH with:

```sh
colima start --profile fieldwork6b --vm-type vz --cpu 2 --memory 4 --disk 12 --mount-type virtiofs --activate=false
```

For another host use its explicit isolated Docker socket/tool and a fresh temporary `fieldwork-package6b` directory. Private Docker config points cliPluginsExtraDirs to the private Compose/Buildx binaries. Python orchestration uses the clean locked test venv; no such test dependencies are required by runtime images. The first invocation must be on a fresh staging project; scripts refuse overwriting an existing context or replaying populated E2E data.

The helpers preserve the actual executed commands from the initial temporary scripts:

```sh
<clean-python> scripts/package6b_tools.py prepare
<clean-python> scripts/package6b_tools.py build
<clean-python> scripts/package6b_tools.py up
<clean-python> scripts/package6b_tools.py defaults
<clean-python> scripts/package6b_tools.py qa-build
<clean-python> scripts/package6b_tools.py tests
<clean-python> scripts/package6b_tools.py scan
<clean-python> scripts/package6b_staging.py
<clean-python> scripts/package6b_recovery.py
<clean-python> scripts/package6b_browser.py
```

`build` executes `docker build --no-cache --progress=plain -t fieldwork6b-backend <clean-backend>` and the corresponding frontend build. `up` executes `docker compose --project-name fieldwork6b --project-directory <clean-context> --env-file <private-synthetic.env> -f <clean-compose.yaml> -f <staging-override.yaml> --profile worker up -d --no-build --wait --wait-timeout120`. It never reads the canonical/private installation .env. `tests` runs pytest only in the separate fieldwork6b-qa container on disposable PG schemas. Runtime injection remains external through protected0600 configuration.

Recovery executes `docker stop -t20` on staging processes, independent leader/scheduler tests, `pg_dump -U fieldwork -d fieldwork6b_e2e -Fc`, `pg_restore --single-transaction --no-owner --no-acl` into fieldwork6b_restore, then PostgreSQL and app restarts. No password is passed on the CLI. Commands run inside the isolated PG container; the scripts validate named targets. Never substitute a personal/production database or a real Gmail account.

## Evidence and limits

backend-build.log/frontend-build.log, safe-start-verification.json, image-scan.json, linux-regressions.log, e2e-results.json, browser-smoke.json and restart-backup-verification.json contain executed evidence. preservation-before.json/preservation.json compare installed source/schema/credentials/service definitions/counts/pause read-only. verification.json is the current gate decision. Initial network and Python3.13 strict-certificate harness failures are recorded and resolved; certificate validation was not disabled. An initial restart assertion incorrectly treated the tick counter as immutable; the corrected check verifies its retained row and nondecreasing version, while full stopped DB restore remains exact.

Linux builds and runtime caught no application path/case/shell/permission/browser-dependency defect requiring a product change. Mac-specific `/private/tmp` exists only in prior native test harness fences; the Linux bootstrap is explicitly fenced separately. Production images use `/app`, configured absolute storage and PostgreSQL ownership. No installed data is mounted.

Container PASS does **not** verify intended hosted ingress/private networking/certificate/backup operations, live Google behavior or actual production activation. Those remain separate gates. Package6C was not begun. The personal installation stays at001 and paused.
