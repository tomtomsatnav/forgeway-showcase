#!/usr/bin/env bash
# Nightly Forgeway database backup, run by forgeway-backup.timer (see deploy/vps/systemd/).
#
# Takes a pg_dump (custom format) from the db container, encrypts it with age to
# AGE_RECIPIENTS (public keys only; the private key never lives on this server) and keeps
# KEEP_DAILY daily and KEEP_WEEKLY weekly copies in BACKUP_DIR. When RCLONE_REMOTE is set it
# also uploads each copy off-site (Cloudflare R2, Backblaze B2 or any S3-compatible bucket) and
# applies the same rotation there. Until it is set, backups live on this VPS only: they do not
# survive losing the VPS (see "Known risks" in deploy/vps/README.md).
#
#   sudo -u forgeway /srv/forgeway/deploy/vps/backup.sh

set -euo pipefail

# shellcheck source=deploy/vps/lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

BACKUP_DIR=${BACKUP_DIR:-/var/backups/forgeway}
AGE_RECIPIENTS=${AGE_RECIPIENTS:-}
KEEP_DAILY=${KEEP_DAILY:-7}
KEEP_WEEKLY=${KEEP_WEEKLY:-4}
WEEKLY_ON=${WEEKLY_ON:-7} # ISO day of the week for the weekly copy; 7 is Sunday
RCLONE_REMOTE=${RCLONE_REMOTE:-} # for example r2:forgeway-backups
MIN_DUMP_BYTES=${MIN_DUMP_BYTES:-4096}
PARTIAL=""

main() {
  need docker age
  [[ -n $AGE_RECIPIENTS ]] || die "AGE_RECIPIENTS is not set (see deploy/vps/ops.env.example)"
  [[ -z $RCLONE_REMOTE ]] || need rclone
  umask 077
  mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"

  local recipients=() key
  for key in $AGE_RECIPIENTS; do recipients+=(-r "$key"); done

  local name
  name="forgeway-$(date -u +%Y%m%dT%H%M%SZ).dump.age"
  PARTIAL="$BACKUP_DIR/.partial-$name"
  trap 'rm -f -- "$PARTIAL"' EXIT

  log "dumping $PGDATABASE_FORGEWAY and encrypting it"
  db_exec pg_dump -U "$PGUSER_FORGEWAY" -d "$PGDATABASE_FORGEWAY" -Fc \
    | age "${recipients[@]}" -o "$PARTIAL"
  local size
  size=$(wc -c <"$PARTIAL" | tr -d ' ')
  ((size >= MIN_DUMP_BYTES)) || die "the encrypted dump is only $size bytes; refusing to keep it"
  mv -- "$PARTIAL" "$BACKUP_DIR/daily/$name"
  log "kept $BACKUP_DIR/daily/$name ($size bytes)"

  local weekly=0
  if [[ $(date -u +%u) == "$WEEKLY_ON" ]]; then
    ln -f -- "$BACKUP_DIR/daily/$name" "$BACKUP_DIR/weekly/$name"
    weekly=1
    log "kept a weekly copy"
  fi
  rotate_local daily "$KEEP_DAILY"
  rotate_local weekly "$KEEP_WEEKLY"

  if [[ -n $RCLONE_REMOTE ]]; then
    rclone copyto --quiet "$BACKUP_DIR/daily/$name" "$RCLONE_REMOTE/daily/$name"
    ((weekly)) && rclone copyto --quiet "$BACKUP_DIR/daily/$name" "$RCLONE_REMOTE/weekly/$name"
    rotate_remote daily "$KEEP_DAILY"
    rotate_remote weekly "$KEEP_WEEKLY"
    log "uploaded to $RCLONE_REMOTE"
  else
    warn "RCLONE_REMOTE is not set: this backup is on this VPS only"
  fi
}

# Delete all but the newest $2 backups in $BACKUP_DIR/$1 (names sort by time).
rotate_local() {
  local files=("$BACKUP_DIR/$1"/forgeway-*.dump.age)
  [[ -e ${files[0]} ]] || return 0
  local excess=$((${#files[@]} - $2))
  if ((excess > 0)); then
    rm -f -- "${files[@]:0:excess}"
    log "removed $excess old $1 backup(s)"
  fi
}

rotate_remote() {
  local old
  rclone lsf --files-only --include 'forgeway-*.dump.age' "$RCLONE_REMOTE/$1/" \
    | sort -r | tail -n +"$(($2 + 1))" \
    | while read -r old; do
      rclone deletefile "$RCLONE_REMOTE/$1/$old"
      log "removed off-site $1/$old"
    done
}

main "$@"
