#!/usr/bin/env bash
# Deploy a release tag, branch or commit of Forgeway to this VPS, and roll back if it fails.
#
#   sudo -u forgeway /srv/forgeway/deploy/vps/deploy.sh v2026.11.0       # a release (the norm)
#   sudo -u forgeway /srv/forgeway/deploy/vps/deploy.sh --rebuild main   # a branch on origin
#
# Only refs origin publishes are deployed: a release tag vYYYY.MM.N matching origin's, a branch on
# origin, or a commit on one of origin's branches (see `resolve`).
#
# Steps: fetch; check out the ref (detached); build images tagged with the commit, unless they
# exist; dump the database; run migrations and the content sync (the migrate service); roll the
# services with health waits (restarting the socket proxy, whose rules compose cannot see change);
# smoke-check /healthz, /readyz, a fresh worker heartbeat and one real grade; tag the
# images `live`. If any step after the checkout fails, it checks out the previous ref, starts its
# images again (rebuilding only if they were pruned), re-syncs its content and smoke-checks it.
#
# Migrations are never reversed: a release's migrations must keep the previous release working
# (add columns and tables; drop them a release later). The pre-deploy dump is the way back from
# a migration that went wrong; see "Restore" in deploy/vps/README.md.
#
# Running it again with the same ref is safe: it rebuilds nothing and re-runs the checks.

set -euo pipefail

# shellcheck source=deploy/vps/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

KEEP_RELEASES=${KEEP_RELEASES:-3}
KEEP_PREDEPLOY_DUMPS=${KEEP_PREDEPLOY_DUMPS:-3}
STATE_DIR="$FORGEWAY_DIR/.deploy"
SERVICES=(socket-proxy api worker web)
IMAGES=(forgeway-backend forgeway-web forgeway-sandbox-python)

usage() {
  cat >&2 <<'EOF'
Usage: deploy.sh [--rebuild] [--no-dump] <release-tag|branch|commit>

  release-tag  vYYYY.MM.N, pushed to origin (the usual way: see deploy/vps/README.md)
  branch       a branch on origin
  commit       a commit on one of origin's branches

  --rebuild   build images even if images for this commit exist
  --no-dump   skip the pre-deploy database dump
EOF
  exit 2
}

# The whole script lives in functions that bash reads before running any of them, so checking
# out another version of this file mid-deploy cannot change what is running.
main() {
  local rebuild=0 dump=1 ref=""
  while (($#)); do
    case $1 in
      --rebuild) rebuild=1 ;;
      --no-dump) dump=0 ;;
      -h | --help) usage ;;
      -*) usage ;;
      *) [[ -z $ref ]] || usage; ref=$1 ;;
    esac
    shift
  done
  [[ -n $ref ]] || usage
  need git docker curl jq flock

  cd "$FORGEWAY_DIR"
  [[ -r $FORGEWAY_ENV_FILE ]] || die "$FORGEWAY_ENV_FILE is missing"
  mkdir -p "$STATE_DIR/dumps"
  chmod 700 "$STATE_DIR"
  exec 9>"$STATE_DIR/lock"
  flock -n 9 || die "another deploy is running"

  if ! git diff --quiet || ! git diff --cached --quiet; then
    die "the checkout in $FORGEWAY_DIR has local changes; commit or discard them first"
  fi

  PREVIOUS_SHA=$(cat "$STATE_DIR/current" 2>/dev/null || git rev-parse HEAD)
  step "fetch"
  git fetch --quiet --tags --prune --force origin
  TARGET_SHA=$(resolve "$ref")
  log "deploying $ref ($(short "$TARGET_SHA")); live now: $(short "$PREVIOUS_SHA")"

  if ((dump)); then
    step "pre-deploy database dump"
    predeploy_dump
  fi

  ROLLBACK_ARMED=1
  step "checkout"
  git checkout --quiet --detach "$TARGET_SHA"
  export FORGEWAY_IMAGE_TAG
  FORGEWAY_IMAGE_TAG=$(short "$TARGET_SHA")

  if ((rebuild)) || ! images_exist "$FORGEWAY_IMAGE_TAG"; then
    step "build images :$FORGEWAY_IMAGE_TAG"
    # One service per image: api, worker and migrate share the backend image, and building them
    # together races to tag it ("image ... already exists").
    compose build --pull migrate web sandbox-image
  else
    log "images :$FORGEWAY_IMAGE_TAG already exist; not rebuilding"
  fi

  step "start the database"
  compose up -d --wait db
  step "migrations and content sync"
  compose run --rm --no-deps migrate
  step "roll services"
  compose up -d --wait --no-deps --no-build --remove-orphans "${SERVICES[@]}"
  restart_proxy
  step "smoke checks"
  smoke strict

  tag_live "$FORGEWAY_IMAGE_TAG"
  printf '%s\n' "$TARGET_SHA" >"$STATE_DIR/current"
  printf '%s %s %s deployed\n' "$(date -u +%FT%TZ)" "$TARGET_SHA" "$ref" >>"$STATE_DIR/history"
  ROLLBACK_ARMED=0
  prune_releases
  log "deployed $ref ($(short "$TARGET_SHA")); previous release $(short "$PREVIOUS_SHA") kept for rollback"
}

