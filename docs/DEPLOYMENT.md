# CoFlow 2.0 — Deployment

Version 0.1 · 4 October 2026 · **draft — nothing here is implemented yet**

How CoFlow 2.0 gets from the development machine to the computer it runs on, how that computer is set up
and administered, and what happens when something fails. Requirement IDs refer to
[REQUIREMENTS.md](REQUIREMENTS.md); the deployment requirements DEP-1…DEP-21 are summarised in §13.
Every host name, address and identity here is synthetic (`coflow-host`, `192.0.2.0/24`, `example.com`,
`<org>`). The configuration of a real installation never lives in this repository (P-12).

---

## 1. Overview

CoFlow is self-hosted: one owner per installation. The owner develops on a Windows machine with native
Python, fakes and synthetic data only. Real data lives on a separate, always-on Linux computer (the
**host**) in a Docker Compose stack. Code reaches the host only as a signed image built by public CI; the
host pulls, verifies and deploys it after the owner approves, and nothing on GitHub can reach into the
home network. Owner devices reach the host over an overlay VPN with SSH; the bot needs no inbound port.

```
  DEV: owner's Windows machine              GITHUB: public repository
  native Python, fakes, synthetic data      GitHub-hosted runners only
  +------------------------------+  push    +---------------------------------+
  | code, tests, docs            | -------> | CI: suites, image, smoke, gates |
  +------------------------------+          | release workflow on tag vX.Y.Z  |
                                            +----------------+----------------+
                                                             | one image per tag, by digest,
                                                             v keyless cosign signature
                                            +---------------------------------+
                                            | GHCR  ghcr.io/<org>/coflow      |
                                            +----------------+----------------+
                                                             ^ pull by digest (outbound only),
                                                             | verify signature, owner approval
  +----------------------------------------------------------+---------------------+
  | coflow-host: Linux, Docker Engine                                              |
  |   coflow-updater (systemd timer; the only thing that calls Docker)             |
  |   Compose project "coflow": core (the only DB writer), stt (no network, no DB) |
  |   volumes: data, models, secrets        published ports: none, or 127.0.0.1    |
  +------^---------------------^-------------------------+--------------+----------+
         | SSH over            | encrypted folder        | long polling | heartbeat
         | overlay VPN         | sync (recordings)       | (outbound)   | every 5 min
         |                     |                         v              v
  +------+---------------------+------+       +------------------+  +------------------+
  | Owner devices: desktop AI clients, | <---> | Telegram Bot API |  | dead-man switch  |
  | terminal, phone                    |       | (owner's chat)   |  | -> email / push  |
  +------------------------------------+       +------------------+  +------------------+
```

Two rules shape everything below. **One writer:** exactly one instance has the production role, and every
copy starts as non-production (§3). **Pull, verify, approve:** the host fetches releases, GitHub never
pushes to it, and no release runs on production without the owner's approval (§7).

## 2. Install paths (DEP-1)

| Path | For | Runs | Data |
|---|---|---|---|
| Docker Compose on Linux | Reference production; the same image on any Docker host or rented server | The release image and the shipped `compose.yaml` | Named volumes on the host's local disk |
| Native Python (Windows, Linux) | Development, contributors, device agents (R2) | The same code from the same lockfile | A local data root; synthetic only in the `dev` role |

One codebase and one universal lockfile; CI tests both paths (§6); Docker is never the only way. Docker
Desktop on the dev machine is optional, for prod-like runs with synthetic data, with the database in a
named volume, never on a Windows-drive bind mount (WAL locking through the VM file share is unreliable). A
Windows production host is unsupported (proposed, D-020): in the configurations tried in v1, Docker
Desktop on Windows required an interactive user session and its WSL VM stopped when idle.

## 3. Environments, roles and the one production writer (DEP-2, DEP-3, DEP-4)

### 3.1 Environments

| Role | Where | Data | Credentials | External writes |
|---|---|---|---|---|
| `dev` | The owner's Windows machine, native | Synthetic fixtures only; never real data | Fakes; the shared test set only when a test needs it | None |
| `staging` | The host, until the switch-over (roadmap stage 6) | Synthetic only | The shared test set | None: the outbox executor is off outside production; external-write acceptance (stage 5) runs against the recording fake calendar. The test bot is polled only for chat and approval cards |
| `production` | The host, from the switch-over | The owner's data | Production credentials | Through the outbox, after approval |
| `drill` | A throwaway Compose project on the host, or CI | A restored snapshot | None: fakes, no bot | None: internal network only |

- **Before the switch-over** the host runs exactly one instance, in the `staging` role. The delivery
  path grows with the roadmap: in stages 0–1 a tagged image reaches any Linux Docker host (a virtual
  machine is enough) through a manual `coflow update <digest>` over SSH; from stage 2 the home host runs
  the staging instance and verifies signatures; from stage 5 deploys use the full production path
  (approval card bound to the digest, write holds, health gate, automatic rollback). Stages 0–5 are
  accepted on synthetic data on the deployed instance. At the switch-over its synthetic data is removed,
  the author's data is imported, and it is promoted.
