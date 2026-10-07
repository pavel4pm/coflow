# CLAUDE.md

Guidance for coding agents (Claude Code and others) working in this repository.

## What this is

CoFlow 2.0 — an open-source (Apache-2.0) personal decision system:
`Signal → Decision → Commitment → Action → Outcome → Learning`. One owner per installation, self-hosted.
**Status: requirements stage — there is no code yet.** Development follows [docs/ROADMAP.md](docs/ROADMAP.md)
and starts with stage 0.

## Read first

| Document | Use it for |
|---|---|
| [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) | What to build: principles P-1…P-14 and requirement IDs with priorities (R1 = stages 0–5) |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Which stage builds what, exit criteria, estimates, how a stage runs |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | The modular monolith: one writing process, module boundaries, contracts, process view |
| [docs/MODULES.md](docs/MODULES.md) | One card per module: owned tables, contracts, quality parameters and acceptance thresholds |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Install paths, CI/CD, the production host, access, backups, drills |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Why things are the way they are; "accepted" = decided by the owner, "proposed" = waiting |
| [docs/BUILD_IN_PUBLIC.md](docs/BUILD_IN_PUBLIC.md) | The weekly cycle, the episode calendar, publication rules |

## Rules

- **English** for code, docs, issues and commit messages. Refer to the owner or author as "the owner" /
  "the author" with they/them.
- **No personal or third-party data, no infrastructure identifiers** (host names, addresses, domains, VPN or
  tunnel ids, SSH users) anywhere in the repository. Fixtures are synthetic. The only name allowed is the
  copyright line in NOTICE.
- **Never record a proposal as the owner's decision.** New decisions go into DECISIONS.md as "proposed"
  until the owner confirms them; requirements that implement a proposed decision stay proposals.
- **IDs are permanent.** Add new requirement IDs at the end of their table; never reuse a retired ID
  (OPS-9, ALN-1, WRK-7). Every ID you reference must exist; place every non-"Later" requirement in a
  roadmap stage.
- **Real cases gate a stage.** Before a stage starts, the owner names 3-5 cases from their own last 30
  days; they become part of that stage's exit criteria and run against the snapshot of real history
  (OPS-15), not only against synthetic fixtures.
- **Review rhythm:** one independent review round per stage; two when the stage writes to the outside world
  or builds a money module. Leftovers become issues, not more polishing rounds.
- **Outward actions need the owner's explicit yes:** pushing, publishing posts, changing repository or
  account settings, deploying to a host that holds real data.
- Before committing documentation changes, run `python tools/check_docs.py` (exits non-zero on problems).
- When code starts (stage 0), the stage-0 requirements in REQUIREMENTS.md and the module cards define the
  quality gates; CI must stay green on Windows and Linux.