CURRENT_STEP="start"
ROLLBACK_ARMED=0
PREVIOUS_SHA=""
TARGET_SHA=""

step() {
  CURRENT_STEP=$1
  log "$1"
}

short() { printf '%s' "${1:0:12}"; }

# Only what origin publishes is deployed, so nothing reaches the server without being pushed:
#   - a release tag, vYYYY.MM.N, whose commit here is the commit origin has under that tag;
#   - a branch on origin (its remote-tracking ref, just fetched with --prune);
#   - a commit (hex, 7-40 characters) on one of origin's branches.
# A local-only branch or tag, a tag that is not a release tag, or anything unknown is refused.
RELEASE_TAG='^v[0-9]{4}\.(0[1-9]|1[0-2])\.[0-9]+$'
resolve() {
  local ref=$1 sha remote
  if [[ $ref =~ $RELEASE_TAG ]]; then
    sha=$(git rev-parse --quiet --verify "refs/tags/$ref^{commit}") \
      || die "unknown release tag: $ref (cut it and push it first; see deploy/vps/README.md)"
    # Annotated tags list the tag object, then the commit as `^{}`; take the commit.
    remote=$(git ls-remote origin "refs/tags/$ref" "refs/tags/$ref^{}" | sort -k2 | awk 'END {print $1}')
    [[ -n $remote ]] || die "release tag $ref is not on origin; push it before deploying"
    [[ $remote == "$sha" ]] || die "release tag $ref here ($(short "$sha")) is not origin's ($(short "$remote"))"
  elif git rev-parse --quiet --verify "refs/tags/$ref" >/dev/null; then
    die "tag $ref is not a release tag; release tags are vYYYY.MM.N, such as v2026.11.0"
  elif sha=$(git rev-parse --quiet --verify "refs/remotes/origin/$ref^{commit}"); then
    :
  elif [[ $ref =~ ^[0-9a-f]{7,40}$ ]] && sha=$(git rev-parse --quiet --verify "$ref^{commit}"); then
    [[ -n $(git for-each-ref --contains "$sha" refs/remotes/origin) ]] \
      || die "commit $ref is on none of origin's branches"
  else
    die "unknown ref: $ref; deploy a release tag (vYYYY.MM.N), a branch on origin or a commit on one"
  fi
  printf '%s' "$sha"
}

images_exist() {
  local image
  for image in "${IMAGES[@]}"; do
    docker image inspect "$image:$1" >/dev/null 2>&1 || return 1
  done
}

tag_live() {
  local image
  for image in "${IMAGES[@]}"; do
    if docker image inspect "$image:$1" >/dev/null 2>&1; then
      docker tag "$image:$1" "$image:live"
    fi
  done
}

