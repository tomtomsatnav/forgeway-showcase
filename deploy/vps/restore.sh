#!/usr/bin/env bash
# Restore drill: restore a Forgeway backup into a scratch database and check it is sound.
#
#   restore.sh [--identity FILE] [--remote] [--keep] [latest | BACKUP_FILE | -]
#
#   latest        the newest daily backup in BACKUP_DIR (or off-site with --remote); the default
#   BACKUP_FILE   a .dump.age file, or a plain .dump
#   -             a decrypted custom-format dump on stdin, so the private key can stay on your
#                 own machine:  age -d -i key.txt X.dump.age | ssh vps sudo -u forgeway restore.sh -
#   --identity    the age private key (default AGE_IDENTITY); needed for .age files
#   --remote      take `latest` from RCLONE_REMOTE instead of BACKUP_DIR
#   --keep        leave the scratch database in place for inspection
#
# It never touches the live database: it restores into RESTORE_DB (forgeway_restore_drill) in
# the same Postgres container, compares it with the live one, and drops it again. Restoring for
# real is a manual procedure; see "Restore" in deploy/vps/README.md.

set -euo pipefail

# shellcheck source=deploy/vps/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

BACKUP_DIR=${BACKUP_DIR:-/var/backups/forgeway}
RCLONE_REMOTE=${RCLONE_REMOTE:-}
RESTORE_DB=${RESTORE_DB:-forgeway_restore_drill}
AGE_IDENTITY=${AGE_IDENTITY:-}
WORK=""
TABLES=(users attempts xp_events exercise_revisions certificates)

main() {
  local remote=0 keep=0 source=latest
  while (($#)); do
    case $1 in
      --identity) AGE_IDENTITY=${2:?--identity needs a file}; shift ;;
      --remote) remote=1 ;;
      --keep) keep=1 ;;
      -h | --help) sed -n '2,17p' "${BASH_SOURCE[0]}"; exit 0 ;;
      *) source=$1 ;;
    esac
    shift
  done
  need docker
  [[ $RESTORE_DB != "$PGDATABASE_FORGEWAY" ]] || die "RESTORE_DB must not be the live database"
  [[ $RESTORE_DB =~ ^[a-z_][a-z0-9_]*$ ]] || die "RESTORE_DB must be a plain identifier"

  WORK=$(mktemp -d)
  trap 'rm -rf -- "$WORK"' EXIT

  if [[ $source == latest ]]; then
    if ((remote)); then
      [[ -n $RCLONE_REMOTE ]] || die "--remote needs RCLONE_REMOTE"
      need rclone
      local newest
      newest=$(rclone lsf --files-only --include 'forgeway-*.dump.age' "$RCLONE_REMOTE/daily/" | sort | tail -n 1)
      [[ -n $newest ]] || die "no backups in $RCLONE_REMOTE/daily/"
      rclone copyto "$RCLONE_REMOTE/daily/$newest" "$WORK/$newest"
      source="$WORK/$newest"
    else
      local files=("$BACKUP_DIR"/daily/forgeway-*.dump.age)
      [[ -e ${files[0]} ]] || die "no backups in $BACKUP_DIR/daily/"
      source=${files[-1]}
    fi
  fi
  log "restoring $source into $RESTORE_DB"

  # Calls that do not read a dump get /dev/null, so they cannot swallow a dump piped in on stdin.
  db_exec dropdb -U "$PGUSER_FORGEWAY" --if-exists "$RESTORE_DB" </dev/null
  db_exec createdb -U "$PGUSER_FORGEWAY" "$RESTORE_DB" </dev/null
  ((keep)) || trap 'drop_scratch; rm -rf -- "$WORK"' EXIT

  decrypted "$source" \
    | db_exec pg_restore -U "$PGUSER_FORGEWAY" -d "$RESTORE_DB" --no-owner --exit-on-error
  sanity_check
  if ((keep)); then
    log "kept $RESTORE_DB; drop it with: dropdb -U $PGUSER_FORGEWAY $RESTORE_DB (in the db container)"
  fi
}

decrypted() {
  case $1 in
    -) cat ;;
    *.age)
      need age
      [[ -r $AGE_IDENTITY ]] || die "an age identity is needed for $1 (--identity FILE)"
      age -d -i "$AGE_IDENTITY" "$1"
      ;;
    *) cat -- "$1" ;;
  esac
}

query() {
  db_exec psql -U "$PGUSER_FORGEWAY" -d "$1" -XAtq -v ON_ERROR_STOP=1 -c "$2" </dev/null
}

sanity_check() {
  local restored live failed=0 table
  restored=$(query "$RESTORE_DB" "SELECT version_num FROM alembic_version")
  live=$(query "$PGDATABASE_FORGEWAY" "SELECT version_num FROM alembic_version")
  printf '%-20s %12s %12s\n' "" restored live
  printf '%-20s %12s %12s\n' "schema revision" "$restored" "$live"
  [[ -n $restored ]] || { warn "the restore has no schema revision"; failed=1; }
  for table in "${TABLES[@]}"; do
    restored=$(query "$RESTORE_DB" "SELECT count(*) FROM $table")
    live=$(query "$PGDATABASE_FORGEWAY" "SELECT count(*) FROM $table")
    printf '%-20s %12s %12s\n' "$table" "$restored" "$live"
  done
  restored=$(query "$RESTORE_DB" "SELECT count(*) FROM exercise_revisions WHERE is_current")
  ((restored > 0)) || { warn "the restore has no current content"; failed=1; }
  if ((failed)); then
    alert "restore drill FAILED for $RESTORE_DB"
    return 1
  fi
  log "restore drill passed (live counts may be higher: the backup is older)"
}

drop_scratch() {
  db_exec dropdb -U "$PGUSER_FORGEWAY" --if-exists "$RESTORE_DB" </dev/null || warn "could not drop $RESTORE_DB"
}

main "$@"
