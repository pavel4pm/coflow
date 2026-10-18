# CLAUDE.md

Guidance for coding agents (Claude Code and others) working in this repository.

## What this is

CoFlow 2.0 — an open-source (Apache-2.0) personal decision system:
`Signal → Decision → Commitment → Action → Outcome → Learning`. One owner per installation, self-hosted.
**Status: stage 0A in progress since 17 October 2026: the decision core** (D-038, D-040). Development has
started and the first code is in progress — the kernel and the decision core, in three gated increments;
there is no release yet. Development follows [docs/ROADMAP.md](docs/ROADMAP.md).

## Read first

| Document | Use it for |
|---|---|
| [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) | What to build: principles P-1…P-16 and requirement IDs with priorities (R1 = stages 0A–5) |
| [docs/SPEC_DECISION_CORE.md](docs/SPEC_DECISION_CORE.md) | The decision core in detail: data model, states and computed values, API, import and shadow, acceptance tests — read before touching DEC or CMT |
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
  days; they become part of that stage's exit criteria and run in the validation instance against the
  snapshot of real history (OPS-15, DEP-23), on throw-away copies through the case runner (OPS-16), not
  only against synthetic fixtures. The case scripts, the snapshot and the case reports live only in the
  validation data root and never enter any repository, public or private.
- **Review rhythm:** one independent review round per stage; two when the stage writes to the outside world
  or builds a money module. Leftovers become issues, not more polishing rounds.
- **Outward actions need the owner's explicit yes:** pushing, publishing posts, changing repository or
  account settings, deploying to a host that holds real data.
- **Two kinds of D numbers.** The project's decision log uses `D-NNN` (DECISIONS.md). Product ids use
  fixed widths: decisions `D-NNNN` (v1 numbers kept, natives from `D-1001`), forks `Q-NNNN`, commitments
  `F-NNNNN` (natives from `F-10001`). Examples in the repository are synthetic (`D-0042`, `D-0907`);
  never a real v1 number.
- **Ranges for the checker.** Write requirement ranges as `DEC-11…20`; write decision ranges as
  `D-038 to D-049`; R2 and Later IDs never appear in ROADMAP before `### Stage 6`.
- Before committing documentation changes, run `python tools/check_docs.py` (exits non-zero on problems).
- Code started at stage 0A: the stage-0A requirements and the STO, IDS, DEC and CMT module cards define the
  quality gates; CI must stay green on Windows and Linux.
