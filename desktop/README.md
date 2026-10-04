# Personal desktop client and staged service templates

Fieldwork.swift is the existing personal native WebKit shell. It loads the configured private local web server; it is a client, not a scheduler. No installed app or launch agent was modified or activated in Module5.

The API/web plist files retain historical personal-machine paths. They are source templates, not an installation command. A future release must render current staged source/environment paths and follow MIGRATION_PLAN.md. `local.vihaan.fieldwork.worker.plist.template` adds the dedicated worker command and supervisor behavior; its placeholder paths must be replaced deliberately. Do not copy/load it during development or point it at the personal database as a test.

The canonical `python -m app.worker` process owns scheduling and bounded response checking. A separate API response loop, scheduled AI agent, old heartbeat send prompt and legacy send worker are not production runtime components. Read DEPLOYMENT.md for health/shutdown/recovery and PROVIDER_CAPABILITIES.md for Gmail/Outlook scope.

A Mac must be logged in, awake and online; closing the client only closes its window. Local launch agents cannot provide reliable24/7 execution while asleep/offline. An always-on private worker is a later rollout choice. No sleep, power, security or authorization setting is changed by these templates. Keep external secret configuration, database, receipts and logs private.
