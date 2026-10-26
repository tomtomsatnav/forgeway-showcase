# Running Forgeway on the VPS

Forgeway runs on one Ubuntu VPS (2 vCPU, 3.7 GB RAM) that it shares with another site. Docker
Compose runs Postgres, the API, the grading worker, nginx with the SPA, and a Docker
socket-proxy. Grading sandboxes run under gVisor (`runsc`). The system Caddy terminates TLS
behind Cloudflare. [ADR 0010](../../docs/adr/0010-vps-deployment.md) explains why, and what
the threat model is.

```
Cloudflare (proxied, Full (strict))
  -> Caddy :443 (system service, UFW: Cloudflare ranges only)
    -> nginx 127.0.0.1:8090 (web) -> api:8000 -> db:5432
                                    worker -> socket-proxy:2375 -> /var/run/docker.sock
                                                -> sandbox containers (runsc, no network)
```

| What | Where |
| --- | --- |
| Repository (owned by `forgeway`) | `/srv/forgeway` |
| Application secrets and settings | `/srv/forgeway/.env.production` (mode 600) |
| Operations settings (alerts, backups) | `/etc/forgeway/ops.env` (root:forgeway, 640), from [`ops.env.example`](ops.env.example) |
| Deploy state, pre-deploy dumps | `/srv/forgeway/.deploy/` |
| Nightly backups | `/var/backups/forgeway/{daily,weekly}/` |
| Units and timers | [`systemd/`](systemd/), installed into `/etc/systemd/system/` |
| Caddy site block | [`Caddyfile.forgeway`](Caddyfile.forgeway), pasted into `/etc/caddy/Caddyfile` |

Every compose command uses the same project and files. `deploy/vps/lib.sh` wraps them for the
scripts; by hand, it is:

```bash
cd /srv/forgeway
sudo -u forgeway -H docker compose -p forgeway -f docker-compose.yml \
  -f deploy/vps/docker-compose.prod.yml --env-file .env.production <command>
```

## First-time setup

The server already has most of this (26 October 2026). This section is the record, and the
recipe for a rebuild.

1. **Packages:** `apt install docker.io docker-compose-v2 docker-buildx git curl jq age`,
   plus `rclone` once there is an off-site bucket. Install gVisor from its apt repository
   (`https://storage.googleapis.com/gvisor/releases`), then run `sudo runsc install`, which
   registers the `runsc` runtime with Docker.
2. **Docker daemon** (`/etc/docker/daemon.json`). Docker publishes ports past UFW, so every
   published port binds to localhost:

   ```json
   {
     "ip": "127.0.0.1",
     "log-driver": "local",
     "runtimes": { "runsc": { "path": "/usr/bin/runsc" } }
   }
   ```

   Then `sudo systemctl restart docker`. Restarting Docker changes iptables, so check the other
   site afterwards.
3. **User:** `sudo useradd --system --create-home --home-dir /var/lib/forgeway --shell
   /usr/sbin/nologin --groups docker forgeway`. Membership of `docker` is root-equivalent; that
   is the reason nothing else runs as this user, and the reason the worker does not get the
   socket itself (see ADR 0010).
4. **Repository:** `sudo mkdir /srv/forgeway && sudo chown forgeway: /srv/forgeway`, then
   clone as `forgeway`. If the repository is private, give `forgeway` a read-only GitHub deploy
   key, because `deploy.sh` fetches as that user.
5. **`.env.production`** in `/srv/forgeway`, owned by `forgeway`, mode 600 (see below).
6. **Operations settings:** `sudo install -d -m 750 -o root -g forgeway /etc/forgeway`, then
   copy `ops.env.example` to `/etc/forgeway/ops.env` (mode 640) and fill it in. Also
   `sudo install -d -m 700 -o forgeway -g forgeway /var/backups/forgeway`.
7. **Timers and journald:**

   ```bash
   sudo cp /srv/forgeway/deploy/vps/systemd/forgeway-*.{service,timer} \
     '/srv/forgeway/deploy/vps/systemd/forgeway-alert@.service' /etc/systemd/system/
   sudo install -D -m 644 /srv/forgeway/deploy/vps/systemd/journald-forgeway.conf \
     /etc/systemd/journald.conf.d/forgeway.conf
   sudo systemctl restart systemd-journald
   sudo systemctl daemon-reload
   sudo systemctl enable --now forgeway-backup.timer forgeway-healthcheck.timer \
     forgeway-prune.timer forgeway-purge.timer
   systemctl list-timers 'forgeway-*'
   ```

   The units are listed under "Timers" below. On a server set up before
   `forgeway-purge.timer` existed, copy and enable that one unit the same way.
