#!/usr/bin/env bash
# Daily account housekeeping, run by forgeway-purge.timer (see deploy/vps/systemd/).
#
# Runs `forgeway accounts purge-unverified` in the api container. That one command applies the
# privacy policy's retention list: accounts left unverified for 7 days, expired emailed links and
# sessions, rate-limit hits too old to count, live runs after 30 days and their usage after 13
# months, waitlist entries after 12 months, and pseudonymised billing consents after six years.
# It is idempotent, so a second run is harmless. A failure alerts through forgeway-alert@.service.
#
#   sudo -u forgeway /srv/forgeway/deploy/vps/purge.sh

set -euo pipefail

# shellcheck source=deploy/vps/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

main() {
  need docker
  log "purging data past its retention period"
  compose exec -T api forgeway accounts purge-unverified
}

main "$@"
