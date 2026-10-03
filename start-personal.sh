#!/bin/zsh
set -eu
for service in api web; do
  launchctl kickstart "gui/$(id -u)/local.vihaan.fieldwork.$service"
done
print 'Fieldwork background services started: http://localhost:3000'