- **After the switch-over** there is no permanent staging stack: pre-release checks run in CI (§6), plus
  an on-demand `coflow drill` that restores the latest snapshot into a throwaway Compose project on an
  `internal: true` network, with fakes and no bot, runs the checks and destroys the project.
- **One shared set of test credentials** (a test bot, a test Google account) serves one instance at a
  time; a second poller on the test bot gets the same 409 as on production and stops (§3.3).
- **Data moves one way only:** production → encrypted backup → non-production restore. Nothing is
  imported into production from dev, staging or a drill; code arrives only as a signed image.

### 3.2 Instance identity

| Element | Created by | Stored in | Purpose |
|---|---|---|---|
| Instance id | `coflow init` | Config and database | Names the instance on the status page, in every MCP response and in logs |
| Role | `coflow init --role …`, `coflow promote` | Config and database | Decides what may run (table above) |
| Volume id | Random, at init | A file on the data volume, and the database | Detects a database copied or restored into another volume |
| Host id | Random, at init | `/etc/coflow/host-id`, mounted read-only into `core` | Detects a database moved to another machine; never derived from hardware |
| Epoch | 1 at the first promote, +1 on each promote | Database | Orders production generations (§3.3) |

At start, `core` compares these values with the database. Any mismatch (a copied database, a restore into
another volume, another machine) starts it as non-production with writers, outbox, bot and collectors off,
and prints the recovery command. Recreating containers, rebooting and upgrading keep production; a new OS
install or system disk creates a new host id and requires `promote` (§12).

### 3.3 Promote, retire and fencing

- `coflow retire` ends a production instance: writers, poller, collectors and outbox refuse to start.
- `coflow promote` makes an instance production. It requires that the previous production was retired,
  or `--previous-lost` with a typed confirmation phrase (the first promote has no predecessor).
- **Promote increments the epoch and requires re-issuing runtime credentials:** revoke and re-create the
  bot token, revoke the Google refresh tokens and log in again, re-issue device and MCP tokens. Credential
  rotation is the fence: an old host that comes back (say, by auto power-on after it was declared lost)
  holds only revoked credentials and cannot act.
- **Fenced mode.** A 409 Conflict from Telegram `getUpdates` (another instance polls the same token), a
  heartbeat with an older epoch than the current one, or a revoked bot token puts the instance into fenced
  mode: the outbox, collectors and every writer stop, not only polling, and the owner is alerted. Leaving
  fenced mode takes an explicit owner command.

## 4. The production host (DEP-14)

### 4.1 Baseline

`coflow doctor --host` checks it: a failed required item fails `doctor`, a recommended one only warns.

| Item | Level | Notes |
|---|---|---|
| A desktop-class or mini-PC machine, not a laptop | Required | A laptop run like a desktop app was v1's server failure |
| Key-only SSH over the private network | Required | Password login off; working before the machine leaves the desk (§8.2) |
| Time sync (NTP) | Required | `doctor` reports clock skew; storage is UTC, rituals use the profile's zone |
| No sleep, suspend or hibernate | Required | The OS sleep targets are disabled |
| Automatic power-on after power loss | Required | Firmware setting ("restore on AC power loss") |
| Database on an internal local disk | Required | Never a network share, USB disk or VM-shared mount; `doctor` refuses nfs, cifs/smb, 9p, fuse and virtiofs |
| Off-host backup present | Required | §10; older than 48 h is a warning |
| Full-disk encryption | Recommended | One tested recipe and its trade-off, below |
| UPS with clean shutdown | Recommended | A USB UPS watched by NUT shuts the host down before the battery runs out |

**Full-disk encryption.** Stage 0 documents one tested recipe: LUKS2 with TPM2 automatic unlock and a
recovery key kept off the machine. It survives an unattended power cut but protects a removed disk, not a
stolen machine, which boots to an unlocked disk unless the unlock is bound to the secure-boot state, the
firmware has a password and USB or network boot is off. Decide before real data arrives (§14).

### 4.2 Hardware

| | Minimum | Reference |
|---|---|---|
| CPU | 4 x86-64 cores | 8 cores |
| RAM | 16 GB | 32 GB; 64 GB only if a local model is wanted (`llm` profile) |
| Disk | SSD | 1–2 TB NVMe |

CPU transcription decides the hardware. Before buying, run `coflow bench stt` on the candidate machine or
one of the same CPU class (real-time factor, peak memory). Targets (NFR-11): a 1-minute voice note in
≤ 20 s, a 1-hour recording in ≤ 30 min on the reference hardware. arm64 hosts are R2 (DEP-20).

Running costs of the host (electricity, object storage for backups, the dead-man service) are measured
after stage 2 and published here together with the hardware choice (§14).

### 4.3 Operating system and reboots