8. **First deploy:** `sudo -u forgeway -H /srv/forgeway/deploy/vps/deploy.sh <tag>`, with a release
   tag cut and pushed as in "Cutting a release" below (`v2026.10.0` for the first release note).
9. **Caddy:** add the site block (see "Caddy"), following the safe change procedure.

### `.env.production`

Compose reads it for the values in `docker-compose.prod.yml`, and the API, worker and migrate
services load it as well, so any `LATTICE_*` setting from [`.env.example`](../../.env.example)
can go here. The override fixes the database URL, cookies, origins, sandbox image and runtime;
those cannot be changed here.

| Key | Required | Value |
| --- | --- | --- |
| `FORGEWAY_DB_PASSWORD` | yes | A long random string (`openssl rand -hex 24`). It is set when the database volume is first created; changing it later also needs `ALTER USER lattice PASSWORD ...`. |
| `FORGEWAY_PUBLIC_URL` | no | `https://forgeway.dev` (the default). |
| `LATTICE_TRUSTED_PROXIES` | yes | The compose network nginx sits on. The API sees requests from nginx, never from Caddy. Find it with `docker network inspect forgeway_default -f '{{(index .IPAM.Config 0).Subnet}}'` (for example `172.18.0.0/16`). Only containers on this host can reach the API, so `172.16.0.0/12` also works and survives the network being recreated. |
| `LATTICE_EMAIL_PROVIDER` | for launch | `resend`. |
| `LATTICE_RESEND_API_KEY` | with Resend | The Resend API key (sending only). |
| `LATTICE_EMAIL_FROM` | with Resend | `Forgeway <hello@forgeway.dev>`, on a domain verified in Resend (SPF and DKIM records in Cloudflare DNS). |
| `LATTICE_TURNSTILE_SITE_KEY`, `LATTICE_TURNSTILE_SECRET` | optional | From a Turnstile widget for `forgeway.dev`. Verification is off while the secret is unset. |
| `LATTICE_REGISTER_PER_IP_PER_HOUR`, `LATTICE_LOGIN_PER_IP_PER_HOUR`, `LATTICE_LOGIN_PER_EMAIL_PER_HOUR`, `LATTICE_PASSWORD_RESET_PER_IP_PER_HOUR`, `LATTICE_PASSWORD_RESET_PER_EMAIL_PER_HOUR`, `LATTICE_VERIFICATION_EMAILS_PER_HOUR`, `LATTICE_ATTEMPTS_PER_DAY`, `LATTICE_GRADING_SECONDS_PER_DAY`, `LATTICE_MAX_QUEUE_DEPTH` | no | Abuse limits and caps. The defaults in `.env.example` suit this VPS. |

The names of the launch settings follow the launch-safety change. Check them against
`.env.example` on the release you deploy.

## Caddy

[`Caddyfile.forgeway`](Caddyfile.forgeway) is the site block. It does the following:

- serves the Cloudflare origin certificate;
- redirects `www` to the apex;
- sets HSTS and a CSP that fits the SPA (its one inline script by hash), Google Fonts and
  Turnstile, plus the usual hardening headers;
- answers 404 for `/api/ops/`;
- keeps the temporary `basicauth` gate on everything except `/healthz`;
- forwards `CF-Connecting-IP`, and replaces `X-Forwarded-For` and `X-Real-IP` with it, so a
  client cannot pose as another address.

It was checked with `caddy validate` on Caddy 2.6.2 and run end to end in a container: the gate
answered 401 and the password 200, `/healthz` answered 200 without the password, `/api/ops/`
answered 404, `www` redirected with 301, a spoofed `X-Forwarded-For` was replaced, and the SPA
loaded in Chromium with no CSP violations.

- **Placeholders:** replace `REPLACE_WITH_BCRYPT_HASH` with the output of
  `caddy hash-password`. The live Caddyfile already has the current hash.
- **When the SPA's inline script changes** (`frontend/index.html`), its CSP hash must change
  too, or the theme falls back to its defaults. Recompute it from the built page:

  ```bash
  docker run --rm forgeway-web:live cat /usr/share/nginx/html/index.html \
    | python3 -c "import sys,re,hashlib,base64; print('sha256-' + base64.b64encode(hashlib.sha256(re.search(r'<script>(.*?)</script>', sys.stdin.read(), re.S).group(1).encode()).digest()).decode())"
  ```

- **Cloudflare features that inject scripts** (Web Analytics, Rocket Loader, email obfuscation)
  are blocked by this CSP. Leave them off, or add their origins.
