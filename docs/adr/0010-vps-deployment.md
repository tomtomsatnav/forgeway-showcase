# ADR 0010: Production on one shared VPS

Status: Accepted
Date: 2026-10-26

## Context

ADR 0003 planned production sandboxes on Cloud Run Jobs, because mounting `docker.sock` into a
worker is root-equivalent on the host. The owner chose to launch on a VPS he already runs
instead:

- Ubuntu, 2 vCPU, 3.7 GB RAM;
- shared with another site;
- system Caddy behind Cloudflare.

It costs nothing extra and needs no cloud account. The stakes at launch are low. Grades are
advisory, there are no prizes, and there are no organisations or signed certificates yet. The
user base is small.

The VPS must still run untrusted learner code without risking the host or the other site, and it
must be operable by one person.

## Decision

**One Docker Compose stack**: Postgres, the API, the grading worker, nginx serving the SPA, and
a Docker socket-proxy. The worker runs each grading attempt in a throwaway container through
the existing `DockerSandboxRunner`, under **gVisor** (`--runtime runsc`), with every control in
ADR 0003:

- no network, a read-only root and capped tmpfs;
- the harness as UID 10001 and out-of-process learner code as 10002, both with no capabilities,
  started by a root launcher that holds only SETUID, SETGID and KILL (ADR 0009), and
  `no-new-privileges`;
- memory, CPU, process and wall-clock limits.

**The worker never holds the Docker socket.** It runs as the image's unprivileged `app` user
and reaches Docker at `tcp://socket-proxy:2375`, on an internal network that only it and the
proxy share. The proxy is `tecnativa/docker-socket-proxy`, pinned by digest, running our own
HAProxy allow-list (`deploy/vps/socket-proxy/haproxy.cfg`) instead of the image's coarse
per-section switches. The allow-list has three parts:

- **Endpoints.** Only what `docker run --rm -i`, `docker kill`, `docker ps` and
  `docker inspect` use, measured from the proxy's log:
  - `HEAD`/`GET /_ping` and `GET /version`;
  - `POST /containers/create`;
  - `POST /containers/{id}/attach|start|wait|kill`;
  - `GET /containers/json` and `GET /containers/{id}/json`.

  Everything else is refused: exec, build, image pull, volumes, networks, info, DELETE and the
  rest. `--rm` is done by the daemon and the sandbox image is local, so no removal or pull calls
  are needed.
- **Container bodies.** A path list alone would still let a compromised worker create a
  privileged container with `/` mounted, so container-create bodies are inspected too. Creation
  is refused unless:
  - the image is a `*sandbox-python:<tag>` image;
  - `NetworkMode` is `none`;
  - the root filesystem is read-only;
  - with `REQUIRE_RUNSC` (the production default), the runtime is `runsc`.

  It is also refused on any sign of host access:
  - privilege, bind or volume mounts, devices, added capabilities;
  - host or container namespaces, cgroup or sysctl changes;
  - seccomp, AppArmor or label overrides;
  - `OomKillDisable`.
- **Defeating the checks.** They are case-insensitive, because Go's JSON decoder matches keys
  that way. They refuse bodies with `\u` escapes or non-ASCII bytes, so a key cannot be spelt
  past them, and they refuse bodies over 16 KB. A duplicated key cannot hide a bad value,
  because every occurrence is checked.

**The edge**:

- Cloudflare proxies the site (SSL Full (strict), an origin certificate), and UFW admits 443
  only from Cloudflare's ranges.
- The system Caddy terminates TLS and forwards to nginx on `127.0.0.1:8090`. It sets HSTS, a
  CSP and the client address from `CF-Connecting-IP`.
- Docker's `daemon.json` sets `"ip": "127.0.0.1"`, so no published port can bypass UFW.
- Postgres and the API publish nothing.

**Operations live in the repository** (`deploy/vps/`):

- tagged deploys with automatic rollback;
- nightly encrypted backups with a restore drill;
- a health check on the site, the worker heartbeat, queue age and disk use;
- Docker pruning and journald limits.

Cloud Run (with Cloud SQL and Cloud Run Jobs on gVisor) remains the scale-up path behind the
same `SandboxRunner` port. It is not built, and no Terraform is written until the owner asks.

## Threat model of the shared host

**Assets:**

- the host and the other site on it;
- learners' accounts and progress, and the database password;
- the Cloudflare origin certificates and keys in `/etc/caddy`;
- the backups;
- the integrity of grades, which are advisory (ADR 0003).