Debian 13 is recommended, Ubuntu 24.04 LTS acceptable: a server install, Docker Engine and the Compose
plugin from Docker's own repository (not Docker Desktop). Unattended security updates are on. Automatic
reboots happen only in a configured window outside the night archive window, never during a deploy: a
pending reboot waits for the updater's deploy lock, and no deploy starts that would run into the window.

## 5. The Compose stack (DEP-5, DEP-6)

### 5.1 Services

| Service | What it does | Network | Data access | Stop grace |
|---|---|---|---|---|
| `core` | The only database writer. A supervisor runs bot long polling, the scheduler, the outbox, MCP over HTTP and the status page; `/healthz` and `/readyz` answer on loopback and the container network | `core-net` (outbound to Telegram, the model provider, Google); listener published on 127.0.0.1 only | `data` (rw), `secrets` (rw), host id (ro) | 30 s |
| `stt` | Stateless faster-whisper worker | None | Inbox (ro), work directory (rw), `models` (ro); no database | 120 s |
| `backup` (profile) | restic: snapshots and media to the off-host repository (§10) | Outbound to the backup target only | Snapshots and media (ro) | — |
| `llm` (profile) | Optional local model | `llm-internal` (`internal: true`) | Its own model volume | — |

Rules, enforced by a Compose lint in CI:

- `core` is never scaled; no other service opens the database. `stt` shares no network with `core`'s API;
  `core` validates its transcript JSON against a schema with size limits, as untrusted data (P-10). An
  out-of-memory kill of `stt` is a transient error, and the bot keeps answering.
