#!/usr/bin/env bash
# Daily day-3 onboarding nudge, run by forgeway-onboarding.timer (see deploy/vps/systemd/).
#
# Runs `forgeway billing nudge` in the api container: one email to each Pro trial at least three
# days old with no exercise passed and no live run yet. Each learner is nudged once, so a second
# run is harmless; with billing off there is nobody to nudge. A failure alerts through
# forgeway-alert@.service.
#
#   sudo -u forgeway /srv/forgeway/deploy/vps/onboarding.sh

set -euo pipefail

# shellcheck source=deploy/vps/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

main() {
  need docker
  log "sending day-3 onboarding nudges"
  compose exec -T api forgeway billing nudge
}

main "$@"
