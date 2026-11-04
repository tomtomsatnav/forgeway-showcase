#!/usr/bin/env bash
# Daily billing reconciliation, run by forgeway-reconcile.timer (see deploy/vps/systemd/).
#
# Runs `forgeway billing reconcile` in the api container: re-fetches every live subscription from
# Stripe and re-applies it, so a lost webhook cannot leave anyone on the wrong plan. A second run
# is harmless; with billing off it does nothing. A failure alerts through
# forgeway-alert@.service.
#
#   sudo -u forgeway /srv/forgeway/deploy/vps/reconcile.sh

set -euo pipefail

# shellcheck source=deploy/vps/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

main() {
  need docker
  log "reconciling subscriptions with Stripe"
  compose exec -T api forgeway billing reconcile
}

main "$@"