- **Removing the gate** (the owner's call, once email verification and the other sign-up
  safeguards are live): delete the `@gated` matcher and the `basicauth` block (four lines), then
  follow the procedure below. Add a Cloudflare rate-limiting rule for `/api/auth/*` at the same
  time.

### Changing Caddy safely

The same Caddy serves the other site, so every change goes like this:

```bash
ts=$(date +%Y%m%d-%H%M%S)
sudo cp -a /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.bak-$ts"   # 1. back up
sudoedit /etc/caddy/Caddyfile                                     # 2. change
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile   # 3. validate
sudo systemctl reload caddy                                       # 4. reload, never restart
curl -sS -o /dev/null -w '%{http_code}\n' https://other-site.example/   # 5. other site: 200
curl -sS -o /dev/null -w '%{http_code}\n' https://forgeway.dev/healthz   #    this site: 200
```

If step 3 fails, fix the file or put the backup back; nothing has changed yet. If step 5 does
not show 200 for both sites, restore the backup and reload:
`sudo cp -a "/etc/caddy/Caddyfile.bak-$ts" /etc/caddy/Caddyfile && sudo systemctl reload caddy`.
Then check `journalctl -u caddy -n 50`.

## Deploying

```bash
sudo -u forgeway -H /srv/forgeway/deploy/vps/deploy.sh v2026.11.0   # a release tag (the norm)
sudo -u forgeway -H /srv/forgeway/deploy/vps/deploy.sh main         # or a branch on origin
```

Production deploys a **release tag** (see "Cutting a release" below). A branch on origin, or a
commit on one of origin's branches, also works, for a hotfix or a test. Anything else is refused
before anything changes: a tag not named `vYYYY.MM.N`, a release tag that is not on origin or
that points elsewhere here than on origin, and a branch or commit that exists only on the server.
Whatever is deployed has been pushed, so it is reviewable and CI has graded it.

[`deploy.sh`](deploy.sh) does the following, and prints each step:

1. Takes a lock. It refuses to run if the checkout has local changes.
2. Fetches, checks the ref is one origin publishes (above), and checks it out detached.
3. Builds images tagged with the commit (`forgeway-backend`, `forgeway-web` and
   `forgeway-sandbox-python`). It skips the build when they exist already; `--rebuild` forces
   one.
4. Dumps the database to `.deploy/dumps/` (it keeps three; `--no-dump` skips this).
5. Runs the `migrate` service: migrations, then the content sync.
6. Rolls the services with `up --wait`.
7. Checks `/healthz`, `/readyz` and a worker heartbeat newer than the roll.
8. Tags the images `live`. It keeps the images of the last three releases.

If any step after the checkout fails, it checks out the previous commit, starts that release's
images again and re-syncs its content. It rebuilds only if those images were pruned. It then
runs the checks again and alerts with the outcome. Running a deploy again with the same ref is
safe, and fast.

**Migrations are never reversed automatically.** A release's migrations must leave the previous
release working: add columns and tables, and drop them a release later. The rollback re-syncs
content but does not run migrations, because the old code does not know the new revision. If a
migration itself damaged data, restore the pre-deploy dump (see "Restore for real").

**To roll back by hand,** deploy the previous tag again. Its images are still there, so nothing
is rebuilt. `.deploy/history` lists what was deployed when.

**The first run on the current server** replaces the stack that was started with
`up -d --build`. The worker then moves behind the socket-proxy as the `app` user. If that first
deploy fails, the rollback goes back to the commit that was checked out, using the old compose
files and their images.

### Cutting a release

A release is an annotated git tag, `vYYYY.MM.N`, on a commit of `main` that CI has passed. The
version without the `v` is the content release's version (`v2026.11.0` ships
`content/releases/2026.11.0.md`). `N` counts releases within the month from 0. Releases are
fortnightly as a rule, with hotfixes as the next `N`.