predeploy_dump() {
  if [[ -z $(compose ps -q db 2>/dev/null) ]]; then
    log "database not running; nothing to dump"
    return 0
  fi
  local file
  file="$STATE_DIR/dumps/predeploy-$(date -u +%Y%m%dT%H%M%SZ)-$(short "$PREVIOUS_SHA").dump"
  (umask 077 && db_exec pg_dump -U "$PGUSER_FORGEWAY" -d "$PGDATABASE_FORGEWAY" -Fc >"$file")
  log "dumped the database to $file ($(du -h "$file" | cut -f1))"
  local dumps=("$STATE_DIR"/dumps/predeploy-*.dump)
  local excess=$((${#dumps[@]} - KEEP_PREDEPLOY_DUMPS))
  ((excess > 0)) && rm -f -- "${dumps[@]:0:excess}"
  return 0
}

# Wait for the site to answer, then for a worker heartbeat newer than the roll, then a real grade.
# Mode `strict` requires the ops status endpoint; `lenient` skips the worker check when the
# release predates it.
smoke() {
  local mode=$1 url
  for url in /healthz /readyz; do
    wait_for "$url" 90 || { warn "$url did not answer 200"; return 1; }
    log "$url ok"
  done
  local rolled_at status age
  rolled_at=$(date +%s)
  if ! curl -fsS --max-time 5 "$FORGEWAY_SITE/api/ops/status" >/dev/null 2>&1; then
    [[ $mode == lenient ]] && { log "no ops status in this release; worker check skipped"; return 0; }
    warn "/api/ops/status did not answer"
    return 1
  fi
  local deadline=$((rolled_at + 60))
  while (($(date +%s) < deadline)); do
    status=$(curl -fsS --max-time 5 "$FORGEWAY_SITE/api/ops/status" || true)
    age=$(jq -r '.worker.age_s // empty' <<<"$status" 2>/dev/null || true)
    if [[ -n $age ]] && jq -e --argjson age "$age" --argjson since "$(($(date +%s) - rolled_at + 1))" \
      -n '$age <= $since' >/dev/null; then
      log "worker heartbeat ok (${age}s ago)"
      smoke_grading
      return
    fi
    sleep 2
  done
  warn "no worker heartbeat since the services were rolled"
  return 1
}

# The proxy's rules are a bind-mounted file, so compose sees no change when only they change and
# would leave the old rules loaded: every grading container then gets a 403.
restart_proxy() {
  compose restart socket-proxy >/dev/null
}

# Grade the first exercise's reference solution for real: the site can answer every health check
# while the worker cannot start a single grading container.
smoke_grading() {
  if compose exec -T worker forgeway content test --only starter.first-completion >/dev/null 2>&1; then
    log "grading ok"
    return 0
  fi
  warn "the first exercise's reference solution did not grade as expected"
  return 1
}

wait_for() {
  local path=$1 seconds=$2 deadline
  deadline=$(($(date +%s) + seconds))
  while (($(date +%s) < deadline)); do
    curl -fsS --max-time 5 -o /dev/null "$FORGEWAY_SITE$path" && return 0
    sleep 2
  done
  return 1
}

rollback() {
  set +e
  warn "deploy failed during: $CURRENT_STEP"
  warn "rolling back to $(short "$PREVIOUS_SHA")"
  cd "$FORGEWAY_DIR" || return 1
  git checkout --quiet --force --detach "$PREVIOUS_SHA" || { alert "deploy failed and rollback could not check out $(short "$PREVIOUS_SHA")"; return 1; }
  export FORGEWAY_IMAGE_TAG
  FORGEWAY_IMAGE_TAG=$(short "$PREVIOUS_SHA")
  local services=() service
  for service in "${SERVICES[@]}"; do
    compose config --services 2>/dev/null | grep -qx "$service" && services+=("$service")
  done
  # The schema may already be newer than this release knows, so only the content is re-synced.
  compose run --rm --no-deps migrate forgeway content sync \
    && compose up -d --wait --no-deps --remove-orphans "${services[@]}" \
    && restart_proxy \
    && smoke lenient
  local result=$?
  if ((result == 0)); then
    tag_live "$FORGEWAY_IMAGE_TAG"
    printf '%s %s rollback-from-%s\n' "$(date -u +%FT%TZ)" "$PREVIOUS_SHA" "$TARGET_SHA" >>"$STATE_DIR/history"
    alert "deploy of $(short "$TARGET_SHA") failed during '$CURRENT_STEP'; rolled back to $(short "$PREVIOUS_SHA"), which passes its checks"
  else
    alert "deploy of $(short "$TARGET_SHA") failed during '$CURRENT_STEP' and the rollback to $(short "$PREVIOUS_SHA") failed too: the site needs attention"
  fi
  return "$result"
}

# Keep the images of the last KEEP_RELEASES deployed commits, plus `live`.
prune_releases() {
  local keep=() sha image tag
  if [[ -f $STATE_DIR/history ]]; then
    while read -r sha; do keep+=("$(short "$sha")"); done < <(
      awk '{print $2}' "$STATE_DIR/history" | tac | awk '!seen[$0]++' | head -n "$KEEP_RELEASES"
    )
  fi
  for image in "${IMAGES[@]}"; do
    while read -r tag; do
      [[ $tag == live || $tag == "<none>" ]] && continue
      [[ " ${keep[*]} " == *" $tag "* ]] && continue
      docker image rm "$image:$tag" >/dev/null && log "removed old image $image:$tag"
    done < <(docker image ls "$image" --format '{{.Tag}}')
  done
}

on_exit() {
  local status=$?
  if ((status != 0 && ROLLBACK_ARMED)); then
    ROLLBACK_ARMED=0
    if rollback; then
      warn "rolled back to $(short "$PREVIOUS_SHA"); $(short "$TARGET_SHA") is NOT deployed"
    else
      warn "rollback failed; see the output above"
    fi
  fi
  exit "$status"
}
# Sourcing the script (its tests do) defines the functions without deploying anything.
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  trap on_exit EXIT
  main "$@"
fi
