#!/usr/bin/env bash
# Daily account housekeeping, run by forgeway-purge.timer (see deploy/vps/systemd/).
#
# Runs `forgeway accounts purge-unverified` in the api container. That one command deletes
# accounts left unverified for 7 days (the privacy policy promises this), expired or used
# emailed links, and rate-limit hits too old to count for any limit. It is idempotent, so a
# second run is harmless. A failure alerts through forgeway-alert@.service.
#
#   sudo -u forgeway /srv/forgeway/deploy/vps/purge.sh

set -euo pipefail

# shellcheck source=deploy/vps/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

main() {
  need docker
  log "purging unverified accounts, expired links and old rate-limit hits"
  compose exec -T api forgeway accounts purge-unverified
}

main "$@"