1. **Release note.** On a branch, write `content/releases/YYYY.MM.N.md`: front matter (version,
   date, title, summary, and the `added`, `updated` and `fixed` exercise ids), then a short body
   in the house voice. [docs/authoring.md](../../docs/authoring.md#release-notes) has the format.
   Platform-only releases still get a note, with no exercise lists, if a learner would notice the
   change.
2. **Check.** `uv run forgeway content validate --require-capstones` checks the note, and
   `uv run forgeway content test` grades every solution and wrong case. CI runs both on the pull
   request.
3. **Merge** to `main`, and wait for CI to pass on the merge commit.
4. **Tag and push the tag** from an up-to-date `main`:

   ```bash
   git switch main && git pull --ff-only
   git tag -a v2026.11.0 -m "Forgeway 2026.11.0: Reranking, and a fix to chunking"
   git push origin v2026.11.0
   ```

   Never move a tag that has been pushed. Fix forward with the next `N`.
5. **Deploy** on the VPS: `deploy.sh v2026.11.0`. The What's new page (the Chronicle in RPG mode)
   shows the note, with an unread marker, once the API restarts.

## Backups

[`backup.sh`](backup.sh) runs nightly at about 03:15 UTC (`forgeway-backup.timer`). It does the
following:

- takes a custom-format `pg_dump` of the `lattice` database from the db container;
- encrypts it with [age](https://age-encryption.org) to `AGE_RECIPIENTS`;
- keeps 7 daily and 4 weekly copies (Sundays) in `/var/backups/forgeway`.

A failure alerts through `forgeway-alert@.service`.

**Off-site copies are optional and off for now.** With no bucket, the backups live on the same
VPS as the database. They survive a bad deploy or a dropped table, but not the loss of the VPS
(see "Known risks"). To turn them on, once a bucket exists:

1. Create a private bucket, for example `forgeway-backups`. Use Cloudflare R2 (10 GB free) or
   Backblaze B2. Create an access key limited to that bucket, with read and write.
2. Write `/etc/forgeway/rclone.conf` (owner `forgeway`, mode 600). For R2:

   ```ini
   [r2]
   type = s3
   provider = Cloudflare
   access_key_id = ...
   secret_access_key = ...
   endpoint = https://<account-id>.r2.cloudflarestorage.com
   no_check_bucket = true
   ```

3. In `ops.env`, set `RCLONE_REMOTE=r2:forgeway-backups` and
   `RCLONE_CONFIG=/etc/forgeway/rclone.conf`. Install `rclone`, then run
   `sudo systemctl start forgeway-backup.service` and check with `journalctl -u forgeway-backup`.

The same daily and weekly rotation then applies in the bucket.

**The age key.** Run `age-keygen -o forgeway-backup.key` on your own machine, not on the
server. Put the `age1...` public key in `AGE_RECIPIENTS`, and keep the private key in your
password manager plus one offline copy. Without it the backups cannot be read; with it, anyone
can read them.

### Restore drill

Run [`restore.sh`](restore.sh) monthly, and after any change to backups. It restores a backup
into a scratch database (`forgeway_restore_drill`) in the same Postgres. It then checks the
schema revision, the row counts against the live database, and that there is current content.
Then it drops the scratch database. It never touches the live database. Two ways to run it,
neither leaving the private key on the server:

```bash
# Decrypt on your machine, restore on the server (the key never leaves your machine):
ssh vps 'sudo cat /var/backups/forgeway/daily/forgeway-20261101T031500Z.dump.age' \
  | age -d -i forgeway-backup.key \
  | ssh vps 'sudo -u forgeway -H /srv/forgeway/deploy/vps/restore.sh -'

# Or put the key on the server for the drill only, in memory:
sudo -u forgeway -H /srv/forgeway/deploy/vps/restore.sh --identity /dev/shm/key.txt latest
shred -u /dev/shm/key.txt
```

`--remote latest` takes the newest backup from the bucket instead, and `--keep` leaves the
scratch database in place for inspection.

### Restore for real

1. Stop writes:
   `docker compose ... stop api worker` (the full command is at the top of this page).
2. Take a dump of the current state, whatever it is:
   `docker compose ... exec -T db pg_dump -U lattice -d lattice -Fc > /var/backups/forgeway/before-restore.dump`.
3. Restore over the live database:
   `age -d -i key.txt X.dump.age | docker compose ... exec -T db pg_restore -U lattice -d lattice --clean --if-exists --no-owner --exit-on-error`.
   A pre-deploy dump in `.deploy/dumps/` is not encrypted, so pipe it in directly.
4. Deploy the release that matches the dump's schema. `restore.sh` prints the revision.
   Then `docker compose ... up -d`.

## Monitoring

[`healthcheck.sh`](healthcheck.sh) runs every five minutes (`forgeway-healthcheck.timer`). It
checks the following:

| Check | Fails when |
| --- | --- |
| Site | `/healthz` or `/readyz` on 127.0.0.1:8090 is not 200 |
| Worker | the last heartbeat is older than `WORKER_MAX_AGE_S` (300 s), or there has never been one |
| Queue | the oldest queued attempt has waited more than `QUEUE_MAX_AGE_S` (300 s) |
| Disk | `/` or `/var/lib/docker` is more than `DISK_MAX_PERCENT` (85 %) full |

The worker and queue figures come from `GET /api/ops/status`. It returns counts and ages only,
with no secrets or personal data, and Caddy hides it from the public. The worker writes its
heartbeat on its poll loop every five seconds. A grading run pauses it: up to 250 seconds with
`LATTICE_SANDBOX_TIMEOUT_FACTOR=2` (120 s, doubled, plus start-up), which is why the limit is
five minutes. The worker takes back an attempt claimed by a dead worker a minute after the
longest possible run (310 s at that factor), so a slow run is never graded twice.

- **Alerts** are sent when the set of failing checks changes, including on recovery, and again
  every six hours while a failure lasts. Set `ALERT_WEBHOOK_URL` to an ntfy topic
  (`https://ntfy.sh/<long-random-topic>`, then subscribe in the ntfy app), a Discord webhook or
  a Slack webhook. **Until one is set, alerts go to the journal only:**
  `journalctl -t forgeway-alert`. Nobody is told; read them as part of the weekly check below.
- **The host itself going down** cannot be reported from the host. Two options, both free:
  point an outside uptime monitor (UptimeRobot, Better Stack) at
  `https://forgeway.dev/healthz`, which the gate leaves open; or set `DEADMAN_URL` to a
  healthchecks.io check. That is pinged after every passing run and alerts when the pings stop.
- **Pruning:** `forgeway-prune.timer` removes dangling images and build cache older than a week,
  daily. It never runs `image prune -a`, which would delete the rollback images.
- **Logs:** containers use Docker's `local` log driver, which rotates them. The journald drop-in
  keeps the journal to 500 MB and 30 days.

## Timers

Each timer runs a oneshot service as `forgeway`. A failed run alerts through
`forgeway-alert@.service` (`OnFailure=`), except the health check, which alerts itself.

| Unit | When | What |
| --- | --- | --- |
| `forgeway-backup.timer` | daily, about 03:15 UTC | [`backup.sh`](backup.sh): encrypted `pg_dump`, rotated (see "Backups") |
| `forgeway-purge.timer` | daily, about 03:45 UTC | [`purge.sh`](purge.sh): `forgeway accounts purge-unverified` in the api container, which deletes accounts left unverified for 7 days (the privacy policy promises this), expired emailed links and old rate-limit hits |
| `forgeway-prune.timer` | daily, about 04:30 UTC | dangling images and build cache older than a week |
| `forgeway-healthcheck.timer` | every five minutes | [`healthcheck.sh`](healthcheck.sh) (see "Monitoring") |

`Persistent=true` on the daily timers runs a missed day once the server is back up. Run one by
hand with `sudo systemctl start forgeway-purge.service`, and read its output with
`journalctl -u forgeway-purge`.

## Day-2 operations

| Task | Command or note |
| --- | --- |
| What is running | `docker compose ... ps`, `cat /srv/forgeway/.deploy/current`, `tail /srv/forgeway/.deploy/history` |
| Status at a glance | `curl -s 127.0.0.1:8090/api/ops/status \| jq`, `systemctl list-timers 'forgeway-*'`, `systemctl --failed` |
| Logs | `docker compose ... logs --since 1h api worker`; `journalctl -u forgeway-healthcheck -u forgeway-backup --since today` |
| Run a check, backup or purge now | `sudo systemctl start forgeway-healthcheck.service` (or `forgeway-backup.service`, `forgeway-purge.service`) |
| Restart one service | `docker compose ... restart worker`. Prefer a deploy for anything else. |
| Grade one exercise in production | `docker compose ... exec worker forgeway content test --only starter.first-completion` |
| Disk is filling | `docker system df`; old release images are removed on each deploy, and the prune timer takes the rest; check `/var/backups/forgeway` |
| Rotate the database password | `ALTER USER lattice PASSWORD '...'` in the db container, update `.env.production`, then `deploy.sh <current tag>` |
| Update the socket-proxy | Change the tag and digest in `docker-compose.prod.yml`, then re-run the probes in ADR 0010 locally. The allow-list is ours (`socket-proxy/haproxy.cfg`), not the image's. |
| Update gVisor | `sudo apt upgrade runsc`, then grade one exercise (above) |
| Weekly | read `journalctl -t forgeway-alert --since -7d`; check the newest backup's date and size |
| Monthly | run the restore drill |

## Known risks

- **Backups are on the VPS only** until an off-site bucket is configured. Losing the VPS, or an
  attacker with root on it, loses the backups too. The fix is the R2 or B2 bucket above, about
  ten minutes of setup.
- **No one is paged** until `ALERT_WEBHOOK_URL` or an outside uptime monitor is set. Failures
  are in the journal only.
- **The host is shared.** A sandbox escape through gVisor, or a compromise of the `forgeway`
  user, reaches the other site on this VPS. ADR 0010 lists the mitigations and when to move
  off.
