# CoFlow 2.0 — Roadmap

Version 0.5 · 5 October 2026 · **status: draft for owner review** (stage 0, 2, 4 and 5 scopes extended
by the 5 October requirements, [REQUIREMENTS.md](REQUIREMENTS.md) 0.5)

The roadmap turns [REQUIREMENTS.md](REQUIREMENTS.md) into stages. Each stage ends with something that works
end to end, a tagged pre-release deployed through CI/CD and per-module acceptance results
([MODULES.md](MODULES.md)), published in the weekly episode of the week it closes
([BUILD_IN_PUBLIC.md](BUILD_IN_PUBLIC.md)). Deployment
details are in [DEPLOYMENT.md](DEPLOYMENT.md), the module structure in [ARCHITECTURE.md](ARCHITECTURE.md).

## Timeline at a glance

| When | What |
|---|---|
| October 2026 | Requirements (this package). The private v1 runs under acceptance testing; its features are frozen |
| From mid-October 2026 | Stage 0 starts after the v1 acceptance period ends |
| One stage per week where possible | A sustainable pace that matches the weekly episode |
| Stage 2 | The separate home production machine is set up and runs CoFlow in the staging role |
| Target: end of December 2026 | **R1** — stages 0–5, tag `v2.0.0` (re-planned after stage 0 with measured speed) |
| January 2027 | Stages 6–7: the author's data moves to the home production machine; learning loop |
| 2027 | Stage 8 modules one by one, in the confirmed order: money, centre and goals, inconsistency findings, send material, negotiation, the whole archive, remote MCP, statement import, week plan and the rest; research after that |

## Stages

The non-functional requirements (NFR-1…11) apply to every stage from stage 0: both platforms in CI,
container jobs, offline tests, privacy canaries under both journal-switch settings, crash-safe steps,
English code and localized texts, a module card with an acceptance suite, a user doc and a usage signal
per feature. Install time (NFR-2), running cost (NFR-3), responsiveness (NFR-4) and transcription speed
(NFR-11) are measured for the R1 release.

**Real cases gate a stage.** Before a stage starts, the author names 3-5 cases from their own last 30
days that the stage must carry end to end. The cases go into that stage's exit criteria and run against
the snapshot of the author's real history (OPS-15), not only against synthetic fixtures. A stage closes
when its cases pass; a case that cannot pass becomes either a named gap in that week's episode or the
next stage's scope. This is how a staged build stays joined to real use while the author keeps living
in the system they have until the switch-over at stage 6.

### Stage 0 — Foundations

Scope:

- Repository layout, Python package, uv for dependencies and environments with a committed `uv.lock`,
  ruff as linter and formatter, standard test runner, CI on Windows and Linux (DEP-7, DEP-22: GitHub-
  hosted runners only, pinned actions, read-only default token, DCO, secret scanning, tag rules).
- The minimal kernel: storage with the SQLite write discipline (OPS-3) and numbered migrations (OPS-4);
  one numbering tap and the prefix registry (IDN-1, IDN-2); a minimal event and outbox layer; data
  classes and the canary framework (PRV-1, NFR-6); the journal switch (PRV-9); `DATA_FLOWS.md` generated
  from code declarations (PRV-2); the model gateway with a fake provider, the cost ledger and the
  no-silent-truncation rule (EXT-2, OPS-7, OPS-12); the interaction trace skeleton (OPS-10); the offline evaluation harness that refuses production
  data (OPS-8).
- Instance and data root (CFG-4), owner profile and locale skeleton (CFG-1…5), `coflow init` with roles
  and `coflow doctor` (OPS-1, DEP-2), one supervisor (OPS-2).
- Backups with a restore test and the deletion log outside snapshots (OPS-5, PRV-7).
- Privacy scaffolding: retention (PRV-3), secrets store and `secrets.example` (PRV-4), network defaults and
  the exposure test (PRV-5), the owner-literal gate (P-12).
- The module map, the module-card template, import-linter contracts and the table-ownership check (P-14,
  NFR-10).
