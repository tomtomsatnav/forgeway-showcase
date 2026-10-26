# shellcheck shell=bash
# Shared helpers for the Forgeway VPS scripts. Sourced by them, never run on its own.
#
# Settings come from the environment, then /etc/forgeway/ops.env (see ops.env.example).

FORGEWAY_OPS_CONFIG=${FORGEWAY_OPS_CONFIG:-/etc/forgeway/ops.env}
if [[ -r $FORGEWAY_OPS_CONFIG ]]; then
  set -a
  # shellcheck source=deploy/vps/ops.env.example
  . "$FORGEWAY_OPS_CONFIG"
  set +a
fi

FORGEWAY_DIR=${FORGEWAY_DIR:-/srv/forgeway}
# Exported: the compose files read it too, to pass the application's settings to its services.
export FORGEWAY_ENV_FILE=${FORGEWAY_ENV_FILE:-$FORGEWAY_DIR/.env.production}
FORGEWAY_PROJECT=${FORGEWAY_PROJECT:-forgeway}
FORGEWAY_SITE=${FORGEWAY_SITE:-http://127.0.0.1:8090}
# An extra compose file layered last, for isolated test runs only.
FORGEWAY_COMPOSE_EXTRA=${FORGEWAY_COMPOSE_EXTRA:-}
ALERT_WEBHOOK_URL=${ALERT_WEBHOOK_URL:-}
PGUSER_FORGEWAY=${PGUSER_FORGEWAY:-lattice}
PGDATABASE_FORGEWAY=${PGDATABASE_FORGEWAY:-lattice}

log() { printf '==> %s\n' "$*" >&2; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }
die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

need() {
  local tool
  for tool in "$@"; do
    command -v "$tool" >/dev/null 2>&1 || die "$tool is not installed (see deploy/vps/README.md)"
  done
}

# docker compose for the production stack, from anywhere.
compose() {
  local files=(-f "$FORGEWAY_DIR/docker-compose.yml" -f "$FORGEWAY_DIR/deploy/vps/docker-compose.prod.yml")
  [[ -n $FORGEWAY_COMPOSE_EXTRA ]] && files+=(-f "$FORGEWAY_COMPOSE_EXTRA")
  docker compose -p "$FORGEWAY_PROJECT" --project-directory "$FORGEWAY_DIR" "${files[@]}" \
    --env-file "$FORGEWAY_ENV_FILE" "$@"
}

# Run a command in the database container as the application's database user.
db_exec() {
  compose exec -T db "$@"
}

# Post an alert to ALERT_WEBHOOK_URL (ntfy, Discord or Slack), or log it to the journal when no
# webhook is configured. Alerting never fails the caller.
alert() {
  local message
  message="[forgeway $(hostname -s)] $*"
  printf 'ALERT: %s\n' "$message" >&2
  if [[ -z $ALERT_WEBHOOK_URL ]]; then
    logger -t forgeway-alert -p user.warning -- "$message" 2>/dev/null || true
    return 0
  fi
  local body type=text/plain
  case $ALERT_WEBHOOK_URL in
    *discord.com/api/webhooks/*)
      body=$(jq -cn --arg m "$message" '{content: $m}')
      type=application/json
      ;;
    *hooks.slack.com/*)
      body=$(jq -cn --arg m "$message" '{text: $m}')
      type=application/json
      ;;
    *) body=$message ;;
  esac
  curl -fsS --max-time 10 -H "Content-Type: $type" --data-binary "$body" "$ALERT_WEBHOOK_URL" \
    >/dev/null || warn "could not reach the alert webhook"
}