**Adversaries:**

1. A learner submitting hostile code. This is the expected one.
2. An internet attacker on the web surface: the API, nginx and Caddy.
3. A compromised dependency in the API or worker image.
4. Someone with the owner's SSH access. Out of scope: they have root anyway.

| Path | Mitigation | What is left |
| --- | --- | --- |
| Learner code to the host kernel | gVisor intercepts syscalls in a user-space kernel; plus no network, read-only root, limits, and learner code non-root with no capabilities (the launcher keeps SETUID, SETGID and KILL as root) | A gVisor escape is a host compromise. This is the residual risk that matters most. |
| Learner code to other containers or the internet | `--network none`; the proxy refuses any other network mode | None known |
| Learner code exhausting the VPS | Memory, CPU, pids, file-size and wall-clock limits per sandbox; the launch caps (a 768 MB memory ceiling, one queued attempt per learner, a daily attempt cap, a queue-depth refusal); the health check's queue and disk alerts | Two concurrent sandboxes still compete with the other site for 3.7 GB |
| Learner code subverting its own grade | Out of scope here; see ADR 0003 and the out-of-process bridge, with learner code as a second user (ADR 0009) | In-process exercises and scripts the tests start still share the harness's user |
| Web attacker to the API process | It runs as UID 10002 with no Docker access and no published port | Code execution there reads the database, as anywhere |
| Web attacker or bad dependency in the worker, to the host | The worker has no socket and no root; the proxy refuses privileged, mounted and host-namespace containers, and every endpoint not needed | The proxy cannot stop a compromised worker killing or attaching to other containers, or flooding sandboxes. The worker already holds the database password, so its data is lost either way. The host is what the proxy protects. |
| Anything to the socket-proxy | It is on an internal network with only the worker; it runs read-only, with no capabilities and `no-new-privileges` | It holds the socket: a bug in HAProxy's request handling is a host compromise |
| The `forgeway` user | Nothing else runs as it; its shell is `nologin` | It is in the `docker` group, so its compromise is root |
| Spoofed client addresses | Caddy replaces `X-Forwarded-For`; only Cloudflare reaches 443; the API trusts forwarding headers only from the compose network | None known |
| Losing the VPS | Nightly age-encrypted dumps, a restore drill, pre-deploy dumps | Off-site copies wait on a bucket; until then backups die with the VPS |

## What would move production off this VPS

Any one of these:

- **Grades start carrying weight**: signed certificates, organisations or paid plans. The
  blast radius of a sandbox escape then matters more than the cost, so move to managed
  per-run isolation (Cloud Run Jobs, or Firecracker microVMs) or a dedicated host.
- **Load**: sustained queue-age alerts, or memory pressure on the other site, with the
  concurrency limits already at their floor.
- **A gVisor or HAProxy escape advisory** without a prompt fix.
- **The other site gains users or data** that a Forgeway compromise must not reach.
- **Real paying customers**, who need an uptime the single host cannot give.

The first step off is cheap: a second small VPS for Forgeway alone, with the same compose files.
Cloud Run follows only if one host is not enough.

## Consequences

Positive:

- No new spend, and one place to look.
- The deploy, backup and health-check scripts are versioned with the code.
- Learner code runs under gVisor, and the worker has neither root nor the raw socket.

Negative:

- Sandbox isolation shares a kernel and a host with another site. gVisor and the proxy reduce
  the risk; they do not remove it.
- The allow-list is coupled to how the docker CLI forms requests. A CLI or API upgrade can
  break grading, which the deploy's smoke check or the first graded attempt shows, and the fix
  is to re-run the probes in this ADR and adjust `haproxy.cfg`.
- One host means no redundancy. A VPS outage is a site outage.

## Alternatives considered

- **Cloud Run Jobs now** (ADR 0003's plan). Deferred: it needs a GCP account, a billing
  commitment and Terraform, for a launch whose stakes do not yet need it.
- **The raw socket in the worker, as in development.** Rejected: any worker compromise would be
  root on a shared host.
- **Rootless Docker or Podman for sandboxes.** A good further layer, but `runsc` support and
  cgroup limits under rootless need more work than the launch allows. It is the next hardening
  step if the proxy's residual risk becomes a concern.
- **Sysbox or Kata Containers.** Stronger isolation, but heavier on a 2 vCPU host and less
  familiar to operate.
- **The proxy's built-in switches** (`CONTAINERS=1`, `POST=1`). Rejected: they allow every
  container endpoint, and any container body.