- Delivery skeleton: Dockerfile, reference Compose file, image lint, the suite inside the image, a Compose
  smoke test with fakes and blocked egress (DEP-1, DEP-5, DEP-6); a tag builds one image pushed by digest
  (DEP-8); a minimal `coflow update <digest>` run by hand over SSH against any Linux Docker host — a
  virtual machine is enough, so the stage does not wait for hardware (DEP-9).

Exit criteria:

- `coflow init` creates a working native dev instance on a clean Windows machine and a working container
  instance on a clean Linux host; `doctor` is green.
- CI is green on both platforms, including the container jobs; the full suite runs offline.
- A backup restores into a fresh volume; a deletion survives the restore.
- A tagged pre-release reaches a Linux test host by digest through the manual updater.
- The literal gate, the canaries (both journal settings) and the ownership check run in CI.
- Estimates for stages 1–5 are recalculated with the measured speed.

### Stage 1 — Memory core, timeline and MCP

Scope:

- People and companies: `resolve_or_create_person`, temporal facts with source and quote, deterministic
  dossier (IDN-3, IDN-4, IDN-6, IDN-7, IDN-8, PPL-1, PPL-2, PPL-4).
- Conversations as sessions and messages; transcript segments in the schema from the start (SIG-1,
  SIG-14); quick log and notes (SIG-15); research-ready signals (REL-6).
- Work registry: directions with ranks and envelopes, goals with their R1 fields, tasks, status log, ball
  holder, goals resolved through `goal_ref`, the goal link at entry (WRK-1…3, WRK-8).
- Journal storage with the local command (PRV-1).
- Search: full text with deterministic row ids, rule-based entities, script variants for Latin and
  Cyrillic, honest coverage (SRC-1…4, P-9).
- Deleting a source with everything derived from it; the derivation graph and per-module erasers (PRV-7).
- Timeline: "what happened on this day / around this event" over every stored layer, with coverage per
  layer; it grows as later stages add layers (TML-1).
- Connector contract and the first adapter, Telegram Desktop export (SIG-5, SIG-6).
- A one-way snapshot of the system the author runs today, imported into a dev instance and never
  written back, so every later stage is tried on real history and not only on fixtures (OPS-15).
- MCP: context-oriented tools, explicit read-only list, Streamable HTTP plus the SSH bridge, scoped
  per-client tokens, Host and Origin checks, generated catalogue, approval model and undo handlers
  (MCP-1…4).

Exit criteria:

- A synthetic Telegram export imports into sessions with resolved participants and no silent duplicates.
- An AI client on the owner's desktop reaches the instance on another host through the SSH bridge and
  answers "what did I agree with this person last month" with sources; a request without a token, or
  with a foreign Host header, is refused; a read-only token cannot write.
- A name typed in Latin finds a person written in Cyrillic, and back.
- The journal canary passes through MCP, search and the timeline; a deleted source leaves no trace.

### Stage 2 — Telegram bot, daily rhythm, control view and the home host

Scope:

- Private bot that talks only to the owner; one token per instance; fenced mode on a 409 (BOT-1).
- Routing: work by default, journal by explicit marker, buttons when in doubt, replies keep their route;
  "this was journal" blanks derived records (BOT-2, BOT-3, P-5).
- Answers through read tools in compact mode; approval cards executed once by the owner only, showing the
  effective value of every option they apply; cost under each answer (BOT-4, BOT-8, P-3, P-4).
- Behaviour written down as owner-readable scenario files with their own tests, prompts and tool
  descriptions checked against them (BOT-9); one question per turn and only about what is missing
  (BOT-10); provider errors, including an exhausted balance, explained to the owner once a day instead of
  raw payloads (OPS-14).
- The owner picks the model tier per function group and sees the monthly cost forecast of each tier next to
  its measured quality (OPS-11).
- Speech-to-text as a stateless worker with job leases; voice messages transcribed on the host before
  routing (BOT-7); `coflow bench stt` (NFR-11).
- Morning plan with a deterministic ranking, evening plan vs. fact, close the day (RHY-1…3); the control
  view (WRK-6); notifications with caps and quiet hours (BOT-5).
- The home production machine: Linux and Docker Engine, the required baseline (DEP-14), per-purpose SSH
  keys (DEP-11), the overlay-VPN recipe (DEP-12), one instance in the staging role deployed through the
  pipeline (DEP-4), promote, retire and fenced mode (DEP-3), signature verification on the host (DEP-8),
  the off-host heartbeat (OPS-6).

