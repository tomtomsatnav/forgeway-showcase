#!/usr/bin/env bash
# Check that Forgeway is healthy and alert when that changes. Run every five minutes by
# forgeway-healthcheck.timer (see deploy/vps/systemd/).
#
# Checks: the site answers /healthz and /readyz; a worker polled the queue recently; no attempt
# has waited too long; the disks are not too full. Alerts go to ALERT_WEBHOOK_URL, or to the
# journal (`journalctl -t forgeway-alert`) when none is set. An alert is sent when the set of
# failures changes (including recovery) and repeated every REALERT_AFTER_S while it persists.
# If DEADMAN_URL is set (for example a healthchecks.io check), it is pinged after every passing
# run, so an outside service notices when this host or this timer stops.
#
# Exits 1 while anything is failing, so `systemctl --failed` shows it too.

set -euo pipefail

# shellcheck source=deploy/vps/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

WORKER_MAX_AGE_S=${WORKER_MAX_AGE_S:-300}
QUEUE_MAX_AGE_S=${QUEUE_MAX_AGE_S:-300}
DISK_MAX_PERCENT=${DISK_MAX_PERCENT:-85}
DISK_PATHS=${DISK_PATHS:-/ /var/lib/docker}
REALERT_AFTER_S=${REALERT_AFTER_S:-21600}
DEADMAN_URL=${DEADMAN_URL:-}
STATE_FILE=${STATE_DIRECTORY:-/var/lib/forgeway}/healthcheck.state

main() {
  need curl jq df
  local failures=()

  local path
  for path in /healthz /readyz; do
    curl -fsS --max-time 10 -o /dev/null "$FORGEWAY_SITE$path" 2>/dev/null \
      || failures+=("site: $path is not answering 200")
  done

  local status
  if status=$(curl -fsS --max-time 10 "$FORGEWAY_SITE/api/ops/status" 2>/dev/null); then
    local worker_age queue_age queued
    worker_age=$(jq -r '.worker.age_s // "none"' <<<"$status")
    queue_age=$(jq -r '.queue.oldest_queued_age_s // 0' <<<"$status")
    queued=$(jq -r '.queue.queued' <<<"$status")
    if [[ $worker_age == none ]]; then
      failures+=("worker: no heartbeat recorded")
    elif older_than "$worker_age" "$WORKER_MAX_AGE_S"; then
      failures+=("worker: last heartbeat ${worker_age}s ago (limit ${WORKER_MAX_AGE_S}s)")
    fi
    if older_than "$queue_age" "$QUEUE_MAX_AGE_S"; then
      failures+=("queue: oldest of $queued queued attempts waited ${queue_age}s (limit ${QUEUE_MAX_AGE_S}s)")
    fi
  else
    failures+=("ops: /api/ops/status is not answering")
  fi

  local disk used
  for disk in $DISK_PATHS; do
    [[ -e $disk ]] || continue
    used=$(df -P "$disk" | awk 'NR == 2 {sub("%", "", $5); print $5}')
    if [[ -n $used ]] && ((used > DISK_MAX_PERCENT)); then
      failures+=("disk: $disk is ${used}% full (limit ${DISK_MAX_PERCENT}%)")
    fi
  done

  report "${failures[@]}"
}

# Whether $1 seconds is more than $2 seconds (ages are decimals).
older_than() {
  jq -en --argjson a "$1" --argjson b "$2" '$a > $b' >/dev/null
}

report() {
  # The signature names the failing checks, not their numbers, so a persisting failure does not
  # alert on every run.
  local now signature="ok" summary="" previous="" last_alert=0 failure
  now=$(date +%s)
  if (($#)); then
    signature=$(for failure in "$@"; do printf '%s ' "${failure%%:*}"; done)
    signature=${signature% }
    summary=$(printf '%s; ' "$@")
    summary=${summary%; }
  fi
  if [[ -r $STATE_FILE ]]; then
    { read -r previous; read -r last_alert; } <"$STATE_FILE" || true
  fi

  if [[ $signature == ok ]]; then
    log "all checks passed"
    [[ $previous != ok && -n $previous ]] && alert "recovered: all checks pass again"
    save_state ok "$now"
    if [[ -n $DEADMAN_URL ]]; then
      curl -fsS --max-time 10 -o /dev/null "$DEADMAN_URL" || warn "could not reach DEADMAN_URL"
    fi
    return 0
  fi

  for failure in "$@"; do warn "$failure"; done
  if [[ $signature != "$previous" ]] || ((now - ${last_alert:-0} >= REALERT_AFTER_S)); then
    alert "failing: $summary"
    save_state "$signature" "$now"
  fi
  return 1
}

save_state() {
  mkdir -p "$(dirname "$STATE_FILE")"
  printf '%s\n%s\n' "$1" "$2" >"$STATE_FILE"
}

main "$@"
