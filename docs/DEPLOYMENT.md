# CoFlow 2.0 — Deployment

Version 0.2 · 18 October 2026 · **draft — nothing here is deployed yet; stage 0A runs natively in the
`dev` and `validation` roles, and the delivery pipeline is stage 0B**

How CoFlow 2.0 gets from the development machine to the computer it runs on, how that computer is set up
and administered, how it is reached from the internet, and what happens when something fails.
Requirement IDs refer to [REQUIREMENTS.md](REQUIREMENTS.md) (v0.7); the deployment requirements
DEP-1…27 are summarised in §13. The host decisions are D-019 to D-024 and D-050 to D-053; what in them is
the owner's and what is proposed is stated in [DECISIONS.md](DECISIONS.md). Every host name, address and
identity here is synthetic (`coflow-host`, `192.0.2.0/24`, `198.51.100.0/24`, `example.com`,
`example.org`, `<org>`). The configuration of a real installation never lives in this repository (P-12).

---

## 1. Overview

CoFlow is self-hosted: one owner per installation. The owner develops on a Windows machine with native
Python, fakes and synthetic data only. Real data lives on a separate, always-on Linux computer (the
**host**) in a Docker Compose stack — a desktop, a mini-PC or a dedicated laptop under the laptop profile
(§4.1); the author's is a home laptop with a GPU, which holds real data only after a 30-day gate (D-050,
§4.4). Until the decision adoption gate, real decision history lives in a validation instance on the
owner's machine (DEP-23, §3.1); from the adoption, in the production instance on the gated host. Code reaches the host only as a signed image built by public CI; the host pulls,
verifies and deploys it after the owner approves, and nothing on GitHub can reach into the home network.
Owner devices reach the host over an overlay VPN with SSH; the bot needs no inbound port. The only public
entry, for cloud AI clients from stage-8 module 0, is the owner's own relay, which forwards encrypted
traffic and never decrypts it (D-053, §8.1).

```
  DEV: owner's Windows machine              GITHUB: public repository
  native Python, fakes, synthetic data;     GitHub-hosted runners only
  the validation instance (real snapshot,
  data root outside any repository)
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
  | coflow-host: Linux, Docker Engine (a desktop, mini-PC or dedicated laptop)     |
  |   coflow-updater (systemd timer; the only thing that calls Docker)             |
  |   Compose project "coflow": core (the only DB writer), stt (no network, no DB, |
  |   optional GPU); R2: edge (no DB; TLS, OAuth pages, MCP parsing)               |
  |   volumes: data, models, secrets        published ports: none, or 127.0.0.1;  |
  |                                         R2: edge only on the relay tunnel      |
  +---^------------------^-------------------+-----------+--------------^----------+
      | SSH over         | encrypted folder  | long      | heartbeat    | WireGuard tunnel
      | overlay VPN      | sync (recordings) | polling   | every 5 min  | opened by the host
      |                  |                   v           v              |
  +---+------------------+---+  +------------------+  +-----------+  +-+------------------+
  | Owner devices: desktop   |  | Telegram Bot API |  | dead-man  |  | owner relay (R2):  |
  | AI clients, terminal,    |  | (owner's chat)   |  | switch -> |  | TLS passthrough by |
  | phone                    |  +------------------+  | email/push|  | server name; no    |
  +--------------------------+                        +-----------+  | data, no keys      |
                                                                     +-^------------------+
                       DNS provider of a separate domain (DNSSEC, CAA)  | HTTPS
                                                                       cloud AI clients
```

Two rules shape everything below. **One writer:** exactly one instance has the production role, and every
copy starts as non-production (§3). **Pull, verify, approve:** the host fetches releases, GitHub never
pushes to it, and no release runs on production without the owner's approval (§7).

## 2. Install paths (DEP-1)

| Path | For | Runs | Data |
|---|---|---|---|
| Docker Compose on Linux | Reference production; the same image on any Docker host or rented server | The release image and the shipped `compose.yaml` | Named volumes on the host's local disk |
| Native Python (Windows, Linux) | Development, contributors, the validation instance, device agents (R2) | The same code from the same lockfile | A local data root; synthetic only in the `dev` role; the owner's snapshot only in the `validation` role |

One codebase and one universal lockfile; CI tests both paths (§6); Docker is never the only way. Docker
Desktop on the dev machine is optional, for prod-like runs with synthetic data, with the database in a
named volume, never on a Windows-drive bind mount (WAL locking through the VM file share is unreliable). A
Windows production host is unsupported (accepted, D-020): in the configurations tried in v1, Docker
Desktop on Windows required an interactive user session and its WSL VM stopped when idle.

## 3. Environments, roles and the one production writer (DEP-2, DEP-3, DEP-4, DEP-23)

### 3.1 Environments

| Role | Where | Data | Credentials | External writes |
|---|---|---|---|---|
| `dev` | The owner's Windows machine, native | Synthetic fixtures only; never real data; it accepts only snapshots marked synthetic | Fakes; the shared test set only when a test needs it | None |
| `validation` | The owner's machine, native, data root outside any repository; until the decision adoption gate | The one-way snapshot of the owner's current system (decisions from stage 0A; people, sessions, commitments and tasks from stage 1), as read-only mirrors; the monitoring of selected project-log decisions; no journal | None: no bot, no production token | None; refused by CI and the live evaluation harness; its data reaches production only by a restore onto a host that passed its gate (DEP-23, DEP-27) |
| `staging` | The host, until the decision adoption gate, or the switch-over (roadmap stage 6) if adoption has not happened | Synthetic only | The shared test set | None: the outbox executor is off outside production; external-write acceptance (stage 5) runs against the recording fake calendar. The test bot is polled only for chat and approval cards |
| `production` | The host, from the decision adoption gate (proposed, D-046), or from the switch-over if adoption has not happened | The owner's decisions from the adoption; the kinds the owner's existing system still owns as one-way read-only mirrors until the switch-over; then all of the owner's data | Production credentials | Through the outbox, after approval |
| `drill` | A throwaway Compose project on the host, or CI | A restored snapshot | None: fakes, no bot | None: internal network only |

- **Until the decision adoption gate** (or the switch-over, if adoption has not happened) the host runs
  exactly one instance, in the `staging` role. The delivery path grows with the roadmap: in stage 0A
  nothing is deployed; in stages 0B–1 a tagged image reaches any Linux Docker host (a virtual machine is
  enough) through a manual `coflow update <digest>` over SSH; from stage 2 the home host runs the staging
  instance, verifies signatures and starts its **30-day gate** (§4.4); from stage 5 deploys use the full
  production path (approval card bound to the digest, write holds, health gate, automatic rollback).
  Stages 0A–5 are accepted on synthetic data on the deployed instance and on the named real cases in the
  validation instance or, after the adoption, on drill copies of the production database.
- **The validation instance** holds the real snapshot from stage 0A. The owner's named cases run on
  throw-away copies of its database (OPS-16). Until the adoption every real record is written in the
  owner's existing system (D-039, D-046).
- **At the decision adoption gate** (not before 1 December 2026; proposed, D-046) the host's staging
  instance is retired, and a backup of the validation instance is restored onto the host and promoted to
  production with decisions only (§3.3; the host must have passed its gate). The validation instance on
  the owner's machine is retired. From then on the kinds the owner's existing system still owns (people,
  sessions, commitments, tasks, goals) are imported one way into production as read-only mirrors until
  the switch-over, and the real cases of stages 3–5 run on throw-away drill copies of the production
  database. At the switch-over everything else is imported into that production instance; if the
  adoption has not happened by then, the staging instance's synthetic data is removed, the author's data
  is imported, and it is promoted — only if the host passed its gate.
- **After the decision adoption** (or the switch-over) there is no permanent staging stack: pre-release
  checks run in CI (§6), plus an on-demand `coflow drill` that restores the latest snapshot into a
  throwaway Compose project on an `internal: true` network, with fakes and no bot, runs the checks and
  destroys the project, before the owner approves a production deploy.
- **One shared set of test credentials** (a test bot, a test Google account) serves one instance at a
  time; a second poller on the test bot gets the same 409 as on production and stops (§3.3).
- **Data moves one way only:** production → encrypted backup → non-production restore, and the owner's
  existing system → the validation instance (after the decision adoption, → the production instance for
  the kinds that system still owns). Nothing is imported into production from dev, staging or a drill;
  code arrives only as a signed image.

### 3.2 Instance identity

| Element | Created by | Stored in | Purpose |
|---|---|---|---|
| Instance id | `coflow init` | Config and database | Names the instance on the status page, in every MCP response and in logs |
| Role | `coflow init --role production\|staging\|validation\|dev\|drill`, `coflow promote` | Config and database | Decides what may run (table above); shown in every non-production answer |
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
  or `--previous-lost` with a typed confirmation phrase (the first promote has no predecessor), and a host
  that passed its gate (DEP-27, §4.4); a disaster-recovery promote may skip the gate after a typed
  confirmation, and the gate then runs on that host.