The morning plan and the notifications start with tasks and goals; later stages add commitments and
decisions (stage 3), recordings and calendar (stage 4), meetings and briefs (stage 5), the weekly review
(stage 7) and goal control (stage-8 module 2).

Exit criteria:

- Canary tests pass over text, voice, captions, replies, commands and forwards, under both journal-switch
  settings; after "this was journal" the canary appears nowhere outside the journal.
- An approval card executes exactly once under double taps and restarts; the same data produces the same
  morning plan; a second poller on the bot token fences the instance.
- Unplugging the home host's network raises an alert on the phone within 30 minutes; status, logs and a
  restore run from the dev machine with no physical access to the host.

### Stage 3 — Decisions and commitments

Scope:

- Decision records with grounds, alternatives, assumptions to monitor, computed health, explicit closing
  (DEC-1…4).
- Commitments with quotes and history (CMT-1).
- Inline, capped commitment proposals from conversations, with the decision rate measured per proposal
  type; a type below its threshold switches itself off (CMT-2, P-13).
- Morning surfacing of the decisions that need the author today, with the reason (DEC-5).
- The centre kept and versioned: the author's existing documents imported unchanged, with decisions and
  directions able to cite them (GOL-13).
- One computed check: what carries no link to a goal or a direction, with the items behind the number
  (GOL-14). The formation protocols and the goal cards stay at stage 8.

Exit criteria:

- A decision goes from creation through monitored assumptions to closing with an outcome.
- A proposal that is not decided does not pile up in a queue; the decision rate per proposal type is
  available through an MCP read tool.
- The author's own centre documents are in the instance byte-identical to their files, and a decision
  cites one of them.
- The link check names what carries no link to a goal or a direction, computed on the snapshot of real
  history, and the author recognises the list.

### Stage 4 — Sources

Scope:

- Recorder pipeline: a watched inbox fed by an encrypted folder sync and by bot voice notes, registration
  after complete arrival, transcription into segments in the worker with its own limits, summaries,
  resilience, recorder profile, archive budget (SIG-2…4, SIG-11, SIG-14); import of an external transcript, preferred
  for attribution when it carries speaker labels (SIG-16).
- Calendar copy, read-only, with freshness flags, per-purpose tokens and a headless login (SIG-9, EXT-3).
- Host plugins, off by default: Telegram user-session collector with voice notes (SIG-7, SIG-8), Gmail
  read (SIG-10) (EXT-1).
- Contact proposals from conversations (PPL-3); recording consent (PRV-6).
- Health and the status page — the only web screen in R1 (OPS-6, UI-1); disk-space policy (DEP-13);
  outage behaviour (DEP-15).

Exit criteria:

- A synthetic audio file synced from the desktop goes from the inbox to search exactly once, also after
  an interrupted sync; a killed transcription worker recovers while the bot keeps answering.
- The calendar copy reports `stale` when it is old; a mass disappearance of events is refused.
- Plugins cannot be enabled without the warning; the collector cannot send (test); each disk threshold
  triggers once on a fake filesystem.

### Stage 5 — Meetings and reliable execution

Scope:

- Meeting intent with participants and a required link to work (MTG-1); a meeting creates the people it
  needs on one approval card instead of sending the owner to another interface (MTG-17); brief before the meeting with
  sources and named gaps (MTG-2); recording to meeting by time overlap or label (MTG-3); outcome to
  commitment and task proposals (MTG-4), with quotes extracted per chunk from segments (MTG-12), honest
  outcome messages (MTG-13), context assembled by rules (MTG-14), the record and analysis modes (MTG-15)
  and the conference link on online meetings (MTG-16); outcome recall measured against the owner's private
  evaluation set before a change ships (OPS-13); time to outcome measured and reported (NFR-12).
- One outbox for external writes, executed only by the production role: states, deterministic external
  ids, read-back before retry, read-back verification (MTG-5, P-8); calendar write safety (MTG-11).
- Fresh preflight: calendar freshness, busy time, booking hours, buffers between meetings with people
  (MTG-6); time model with DST handling and no host time zone (MTG-7).
