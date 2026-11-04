#!/usr/bin/env bash
# Send one alert (webhook, or the journal when none is configured). Used by systemd's
# OnFailure= hook, forgeway-alert@.service:  alert.sh "forgeway-backup.service failed"

set -euo pipefail

# shellcheck source=deploy/vps/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

(($#)) || die "usage: alert.sh MESSAGE"
alert "$*"