- No published ports, or 127.0.0.1 only: Docker-published ports can bypass host firewall rules such as
  ufw ([Docker docs: packet filtering and firewalls](https://docs.docker.com/engine/network/packet-filtering-firewalls/))
  (PRV-5). Never a Docker socket mount.
- Every service has a health check, a restart policy, a stop grace period, CPU and memory limits and
  `local` log rotation. Restart policies act only when a process exits, so the supervisor exits non-zero
  on a fatal stall. Memory checks and thread counts read cgroup limits, not host totals.
- **Logs carry ids only** (interaction, instance and record ids, error codes): never message, transcript
  or journal text, never secrets, and they are not shipped to a third-party service.

### 5.2 Volumes and secrets

| Volume | Contents | Backed up |
|---|---|---|
| `data` | `db/` (SQLite, WAL), `inbox/`, `media/`, `work/`, `snapshots/`, the deletion log (§10.2), the volume id | Yes: snapshots and media |
| `models` | STT (and optional local-model) weights, downloaded at init, pinned to a revision and a sha256 that `doctor` verifies; a mismatch stops STT | No, re-downloadable |
| `secrets` | Runtime-written tokens (OAuth refresh tokens, sessions), encrypted | No; after a restore they show as "needs login" |

Static secrets (bot token, model API key, OAuth client, backup key) are Compose file secrets read through
a `*_FILE` convention (mode 0600), never environment variables. Directories are mounted, never a single
database file, so `-wal` and `-shm` stay with it; an override swaps named volumes for local bind mounts.

### 5.3 The image

- Stateless (no secrets, no models); a non-root fixed UID; a read-only root filesystem with `tmpfs` for
  `/tmp`; all capabilities dropped; `no-new-privileges`; an exec-form entrypoint under a minimal init.
- Base images pinned by digest; dependencies from the hashed lockfile; version, commit and digest stamped
  into a label and a file (OPS-10). A licence gate fails on AGPL or GPL components in the core image, and
  on LGPL components outside plugins unless listed under the D-001 audio-decoding exception (D-001).
- R2 (DEP-20): published SBOM and provenance attestations, arm64 and CUDA variants, repository-policy checks.

### 5.4 Compose excerpt

Illustrative only; all values are synthetic, and the shipped file is defined in stage 0.

```yaml
name: coflow
x-common: &common                       # applied to every service
  restart: unless-stopped
  init: true
  user: "10001:10001"
  read_only: true
  tmpfs: ["/tmp"]
  cap_drop: [ALL]
  security_opt: ["no-new-privileges:true"]
  logging: { driver: local, options: { max-size: "10m", max-file: "5" } }

services:
  core:
    <<: *common
    image: ghcr.io/<org>/coflow@sha256:<release-digest>   # always by digest, never by tag
    command: ["coflow", "serve"]
    secrets: [telegram_bot_token, model_api_key]          # read via *_FILE, never env values
    volumes: ["data:/data", "secrets:/secrets", "/etc/coflow/host-id:/run/coflow/host-id:ro"]
    ports: ["127.0.0.1:8730:8730"]      # MCP and status page; never on another address
    networks: [core-net]
    healthcheck: { test: ["CMD", "coflow", "probe", "readyz"], interval: 30s, start_period: 60s }
    stop_grace_period: 30s
    deploy: { resources: { limits: { cpus: "2", memory: 2g } } }

  stt:
    <<: *common
    image: ghcr.io/<org>/coflow@sha256:<release-digest>
    command: ["coflow", "stt-worker"]
    network_mode: none                  # no network, no database
    volumes:
      - { type: volume, source: data, target: /inbox, read_only: true, volume: { subpath: inbox } }
      - { type: volume, source: data, target: /work, volume: { subpath: work } }
      - models:/models:ro
    healthcheck: { test: ["CMD", "coflow", "stt-worker", "--health"], interval: 60s }
    stop_grace_period: 120s
    deploy: { resources: { limits: { cpus: "4", memory: 4g } } }
  # profiles "backup" and "llm", and the top-level networks, volumes and secrets, are omitted
```

## 6. CI (DEP-7)

Public CI runs only on GitHub-hosted runners. A self-hosted runner is never attached to this repository:
GitHub's guidance is that self-hosted runners "should almost never be used for public repositories"
([secure use reference](https://docs.github.com/en/actions/reference/security/secure-use)), because code
from a fork's pull request could run on them — here, on the machine that holds the journal.

| Job | Runs on | What it proves |
|---|---|---|
| Native suite | Windows and Linux runners | The offline suite with fakes passes on both platforms |
| Image build | Linux | Digest-pinned base, hashed lockfile, image lint (non-root, read-only root, no secrets, no models), licence gate |
| Suite in the image | Linux | The same suite passes inside the image that production runs |
| Compose smoke | Linux | `docker compose up --wait` with fakes and egress blocked turns healthy; `doctor` passes |
| Exposure test | Linux | Nothing answers on a non-loopback host address (PRV-5) |
| Upgrade test | Linux | The previous release on a synthetic database, upgraded by the new image, ends with the same schema as a clean install |
| Restore test | Linux | A backup restores into a fresh volume with equal counters; the deletion log is re-applied |
| Literal gate | Linux | No owner or infrastructure literals: emails, phone numbers, non-example domains, IPs outside documentation ranges, host names, tunnel or VPN ids (P-12) |
| Secret scanning | Linux | No secret in the code, the image or the logs |
| DCO | — | Every commit carries a sign-off (D-015) |
| MCP catalogue | Linux | The generated tool catalogue matches the code (MCP-3) |

Repository rules:

- Actions pinned by commit SHA, enforced by the allowed-actions policy. The default workflow token is
  read-only; `id-token: write` exists only in the release job, behind a protected `release` environment.
- Pull requests from forks hold no secret and never publish; outside contributors' workflows need approval.
- Dependency updates come from a bot with a cooldown and are merged by a human; auto-merge is off.
- Rulesets: `main` is protected and requires the checks above. `v*` tags can be created only by the
  release workflow, only on commits reachable from protected `main`, and are never moved or deleted.

## 7. Releases and the updater (DEP-8, DEP-9, DEP-10)

### 7.1 Releases

- Conventional Commits. A release pull request collects the changelog; merging it lets the release
  workflow create the `vX.Y.Z` tag (pre-releases `v2.0.0-alpha.N`). Stage 0 settles the exact mechanism,
  since tags pushed with the default workflow token trigger no other workflow.
- Each tag builds exactly one image, pushed to GHCR by digest and signed keyless with cosign: the release
  job's OIDC token obtains a short-lived certificate and the signature goes into a public transparency
  log, so there is no long-lived signing key to steal
  ([Sigstore: signing overview](https://docs.sigstore.dev/cosign/signing/overview/)).
- Migration notes (ids, an irreversible flag, the target schema version) travel in the image labels,
  which the signed digest covers; the updater reads them from the registry without running the image.
- Builds of `main` are not published; the host runs only tagged releases. Public images need no pull
  credentials, so the host holds no registry secret.

The host verifies every image against one pinned identity (repository, release workflow path, tag ref):

```
cosign verify ghcr.io/<org>/coflow@sha256:<digest> \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --certificate-identity-regexp '^https://github\.com/<org>/coflow/\.github/workflows/release\.yml@refs/tags/v[0-9]+\.[0-9]+\.[0-9]+(-alpha\.[0-9]+)?$'
```

### 7.2 The updater

Generic updaters do not fit: none knows about snapshots, migrations, the outbox or Telegram's one-poller
rule, and a widely used one, Watchtower, was archived on 17 December 2025
([announcement](https://github.com/containrrr/watchtower/discussions/2135)). CoFlow ships its own:

- `coflow-updater` is a small host-side component (stdlib-only Python or ASCII-only shell), installed by
  `coflow init --role production` (before the switch-over, by the staging init on the same path) and run
  by a systemd timer, hourly by default. It is **the only thing allowed to call Docker**; the host-side
  `coflow` command is a thin wrapper around it.
- It is its own signed release asset, updated only by an explicit owner command after a separate
  approval, never from a pulled application image. Nothing from a new image runs before approval.

### 7.3 Approvals

| Stages | Channel | How |
|---|---|---|
| 0–4 | CLI over SSH (admin key) | `coflow-update approve <version>` shows the computed facts below and records the approval |
| From 5 | Approval card in the owner's bot (P-4) | `core` shows the card; on approval it writes the approved release to a file on a shared volume (`control/` on the data volume), which the updater reads |

The preview hash covers the image digest, the signer identity, the target instance id and role, the
migration ids with their irreversible flags, and an expiry. The updater recomputes it and refuses an
approval that does not match, has expired, or comes from anywhere but the core of the instance it manages
(the production core; before the switch-over, the single staging instance), never from a drill. The
contributor-written changelog appears below the computed facts, marked as untrusted text.

### 7.4 Deploy sequence

1. **Detect** a new release tag; ignore tags already handled.
2. **Pull by digest; verify the signature** against the pinned identity; refuse and alert otherwise.
3. **Read the migration notes** from the signed labels; build the approval preview.
4. **Wait for approval** (§7.3).
5. **Check preconditions:** free space (§11); no transcription running; outside archive and reboot windows.
6. **Hold writes** (table below).
7. **Snapshot** the database (`VACUUM INTO`) and check its integrity.
8. **Stop** `core` and `stt` within their grace periods.
9. **Migrate** in a one-off container of the new image: forward-only, never on service start.
10. **Start** the new digest with the holds still on.
11. **Health gate and smoke check** without external writes: `/readyz`, schema version, supervisor tick,
    database writable, STT model loads, MCP answers read-only.
12. **Release the holds;** record the deploy in the status-page history; prune old images and snapshots.

| Held during steps 6–11 | Effect |
|---|---|
| Bot polling | Telegram keeps unconfirmed updates; no owner message is lost |
| Outbox | No external write happens, so a rollback has nothing to undo |
| Ingestion | R1: inbox registration pauses and files wait. R2: the ingestion API answers 503 with `Retry-After` |
| MCP | Read-only |
| Collectors and scheduler | Paused |

### 7.5 Rollback and its limits

- **Automatic only while the holds are on.** If migration, the health gate or the smoke check fails, the
  updater stops the new version, restores the pre-migration snapshot, re-applies the deletion log (§10.2),
  starts the previous digest, releases the holds after its health gate, and alerts the owner.
- **After the holds are released there is no automatic rollback;** fix forward with a new release. A
  manual `coflow rollback --to-snapshot` warns that every write since the snapshot will be lost. One
  previous digest and one snapshot are kept; expand-only migrations and schema ranges are R2.
- **A rollback cannot undo** executed outbox actions (calendar events, sent messages), data already sent
  to the model provider, or bot updates already confirmed to Telegram.
- **If the rollback itself fails,** the updater leaves everything stopped and alerts through the off-host
  monitor, because the bot is down too (§11).

### 7.6 Later: optional push deploy (DEP-21)

A `production` environment (tags only, the owner as required reviewer) whose job joins the private network
as an ephemeral node with workload identity; the ACL lets it reach only SSH on the host, where a forced
command runs the same updater with the version as its only argument. Still never a self-hosted runner.

## 8. Access and remote administration (DEP-11, DEP-12)

### 8.1 Access recipes

| Recipe | Status | Who can see plaintext | Data classes (default policy) | Check |
|---|---|---|---|---|
| Overlay VPN (WireGuard-based, e.g. Tailscale) + SSH | R1 default | The owner's devices and the host. The coordinator sees metadata (devices, addresses, connection times) and, without node-key signing, could add a device | Work and system data; the journal only over SSH: the journal-append key, or journal reads in the owner's own admin terminal (§8.2, §9.3); never through the MCP bridge or HTTP | `coflow doctor --access vpn` |
| LAN, SSH only | R1 | Nobody else | As above | `coflow doctor --access lan-ssh` |
| LAN, HTTPS terminated on the host | R1 alternative | Nobody else (private CA or pinned certificate) | As above | `coflow doctor --access lan-tls` |
| Edge tunnel that terminates TLS | Opt-in, R2 with MCP-5 | The edge provider sees everything that passes | Only MCP and OAuth paths, on a separate edge listener; never the journal; third-party content only if allowed in `DATA_FLOWS.md` | `coflow doctor --access edge` |

- **Never plaintext HTTP on a non-loopback address**, the VPN interface included. Owner devices reach MCP
  and the status page through the SSH bridge (§8.2), an SSH port forward, or HTTPS terminated on the host.
- **Overlay VPN:** turn on node-key signing (tailnet lock) and two-factor login on the coordinator
  account; the ACL lets only the owner's devices reach the host's SSH.
- **Edge tunnel:** the provider decrypts all traffic, and regional ISP blocking of shared edge IP ranges,
  reported in some countries in court-ordered anti-piracy blocking, makes it unreliable. It reaches only a separate edge
  listener with the MCP and OAuth paths for cloud AI clients (MCP-5); everything else is refused there.
- Each recipe has a `DATA_FLOWS.md` row. `coflow doctor --access`, run from another device, reports which
  recipes actually work: deployment state comes from health output, not from prose.
- **Recommended: a second remote path** independent of the VPN coordinator: a WireGuard port forward on
  the home router, or a remotely switchable smart plug plus the firmware's power-on-after-AC setting.

MCP for the owner's devices (MCP-1): tokens carry a scope (`read` or `read-write`); tokens for
coding-capable clients, such as AI coding agents, are read-only on production by default; every MCP
response states the instance role and id, so a client cannot confuse dev and production.

### 8.2 Remote administration

Key-only SSH over the private network is a precondition for a production host and is tested before real
data arrives. Each purpose has its own key with a forced command in `authorized_keys`:

| Key | Account | Forced command | Restrictions |
|---|---|---|---|
| MCP bridge (one per client) | `coflow-mcp` | `coflow-bridge mcp --client=<id>` | No pty, no forwarding. Not in the `docker` group; the bridge connects to `core`'s HTTP MCP on 127.0.0.1 with that client's token, so scopes and logging apply |
| Journal append | `coflow-journal` | `coflow journal add` | Write-only, through a journal-write token that cannot read. Text comes from stdin or `$EDITOR`, never from arguments (shell history, process list) |
| Admin | `coflow-admin` | None (shell) | Passphrase-protected or hardware-backed; never loaded into an ssh-agent that AI coding agents can use; Docker only through `sudo` |

```
# ~coflow-mcp/.ssh/authorized_keys (synthetic example)
command="coflow-bridge mcp --client=desktop-ai",restrict ssh-ed25519 AAAAC3...EXAMPLE desktop-ai
# ~coflow-journal/.ssh/authorized_keys
command="coflow journal add",restrict,pty ssh-ed25519 AAAAC3...EXAMPLE journal
```

An AI client on the desktop runs `ssh -i <mcp-key> coflow-mcp@coflow-host` as its stdio command; the
journal is written with `ssh -t -i <journal-key> coflow-journal@coflow-host`, which opens an editor.
Every operation is a `coflow` command run by the admin over SSH: `status`, `logs` (ids only), `doctor`,
`backup`, `restore`, `drill`, `update`, `rollback`, `stop`, `promote`, `retire`, `bench stt`. Journal
read commands run only in the owner's own terminal, never in a session an AI coding agent controls.
Fallbacks when the VPN is down: LAN SSH, the second remote path (§8.1), the physical runbook.

## 9. Data on the move

### 9.1 Recordings and voice notes (R1)

- **Recordings** reach the inbox through an encrypted peer-to-peer folder sync (for example Syncthing)
  from the desktop (the recorder's export folder) and the phone; the sync tool runs on the host outside
  `core`. Its discovery and relay servers see device ids and addresses (relays carry only encrypted data);
  both can be switched off to sync over the VPN only. Telegram Desktop exports travel the same way.
- A file is **registered only after complete arrival** (temporary name plus atomic rename, or a
  stable-size check), found by polling, within ≤ 2 min. In R1 nothing deletes the source on the device.
- **Short voice notes go through the bot.** Telegram bots can download files of up to 20 MB
  ([getFile](https://core.telegram.org/bots/api#getfile)), so long recordings never use this path.
- Audio is transcribed by `stt` on the host, never by a cloud service by default.

### 9.2 Device agents (R2, stage 6)

- **Ingestion API (DEP-16):** resumable chunked uploads on the `core` listener; per-device tokens (listed,
  revocable, ingest-only, scoped to the declared source type); idempotency keys; content-hash check; size
  and rate limits. **Windows desktop uploader (DEP-17)** and the activity agent (RHY-5) push through it
  and buffer while the host is unreachable.
- Device-pushed text is tagged with its device provenance; it is never treated as the owner's instruction
  and never becomes a source of rules or approvals.

### 9.3 The journal

The journal is a separate data class. Whether journal text may go to the model provider (for analysis
modules the owner enables) and over which access recipes is a **per-installation policy in
`DATA_FLOWS.md`**. `coflow init` asks for the journal switch per analysis module with no preselected
answer and records the choice (PRV-9, D-025); the project's advice for new installations is "off"
(proposed, D-025), and the owner can change it later.

- **Model provider:** as chosen at init. **Never, whatever the policy:** MCP, the status page, the edge
  listener.
- **Channels:** `coflow journal add` over the journal SSH key or on the host (end to end to the host).
  Entries written through the bot pass Telegram's servers (bot chats are not end-to-end encrypted), which
  is listed in `DATA_FLOWS.md`; the SSH path is the messenger-free way.
- **Backups** are encrypted off-host. A rented server as the host puts the journal at rest with the
  provider and needs an explicit owner switch.
- Voice journal entries are transcribed on the host only. The dev machine never holds journal data.

### 9.4 Rows that deployment adds to `DATA_FLOWS.md`

The overlay VPN coordinator (devices, addresses, connection times); folder-sync discovery and relays
(device ids, addresses; relays see ciphertext); Telegram (every bot message, including journal entries
written in the bot); GHCR (the host's address and pull times); off-host backup storage (ciphertext, sizes,
times; EU jurisdiction); the dead-man switch (source address, ping times, a rotating check id); the edge
tunnel, opt-in (plaintext of MCP and OAuth traffic); a rented server, opt-in (all data at rest).

## 10. Backups, restore and drills (OPS-5)

### 10.1 Backups

- A daily consistent snapshot (`VACUUM INTO`) plus the pre-deploy snapshot (§7.4).
- **Default off-host copy:** an encrypted restic repository in EU object storage, filled by the `backup`
  profile with the snapshot and the media. The host's credential can write but not delete, or the bucket
  uses object lock (restic creates and removes lock files, so test backups with that credential).
- The repository key is kept in the owner's password manager, never only on the host. **Prune** runs
  monthly from another owner machine with a separate delete-capable credential, never stored on the host.
- **Maximum retention** is documented in `DATA_FLOWS.md` so that deleted data leaves the backups; proposed
  default 14 daily, 8 weekly, 6 monthly (about six months), with any object-lock period shorter. A weekly
  `restic check` reads a subset of the data.
- **Optional fast tier:** a second internal disk or a rotated USB disk; never the dev laptop (it sleeps,
  travels and runs AI coding agents). The `secrets` volume is never backed up. An off-host backup older
  than 48 h is a warning in health and in the morning plan.

### 10.2 Restore and deletions

`coflow restore` (Docker or native) stops all processes, restores the database (handling the WAL files)
and the media, re-applies the deletion log and starts as non-production; only `promote` makes it production.

**Deletions survive restores.** Deletions and blanking (PRV-7, BOT-3) go into an append-only log of ids
and hashes, no content, kept outside the SQLite snapshot (on the data volume and in the off-host copy). It
is re-applied before any restored instance serves (rollback, drill, rebuild, move).

### 10.3 Drills

| Drill | Pass condition | When |
|---|---|---|
| Restore (`coflow drill`) | A snapshot restores into a throwaway project with equal counters; the project is destroyed | Monthly; in CI on every pull request |
| Rollback | A deliberately broken release rolls back automatically with no lost bot message and no external write | Before R1 (stage 5); after every updater change |
| Failed rollback | Everything stays stopped and the off-host alert arrives | Before the switch-over |
| Network unplug | An alert reaches the phone within 30 min | At host setup (stage 2 at the latest); twice a year |
| Power cut | After power returns, the instance is healthy without any action | At host setup and after enabling encryption; yearly |
| 48 h outage + travel runbook | No duplicate import, no blind external write; the bot reports the possible gap | Before the switch-over; yearly |
| Rebuild on another machine | §12; equal counters within the target time | Stage-6 exit; after every major host change |

## 11. Monitoring, disk space and outages (OPS-6, DEP-13, DEP-15)

**Health** shows role, instance id and epoch, version and image digest, deploy history, queues, the STT
backlog and benchmark, source freshness, backup and off-host ages, disk and memory, clock skew, and token
expiry (reported ≥ 14 days ahead), on the status page, in the bot's `/status` and in the morning plan.

**Off-host monitor.** Nothing inside the host can report that the host is down. The R1 default is an
external dead-man-switch service, pinged every 5 minutes with a content-free, rotating check id; missed
pings (and a failed-rollback signal from the updater) make it alert the owner by email or push through its
own channel, not the bot. It learns the source address and timing (a `DATA_FLOWS.md` row). Detecting a
second production instance is the job of the 409 detector and fencing (§3.3), not the monitor.

**Disk space (DEP-13):**

| Condition | Behaviour |
|---|---|
| Disk > 80 % used | Warning in health and the morning plan |
| Disk > 90 % used | Archive transcription and new uploads pause; the bot and database writes continue |
| Before a deploy | Refused unless free space ≥ 2 × database size + image size + 5 GB |
| After a deploy | The updater prunes old images and snapshots beyond the retained ones |

**Outages (DEP-15):**

- While the host or its network is down, devices buffer and the off-host monitor alerts the owner; on
  recovery the host catches up, and outbox items with a stale preflight are re-checked, never run blindly.
- Telegram keeps undelivered bot updates for about 24 hours
  ([Bot API: getting updates](https://core.telegram.org/bots/api#getting-updates)). After more than 20 h
  without polling, the bot
  warns on recovery that messages sent before `<time>` may be lost and should be resent.
- Before the switch-over: a 48 h outage drill and a "host unreachable while travelling" runbook (check the
  monitor; try the VPN, then the second remote path; power-cycle; if the host is lost, rebuild per §12).

## 12. Moving to new hardware or a rented server (DEP-18, DEP-19)

1. `coflow retire` on the source, if reachable; verify through health output that it no longer writes.
2. A final backup to the off-host repository.
3. Prepare the target (§4), `coflow init`, restore from the off-host backup (starts as non-production).
4. Compare table counters and the last public ids with the source's final report.
5. `coflow promote` (`--previous-lost` if the source is gone): new epoch, rotated credentials (§3.3).
6. Re-point devices: folder sync, VPN ACL, MCP clients.

| Secret | After a move or restore |
|---|---|
| OAuth client, model API key, backup repository key | Static: may be kept in the owner's password manager and re-entered |
| Bot token | Kept in the password manager, but promote revokes and re-creates it; store the new one |
| Google refresh tokens, user sessions, device tokens, MCP tokens | Runtime: always re-created |

After a restore, `doctor` lists every missing secret with the command that re-creates it.

**Stage-6 exit:** before the switch-over completes, the instance is rebuilt on a different machine from
the off-host backup only, following this document, within a measured time (target ≤ 2 h excluding the OS
install) and with equal counters. Repeat after every major host change.

**DR targets (R2, DEP-19):** RPO ≤ 24 h, RTO ≤ 4 h, onto another Linux machine or a rented server (which
holds the journal at rest with a provider: an explicit owner switch in `DATA_FLOWS.md`, decidable in
advance). The dev machine is not a DR target.

## 13. R1, R2 and Later

| ID | Requirement | Pri | Section |
|---|---|---|---|
| DEP-1 | Two install paths: Docker Compose on Linux (reference production), native Python (dev, contributors, device agents) | R1 | §2 |
| DEP-2 | Instance identity and roles: instance id, role, volume id, host id | R1 | §3.2 |
| DEP-3 | One production writer: promote, retire, epoch, credential rotation, fenced mode | R1 | §3.3 |
| DEP-4 | Environments: one staging instance until the switch-over, `coflow drill`, the shared test credentials | R1 | §3.1 |
| DEP-5 | Container image: stateless, hardened, pinned, licence gate | R1 | §5.3 |
| DEP-6 | Reference Compose stack: `core` + `stt`, profiles, volumes, limits, id-only logs | R1 | §5 |
| DEP-7 | Public CI on GitHub-hosted runners and repository rules | R1 | §6 |
| DEP-8 | Releases and keyless signatures with one pinned identity | R1 | §7.1 |
| DEP-9 | Host-side updater, approvals by stage, write holds, deploy history | R1 | §7.2–7.4 |
| DEP-10 | Rollback: automatic only while the holds are on; limits stated | R1 | §7.5 |
| DEP-11 | Remote administration: per-purpose SSH keys, the `coflow` CLI | R1 | §8.2 |
| DEP-12 | Access recipes with checks and `DATA_FLOWS.md` rows; the edge-tunnel recipe is opt-in, R2 with MCP-5 | R1 | §8.1 |
| DEP-13 | Disk space policy | R1 | §11 |
| DEP-14 | Production host baseline, hardware guidance, reboot policy | R1 | §4 |
| DEP-15 | Outage behaviour | R1 | §11 |
| DEP-16 | Resumable ingestion API with per-device tokens | R2 | §9.2 |
| DEP-17 | Windows desktop uploader (device agent) | R2 | §9.2 |
| DEP-18 | Moving an instance; the rebuild drill as the stage-6 exit | R2 | §12 |
| DEP-19 | DR targets: RPO ≤ 24 h, RTO ≤ 4 h | R2 | §12 |
| DEP-20 | Supply-chain extras: published SBOM and provenance attestations, arm64 and CUDA variants, repository-policy checks | R2 | §5.3 |
| DEP-21 | Optional push deploy over the private network | Later | §7.6 |

Related: NFR-11 (STT benchmark, §4.2), PRV-5 (no exposure, §5.1, §6), MCP-1 (owner-device MCP, §8),
MCP-5 (internet-facing MCP, R2, §8.1), OPS-5 (backups, §10), OPS-6 (health, off-host monitor, §11).

## 14. Open questions for the owner

Resolved on 4 October 2026: the author's existing gaming desktop becomes the production host and moves
from Windows to Linux (D-020); its old v1 instance is retired in the process.

1. **Operating system.** Debian 13 or Ubuntu 24.04 LTS? The docs test one recipe (encryption, baseline,
   reboots) end to end. Recommendation: Debian 13, unless Ubuntu is more familiar.
2. **Hardware.** Does the existing desktop meet the reference class (8 cores, 32 GB, NVMe), and is its GPU
   worth using for transcription or a local model (the GPU image variant is R2, DEP-20)? Decide after
   `coflow bench stt` on that machine.
3. **Overlay VPN provider and tailnet lock.** A hosted coordinator (e.g. Tailscale), a self-hosted one, or
   plain WireGuard? Recommendation: hosted, with tailnet lock and 2FA, plus a WireGuard port forward as
   the second remote path.
4. **Backup object-storage provider.** Which EU provider? It must offer a write-without-delete credential
   or object lock, work with restic, and get its `DATA_FLOWS.md` row (jurisdiction, key holder, retention).
5. **Full-disk encryption: yes or no?** (a) LUKS with TPM automatic unlock and an off-machine recovery
   key: survives power cuts, protects a removed disk but not a stolen machine; (b) a passphrase at boot:
   stronger, but every power cut needs someone at the machine; (c) none: simplest, a stolen disk exposes
   the data. Decide before real data arrives; adding encryption later usually means reinstalling.