- The full deploy path: write holds during a deploy, the bot approval card bound to the image digest
  (DEP-9), automatic rollback while the holds are on (DEP-10).

Exit criteria (two review rounds — this stage writes to the outside world):

- A lost response, a double approval and a crash between steps each leave exactly one meeting and one
  calendar event (fake calendar that records every call); a foreign or recurring event is never changed.
- DST gaps and overlaps are refused or asked; every quote in an outcome is an exact substring of a
  transcript segment.
- A deliberately broken release rolls back automatically with no lost bot message and no external write.

**R1 release:** tag `v2.0.0`. The Docker production install is verified on a clean Linux host by someone
other than the author within the NFR-2 budget; the native dev install on Windows by the author. The
author's home machine has run CD-delivered pre-releases in the staging role for at least two weeks, with
at least one automatic-rollback drill and one restore drill. The demo is a Compose profile with synthetic
data that users run themselves. Release episode.

### Stage 6 — Import and the author's switch-over to the home host

Scope:

- A documented import format, the same as the full export (PRV-8); `coflow import`.
- Merge and undo of people (IDN-5); export and "forget" for a person (PPL-6).
- Functions the author uses in v1 today that R1 does not cover: the integration contract for external
  apps (EXT-4), the ingestion API (DEP-16), the Windows desktop uploader
  (DEP-17) and the activity-tracking device agent (RHY-5).
- The author's exporter from the private v1 lives in the private repository, not here. Other people can
  write exporters from their own tools the same way.
- Moving and rebuilding an instance (DEP-18): media moves with a hash manifest; bot, calendar and session
  credentials are created again on the host; recorder, uploader and agents are re-pointed. Disaster
  recovery targets are documented and drilled yearly from here on (DEP-19).

Exit criteria:

- A dry run of the author's data in a throwaway drill instance on the host: counts match, the canaries
  pass, no data is lost.
- The instance is rebuilt on a different machine from the off-host backup alone, following
  DEPLOYMENT.md, within the measured time (target ≤ 2 h excluding the OS install); a 48-hour outage drill
  passes (DEP-15).
- A switch-over checklist: every v1 function used in the last 30 days is either available in v2 or
  explicitly paused by the author (for example the unused week plan, MTG-10); the author's centre
  documents stay in files until stage-8 module 2 imports them (GOL-2).
- Promote on the home host; v1 is retired and the retirement is verified through health output, not by
  assumption.

### Stage 7 — Learning loop

Scope:

- Weekly review as a structured debrief (RHY-4).
- Owner corrections become typed, versioned rules through approval cards; explicit `/remember` and
  `/problem`; one-off exceptions with expiry; `/rules` (LRN-1…4).
- Incidents packaged with a synthetic fixture and redacted infrastructure identifiers, ready to become a
  public issue (LRN-5).
- A capability gap becomes a proposed scenario change the owner approves in the chat, never a bare "I
  can't" (LRN-7).
- Sources under answers and a "wrong" button (BOT-6).
- Supply-chain extras: published SBOM and provenance attestations, arm64 image, repository-policy checks
  (DEP-20).

Exit criteria:

- A rule explained once works in a new conversation and after a restart; forwarded text creates no rule.
- An incident package contains no journal text, no real third-party data and no infrastructure
  identifier (test).

### Stage 8 — Modules after the switch-over

Each module is a separate mini-stage with its own module cards, review, deploy and episode. The order of
the modules, including the centre and goals module at position 2, is confirmed by the author (D-031);
the split of money into two parts is a proposal.