- **Promote increments the epoch and requires re-issuing runtime credentials:** revoke and re-create the
  bot token, revoke the Google refresh tokens and log in again, re-issue device and MCP tokens. Credential
  rotation is the fence: an old host that comes back (say, by auto power-on after it was declared lost)
  holds only revoked credentials and cannot act.
- **Fenced mode.** A 409 Conflict from Telegram `getUpdates` that arrives on the current long-poll request
  and repeats (default 3 within 2 minutes; another instance polls the same token), a heartbeat with an
  older epoch than the current one, or a revoked bot token puts the instance into fenced mode: the outbox,
  collectors and every writer stop, not only polling, and the owner is alerted. A network cut or a
  container restart does not fence; the client's request timeout exceeds the long-poll timeout. Leaving
  fenced mode takes an explicit owner command.

## 4. The production host (DEP-14, DEP-26, DEP-27)

### 4.1 Baseline

`coflow doctor --host` checks it against the live system state, not configuration files: a failed
required item fails `doctor`, a recommended one only warns. The **laptop profile** applies when the
firmware reports a portable chassis. A laptop is not disqualified: v1's home server failed because it was
run like a desktop application (start at logon, sleep on a closed lid, no remote administration), not
because it was a laptop. A laptop differs in four ways that matter — its firmware rarely powers on when
AC returns, its battery keeps the host running but not the network equipment, firmware and boot-chain
updates can stop an unattended disk unlock, and it is tempting to take on a trip — and the profile answers
each.

| Item | Level | Notes |
|---|---|---|
| A desktop, mini-PC or laptop dedicated to the instance | Required | The host runs the instance and nothing else: no other workloads, no second user, no processing agent of another app (D-051) |
| Key-only SSH over the private network | Required | Password login off; working before the machine leaves the desk (§8.2) |
| Time sync (NTP) | Required | `doctor` reports clock skew; storage is UTC, rituals use the profile's zone |
| No sleep, suspend or hibernate | Required | The sleep, suspend, hibernate and hybrid-sleep targets are masked |
| Power-on after power loss, or a tested equivalent (DEP-14) | Required | The firmware setting ("restore on AC power loss") on a desktop or mini-PC; on a laptop one of the substitutes below, recorded by the power-cut drill |
| Database on an internal local disk | Required | Never a network share, USB disk or VM-shared mount; `doctor` refuses nfs, cifs/smb, 9p, fuse and virtiofs |
| Off-host backup present | Required | §10; older than 48 h is a warning |
| **Laptop:** lid switch ignored | Required on a laptop | Ignored on battery, on external power and when docked; `doctor` reads the live login-manager state |
| **Laptop:** operating position | Required on a laptop | Lid open with the panel blanked: many laptops take air through the keyboard, and an unblanked panel burns in |
| **Laptop:** wired network | Required on a laptop | Wi-Fi only as a fallback; a static address outside the DHCP pool; two resolvers |
| **Laptop:** battery as the UPS | Required on a laptop | A clean shutdown at a configured reserve; a charge limit (for example 50–60 %) where the firmware or kernel supports one, checked by fact, not by setting |
| **Laptop:** hardware watchdog | Required on a laptop | On, and verified by a forced-panic drill (§10.3) |
| **Laptop:** the host does not travel | Required on a laptop | Trips need another machine; travel mode covers the time away (§4.3) |
| Full-disk encryption | Required on a laptop (PRV-11), recommended otherwise | The recipe below |
| Battery health | Warning | `doctor` warns below 70 % of design capacity and when the battery discharges while AC is present |
| Network equipment on a UPS | Recommended | Without it, a host that keeps running on its battery is still unreachable while the router restarts |
| UPS with clean shutdown | Recommended (desktop, mini-PC) | A USB UPS watched by NUT shuts the host down before the battery runs out |

**Full-disk encryption (PRV-11).** Encryption is chosen at install; the unlock mode can change later
without reinstalling. Before install the disk is secure-erased, and every credential that lived on a
previous operating system of that disk is rotated. Tested unlock modes:

- **Default:** LUKS2 with TPM2, bound to a signed policy over the unified kernel image (PCR 11) together
  with the Secure Boot state (PCR 7). Reboots stay unattended, and a modified initrd does not unlock. PCR 7
  alone with an unsigned initrd is not an accepted mode: it records only the Secure Boot state.
- TPM2 together with a network-bound key server on the home network, so the disk does not unlock elsewhere
  (needs another always-on device at home).
- A passphrase at boot: strongest against a stolen machine, but every power cut needs someone at it.

With every mode: a firmware password; USB and network boot off; IOMMU and DMA protection on; new USB
devices blocked by policy; a hardware TPM (not a firmware test key); the GPU kernel modules and the kernel
image signed and enrolled before the TPM binding; the recovery key kept off the machine (in the owner's
password manager and on paper). A powered-on stolen machine holds its key in memory — a residual risk
(SECURITY.md).

**Power-on substitutes on a laptop (DEP-14).** Laptop firmware rarely offers "restore on AC power loss".
From cheapest to most reliable, each tried on the gate:

1. A firmware option: AC power on, resume by RTC, or wake-on-LAN (which needs the firmware's
   low-power-standby mode off and another always-on device at home).
2. **An RTC wake loop with a charge reserve:** shut down at a reserve high enough to wake again (around
   30 % instead of 10–15 %) with an RTC alarm armed; on wake, continue only on AC, otherwise re-arm with a
   growing interval. It works only if the firmware wakes from soft-off, and with TPM unlock the loop needs
   no one.
3. **A remote button actuator** with its hub (without the hub it cannot be pressed remotely); its vendor's
   cloud sees only the presses, and it gets a `DATA_FLOWS.md` row.
4. A documented manual step that the off-host monitor announces: someone at home, and a label on the
   machine.

A switchable smart plug does not count: the battery keeps the laptop running, so cutting AC restarts
nothing. `doctor --host` records which method passed the power-cut drill.

### 4.2 Hardware

| | Minimum | Reference |
|---|---|---|
| CPU | 4 x86-64 cores | 8 cores |
| RAM | 16 GB | 32 GB; 64 GB only if a local model is wanted (`llm` profile) |
| Disk | SSD | 1–2 TB NVMe, with room for a year of active recordings below the 80 % warning |
| GPU | — (optional) | A GPU reserved only for `stt` and the optional `llm` profile, never for `core` (DEP-25) |

Transcription decides the hardware. Before buying, run `coflow bench stt` on the candidate machine or one
of the same class — `--device gpu` where there is a GPU (real-time factor, peak memory). Targets (NFR-11):
a 1-minute voice note in ≤ 20 s, a 1-hour recording in ≤ 30 min on the reference hardware. arm64 hosts
are R2 (DEP-20). The cold archive (terabytes of older recordings) may stay on another owner machine; the
host keeps the database and active recordings.

Running costs of the host (electricity, the relay, the separate domain, object storage for backups, the
dead-man service) are measured after stage 2 and published here together with the hardware choice (§14).

### 4.3 Operating system, reboots, platform updates and travel mode

Debian 13 is recommended, Ubuntu 24.04 LTS acceptable: a server install without a graphical session or
auto-login, Docker Engine and the Compose plugin from Docker's own repository (not Docker Desktop).
Unattended upgrades cover only the distribution's security channel; third-party repositories (Docker, the
GPU vendor, the VPN client, the folder-sync tool) update by hand in the window. Automatic reboots happen
only in a configured window outside the night archive window, never during a deploy: a pending reboot
waits for the updater's deploy lock, and no deploy starts that would run into the window. The previous
kernel stays in the boot menu.

**Platform updates (DEP-26).** The kernel, the GPU driver and its kernel modules, the bootloader, shim,
firmware and Secure Boot revocation updates are held from unattended upgrades and applied only by an
explicit owner command, at home. Before any reboot, `doctor` predicts the measurements of the disk-unlock
policy and refuses if they will not match: a changed Secure Boot measurement after a firmware update is a
known path to the recovery-key prompt, which only someone at the machine can answer. The container
toolkit's minimum version is data updated with each release and checked by `doctor`.

**Travel mode (DEP-26)**, `coflow travel on --until <date>`:

- no window reboots and no platform updates;
- archive transcription capped;
- after a GPU fault, `stt` keeps working on the CPU instead of rebooting the host;
- on activation, `doctor` checks that the recovery key, the backup password and the runbook are
  reachable from the owner's phone.

While the owner travels, up to 7 days of downtime is accepted (an operating tolerance, not a gate
allowance). The travel runbook is §11.

### 4.4 The host gate before real data (DEP-27)