| # | Module | Requirements | Size | Agent tokens | Workflow hours | Note |
|---|---|---|---|---|---|---|
| 1a | Money core: books and taxpayers, money between books, ledger, invoice register, document archive, financial goals, reports | FIN-1, FIN-2, FIN-4…9, FIN-14, FIN-16 (file adapter) | L, 2 rounds | 7–10M | 13–19 | Planning and evidence; invoices registered from a certified invoicing program, never issued (D-026). Proposed: Norma 43 and one CSV profile pulled in here (+1–2M, +2–4 h) so the ledger reconciles from day one. Without that pull-in, balances are entry-based and are not reconciled with the bank until module 7 — owner to decide (REQUIREMENTS §8 q.9); a short legal opinion before publishing (covers 1a and 1b) |
| 1b | Country pack: the interface and the Spain reference pack — calendar, reserves, advisor export, thresholds, rules-watch | FIN-10…13, FIN-15, FIN-17, FIN-18 | L, 2 rounds | 5–8M | 12–17 | Golden tests per tax year; a short legal opinion before publishing |
| 2 | Centre and goals: import, formation sessions, versions, rule objects, control, reviews, weekly reflection | GOL-1…12, LRN-6, RHY-4 link | L | 6–8M | 12–16 | Position confirmed (D-031); provenance test; planted-problem evaluation year |
| 2b | Inconsistency findings: what the owner thinks, says and does against the centre | ALN-2…5 | L | 4–6M | 8–12 | By the owner's decision, right after goals; evidence on both sides, "can't judge", a planted evaluation set before any finding is shown; the journal under PRV-9 |
| 3 | "Send material" commitment | CMT-3 | M | 2–3M | 4–6 | — |
| 4 | Negotiation through the owner's messenger account | MTG-8 | L, 2 rounds | 6–9M | 14–19 | Starts with a spike: account requirements, 24-hour window, how messages look to the counterpart |
| 5 | The whole personal archive in the timeline | TML-2 | L | 4–6M | 8–12 | Plus a one-off model cost, estimated on a sample first |
| 6 | Internet-facing MCP for cloud clients | MCP-5 | M, 2 rounds | 3–4M | 6–8 | Separate listener, OAuth, TLS on the owner's host |
| 7 | Statement import, other formats | FIN-3 | M | 2–3M | 4–6 | camt.053, OFX, more CSV profiles |
| 8 | Week plan; birthdays, client view, hypotheses | MTG-10, PPL-5, PPL-7, WRK-4 | M | 2–4M | 4–8 | The week plan exists in v1 but is unused so far |

### Research (after stage 8; indicative, not planned)

Each research module starts only on core data (REL-6), with a pre-registered protocol and its own
evaluation set.

| # | Research | Requirements | Size | Agent tokens | Workflow hours |
|---|---|---|---|---|---|
| R-a | Relationship balance | REL-1…3 | M | 2–4M | 4–8 |
| R-c | Conductivity protocol and predicting G(t+1) — after a planned experiment gate (November 2026) | REL-4, REL-5 | L | 4–6M | 8–12 |
| R-d | Change over time | TML-3 | M | 2–4M | 4–8 |

## Estimates

Units:

- **Agent tokens** — the sum of tokens of the coding agents in the stage's workflows.
- **Workflow hours** — wall-clock time while the stage's workflows and CI run, sequentially.
- **Owner hours** — reviews, decisions, acceptance, host setup and drills; not included in workflow hours.

The basis is measured work on the private v1 in September–October 2026: a large stage with external
writes and two review rounds took ≈ 7.4M tokens and 13.6 hours; a medium stage with one round took
≈ 1.5–2.5M tokens and 3–5 hours. Porting proven code is cheaper than inventing it, but the rewrite is
broader and now includes the delivery pipeline. These are forecasts, not commitments; they are
recalculated after stage 0.

| Stage | Size | Agent tokens | Workflow hours | Owner hours |
|---|---|---|---|---|
| 0 Foundations and delivery skeleton | L | 7–10M | 13–20 | 2–3 |
| 1 Memory core, timeline and MCP | L | 9–14M | 18–27 | 1–2 |
| 2 Bot, rhythm, control view and the home host | L | 7–10M | 13–20 | 11–17 (incl. moving the existing desktop to Linux and setting it up as the host) |
| 3 Decisions and commitments | M | 3–5M | 6–10 | 1 |
| 4 Sources | L | 6–9M | 12–18 | 2–3 |
| 5 Meetings, reliable execution, rollback | L, 2 rounds | 7–11M | 14–22 | 2–4 |
| **R1 (stages 0–5)** | | **39–59M** | **76–117** | **19–30** |
| 6 Import, switch-over, device agents, rebuild drill | L | 8–12M | 15–23 | 4–6 |
| 7 Learning loop | L | 5–7M | 10–14 | 1–2 |
| **Stages 6–7** | | **13–19M** | **25–37** | **5–8** |
| 8 Modules 1a–8 (incl. 2b) | per module | 41–61M | 85–123 | 1–3 per module |
| Research R-a, R-c, R-d | indicative | 8–14M | 16–28 | per protocol |