The host decision changed several times before this design; a measured gate is meant to stop that
(accepted by the owner on 18 October 2026, D-050). A host receives the owner's real data — by promote at
the switch-over or by the decision adoption — only after **at least 30 days in the staging role**, with
every measurement recorded by `doctor --host`:

| Measurement or drill | Pass condition |
|---|---|
| Availability | ≥ 99 %, measured by the off-host monitor (OPS-6), with no failure that needed physical intervention while the owner was away |
| Short power cut (a 20-minute breaker drill) | The host **and** the network stay reachable from outside |
| Long power cut | A clean shutdown at the reserve, then an unattended power-on by a tested method (§4.1) |
| Network unplug | An alert on the owner's phone within 30 minutes; a router restart shorter than the grace period raises none |
| Watchdog | A forced kernel panic is recovered by the hardware watchdog |
| 48-hour outage | The DEP-15 drill: no duplicate import, no blind external write, the gap reported |
| Heat | A 4-hour sustained transcription run in the operating position: the real-time factor of the last hour within 20 % of the first 5 minutes; GPU, disk and battery temperatures under configured limits; no thermal shutdown; the battery does not discharge on AC |
| Battery | Health ≥ 70 % of design capacity on a portable host; the charge limit holds |
| Restore | Four consecutive green weekly off-host restore drills, and a rebuild of the first two restore tiers on another machine within 2 hours (OPS-5) |
| Platform update at home, once (proposed) | One platform update (kernel and driver) applied at home with the unlock-policy prediction; after the reboot the disk unlocked without the recovery key |
| Lid closed (proposed) | One hour of sustained load with the lid closed: no sleep, at most 20 % slowdown |
| Regional blocking window (proposed) | The bot, the VPN and the relay path checked from a mobile network during a regional blocking window; no false alarm from the off-host monitor |
| Disk room (proposed) | Free disk for a year of active recordings stays below the 80 % warning (DEP-13) |

The rows marked proposed are details beyond the owner's list of 18 October 2026; they are part of DEP-27,
which is the single list. `coflow promote` and the decision adoption onto a host without a recorded passed
gate are refused, naming every missing measurement. If the gate fails, another home machine with a GPU takes the same image and
runs its own gate. A rented server stays a disaster-recovery target only (DEP-19, §12).

## 5. The Compose stack (DEP-5, DEP-6)

### 5.1 Services

| Service | What it does | Network | Data access | Stop grace |
|---|---|---|---|---|
| `core` | The only database writer. A supervisor runs bot long polling, the scheduler, the outbox, MCP over HTTP and the status page; `/healthz` and `/readyz` answer on loopback and the container network | `core-net`; outbound only to declared destinations — the messenger API, the model provider, the calendar provider, declared pull sources (PRV-12); listener published on 127.0.0.1 only, never internet-facing | `data` (rw), `secrets` (rw), host id (ro) | 30 s |
| `stt` | Stateless faster-whisper worker; it may reserve the GPU and falls back to CPU with a warning (DEP-25) | None | Inbox (ro), work directory (rw), `models` (ro); no database | 120 s |
| `backup` (profile) | restic: snapshots and media to the off-host repository (§10) | Outbound to the backup target only | Snapshots and media (ro) | — |
| `llm` (profile) | Optional local model; it may reserve the GPU | `llm-internal` (`internal: true`) | Its own model volume | — |
| `edge` (profile, R2, stage-8 module 0) | The internet-facing listener for cloud AI clients: TLS, the OAuth and consent pages, MCP parsing, its own route table and worker pool (PRV-13) | Published only on the relay tunnel's address; no outbound requests (host firewall); reaches `core` only through the internal cloud-view API over `cloud-view` (`internal: true`) | None: no database, no secret except its TLS key | 10 s |

Rules, enforced by a Compose lint in CI:

- `core` is never scaled; no other service opens the database. `stt` shares no network with `core`'s API;
  `core` validates its transcript JSON against a schema with size limits, as untrusted data (P-10). An
  out-of-memory kill of `stt` is a transient error, and the bot keeps answering.