Model API cost while developing (evaluation runs with a live model, behind an explicit flag): on the order
of $30–60 for R1. Running costs of the home host (electricity, object storage for backups, the dead-man
service) are measured after stage 2 and published in [DEPLOYMENT.md](DEPLOYMENT.md) §4 together with the
hardware choice (§14).

## How a stage runs

1. **Slice.** The requirement IDs of the stage become a short stage spec with acceptance cases and the
   module cards it touches.
2. **Build.** Coding agents implement it; tests use temp data, fake providers and no network.
3. **Review.** One independent review round; two when the stage writes to the outside world or builds a
   money module. No further polishing rounds: leftovers become issues.
4. **Release.** A tagged pre-release `v2.0.0-alpha.N`, one signed image, changelog, updated docs.
5. **Deploy.** Through the CD path: the staging role on the home host before the switch-over, production
   after it.
6. **Accept.** On the deployed instance, against the module cards: CI scorecards for every module; the
   owner personally accepts the modules that hold money, the journal or external writes, and the goals
   module. Stages 0–5 are accepted on synthetic data. A failed acceptance is answered with a rollback or a
   new release, never a fix on the host.
7. **Episode.** Episodes are weekly, whatever the stage boundaries: what was done, what was tested, what
   was worked through, the numbers, what was learned. The stage's acceptance results go into the episode of
   the week it closes.

## Rules while v2 is built

- **The private v1 is frozen** since 4 October 2026: acceptance fixes and dangerous bugs only. Everything
  else becomes a v2 issue.
- **Nothing for growth.** A requirement without a usage signal or an explicit decision of the author waits.
- **Synthetic data only** in the repository, issues, screenshots and episodes; no identifiers of the
  author's infrastructure (host names, addresses, domains, VPN or tunnel ids, SSH users).

## Risks

| Risk | Mitigation |
|---|---|
| The second-system trap: the rewrite grows beyond R1 | R1 scope is fixed by requirement IDs; additions need a usage signal and an owner decision; deployment extras are R2 or Later |
| Delivery work swallows stage 0 | Stage 0 builds only a skeleton against any Linux host; the physical host comes in stage 2, rollback in stage 5 |
| v1 needs change during the rewrite | Feature freeze; acceptance fixes only; v2 issues instead |
| Development competes with paid work | One stage per week at most; a stage can slip, the scope cannot grow |
| The production host is unreachable while the owner is away | Remote administration is a precondition; an off-host heartbeat; power-on after power loss; a second remote path; a travel runbook |
| A second writer appears across dev, drills and production (the v1 collision) | Instance roles, promote/retire with credential rotation, fenced mode, one-way data flow, no sync |
| The CI/CD supply chain delivers malicious code to the host that holds private data | GitHub-hosted runners only; pinned actions and base images; tag rules; keyless signatures verified on the host; pull-based deploy with owner approval; no CI credential into the home network |
| Personal or third-party data, or infrastructure identifiers, leak into the public repository or episodes | Synthetic fixtures, the literal gate, secret scanning, installation config kept off the repository, review of every episode |
| Tax rules change and a stale pack gives wrong dates or figures | Rules as data with official sources and dates, a quarterly rules-watch, "unverified" marking, tests pinned to a tax year |
| Legal exposure of the money features | No invoicing or filing (D-026), read-only invoice adapters, labelled estimates; a short legal opinion before publishing module 1 that also tests whether LGT art. 29.2.j and 201 bis (accounting and management software) apply to the ledger (REQUIREMENTS §8 question 10) |
| The goals module drifts into model-written content | Approval only in owner-typed channels, the provenance test, rule objects as typed fields and exact quotes |
| Platform terms (Telegram user sessions, Google OAuth for personal accounts) | The collector is an off-by-default plugin with a warning; the OAuth path is verified in stage 0 and documented |
| A single maintainer | Decisions, lessons, module cards and stage specs are public |