- A GPU is reserved only for `stt` and `llm`, never for `core`.
- No published ports, or 127.0.0.1 only (the `edge` profile: only the relay tunnel's address): Docker-
  published ports can bypass host firewall rules such as ufw
  ([Docker docs: packet filtering and firewalls](https://docs.docker.com/engine/network/packet-filtering-firewalls/))
  (PRV-5). Never a Docker socket mount.
- Every service has a health check, a restart policy, a stop grace period, CPU and memory limits and
  `local` log rotation. Restart policies act only when a process exits, so the supervisor exits non-zero
  on a fatal stall. Memory checks and thread counts read cgroup limits, not host totals. Core dumps are
  off for every service.
- **Logs carry ids only** (interaction, instance and record ids, error codes): never message, transcript
  or journal text, never secrets, and they are not shipped to a third-party service.

### 5.2 Volumes and secrets

| Volume | Contents | Backed up |
|---|---|---|
| `data` | `db/` (SQLite, WAL), `inbox/`, `media/`, `work/`, `snapshots/`, the deletion log (§10.2), the volume id | Yes: snapshots and media |
| `models` | STT (and optional local-model) weights, downloaded at init in formats that do not execute code, pinned to a revision and a sha256 that `doctor` verifies; a mismatch stops STT | No, re-downloadable |
| `secrets` | Runtime-written tokens (OAuth refresh tokens, sessions, device and MCP tokens), encrypted | No; after a restore they show as "needs login" |

Static secrets (bot token, model API key, OAuth client, backup key) are Compose file secrets read through
a `*_FILE` convention (mode 0600), never environment variables; on the host they are encrypted at rest,
bound to the host's TPM where one exists, and decrypted into memory at service start (PRV-4). Each
installation uses its own model API key with a provider-side spend limit. Swap lives only inside the
encrypted volume or in compressed memory. Directories are mounted, never a single database file, so
`-wal` and `-shm` stay with it; an override swaps named volumes for local bind mounts.

### 5.3 The image

- Stateless (no secrets, no models); a non-root fixed UID; a read-only root filesystem with `tmpfs` for
  `/tmp`; all capabilities dropped; `no-new-privileges`; an exec-form entrypoint under a minimal init.
- Base images pinned by digest; dependencies from the hashed lockfile; version, commit and digest stamped
  into a label and a file (OPS-10). A licence gate fails on AGPL or GPL components in the core image, and
  on LGPL components outside plugins unless listed under the D-001 audio-decoding exception (D-001).
- **GPU image variant (R1, stage 2, DEP-25):** the GPU runtime for `stt` and the optional `llm` profile.
  The image declares, in a signed label, the minimum host driver branch it needs, and the updater refuses
  an image whose requirement the host does not meet. The licence gate records how the GPU runtime is
  licensed before the variant ships.
- R2 (DEP-20): published SBOM and provenance attestations, an arm64 variant, repository-policy checks.

### 5.4 Compose excerpt

Illustrative only; all values are synthetic, and the shipped file is defined in stage 0B.

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
  ulimits: { core: 0 }                  # no core dumps
  logging: { driver: local, options: { max-size: "10m", max-file: "5" } }

services:
  core:
    <<: *common
    image: ghcr.io/<org>/coflow@sha256:<release-digest>   # always by digest, never by tag
    command: ["coflow", "run"]
    secrets: [telegram_bot_token, model_api_key]          # read via *_FILE, never env values
    volumes: ["data:/data", "secrets:/secrets", "/etc/coflow/host-id:/run/coflow/host-id:ro"]
    ports: ["127.0.0.1:8741:8741"]      # the default listener port; per-instance configuration (PRV-5); never on another address
    networks: [core-net, cloud-view]
    healthcheck: { test: ["CMD", "coflow", "probe", "readyz"], interval: 30s, start_period: 60s }
    stop_grace_period: 30s
    deploy: { resources: { limits: { cpus: "2", memory: 2g } } }   # never a GPU reservation

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
    deploy:
      resources:
        limits: { cpus: "4", memory: 4g }
        reservations: { devices: [{ capabilities: [gpu], count: 1 }] }   # GPU image variant only (DEP-25)

  edge:                                 # R2, stage-8 module 0 (PRV-13)
    <<: *common
    profiles: [edge]
    image: ghcr.io/<org>/coflow@sha256:<release-digest>
    command: ["coflow", "edge"]
    secrets: [edge_tls_key]             # its TLS key only: no database, no other secret
    ports: ["<relay-tunnel-address>:443:8443"]   # never 0.0.0.0; outbound blocked by the host firewall
    networks: [edge-in, cloud-view]     # cloud-view is internal: true and reaches only core's cloud-view API
  # profiles "backup" and "llm", and the top-level networks, volumes and secrets, are omitted
```

## 6. CI (DEP-7)

Public CI runs only on GitHub-hosted runners. A self-hosted runner is never attached to this repository:
GitHub's guidance is that self-hosted runners "should almost never be used for public repositories"
([secure use reference](https://docs.github.com/en/actions/reference/security/secure-use)), because code
from a fork's pull request could run on them — here, on the machine that holds the journal.

| Job | Runs on | What it proves |
|---|---|---|
| Native suite | Windows and Linux runners | The offline suite with fakes passes on both platforms (from stage 0A) |
| Toolchain | Windows and Linux runners | `uv sync --frozen` resolves the committed lock; ruff check and format; a lock that does not match `pyproject.toml` fails (DEP-22) |
| Image build | Linux | Digest-pinned base, hashed lockfile, image lint (non-root, read-only root, no secrets, no models), licence gate |
| Suite in the image | Linux | The same suite passes inside the image that production runs |
| Compose smoke | Linux | `docker compose up --wait` with fakes and egress blocked turns healthy; `doctor` passes; the Compose lint (no GPU for `core`, no socket mount, the `edge` route table equal to its allow-list) |
| Exposure test | Linux | Nothing answers on a non-loopback host address (PRV-5) |
| Egress test | Linux | With a fake resolver, an undeclared destination is refused and logged (PRV-12) |
| Upgrade test | Linux | The previous release on a synthetic database, upgraded by the new image, ends with the same schema as a clean install |
| Restore test | Linux | A backup restores into a fresh volume with equal counters; the deletion log is re-applied |
| Role refusals | Linux | A job pointed at a validation or production data root refuses; a dev instance refuses a snapshot not marked synthetic, and a validation instance one marked synthetic (DEP-23) |
| Literal gate | Linux | No owner or infrastructure literals: emails, phone numbers, non-example domains, IPs outside documentation ranges, host names, tunnel or VPN ids (P-12) |
| Secret scanning | Linux | No secret in the code, the image or the logs |
| DCO | — | Every commit carries a sign-off (D-015) |
| MCP catalogue | Linux | The generated tool catalogue matches the code (MCP-3); a linter flags tool descriptions that address the assistant with instructions |

Repository rules:

- Actions pinned by commit SHA, enforced by the allowed-actions policy. The default workflow token is
  read-only; `id-token: write` exists only in the release job, behind a protected `release` environment.
- Pull requests from forks hold no secret and never publish; outside contributors' workflows need approval.
- Dependency updates come from a bot with a cooldown and are merged by a human; auto-merge is off.
- **Security-sensitive paths** — edge and authorization, the MCP response layer, data-class policy,
  egress, the updater, secrets handling, Compose and CI workflows — need a review by a human code owner,
  and automatic merges never touch them (DEP-8). An agent that reads untrusted issue text holds no token
  with write access.
- Rulesets: `main` is protected and requires the checks above. `v*` tags can be created only by the
  release workflow, only on commits reachable from protected `main`, and are never moved or deleted.

## 7. Releases and the updater (DEP-8, DEP-9, DEP-10)

### 7.1 Releases

- Conventional Commits. A release pull request collects the changelog; merging it lets the release
  workflow create the `vX.Y.Z` tag (pre-releases `v2.0.0-alpha.N`). Stage 0B settles the exact mechanism,
  since tags pushed with the default workflow token trigger no other workflow.
- Each tag builds exactly one image, from a clean checkout and without a cache, pushed to GHCR by digest
  and signed keyless with cosign: the release job's OIDC token obtains a short-lived certificate and the
  signature goes into a public transparency log, so there is no long-lived signing key to steal
  ([Sigstore: signing overview](https://docs.sigstore.dev/cosign/signing/overview/)).
- Migration notes (ids, an irreversible flag, the target schema version) travel in the image labels,
  which the signed digest covers; the updater reads them from the registry without running the image, and
  only after the signature has verified.
- Builds of `main` are not published; the host runs only tagged releases. Public images need no pull
  credentials, so the host holds no registry secret. A release that changes a sensitive path without a
  code-owner review cannot be tagged.

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
  `coflow init --role production` (before the decision adoption or the switch-over, by the staging init
  on the same path) and run
  by a systemd timer, hourly by default. It is **the only thing allowed to call Docker**; the host-side
  `coflow` command is a thin wrapper around it.
- It is its own signed release asset, updated only by an explicit owner command after a separate
  approval, never from a pulled application image. Nothing from a new image runs before approval.
- It accepts only a higher version whose commit, taken from the signing certificate or the provenance,
  descends from the deployed one, so a correctly signed older release is refused. It never applies
  platform updates (§4.3).

### 7.3 Approvals

| Stages | Channel | How |
|---|---|---|
| 0B–4 | CLI over SSH (admin key) | `coflow-update approve <version>` shows the computed facts below and records the approval |
| From 5 | Approval card in the owner's bot (P-4) | `core` shows the card; on approval it writes the approved release to a file on a shared volume (`control/` on the data volume), which the updater reads |

The preview hash covers the image digest, the signer identity, the target instance id and role, the
migration ids with their irreversible flags, and an expiry. The card shows facts computed by CI: changed
security-sensitive paths, the MCP catalogue diff, the egress diff and new dependencies. A deploy with an
irreversible migration needs a second factor (BOT-11). The updater recomputes the hash and refuses an
approval that does not match, has expired, or comes from anywhere but the core of the instance it manages
(the production core; before the decision adoption, or before the switch-over if adoption has not
happened, the single staging instance), never from a drill. The
contributor-written changelog appears below the computed facts, marked as untrusted text.

### 7.4 Deploy sequence

1. **Detect** a new release tag; ignore tags already handled.
2. **Pull by digest; verify the signature** against the pinned identity before reading any label; check
   the version ascent; refuse and alert otherwise.
3. **Read the migration notes** from the signed labels, and the image's minimum driver branch (GPU
   variant); build the approval preview.
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

Access means three different things (D-052), and only the third needs a public entry:

| Who | Path | Public entry | From |
|---|---|---|---|
| The owner from the phone, anywhere | The bot: `core` long-polls the messenger, outbound | None | Stage 2 |
| The owner's devices: phone, a travelling laptop, desktop AI clients | The overlay VPN with SSH and the stdio bridge; a second path through the relay tunnel | None | Stage 2 |
| Cloud AI clients in the browser and on the phone, whose connections come from their operator's cloud | The owner relay → a WireGuard tunnel opened by the host → `edge` → the cloud view of `core` | Two neutral host names on a separate domain | Stage-8 module 0 |

### 8.1 Access recipes

| Recipe | Status | Who can see plaintext | Data classes (default policy) | Check |
|---|---|---|---|---|
| Overlay VPN (WireGuard-based, e.g. Tailscale) + SSH | R1 default for owner devices | The owner's devices and the host. The coordinator sees metadata (devices, addresses, connection times) and, without node-key signing, could add a device | Work and system data; the journal only over SSH: the journal-append key, or journal reads in the owner's own admin terminal (§8.2, §9.3); never through the MCP bridge or HTTP | `coflow doctor --access vpn` |
| LAN, SSH only | R1 | Nobody else | As above | `coflow doctor --access lan-ssh` |
| LAN, HTTPS terminated on the host | R1 alternative | Nobody else (private CA or pinned certificate) | As above | `coflow doctor --access lan-tls` |
| **Owner relay** with TLS passthrough and WireGuard to the host, on a separate domain | Default for MCP-5 (D-053); from stage 2 the tunnel alone is the second remote path, with no public name | Nobody but the host and the client. The relay sees client addresses, server names, timing and volumes | Only the `edge` listener (MCP and OAuth paths), through the cloud view; never the journal, `untrusted_external` text withheld by default, never the admin API, the ingestion API or the status page | `coflow doctor --access relay` |
| Mesh-VPN funnel that terminates TLS on the node | Accepted fallback if the relay fails | Nobody but the host; the funnel's vendor sees metadata | As the relay | `coflow doctor --access funnel` |
| Edge tunnel that terminates TLS (for example Cloudflare Tunnel with Cloudflare Access) | Opt-in only, R2 with MCP-5; never the default | The edge provider sees everything that passes: responses, tokens, identities | Only MCP and OAuth paths, routed only to the `edge` listener; never the journal; third-party content only if allowed in `DATA_FLOWS.md` | `coflow doctor --access edge` |

- **Never plaintext HTTP on a non-loopback address**, the VPN interface included. Owner devices reach MCP
  and the status page through the SSH bridge (§8.2), an SSH port forward, or HTTPS terminated on the host.
- **Overlay VPN:** turn on node-key signing (tailnet lock) with signing nodes other than the phone, and
  phishing-resistant two-factor login on the coordinator account; the ACL lets only the owner's devices
  reach the host's SSH, and the phone only its operations key (§8.2); `doctor` compares the ACL with the
  expected one, because node signing does not protect against an ACL edited in the console. The host is a
  tagged node whose key does not expire; the coordinator's own SSH feature stays off.
- Each recipe has a `DATA_FLOWS.md` row. `coflow doctor --access`, run from another device, reports which
  recipes actually work and which listener each one reaches: deployment state comes from health output,
  not from prose.
- **A second remote path** that does not depend on the VPN coordinator: WireGuard inside the relay tunnel
  (DEP-11, below); on a laptop, power-on after AC loss follows DEP-14 (§4.1).

**The owner relay recipe (DEP-12; accepted 18 October 2026, D-053; details proposed).**

```
 cloud AI client --TLS--> relay (rented VM, used for nothing else)       home: coflow-host
  a1.example.org          198.51.100.10                                   +--------------------+
  a2.example.org          +-----------------------------------+  wg-edge   | edge (TLS ends here)|
                          | TCP 443 forwarded by server name, |<---------->| core (cloud view)   |
                          | never decrypted; PROXY protocol   |  opened by +--------------------+
                          | WireGuard UDP port                |  the host  ^ wg-admin inside wg-edge:
                          | no port 80, no SSH from internet  |            | keys only on owner devices
                          +-----------------------------------+            | (the relay cannot reach SSH)
```

- **What the relay is:** a small rented virtual machine used for nothing else — not shared with any other
  service. It forwards TCP 443 by server name for two
  neutral host names (MCP and authorization) only, without decrypting, into a WireGuard tunnel that the
  host opens outbound (all paths are outbound, so CGNAT does not matter; keepalive keeps the tunnel up).
- **What it never holds:** data, TLS keys, application secrets or the keys of the admin tunnel. TLS, OAuth
  and every check terminate on the host, in the `edge` container (PRV-13).
- **Its own hardening:** a provider-level firewall that admits only TCP 443 and the WireGuard port; no
  TLS-terminating proxy, no port 80, no SSH from the internet (SSH only through WireGuard or the provider's
  console), a hardware-backed root key; its provider credential is never stored on a development machine
  and is entered only in a clean admin session, with a read-only token for checks. Its configuration has
  one source in this project's recipe, is changed only from this recipe, is provider-neutral, and has been
  applied once on a second provider. The host re-resolves the relay's
  endpoint name periodically.
- **The tunnel's rules:** the relay's peer reaches only the edge port. The client address arrives through
  the PROXY protocol, accepted only from the relay's tunnel address and used for logs and rate limits only,
  never for authorization. The AI provider's published egress ranges may filter noise, never
  authenticate.
- **The domain:** the host names live on a separate registrable domain, outside any zone shared with
  public apps, whose DNS provider is neither an edge platform that rewrites CAA records nor the relay's
  provider, with DNSSEC and a registrar lock. Until MCP-5 opens, CAA forbids all issuance; afterwards it
  allows one certificate authority, the host's ACME account (`accounturi`) and `tls-alpn-01`, with wildcard
  issuance forbidden and an `iodef` report address. The certificate is issued on the host through
  TLS-ALPN-01 across the relay, so the host holds no DNS token. Certificate-transparency monitoring of the
  whole domain alerts in both channels (OPS-17). On a zone served by an edge platform with universal
  certificates, CAA account binding may not be enforced (D-053), and cookies and the passkey relying party
  would share a site with public apps — hence the separate domain.
- **The relay is never an administration path of its own.** The public entry exposes no admin API, no
  status page, no ingestion API and no SSH. The only administration that crosses the relay is the owner's
  own WireGuard tunnel nested inside the relay tunnel (from stage 2, the second remote path): the relay
  forwards its encrypted packets and holds none of its keys. Check: from the relay as root, a connection
  to the host's SSH port inside the tunnel fails. No public name exists before stage 8.
- **Monitoring:** the off-host monitor checks the relay path end to end (a TLS handshake for the MCP name
  reaches the host) every 15 minutes, separately from the host heartbeat; once a day the relay's address
  is compared with public lists of regionally blocked addresses, and a match alerts (the address changes
  in minutes).

**The edge-tunnel recipe (opt-in).** Cloudflare Tunnel with Cloudflare Access, or a similar edge tunnel,
remains a documented recipe for owners who accept its trade-offs. Its one gain is a managed access and
OAuth layer in front of the host. Its costs: the edge provider terminates TLS and sees every response and
token and could act as the client; its account becomes a route to services on the host; request sizes are
capped; and shared edge address ranges are blocked by some regional internet providers during sports
broadcasts by court order, so the entry — and an owner's own login to it — can fail for hours. It routes
only to the `edge` listener, never to `core`, and `doctor --access edge` warns about each of these points.

MCP for the owner's devices (MCP-1): tokens carry a scope (`read` or `read-write`); tokens for
coding-capable clients, such as AI coding agents, are read-only on production by default; every MCP
response states the instance role and id, so a client cannot confuse dev, validation and production. On
the instance's own machine, local AI clients use the stdio shim `coflow mcp-stdio`, which never resolves
the database path.

### 8.2 Remote administration

Key-only SSH over the private network is a precondition for a production host and is tested before real
data arrives. sshd listens only on the VPN and admin-tunnel interfaces. Each purpose has its own key with a
forced command in `authorized_keys`, and every key to the host is hardware-backed and needs a touch (a
long-lived stdio bridge needs the touch only when it connects):

| Key | Account | Forced command | Restrictions |
|---|---|---|---|
| MCP bridge (one per client) | `coflow-mcp` | `coflow-bridge mcp --client=<id>` | No pty, no forwarding. Not in the `docker` group; the bridge connects to `core`'s HTTP MCP on 127.0.0.1 with that client's token, so scopes and logging apply |
| Journal append | `coflow-journal` | `coflow journal add` | Write-only, through a journal-write token that cannot read. Text comes from stdin or `$EDITOR`, never from arguments (shell history, process list) |
| Operations key (optional, the owner's phone) | `coflow-ops` | `coflow ops <command>` | Stored in the phone's hardware keystore; only `status`, `unfence` (refused if a conflict was seen in the last 10 minutes), `stt restart`, `archive pause\|resume` and `travel on\|off`; no shell, no data, no Docker |
| Admin | `coflow-admin` | None (shell) | Hardware-backed with a touch; never loaded into an ssh-agent that AI coding agents can use; never on the phone; Docker only through `sudo` |

```
# ~coflow-mcp/.ssh/authorized_keys (synthetic example; in practice security-key types that need a touch)
command="coflow-bridge mcp --client=desktop-ai",restrict ssh-ed25519 AAAAC3...EXAMPLE desktop-ai
# ~coflow-journal/.ssh/authorized_keys
command="coflow journal add",restrict,pty ssh-ed25519 AAAAC3...EXAMPLE journal
```

An AI client on the desktop runs `ssh -i <mcp-key> coflow-mcp@coflow-host` as its stdio command; the
journal is written with `ssh -t -i <journal-key> coflow-journal@coflow-host`, which opens an editor.
Every operation is a `coflow` command run by the admin over SSH: `status`, `logs` (ids only), `doctor`,
`backup`, `restore`, `drill`, `update`, `rollback`, `stop`, `promote`, `retire`, `travel`, `bench stt`.
Journal read commands run only in the owner's own terminal, never in a session an AI coding agent
controls. Fallbacks when the VPN is down: the relay tunnel (§8.1), LAN SSH, the physical runbook.

### 8.3 Security baseline before the first internet exposure

The first internet exposure is the first day the owner's real data is reachable from outside the home:
the bot and the VPN once the host holds real data (at the decision adoption gate or the switch-over,
whichever comes first). Public names for cloud AI clients open later, with stage-8 module 0. Every item is
checked by `doctor`, a CI test or a drill. The baseline is generic; the owner's own checklist with
providers and accounts lives outside this repository.

**Accounts and the domain (before any real data reaches the host):**

- Phishing-resistant two-factor login (a passkey or a hardware key; two keys, a primary and a spare) on
  every account that can reach the host, its releases or its data: the code host (the release identity),
  the overlay-VPN coordinator or its identity provider, the relay's provider, the registrar and DNS
  provider of the instance's domain, the backup storage, the model provider's console, the calendar
  account.
- The messenger: a cloud password and an app passcode on the phone; the desktop messenger with a local
  passcode and a current version, or logged out — a copy of a desktop session folder can be used without
  SMS or the cloud password; active sessions reviewed; a bot-token rotation from the phone in at most
  5 minutes, in the runbook (DEP-24).
- The overlay VPN as in §8.1.
- A separate model API key for the instance with a provider-side spend limit (PRV-4).
- Everything that lived on a previous operating system of the host's disk is treated as exposed: the disk
  is secure-erased and those credentials rotated (PRV-11). Any edge tunnel not used by this instance is
  removed with its DNS records and access applications, because the holder of its token could start
  another connector and receive traffic.
- Provider tokens and root keys out of plain files into a password manager; read-only tokens for checks.
- The separate domain is bought early and kept closed (CAA forbids all issuance) until the entry opens
  (D-053).

**The host (stage 2, before real data):**

- The baseline and the laptop profile of §4.1, full-disk encryption, the power-on method, the watchdog and
  platform updates by owner command (§4.3).
- A default-deny inbound firewall; container ports published only on 127.0.0.1 (Docker bypasses ufw); the
  relay's peer reaches only the admin tunnel's UDP port (and, from stage-8 module 0, TCP 443 of `edge`);
  sshd listens only on the admin tunnel and the VPN; `doctor --access` from an external machine finds, in
  stage 2, that nothing on the host answers from the internet, and from stage-8 module 0 that only the
  edge port answers, and only through the relay.
- Secrets in the inventory with their expiry (tokens, payment cards on file, the domain, VPN node keys,
  subscriptions), warned ≥ 14 days ahead; encrypted at rest and bound to the TPM; the bot token only on
  the production host; core dumps off; swap only encrypted or compressed in memory.
- The host is dedicated: no second user, no other apps. The folder-sync tool runs as its own user or
  container, with a receive-only folder that writes only to `inbox/`, its interface on loopback, its
  network only over the VPN, global discovery and relays off; received files are parsed only in `stt`,
  which has no network.
- Dependencies: images only from the release registry, never from a registry served from address ranges
  that regional providers block; model weights only in formats that do not execute code, with a sha256;
  `doctor --deps` lists every external dependency with its network (OPS-6).

**The relay (stage 2, as the second remote path):** as in §8.1 — a dedicated machine, its own project and
token at its provider, the provider-level firewall, no TLS proxy, no port 80, no SSH from the internet,
one configuration source, WireGuard inside WireGuard, and the check that the relay cannot reach the host's
SSH.

**Observation, recovery, bot and releases (stage 2; with real data, before it arrives):**

- The off-host dead-man switch, not on blocked address ranges, with a content-free status (`ok`,
  `degraded`, `fenced`) and a grace period of at least 15 minutes (OPS-6).
- Security alerts without content, always in two channels — the bot and a channel that does not depend
  on the messenger, because a hijacked messenger session also sees the bot (OPS-17).
- Backups every 4 hours, media on arrival, a weekly off-host restore drill, restore in tiers (OPS-5, §10).
- The lost-host and lost-device runbooks with the revocation list generated from the secrets inventory,
  dry-run once before the host holds real data (DEP-24).
- The bot: fencing only on a repeated conflict; a second factor for high-risk approvals (BOT-11);
  journal entries over SSH by default, and one sent through the bot deleted from the chat after ingestion
  with the bot's reply (BOT-12); a message stored before any model call.
- Releases (by stage 5, when the deploy card appears): §6 and §7 — code-owner review of sensitive paths,
  no automatic merges there, a clean release build, signature before labels, version ascent, CI facts on
  the card.

**Before the first public name (stage-8 module 0):**

- The relay forwards only the two neutral names; the PROXY address decides nothing; the end-to-end relay
  check and the blocked-address check run (§8.1).
- CAA switched from "forbidden to all" to the pinned authority, account and method; `dig +dnssec CAA`
  through three different public resolvers returns exactly the configured records; a test issuance from a
  foreign ACME account fails with a CAA error; certificate-transparency monitoring alerts in both
  channels; renewal starts 30 days before expiry and retries.
- `edge` as a separate container with its route table equal to the allow-list, the owner's login a passkey
  registered on two hardware authenticators (primary and spare) with offline recovery codes, pairing windows confirmed in the bot, an
  absolute grant lifetime, quotas and quiet-hour alerts, the cloud view without `untrusted_external` text
  by default (MCP-5, PRV-13, PRV-14).
- Interoperability and pairing — including an attempt from a foreign account at the AI provider — are
  first tested on a throwaway machine with synthetic data and a throwaway name, never on the production
  host or the production domain.

### 8.4 The owner's devices: the developer desktop and the phone (PRV-15)

The weakest place is usually not the host but the development machine and the desktop messenger: they
hold the keys, the messenger session that is the bot's owner channel, and AI agents with access to files
and the internet.

- Full-disk encryption on the development machine's system and data disks.
- Development and every AI agent or tool that reads public input (web pages, issues, dependency READMEs)
  run under a separate operating-system account that cannot read recordings, messenger profiles, SSH
  keys, secret stores or a validation data root. Operating-system credential stores are per account, so
  the separation is real; in the owner's own account the AI tools' permission rules close the same paths.
  Required before the first real snapshot enters the validation instance (stage 0A; proposed, PRV-15),
  together with the encrypted development disk; the other items of this list by stage 2.
- Every SSH key to the host — admin, the read-write MCP bridge, journal append — is hardware-backed and
  needs a touch (§8.2).
- No provider token as a plain file where the tool allows otherwise: a password manager or the operating
  system's credential store.
- The desktop messenger with a local passcode and a current version, or logged out.
- The validation data root lies outside any repository working tree and outside folders that agents read,
  sync or package (DEP-23).
- The phone: the messenger's passcode; the operations key in the hardware keystore; the recovery key, the
  backup password and the runbook reachable from it (travel mode checks this, §4.3).

## 9. Data on the move

### 9.1 Recordings and voice notes (R1)

- **Recordings** reach the inbox through an encrypted peer-to-peer folder sync (for example Syncthing)
  from the desktop (the recorder's export folder) and the phone; the sync tool runs on the host outside
  `core`. Its discovery and relay servers see device ids and addresses (relays carry only encrypted data);
  both are switched off on the host, so it syncs over the VPN only. Telegram Desktop exports travel the
  same way.
- A file is **registered only after complete arrival** (temporary name plus atomic rename, or a
  stable-size check), found by polling, within ≤ 2 min. In R1 nothing deletes the source on the device.
- **Short voice notes go through the bot.** Telegram bots can download files of up to 20 MB
  ([getFile](https://core.telegram.org/bots/api#getfile)), so long recordings never use this path.
- Audio is transcribed by `stt` on the host, never by a cloud service by default.

### 9.2 Device agents and hosted apps (R2, stage 6)

- **Ingestion API (DEP-16):** resumable chunked uploads on the `core` listener; per-device tokens (listed,
  revocable, ingest-only, scoped to the declared source type); idempotency keys; content-hash check; size
  and rate limits. **Windows desktop uploader (DEP-17)** and the activity agent (RHY-5) push through it
  and buffer while the host is unreachable.
- Device-pushed text is tagged with its device provenance and the `untrusted_external` sub-class; it is
  never treated as the owner's instruction and never becomes a source of rules or approvals (PRV-14).
- **Hosted apps** on a third-party platform never push into the home network and never hold a credential
  of the instance: `core` pulls from them outbound with a read-only export token for one workspace the
  owner owns, acknowledgement being a separate right with its own token, by cursor, with size limits and a
  schema check, never through a fallback host name whose TLS terminates on a third machine (D-051,
  EXT-4). Pulled items become proposals. Data the owner processes on behalf of an app's customers is not
  pulled unless the customer agreed to that purpose, and backups of hosted apps never restore onto the
  host.

### 9.3 The journal

The journal is a separate data class. Whether journal text may go to the model provider (for analysis
modules the owner enables) and over which access recipes is a **per-installation policy in
`DATA_FLOWS.md`**. `coflow init` asks for the journal switch per analysis module with no preselected
answer and records the choice (PRV-9, D-025); the project's advice for new installations is "off"
(proposed, D-025), and the owner can change it later.

- **Model provider:** as chosen at init. **Never, whatever the policy:** MCP, the status page, the `edge`
  listener and the cloud view, the validation snapshot.
- **Channels:** `coflow journal add` over the journal SSH key or on the host (end to end to the host), the
  default (BOT-12). Entries written through the bot pass Telegram's servers (bot chats are not end-to-end
  encrypted), which is listed in `DATA_FLOWS.md`; the bot deletes such an entry and its reply from the
  chat after ingestion.
- **Backups** are encrypted off-host. A rented server as the host puts the journal at rest with the
  provider and needs an explicit owner switch.
- Voice journal entries are transcribed on the host only. The dev machine never holds journal data.

### 9.4 Rows that deployment adds to `DATA_FLOWS.md`

| Destination | Data classes | Who sees plaintext | At rest | Switch |
|---|---|---|---|---|
| Overlay-VPN coordinator | System: devices, addresses, connection times | The coordinator, metadata only | Its logs | — |
| Folder-sync discovery and relays (off on the host) | System: device ids, addresses | Relays see ciphertext | — | Per device |
| Telegram | Every bot message, including journal entries written in the bot until they are deleted | Telegram | Chat history | BOT-12 |
| GHCR | System: the host's address and pull times | The registry | Its logs | — |
| Off-host backup storage | Ciphertext of everything backed up; sizes, times; EU jurisdiction | Nobody without the repository key | Encrypted snapshots, within the documented retention | OPS-5 |
| Dead-man switch | System: source address, ping times, a rotating check id, a content-free status | The monitor's operator | Its logs | OPS-6 |
| `edge` — owner relay | MCP and OAuth traffic as ciphertext | Nobody but the host; the relay's provider sees client addresses, server names, sizes and times | Connection metadata in rotated relay logs | MCP-5 |
| `edge` — edge tunnel (opt-in) | MCP and OAuth paths | The edge provider: content, tokens, identities | Provider logs | Opt-in |
| `mcp:<client>` (each cloud or desktop AI client) | As allowed per client; `untrusted_external` off by default for cloud clients | The client's operator receives every result and holds a refresh token until the absolute grant lifetime ends | Per that operator's policy | Per client |
| DNS provider of the instance's domain | System | Queried names | Zone records, including CAA | — |
| Remote power-button service (optional) | System: button presses | The device vendor's cloud | Press history | DEP-14 |
| `app:<client>` pull connector | As declared per connector, with the controller of every pulled data class | The hosted app's platform, as for any of its traffic | The connector's cursor in the instance | Per connector |
| Yearly rebuild drill on a rented machine (optional) | All, including the journal | The machine's provider, for the drill's duration | Encrypted disk, destroyed after the drill; a log entry per drill | DEP-19 |
| A rented server as the host or DR target (opt-in) | All data at rest | The provider, with physical access | The provider's disks | DEP-19 |
| Source system → `validation` instance | Work data of the snapshot, no journal | The owner's machine only | The validation data root | OPS-15 |

## 10. Backups, restore and drills (OPS-5)

### 10.1 Backups

- A daily consistent snapshot (`VACUUM INTO`) plus the pre-deploy snapshot (§7.4); the database is also
  copied to the off-host repository every few hours (default 4), and media on arrival — voice notes from
  the bot and recordings from the phone exist only on the host.
- **Default off-host copy:** an encrypted restic repository in EU object storage that supports object lock,
  is not served from address ranges that regional providers block on court order and is not run by the
  relay's provider, filled by the `backup` profile. The host's credential can write but not delete, or the
  bucket uses object lock (restic creates and removes lock files, so test backups with that credential).
- The repository key is kept in the owner's password manager, never only on the host. **Prune** runs
  monthly from another owner machine with a separate delete-capable credential, never stored on the host.
  Optionally, database snapshots are also encrypted to a public key whose private key is kept offline.
- **Maximum retention** is documented in `DATA_FLOWS.md` so that deleted data leaves the backups; proposed
  default 14 daily, 8 weekly, 6 monthly (about six months), with any object-lock period shorter. A weekly
  `restic check` reads a subset of the data.
- **Optional fast tier:** a second internal disk or a rotated USB disk; never the dev laptop (it sleeps,
  travels and runs AI coding agents). The `secrets` volume is never backed up. An off-host backup older
  than 48 h is a warning in health and in the morning plan.

### 10.2 Restore and deletions

`coflow restore` (Docker or native) stops all processes, restores the database (handling the WAL files)
and the media, re-applies the deletion log and starts as non-production; only `promote` makes it
production. It runs in **tiers**, each timed and published: the database and the secrets inventory first,
then the media of the last 30 days, then the rest in the background. The time targets of the rebuild and
of disaster recovery apply to the first two tiers.

**Deletions survive restores.** Deletions and blanking (PRV-7, BOT-3) go into an append-only log of ids
and hashes, no content, kept outside the SQLite snapshot (on the data volume and in the off-host copy). It
is re-applied before any restored instance serves (rollback, drill, rebuild, move).

### 10.3 Drills

The drills of the 30-day host gate are listed in §4.4 (DEP-27); this table is the standing schedule.

| Drill | Pass condition | When |
|---|---|---|
| Restore (`coflow drill`) | A snapshot restores into a throwaway project with equal counters; the project is destroyed | Monthly; in CI on every pull request |
| Weekly off-host restore (`coflow drill --from offsite`) | The latest **off-host** snapshot, not the local one, restores into a throwaway project with equal counters; the result is a line in the morning plan, a failure alerts | Weekly, automated, from stage 2 |
| Rollback | A deliberately broken release rolls back automatically with no lost bot message and no external write | Before R1 (stage 5); after every updater change |
| Failed rollback | Everything stays stopped and the off-host alert arrives | Before the switch-over |
| Network unplug | An alert reaches the phone within 30 min; also once during a regional blocking window, with no false alarm from the monitor | At host setup (stage 2 at the latest); twice a year |
| Short power cut (20-minute breaker drill) | The host and the network stay reachable from outside | On the gate; yearly |
| Power cut | After power returns, the instance is healthy without any action; on a laptop the drill records the battery runtime, the clean shutdown and the power-on method that worked | At host setup and after enabling encryption; yearly |
| Watchdog | A forced kernel panic is recovered by the hardware watchdog | On the gate; after a kernel or firmware change |
| 48 h outage + travel runbook | No duplicate import, no blind external write; the bot reports the possible gap | On the gate; before the switch-over; yearly |
| Lost host and lost device | The dry run lists every secret in the inventory; revoking the MCP grants makes every client fail its next call | Before the host holds real data; yearly (DEP-24) |
| Rebuild on another machine | §12; equal counters within the target time for the first two restore tiers | On the gate; stage-6 exit; after every major host change |

## 11. Monitoring, disk space and outages (OPS-6, DEP-13, DEP-15)

**Health** shows role, instance id and epoch, version and image digest, deploy history, queues, the STT
backlog, the device in use and the benchmark, source freshness, backup and off-host ages, disk space and
disk health (a critical warning, media errors, wear above a threshold), memory, clock skew, and the expiry
of tokens, payment cards on file, the domain, VPN node keys and subscriptions (reported ≥ 14 days ahead),
on the status page, in the bot's `/status` and in the morning plan.

**Off-host monitor.** Nothing inside the host can report that the host is down. The R1 default is an
external dead-man-switch service, pinged every 5 minutes with a content-free, rotating check id and a
status (`ok`, `degraded`, `fenced`), with a grace period of at least 15 minutes; missed pings (and a
failed-rollback signal from the updater) make it alert the owner by email or push through its own channel,
not the bot. It learns the source address and timing (a `DATA_FLOWS.md` row). Detecting a second
production instance is the job of the 409 detector and fencing (§3.3), not the monitor.

**Dependencies.** The off-host monitor, the backup target and the image registry must not depend on shared
edge address ranges that providers in the owner's region block on court order; if one does, it has a
documented retry or bypass. `coflow doctor --deps` lists every external dependency of the host with its
network and whether it is reachable during a blocking window.

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
  The bot answers queued messages with their original time, collapses missed briefs and reminders into one
  summary and names approval cards that expired. A message is stored before any model call, so the bot
  can confirm receipt while the model provider is down.
- Telegram keeps undelivered bot updates for about 24 hours
  ([Bot API: getting updates](https://core.telegram.org/bots/api#getting-updates)). After more than 20 h
  without polling, the bot warns on recovery that messages sent before `<time>` may be lost and should be
  resent. The outage alert and the runbook say so too, and suggest keeping new messages in the
  messenger's own saved messages and forwarding them after recovery.

**Travelling.** While the owner travels, up to 7 days of downtime is accepted, and travel mode is on
(§4.3). The runbook for "host unreachable while travelling": check the monitor and `doctor --deps`; try
the VPN, then the relay tunnel; use the operations key for `status`, `unfence`, `stt restart` or
`archive pause`; if the host is off, use the power-on method that passed the gate (RTC wake, the remote
button, someone at home); if the host is lost, rebuild per §12.

| Host state | Seen from outside | Fixable remotely? | How |
|---|---|---|---|
| `core` or `stt` crashed, the OS alive | Heartbeat `degraded`, the bot silent | Yes | Restart policies; SSH over the VPN or the relay tunnel |
| The GPU dropped off the bus | An alert "stt on CPU" | Partly | Work continues on the CPU; a reboot only by the owner's decision and not in travel mode |
| The OS hung | No heartbeat, no SSH | Yes, if the watchdog passed its drill | The hardware watchdog |
| A reboot stopped at the recovery-key prompt | No heartbeat | **No** | Only at home; hence platform updates only at home |
| Powered off (power cut, heat, someone closed it) | No heartbeat | Only through the tested power-on method or a person | §4.1 |
| The home internet is down | No heartbeat | No | Wait; a mobile-data backup only if the gate shows frequent outages |
| The VPN is down or a node key expired | Heartbeat present, no VPN | Yes | WireGuard through the relay tunnel; the host's node key does not expire |
| The relay is down | Heartbeat present, cloud clients fail | Yes | The VPN; re-create the relay from its recipe |
| Fenced mode | Heartbeat `fenced`, the bot silent | Yes | The phone's operations key (`unfence`) |
| The disk or the board died | Nothing | Only disaster recovery | A tiered restore onto another machine (§12) |

## 12. Moving to new hardware or a rented server (DEP-18, DEP-19)

1. `coflow retire` on the source, if reachable; verify through health output that it no longer writes.
2. A final backup to the off-host repository.
3. Prepare the target (§4), `coflow init`, restore from the off-host backup in tiers (starts as
   non-production).
4. Compare table counters and the last public ids with the source's final report.
5. `coflow promote` (`--previous-lost` if the source is gone): new epoch, rotated credentials (§3.3); the
   target must have passed its host gate (§4.4), except for a disaster-recovery promote after a typed
   confirmation.
6. Re-point devices: folder sync, VPN ACL, the relay tunnel, MCP clients.

| Secret | After a move or restore |
|---|---|
| OAuth client, model API key, backup repository key | Static: may be kept in the owner's password manager and re-entered |
| Bot token | Kept in the password manager, but promote revokes and re-creates it; store the new one |
| Google refresh tokens, user sessions, device tokens, MCP tokens and cloud grants | Runtime: always re-created |

After a restore, `doctor` lists every missing secret with the command that re-creates it.

**Stage-6 exit:** before the switch-over completes, the instance is rebuilt on a different machine from
the off-host backup only, following this document, within a measured time (target ≤ 2 h for the first two
restore tiers, excluding the OS install) and with equal counters. Repeat after every major host change.

**DR targets (R2, DEP-19):** RPO ≤ 24 h, RTO for the first two restore tiers ≤ 4 h, onto another Linux
machine or a rented server (which holds the journal at rest with a provider: an explicit owner switch in
`DATA_FLOWS.md`, decidable in advance; a recovery target only, never the planned host, D-050). The machine
for the yearly rebuild drill with real data is declared before the drill: a rented machine used only for
the drill (an encrypted disk, destroyed afterwards, a `DATA_FLOWS.md` row and a log entry per drill) or
another owner machine that is not the development machine. The dev machine is not a DR target.

## 13. R1, R2 and Later

| ID | Requirement | Pri | Section |
|---|---|---|---|
| DEP-1 | Two install paths: Docker Compose on Linux (reference production), native Python (dev, contributors, the validation instance, device agents) | R1 | §2 |
| DEP-2 | Instance identity and roles (production, staging, validation, dev, drill): instance id, role, volume id, host id | R1 | §3.2 |
| DEP-3 | One production writer: promote (only onto a gated host), retire, epoch, credential rotation, fenced mode on a repeated conflict | R1 | §3.3 |
| DEP-4 | Environments: real history only in the validation instance until the decision adoption, then in production; one staging instance until the adoption (or the switch-over), `coflow drill`, the shared test credentials | R1 | §3.1 |
| DEP-5 | Container image: stateless, hardened, pinned, licence gate | R1 | §5.3 |
| DEP-6 | Reference Compose stack: `core` + `stt` (GPU only for `stt` and `llm`), profiles including `edge`, volumes, limits, id-only logs | R1 | §5 |
| DEP-7 | Public CI on GitHub-hosted runners and repository rules | R1 | §6 |
| DEP-8 | Releases and keyless signatures with one pinned identity; code-owner review of security-sensitive paths | R1 | §6, §7.1 |
| DEP-9 | Host-side updater, approvals by stage with CI-computed facts, signature before labels, version ascent, write holds, deploy history | R1 | §7.2–7.4 |
| DEP-10 | Rollback: automatic only while the holds are on; limits stated | R1 | §7.5 |
| DEP-11 | Remote administration: per-purpose hardware-backed SSH keys, the phone's operations key, the `coflow` CLI, a second path inside the relay tunnel | R1 | §8.2 |
| DEP-12 | Access recipes with checks and `DATA_FLOWS.md` rows; the overlay VPN for owner devices; the owner relay is the public entry for MCP-5 (R2) on a separate domain; the edge tunnel is opt-in | R1 | §8.1 |
| DEP-13 | Disk space policy | R1 | §11 |
| DEP-14 | Production host baseline with the laptop profile, hardware guidance, reboot policy | R1 | §4.1–4.3 |
| DEP-15 | Outage behaviour, including one summary after recovery and the messenger's 24-hour limit | R1 | §11 |
| DEP-16 | Resumable ingestion API with per-device tokens | R2 | §9.2 |
| DEP-17 | Windows desktop uploader (device agent) | R2 | §9.2 |
| DEP-18 | Moving an instance; the rebuild drill as the stage-6 exit, timed for the first two restore tiers | R2 | §12 |
| DEP-19 | DR targets: RPO ≤ 24 h, RTO ≤ 4 h for the first two restore tiers; the drill machine declared in advance | R2 | §12 |
| DEP-20 | Supply-chain extras: published SBOM and provenance attestations, an arm64 variant, repository-policy checks | R2 | §5.3 |
| DEP-21 | Optional push deploy over the private network | Later | §7.6 |
| DEP-22 | Toolchain and reproducible installs: uv with a committed lock, ruff | R1 | §6 |
| DEP-23 | The validation role: the real snapshot on the owner's machine, never acting outward | R1 | §3.1 |
| DEP-24 | Lost-host and lost-device runbooks with a revocation list from the secrets inventory | R1 | §8.3, §10.3 |
| DEP-25 | GPU image variant: `stt` and `llm` only, CPU fallback with a warning, the driver-branch check | R1 | §5.3 |
| DEP-26 | Platform updates only by owner command, and travel mode | R1 | §4.3 |
| DEP-27 | The host gate: at least 30 measured days in the staging role before real data | R1 | §4.4 |

Related: NFR-11 (STT benchmark, §4.2), PRV-5 (no exposure, §5.1, §6), PRV-11 (full-disk encryption,
§4.1), PRV-12 (egress allow-list, §5.1, §6), PRV-13 (ingress isolation, R2, §5.1), PRV-15 (owner devices,
§8.4), MCP-1 (owner-device MCP, §8), MCP-5 (internet-facing MCP, R2, §8.1), OPS-5 (backups, §10), OPS-6
(health, off-host monitor, §11), OPS-17 (security alerts in two channels, §8.3).

## 14. Open questions for the owner

Resolved on 4 October 2026: the author's existing gaming desktop becomes the production host and moves
from Windows to Linux (D-020); its old v1 instance is retired in the process. Changed on 17–18 October
2026: the production host is a separate home laptop with a GPU dedicated to this work, holding real data
only after a 30-day gate (D-050, D-020); hosted apps stay where they run and are pulled read-only (D-051);
internet access comes in two steps, the bot and the VPN first (D-052); the public entry is the owner's
relay on a separate domain (D-053).

1. **Operating system.** Debian 13 or Ubuntu 24.04 LTS? The docs test one recipe (encryption, baseline,
   reboots) end to end. Recommendation: Debian 13, unless Ubuntu is more familiar.
2. **Hardware — closed:** the GPU laptop, with the GPU used for transcription. `coflow bench stt --device
   gpu` still decides the reference class, the int8 or fp16 choice and whether the `llm` profile is
   realistic.
3. **Overlay VPN provider and tailnet lock.** A hosted coordinator (e.g. Tailscale), a self-hosted one, or
   plain WireGuard? Recommendation: hosted, with tailnet lock and phishing-resistant two-factor login; the
   second remote path is the relay tunnel (§8.1), not a port forward on the home router.
4. **Backup object-storage provider.** Which EU provider? It must offer a write-without-delete credential
   or object lock, work with restic, not be served from regionally blocked address ranges, not be the
   relay's provider, and get its `DATA_FLOWS.md` row (jurisdiction, key holder, retention).
5. **Full-disk encryption** — required on a laptop host (PRV-11). Proposed default unlock: TPM2 with a
   signed PCR 11 policy over the unified kernel image together with PCR 7, without a passphrase at boot;
   a network-bound key server if a small always-on device appears at home. Decide before real data
   arrives; adding encryption later usually means reinstalling.
6. **The relay and the domain providers.** Which provider for the relay machine (not the backup's
   provider), and which DNS provider for the separate domain (not an edge platform that rewrites CAA, not
   the relay's provider)? The provider-neutral recipe keeps this reversible.
7. **A second laptop for travel** (proposed): the host does not travel, so trips need another machine; if
   there is none, the rule will not hold, and either such a machine or another host is needed.
8. **The yearly rebuild drill machine** (DEP-19): a rented machine used only for the drill, or another
   owner machine that is not the development machine.
