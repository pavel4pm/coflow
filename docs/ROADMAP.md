# CoFlow 2.0 — Roadmap

Version 0.8 · 18 October 2026 · **status: draft for owner review** (the decision core moves to stage 0A,
D-038 to D-049; the home laptop, its gate and the internet entry, D-050 to D-053; capture moves into
increment I2 and the owner's own use gates its start, D-055; [REQUIREMENTS.md](REQUIREMENTS.md) 0.8)

The roadmap turns [REQUIREMENTS.md](REQUIREMENTS.md) into stages. Each stage ends with something that works
end to end, a tagged pre-release deployed through CI/CD (from stage 0B, when the delivery pipeline exists)
and per-module acceptance results ([MODULES.md](MODULES.md)), published in the weekly episode of the week
it closes ([BUILD_IN_PUBLIC.md](BUILD_IN_PUBLIC.md)). Deployment details are in
[DEPLOYMENT.md](DEPLOYMENT.md), the module structure in [ARCHITECTURE.md](ARCHITECTURE.md), the decision
core in [SPEC_DECISION_CORE.md](SPEC_DECISION_CORE.md).

## Timeline at a glance

| When | What |
|---|---|
| October 2026 | Requirements and the decision-core design (this package). The private v1 runs under acceptance testing; its features are frozen, except the decision loop (D-037) and, from 1 November 2026, less notification noise outside the decision module (D-055) |
| 17 October 2026 | Stage 0A starts: the kernel and the decision core, in three increments (D-038, D-040); v1 acceptance continues in parallel and no longer gates code |
| The week of 19 October 2026 | A one-off offline capture experiment on the owner's own AI working sessions of 1–18 October 2026: read-only, thresholds written before the run, results outside the repository (D-055) |
| 1 November 2026 | The start of increment I2 is decided from two weekly readings of the owner's own answer-on-the-due-day rate (D-055) |
| Not before 2 November 2026 | Nothing from the capture experiment is shown in the daily flow before a separate decision (D-055) |
| From the first increment of 0A until 1 December 2026 | v2 runs in shadow on daily one-way snapshots of v1's decisions; v1 stays the decision system of record, and the forecast pilot's change journal records that the owner reads the shadow daily (D-039) |
| Not before 1 December 2026 | Decisions move to v2 for good at the adoption gate, onto a host that passed its gate, where the restored instance becomes production (D-039, OPS-16, DEP-27) |
| One stage per week where possible | A sustainable pace that matches the weekly episode |
| Stage 2 | The home production laptop is set up, runs CoFlow in the staging role, and its 30-day gate starts (D-050); the owner's relay comes up as a second remote administration path, with no public name yet (D-053) |
| Target: end of December 2026 | **R1** — stages 0A–5, tag `v2.0.0` (re-planned after the first increment of stage 0A with measured speed; proposed, D-055: the re-scoped I2 makes the path to 1 December 2026 about a week longer at one stage a week) |
| January 2027 | Stages 6–7: the rest of the author's data moves into the production instance on the home laptop (whose gate has passed); learning loop |
| 2027 | Stage 8 modules one by one: first internet-facing MCP for cloud clients, read-only first (D-052); then, in the confirmed order, money, centre and goals, inconsistency findings, send material, negotiation, the whole archive, statement import, week plan and the rest; research after that |

## Stages

The non-functional requirements (NFR-1…13) apply to every stage from stage 0A: both platforms in CI,
container jobs (from stage 0B), offline tests, privacy canaries under both journal-switch settings,
crash-safe steps, English code and localized texts, a module card with an acceptance suite, a user doc
and a usage signal per feature, provenance and event times on every record. Install time (NFR-2), running
cost (NFR-3), responsiveness (NFR-4) and transcription speed (NFR-11) are measured for the R1 release.

**Proof levels (proposed).** Stages 0A–2 serve observation and the execution loop: decisions are recorded,
checked, reviewed and closed with a learning. Stages 3–6 serve outcome. Calibration (research R-e) is
not promised before the forecast pilot's report.

**Real cases gate a stage.** Before a stage starts, the author names 3-5 cases from their own last 30
days that the stage must carry end to end. The cases go into that stage's exit criteria and run in the
validation instance against the snapshot of the author's real history (OPS-15, DEP-23), and from stage 0A
on throw-away copies through the case runner (OPS-16), not only against synthetic fixtures; after the
decision adoption they run on throw-away drill copies of the production database (proposed, D-046). The
case scripts, their results and the snapshot live only in the validation data root (after the adoption,
the production data root), never in any repository, public or private. A stage closes when its cases
pass; a case that cannot pass becomes either a named gap in that week's episode or the next stage's scope. This is how a staged
build stays joined to real use while the author keeps living in the system they have: v1 until the
adoption gate for decisions, and until the switch-over at stage 6 for everything else.

### Stage 0A — Kernel and decision core

Scope:

- **Toolchain and CI:** uv and ruff with a committed `uv.lock`, CI on Windows and Linux on GitHub-hosted
  runners with DCO, pinned actions, a read-only default token and a secret scan, and the minimal literal
  gate (DEP-7, DEP-22, P-12).
- **The minimal kernel:** storage with the SQLite write discipline, the transaction log, numbered
  migrations and the table registry with append-only, set-once and erasable columns enforced by generated
  triggers (OPS-3, OPS-4, NFR-13); one numbering tap, the prefix registry fixed before the first number is
  issued, foreign and burned numbers and aliases (IDN-1, IDN-2, IDN-9, IDN-10); events written in the same
  unit of work (P-14); data classes and the canary fixture (PRV-1, NFR-6); the owner profile minimum and the
  instance data root (CFG-1, CFG-3, CFG-4); `coflow init` with the `dev` and `validation` roles and a basic
  `doctor` that refuses a data root inside a repository (OPS-1, DEP-2, DEP-23).
- **The decision core:** decisions with kinds, deciders and depth, forks and options recorded before the
  choice, assumptions with check dates, an append-only check log, readings that only propose, facts with
  evidence, reviews that keep the number and seal a new edition, outcomes with a basis, learnings at
  closing, computed health on two axes with the unverifiable share first, one waiting list with the
  context needed to answer it, goal changes as one question, typed decision links with an owner per kind,
  the entry-time link and the unlinked report, decision history and as-of, loop metrics, and proposals
  from AI clients approved only in an owner channel (DEC-1…4, DEC-6, DEC-11…20); minimal commitments that
  name the decision they execute or say "none" with a reason (CMT-1); publishability per decision
  (PRV-10); independence from every external app (EXT-6).
- **Capture where decisions are born, and the fields that are costly to add later** (moved into increment
  I2, accepted, D-055; what they contain is proposed): a capture scope that lets a coding client draft the
  owner's decisions with the owner's quoted words and propose more (MCP-6); AI working sessions as a source
  that passes on only the owner's typed text, through an adapter outside the core (SIG-19); proposals with
  deterministic matches, one budget, expiry and the decided time taken from the quote (DEC-17); exit rules
  written at decision time, outside the seal (DEC-26); the kind of closing and checks recorded at closing
  (DEC-15); the return date named when a record is made (DEC-4, CMT-1); a compact "why we decided" card and
  decisions as context for the AI client's work (DEC-20, MCP-3); commitments by decision, in I3 (CMT-6).
- **Shadow, cases and adoption:** the daily one-way snapshot of v1's decisions imported into the validation
  instance as read-only mirrors that keep their numbers; the shadow report that classifies every
  difference; the case runner on throw-away copies; the selected entries of the project's own decision log
  imported as native drafts; the adoption gate, refusing until its conditions hold (OPS-15, OPS-16). The
  exporter on the v1 side lives in the owner's private repository.
- **The owner-device baseline for the validation data root** (PRV-15; proposed): before the first real
  snapshot enters the validation instance, AI coding agents and tools that read public input run under an
  operating-system account that cannot read the validation data root, and the development machine's disk
  is encrypted. The hardware-backed keys and the messenger items of PRV-15 stay at stage 2.
- **Interfaces:** MCP on loopback with a local stdio shim, the tools in their own `dec_` and `cmt_`
  namespaces, an explicit read-only list, per-client tokens, the generated catalogue, the approval model
  and undo handlers (MCP-1, MCP-2, MCP-3, MCP-4); the CLI through the loopback admin API, with a documented
  morning pull of the waiting list before the bot exists.
- The DEC and CMT module cards and their acceptance suites (NFR-10).

Built in three gated increments, each usable on its own and each closed with its tests green on Windows
and Linux before the next starts:

| Increment | What the owner can do when it closes | Agent tokens | Workflow hours | Owner hours |
|---|---|---|---|---|
| Skeleton | Nothing yet: shared contracts, ports with fakes, CI; the owner also labels the candidates of the capture experiment (about 45 minutes) | 0.5–1M | 1–2 | 1–1.5 |
| I1 · read-only shadow | Ask v2 "what is waiting and why" about the real v1 decisions, through MCP or the CLI, with the shadow report beside it | 4–6M | 8–12 | 1 |
| I2 · native loop and capture | Record, activate, check, review, close and learn on the selected project-log decisions and on synthetic decisions; capture drafts and proposals from AI working sessions and approve them in an owner channel; exit rules, the kind of closing and the return date from the first native record; the owner's own new decisions are recorded in v1 until the adoption gate (D-039) | 5.5–9M | 11–18 | 1 |
| I3 · execution and evidence | Attach commitments to decisions, ask what was promised per decision, see execution in reviews, ask "what changed and why" over a period, run the real cases | 3.5–4.5M | 7–10 | 1–2 |

**The I2 gate (accepted, D-055).** The start of I2 is decided on 1 November 2026 from two weekly readings
of the owner's own answer-on-the-due-day rate:

- both readings ≥ 50 % → I2 as re-scoped above;
- both below → capture and the attention budget first, and the native loop waits;
- mixed → the capture tracks first.

**The experiment (accepted, D-055).** A one-off offline capture experiment on the owner's own AI working
sessions of 1–18 October 2026 runs this week, read-only, with thresholds written before the run; its
results stay outside the repository; nothing is shown in the daily flow before a separate decision, not
before 2 November 2026. The owner's usage signal counts a decision as one that arrived as a proposal when
anyone but the owner proposed it first (the AI client in a session, a review card, a
meeting-without-decision question); retro records from the experiment do not count (accepted, D-055).

Proposed with them (D-055): the experiment is the precondition of the extraction track - the adapter of
SIG-19 shows nothing until the offline non-decision rule of OPS-13 holds on the owner's own sessions -
while the capture scope (MCP-6) is built either way, since it does not depend on extraction; in the "both
below" branch, the attention budget is the specification of the stage-2 gate, built with that stage; the
re-scoped I2 adds about 1.5–3M agent tokens, part of them moved from I3.

The slice is model-free and offline; the AI-session adapter lives outside it, calls no model itself (the
owner's coding client finds the candidates) and reaches it only as proposals. Stage 0A is accepted natively and in the validation instance; the
first image and the CD path arrive with stage 0B.

Exit criteria:

- The slice's acceptance tests are green in CI on Windows and Linux.
- The first real snapshot is imported into a validation instance with equal counts; the shadow report has
  run on at least 7 daily snapshots, and every unexpected difference is fixed or turned into a numbered
  rule with a test.
- At least three decisions of the project's own decision log are monitored natively, with assumptions and
  review dates added by the owner.
- The four real cases named by the owner on 17 October 2026 run with the case runner on throw-away copies
  of the validation database and pass, in their scripted form (proposed); a further case named the same
  day waits for stage 5.
- Proposed (D-055): a draft captured from a synthetic AI session reaches an owner-channel approval with its
  two quotes and none typed by anyone else; a violated assumption with an exit rule shows the rule's words
  and date; every return date an answer promised appears on its day.

### Stage 0B — Delivery and operations

Scope (the rest of the former stage 0):

- The event outbox and the scheduler for kernel jobs; the journal switch (PRV-9); `DATA_FLOWS.md` generated
  from code declarations (PRV-2); the model gateway with a fake provider, the cost ledger and the
  no-silent-truncation rule (EXT-2, OPS-7, OPS-12); the interaction trace skeleton (OPS-10); the offline
  evaluation harness that refuses production and validation data roots (OPS-8).
- Owner profile and locale skeleton in full (CFG-1…5), `coflow init` with every role and the full `doctor`
  (OPS-1), one supervisor that also imports the daily snapshot and runs the daily usage-signal job (OPS-2).
- Backups with a restore test, restore tiers, and the deletion log outside snapshots (OPS-5, PRV-7).
- Privacy scaffolding: retention (PRV-3), the secrets store and `secrets.example`, a per-installation model
  key with a provider-side spend limit, core dumps off (PRV-4), network defaults and the exposure test
  (PRV-5), the full owner-literal gate (P-12).
- The module map, the module-card template, import-linter contracts and the table-ownership check (P-14,
  NFR-10).
- Delivery skeleton: Dockerfile, reference Compose file with an optional GPU reservation only for `stt`,
  image lint, the suite inside the image, a Compose smoke test with fakes and blocked egress (DEP-1, DEP-5,
  DEP-6); a tag builds one image pushed by digest, and security-sensitive paths need a human code owner's
  review (DEP-8); a minimal `coflow update <digest>` run by hand over SSH against any Linux Docker host — a
  virtual machine is enough, so the stage does not wait for hardware (DEP-9).
- **The trust minimum** (proposed, D-055), cheaper than screens the owner would not open: every privacy
  promise names its test (P-17); a content tripwire for the journal and sealed decisions in the model
  gateway's outgoing text (PRV-17); a "what went where" view over the model-call log, with a card only on
  a deviation (PRV-18); a model function nobody uses pauses (OPS-7); no telemetry, checked in the lock and
  by an idle test (PRV-12); the canaries also run after a change of a switch or a grant (NFR-6).

Exit criteria:

- `coflow init` creates a working native dev instance on a clean Windows machine and a working container
  instance on a clean Linux host; `doctor` is green.
- CI is green on both platforms, including the container jobs; the full suite runs offline.
- A backup restores into a fresh volume; a deletion survives the restore.
- A tagged pre-release reaches a Linux test host by digest through the manual updater.
- The literal gate, the canaries (both journal settings) and the ownership check run in CI.
- The supervisor imports the daily snapshot and records the daily usage signals.
- Proposed (D-055): a planted wrong route of journal text is caught by the tripwire; the documentation
  check finds no privacy statement without a test; a telemetry package in the lock fails CI.
- Estimates for stages 1–5 are recalculated with the measured speed.

### Stage 1 — Memory core with decision anchors

Scope:

- People and companies: `resolve_or_create_person`, temporal facts with source and quote, deterministic
  dossier (IDN-3, IDN-4, IDN-6, IDN-7, IDN-8, PPL-1, PPL-2, PPL-4).
- Conversations as sessions and messages; transcript segments in the schema from the start (SIG-1,
  SIG-14); quick log and notes (SIG-15); research-ready signals (REL-6).
- Work registry: directions with ranks and envelopes, goals with their R1 fields, tasks, status log, ball
  holder, goals resolved through `goal_ref`, tasks that store the decision they execute, the decision or
  goal link at entry, which offers "or is it a fork?" when the text has an explicit fork form (WRK-1…3,
  WRK-8; the fork option proposed, D-055).
- Decision anchors, the spoke side of the ports built in stage 0A (DEC-11, DEC-19): SIG uses
  `DecisionDirectory` for quick logs naming a decision and implements `EvidenceResolver`; WRK implements
  `GoalDirectory` and the attachment probe.
- What was promised, by whom and to whom, asked per person: the stage-1 half of the commitment query built
  in I3 (proposed, D-055).
- Text not written by the owner carries the `untrusted_external` sub-class, and items from satellites wait
  in a quarantine as proposals (PRV-14); connecting an AI client shows one card on where its model runs,
  its terms and its outside tools, with no preselected answer about that text (proposed, D-055).
- Journal storage with the local command (PRV-1).
- Search: full text with deterministic row ids, rule-based entities, script variants for Latin and
  Cyrillic, honest coverage (SRC-1…4, P-9).
- Deleting a source with everything derived from it; the derivation graph and per-module erasers (PRV-7).
- Timeline: "what happened on this day / around this event" over every stored layer, with coverage per
  layer; it grows as later stages add layers (TML-1).
- Connector contract and the first adapter, Telegram Desktop export (SIG-5, SIG-6).
- The one-way snapshot extended from decisions (stage 0A) to people, sessions, commitments and tasks,
  imported into the validation instance as mirrors and never written back (OPS-15); a person deleted in
  v1 arrives as a tombstone that also blanks the records derived from them (proposed, D-055).
- MCP across machines: the SSH bridge and the network listener for the owner's devices, with the tools
  growing to people, sessions, tasks and search (MCP-1).

Exit criteria:

- A synthetic Telegram export imports into sessions with resolved participants and no silent duplicates.
- An AI client on the owner's desktop reaches the instance on another host through the SSH bridge and
  answers "what did I agree with this person last month" with sources; a request without a token, or
  with a foreign Host header, is refused; a read-only token cannot write.
- A task created through MCP is offered its likely decision; a quick log "D-0042: …" becomes a fact
  proposal on that decision; the unlinked report shows tasks and commitments.
- A name typed in Latin finds a person written in Cyrillic, and back.
- The journal canary passes through MCP, search and the timeline; a deleted source leaves no trace; the
  planted-instruction corpus triggers no tool, rule or approval.

### Stage 2 — Telegram bot, daily rhythm, the decision loop in chat and the home laptop

Scope:

- Private bot that talks only to the owner; one token per instance; fenced mode only on a 409 that repeats
  on the current long-poll request (BOT-1).
- Routing: work by default, journal by explicit marker, buttons when in doubt, replies keep their route;
  "this was journal" blanks derived records (BOT-2, BOT-3, P-5). Journal entries are written over SSH by
  default, and one received through the bot is deleted from the chat after ingestion (BOT-12).
- Answers through read tools in compact mode; approval cards executed once by the owner only, showing the
  effective value of every option they apply; cost under each answer (BOT-4, BOT-8, P-3, P-4). High-risk
  approvals need a second factor, so a hijacked messenger session alone cannot approve (BOT-11).
- **The decision loop in the chat:** morning surfacing, the review asked one question at a time with every
  write behind one approval card, and a context change recorded on one card (DEC-5, DEC-7, DEC-9),
  measured against the owner's private evaluation set (OPS-13); every list of decisions filtered and grouped
  by direction (DEC-24, D-054; placement proposed).
- Behaviour written down as owner-readable scenario files with their own tests, prompts and tool
  descriptions checked against them (BOT-9); one question per turn and only about what is missing
  (BOT-10); provider errors, including an exhausted balance, explained to the owner once a day instead of
  raw payloads (OPS-14).
- The owner picks the model tier per function group and sees the monthly cost forecast of each tier next to
  its measured quality (OPS-11).
- Speech-to-text as a stateless worker with job leases; voice messages transcribed on the host before
  routing (BOT-7); `coflow bench stt`, on the GPU where there is one (NFR-11).
- Morning plan with a deterministic ranking, headed by the decision waiting list, evening plan vs. fact,
  close the day (RHY-1…3); the control view (WRK-6); notifications with caps and quiet hours (BOT-5).
- **The attention gate, shipped with the first proactive message, not after it** (proposed, D-055): one
  door for every message, with classes, budgets, quiet hours for sound and one daily budget for questions
  about decisions, which sound only for news (BOT-13, DEC-7); an outcome log with one definition of
  "acted" (BOT-14); one switch-off automaton for message types, its fast rule now and its slow rule after
  4–6 weeks of the log (BOT-15); "not now" apart from "postpone", and a quiet command (BOT-16); one weekly
  package inside the Monday plan (RHY-6); the trace "a meeting was held, nothing was decided" on the
  mirrored sessions (DEC-25); a "record as a decision?" button under answers that use decision words
  (BOT-9); `/why` for the compact card. Without the gate the stage-2 bot would repeat v1: 7 messages with
  sound a day and about 4 % answered.
- **The home production laptop:** Linux and Docker Engine under the laptop profile of the baseline
  (DEP-14), full-disk encryption (PRV-11), the GPU image variant (DEP-25), platform updates only by owner
  command and travel mode (DEP-26); per-purpose SSH keys, the phone's operations key and the relay tunnel
  as the second remote path, with no public name yet (DEP-11, DEP-12); the overlay-VPN recipe (DEP-12); the
  egress allow-list (PRV-12) and the rest of the owner-device baseline (PRV-15: hardware-backed SSH keys,
  the messenger); one instance in the staging role
  deployed through the pipeline (DEP-4); promote, retire and fenced mode (DEP-3); signature verification on
  the host (DEP-8, DEP-9); `doctor` and `run` naming a configured port already in use (DEP-28); the
  off-host heartbeat with its status, the dependency rule and disk health
  (OPS-6); the off-host copy every 4 hours and the weekly off-host restore drill (OPS-5); security alerts
  in two channels (OPS-17); the lost-host and lost-device runbooks, dry-run before the host holds real
  data (DEP-24). **The 30-day host gate starts here** (DEP-27, D-050).

The morning plan and the notifications start with the decision waiting list, tasks and goals; later
stages add commitment proposals (stage 3), recordings and calendar (stage 4), meetings and briefs (stage
5), the weekly review (stage 7) and goal control (stage-8 module 2).

Exit criteria:

- Canary tests pass over text, voice, captions, replies, commands and forwards, under both journal-switch
  settings; after "this was journal" the canary appears nowhere outside the journal.
- An approval card executes exactly once under double taps and restarts; the same data produces the same
  morning plan; a second poller on the bot token fences the instance, while a network cut or a container
  restart does not.
- An answer in the chat goes from the question to an approved card to the record with no write before
  approval, on native and project-log decisions; a card taken from a stale fixture decision is answerable
  without opening anything else.
- The owner's context-change case passes as one sentence → one card (DEC-9).
- On the snapshot, every list of decisions groups by direction with the source shown, and the decisions
  without one are named (DEC-24).
- Proposed (D-055): a contract test finds no message sent outside the gate; nothing below class A sounds
  in quiet hours; 12 failures within 30 minutes produce one message; "not now" changes no date; on a
  synthetic month the daily median of messages with sound is at most 4.
- `doctor --host` passes with the laptop profile; the gate's measurement log runs; unplugging the home
  host's network raises an alert on the phone within 30 minutes; status, logs and a restore run from the
  dev machine with no physical access to the host; the lost-host runbook dry run lists every secret.

### Decision adoption gate (not before 1 December 2026)

Decisions move to v2 for good when the gate of OPS-16 holds (D-039; the date and the named cases
accepted, the other conditions proposed): the date (not before the forecast pilot's report on 1 December
2026, unless the owner records otherwise), the named cases passed, 14 consecutive clean daily runs,
backups with a tested restore, the daily asking channel of stage 2, and a target host that passed its gate
(DEP-27). v1's decision module becomes read-only.

Proposed (D-046): at the adoption gate the host's staging instance is retired, and the restored validation
instance is promoted to production with decisions only (DEP-23); the validation instance on the owner's
machine is retired. From then on there is no staging instance: pre-releases are checked in CI and by
`coflow drill` before the owner approves a production deploy; the kinds v1 still owns (people, sessions,
commitments, tasks, goals) are imported one way into production as read-only mirrors until stage 6; the
real cases of stages 3–5 run on throw-away drill copies of the production database.

Proposed: if stage 2 and the 30 gate days are not done by 1 December 2026, adoption waits; the owner may
instead record an interim production host. Adopting with a pull-only loop (CLI and MCP, without the chat
loop) would need a separate owner decision.

Proposed (D-055): the gate's checklist adds a clean start - one card that offers to cancel decisions whose
goal was dropped, spreads the remaining postponed checks over weekdays and never redates a review - and one
sender per message type while two bots run, v1 keeping plans, briefs and recordings and no longer asking
about decisions (OPS-16). At adoption the capture adapter switches its target from synthetic and
project-log data to v2, and its answers move to the bot, the owner channel.

### Stage 3 — Capture, commitment proposals and the centre slice

Scope:

- Inline, capped commitment proposals from conversations, with the decision rate measured per proposal
  type; a type below its threshold switches itself off (CMT-2, P-13).
- Decision proposals extended from AI clients (stage 0A) to conversations, extracted from segments and
  never from summaries, behind the evaluation gate (DEC-17); the two non-decision rules, offline and live,
  hold before chats or recordings propose anything (OPS-13; proposed, D-055).
- Readings computed from a catalogue of sources (hours against a budget, record counts, a commitment by its
  date), each source declaring whether it undercounts, so a short count yields a coverage line, never a
  violation (DEC-13; proposed, D-055).
- Occasions as attendance decisions with a brief file for an event app (DEC-21).
- Silence and contradiction as questions: an expectation with no fact by its date, and a new fact that
  contradicts an active assumption, each become one capped item (DEC-22).
- The decision schemas of the integration contract, with the event app's file adapter as their first
  consumer (EXT-5).
- The centre kept and versioned: the author's existing documents imported unchanged, with decisions and
  directions able to cite them (GOL-13).
- One computed check: what carries no link to a decision, a goal or a direction, with "framed by a goal
  only" and "explicit none" shown apart and the items behind every number (GOL-14). The formation
  protocols and the goal cards stay at stage 8.

Exit criteria:

- The decision-extraction thresholds (OPS-13) are met on the evaluation tiers; a planted retelling of an
  existing decision yields a fact on it, not a new decision.
- A planted contradiction yields exactly one card; a planted silence yields exactly one question.
- An occasion brief file is produced from an attendance decision, and a synthetic batch returns readings
  and commitments on that decision.
- A proposal that is not decided does not pile up in a queue; the decision rate per proposal type is
  available through an MCP read tool.
- The author's own centre documents are in the instance byte-identical to their files, and a decision
  cites one of them.
- The link check, computed on the snapshot of real history, names what carries no link to a decision, a
  goal or a direction, and the author recognises the list.

### Stage 4 — Sources

Scope:

- Recorder pipeline: a watched inbox fed by an encrypted folder sync and by bot voice notes, registration
  after complete arrival, transcription into segments in the worker with its own limits, summaries,
  resilience, recorder profile, archive budget (SIG-2…4, SIG-11, SIG-14); import of an external
  transcript, preferred for attribution when it carries speaker labels (SIG-16).
- Calendar copy, read-only, with freshness flags, per-purpose tokens and a headless login (SIG-9, EXT-3);
  with it, the stage-2 trace rules gain the calendar trace: a trip or an event that appears for the first
  time proposes an attendance decision (proposed, D-055).
- Host plugins, off by default: Telegram user-session collector with voice notes (SIG-7, SIG-8), Gmail
  read (SIG-10) (EXT-1).
- Contact proposals from conversations (PPL-3); recording consent with its basis and an "off the record"
  button (PRV-6; the basis and the button proposed, D-055).
- Health and the status page — the only web screen in R1 (OPS-6, UI-1); disk-space policy (DEP-13);
  outage behaviour, with missed briefs collapsed into one summary after recovery and expired cards named
  (DEP-15).

Exit criteria:

- A synthetic audio file synced from the desktop goes from the inbox to search exactly once, also after
  an interrupted sync; a killed transcription worker recovers while the bot keeps answering.
- The calendar copy reports `stale` when it is old; a mass disappearance of events is refused.
- Plugins cannot be enabled without the warning; the collector cannot send (test); each disk threshold
  triggers once on a fake filesystem.
- After a simulated outage, missed briefs arrive as one summary.

### Stage 5 — Meetings and reliable execution

Scope:

- Meeting intent with participants and a required link to work, where a decision counts as a link
  (MTG-1); a meeting creates the people it needs on one approval card instead of sending the owner to
  another interface (MTG-17); brief before the meeting with sources and named gaps, listing the decisions
  in play with their assumptions to probe (MTG-2); recording to meeting by time overlap or label (MTG-3);
  outcome to decision items first, then commitment and task proposals (MTG-4), with quotes extracted per
  chunk from segments (MTG-12), honest outcome messages (MTG-13), context assembled by rules (MTG-14), the
  record and analysis modes (MTG-15) and the conference link on online meetings (MTG-16); outcome recall
  measured against the owner's private evaluation set from stage 2 before a change ships (OPS-13); time to
  outcome measured and reported (NFR-12).
- One outbox for external writes, executed only by the production role: states, deterministic external
  ids, read-back before retry, read-back verification (MTG-5, P-8); calendar write safety (MTG-11).
- Fresh preflight: calendar freshness, busy time, booking hours, buffers between meetings with people
  (MTG-6); time model with DST handling and no host time zone (MTG-7).
- The full deploy path: write holds during a deploy, the bot approval card bound to the image digest and
  showing the facts computed by CI (DEP-9), automatic rollback while the holds are on (DEP-10).

Exit criteria (two review rounds — this stage writes to the outside world):

- A lost response, a double approval and a crash between steps each leave exactly one meeting and one
  calendar event (fake calendar that records every call); a foreign or recurring event is never changed.
- DST gaps and overlaps are refused or asked; every quote in an outcome is an exact substring of a
  transcript segment.
- A meeting planned for a decision shows its assumptions to probe in the brief.
- A deliberately broken release rolls back automatically with no lost bot message and no external write;
  a correctly signed release of an older commit is refused.

**R1 release:** tag `v2.0.0`. The Docker production install is verified on a clean Linux host by someone
other than the author within the NFR-2 budget; the native dev install on Windows by the author. The
author's home laptop has run CD-delivered pre-releases for at least two weeks, in the staging role or,
after the decision adoption, production, its 30-day gate under way or passed (DEP-27), with at least one
automatic-rollback drill and one restore drill. The demo
is a Compose profile with synthetic data that users run themselves. Release episode.

### Stage 6 — Import and the switch-over of everything else to the home laptop

Scope:

- A documented import format, the same as the full export (PRV-8); `coflow import`.
- Merge and undo of people (IDN-5); export and "forget" for a person (PPL-6).
- Functions the author uses in v1 today that R1 does not cover: the integration contract for external
  apps, with the decision anchors and read-only pull connectors for hosted apps (EXT-4), the ingestion
  API (DEP-16), the Windows desktop uploader (DEP-17), the activity-tracking device agent (RHY-5),
  external decision references (DEC-23) and delegated commitments from a team tool (CMT-5).
- The author's exporter from the private v1 lives in the private repository, not here. Other people can
  write exporters from their own tools the same way. Decisions moved earlier, at the adoption gate.
- Moving and rebuilding an instance (DEP-18): media moves with a hash manifest; bot, calendar and session
  credentials are created again on the host; recorder, uploader and agents are re-pointed; restores run in
  tiers, and the time target applies to the first two (DEP-18, DEP-19, OPS-5). Disaster recovery targets
  are documented and drilled yearly from here on, on a machine declared in advance (DEP-19).

Exit criteria:

- A dry run of the author's data in a throwaway drill instance on the host: counts match, the canaries
  pass, no data is lost.
- The instance is rebuilt on a different machine from the off-host backup alone, following
  DEPLOYMENT.md, within the measured time (target ≤ 2 h for the first two restore tiers, excluding the OS
  install); a 48-hour outage drill passes (DEP-15).
- A switch-over checklist: every v1 function used in the last 30 days is either available in v2 or
  explicitly paused by the author (for example the unused week plan, MTG-10).
- The host gate of DEP-27 has passed before promote (D-050).
- Everything else is imported into the production instance on the home laptop; promote there only if the
  decision adoption has not happened; v1 is retired and the retirement is verified through health output,
  not by assumption.

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
  (DEP-20; the GPU image variant moved to stage 2).

Exit criteria:

- A rule explained once works in a new conversation and after a restart; forwarded text creates no rule.
- An incident package contains no journal text, no real third-party data and no infrastructure
  identifier (test).

### Stage 8 — Modules after the switch-over

Each module is a separate mini-stage with its own module cards, review, deploy and episode. The order of
the modules, including the centre and goals module at position 2, is confirmed by the author (D-031); the
split of money into two parts is a proposal. On 18 October 2026 the author moved internet-facing MCP for
cloud clients to the front of the queue as module 0 (D-031, D-052).

| # | Module | Requirements | Size | Agent tokens | Workflow hours | Note |
|---|---|---|---|---|---|---|
| 0 | Internet-facing MCP for cloud clients, read-only first | MCP-5, PRV-13 | L, 2 rounds | 7–10M (estimate, re-planned at the module start) | 14–20 | First in the queue (D-052); the owner relay on a separate domain (D-053); a separate `edge` container, pairing confirmed in the bot, the cloud view without untrusted external text (PRV-14); writes later as a separate resource, off by default; interoperability first tested on a throwaway machine with synthetic data |
| 1a | Money core: books and taxpayers, money between books, ledger, invoice register, document archive, financial goals, reports | FIN-1, FIN-2, FIN-4…9, FIN-14, FIN-16 (file adapter) | L, 2 rounds | 7–10M | 13–19 | Planning and evidence; invoices registered from a certified invoicing program, never issued (D-026). Proposed: Norma 43 and one CSV profile pulled in here (+1–2M, +2–4 h) so the ledger reconciles from day one. Without that pull-in, balances are entry-based and are not reconciled with the bank until module 7 — owner to decide (REQUIREMENTS §8 q.9); a short legal opinion before publishing (covers 1a and 1b) |
| 1b | Country pack: the interface and the Spain reference pack — calendar, reserves, advisor export, thresholds, rules-watch | FIN-10…13, FIN-15, FIN-17, FIN-18 | L, 2 rounds | 5–8M | 12–17 | Golden tests per tax year; a short legal opinion before publishing |
| 2 | Centre and goals: import, formation sessions, versions, rule objects, control, reviews, weekly reflection | GOL-1…12, LRN-6, RHY-4 link | L | 6–8M | 12–16 | Position confirmed (D-031); provenance test; planted-problem evaluation year; goal states and verdicts tied to the `pursue` decision and its learnings (GOL-7, GOL-9) |
| 2b | Inconsistency findings: what the owner thinks, says and does against the centre | ALN-2…5 | L | 4–6M | 8–12 | By the owner's decision, right after goals; evidence on both sides, "can't judge", a planted evaluation set before any finding is shown; the journal under PRV-9 |
| 3 | "Send material" commitment | CMT-3 | M | 2–3M | 4–6 | — |
| 4 | Negotiation through the owner's messenger account | MTG-8 | L, 2 rounds | 6–9M | 14–19 | Starts with a spike: account requirements, 24-hour window, how messages look to the counterpart |
| 5 | The whole personal archive in the timeline | TML-2 | L | 4–6M | 8–12 | Plus a one-off model cost, estimated on a sample first |
| 7 | Statement import, other formats | FIN-3 | M | 2–3M | 4–6 | camt.053, OFX, more CSV profiles |
| 8 | Week plan; birthdays, client view, hypotheses | MTG-10, PPL-5, PPL-7, WRK-4 | M | 2–4M | 4–8 | The week plan exists in v1 but is unused so far; hypotheses are decisions of kind `test` |

Module 6 moved to the front as module 0; the number 6 is not reused.

### Research (after stage 8; indicative, not planned)

Each research module starts only on core data (REL-6), with a pre-registered protocol and its own
evaluation set.

| # | Research | Requirements | Size | Agent tokens | Workflow hours |
|---|---|---|---|---|---|
| R-a | Relationship balance | REL-1…3 | M | 2–4M | 4–8 |
| R-c | Conductivity protocol and predicting G(t+1) — after a planned experiment gate (November 2026) | REL-4, REL-5 | L | 4–6M | 8–12 |
| R-d | Change over time | TML-3 | M | 2–4M | 4–8 |
| R-e | Calibration: weekly sealed forecasts by the author and a model, scored against base rates — after the v1 pilot ends (30 November 2026) and reports (1 December 2026) | DEC-10 | S | 1–2M | 2–4 |

DEC-8 (a decision view behind UI-2) stays Later.

## Estimates

Units:

- **Agent tokens** — the sum of tokens of the coding agents in the stage's workflows.
- **Workflow hours** — wall-clock time while the stage's workflows and CI run, sequentially.
- **Owner hours** — reviews, decisions, acceptance, host setup and drills; not included in workflow hours.

The basis is measured work on the private v1 in September–October 2026: a large stage with external
writes and two review rounds took ≈ 7.4M tokens and 13.6 hours; a medium stage with one round took
≈ 1.5–2.5M tokens and 3–5 hours. Porting proven code is cheaper than inventing it, but the rewrite is
broader and now includes the delivery pipeline and the decision core. These are forecasts, not
commitments; they are recalculated after the first increment of stage 0A with the measured speed, and
again after stage 0B.

| Stage | Size | Agent tokens | Workflow hours | Owner hours |
|---|---|---|---|---|
| 0A Kernel and decision core | L (capture and the costly-later fields in I2, D-055) | 13.5–20.5M | 27–42 | 4–5.5 |
| 0B Delivery and operations | M (the trust minimum, D-055) | 6–10M | 12–20 | 1–2 |
| 1 Memory core with decision anchors | L | 9.5–15M | 19–29 | 1–2 |
| 2 Bot, rhythm, the decision loop in chat, and the home laptop | L (re-estimated at the stage start: the chat loop from stage 3, D-040; the host security items, D-050 to D-053; the attention gate, D-055) | 8.2–12M | 15–24 | 23–39 (incl. moving the laptop to Linux with the laptop profile and disk encryption, ≈ 8–16 h, and the relay as the second remote path, ≈ 3–5 h; estimates) |
| 3 Capture, commitment proposals, centre slice | M | 4.3–6.5M | 9–13 | 1 |
| 4 Sources | L | 6–9M | 12–18 | 2–3 |
| 5 Meetings, reliable execution, rollback | L, 2 rounds | 7–11M | 14–22 | 2–4 |
| **R1 (stages 0A–5)** | | **54.5–84M** | **108–168** | **34–56.5** |
| 6 Import, switch-over, device agents, rebuild drill | L | 8–12M | 15–23 | 4–6 |
| 7 Learning loop | L | 5–7M | 10–14 | 1–2 |
| **Stages 6–7** | | **13–19M** | **25–37** | **5–8** |
| 8 Modules 0, 1a–5, 7, 8 (incl. 1b, 2b) | per module | 45–67M | 93–135 | 1–3 per module |
| Research R-a, R-c, R-d, R-e | indicative | 9–16M | 18–32 | per protocol |

The R1 totals are before the stage-2 re-estimate. Proposed (D-055), from the estimates of the
adoption-barrier designs and their reviews: capture in I2, the trust minimum in 0B and the attention gate in
stage 2 add about 9–15M agent tokens gross, of which about 2–3M were already budgeted (BOT-5, DEC-7,
`dec_propose`), so about 7–12M net, 10–25 % of the earlier R1 total (47.5–72M): I2 +1.5–3M, 0B +2–4M,
stage 2 +1.2–2M, and the rest across I3 and stages 1 and 3. At one stage a week the path to 1 December 2026
becomes about a week longer, which the weekly episode names. Model cost of capture from every source stays
under $15 a month; the owner's time on the decision layer after it starts is about 15–25 minutes a week,
against about none in v1. Model API cost while developing (evaluation runs with a
live model, behind an explicit flag): on the order of $30–60 for R1; stage 0A makes no model call. Running
costs of the home host (electricity, the relay, object storage for backups, the dead-man service) are
measured after stage 2 and published in [DEPLOYMENT.md](DEPLOYMENT.md) §4 together with the hardware
choice (§14).

## How a stage runs

1. **Slice.** The requirement IDs of the stage become a short stage spec with acceptance cases and the
   module cards it touches.
2. **Build.** Coding agents implement it; tests use temp data, fake providers and no network.
3. **Review.** One independent review round; two when the stage writes to the outside world or builds a
   money module. No further polishing rounds: leftovers become issues.
4. **Release.** A tagged pre-release `v2.0.0-alpha.N`, one signed image, changelog, updated docs (from
   stage 0B; stage 0A closes with green CI and its acceptance results).
5. **Deploy.** Through the CD path to the home laptop: the staging role until the decision adoption (or
   the switch-over, if adoption has not happened), production after it (proposed, D-046). Stage 0A runs
   natively in the `dev` and `validation` roles on the owner's machine.
6. **Accept.** On the deployed instance, against the module cards: CI scorecards for every module; the
   owner personally accepts the modules that hold money, the journal or external writes, the goals
   module, and the decision core. Stages 0A–5 are accepted on synthetic data in CI and on the stage's
   named real cases in the validation instance or, after the decision adoption, on throw-away drill
   copies of the production database (D-046). A failed acceptance is answered with a rollback or
   a new release, never a fix on the host.
7. **Episode.** Episodes are weekly, whatever the stage boundaries: what was done, what was tested, what
   was worked through, the numbers, what was learned. The stage's acceptance results go into the episode of
   the week it closes.

## Rules while v2 is built

- **Development started on 17 October 2026** (D-038), which overrides the timing of D-004 ("code after
  the v1 acceptance period"): the acceptance period continues in parallel and is no longer a condition for
  code.
- **The private v1 is frozen** since 4 October 2026: acceptance fixes and dangerous bugs only. Everything
  else becomes a v2 issue. One exception since 17 October 2026: the decision loop (D-006, D-037) and, from
  17 October 2026, a read-only exporter of v1's decisions in the private repository (D-039). A second
  exception from 1 November 2026: v1's notification noise outside the decision module is reduced (D-055).
- **The capture experiment stays outside the daily flow** (D-055): it is read-only, its results stay outside
  every repository, and nothing from it is shown in the daily flow before a separate decision, not before
  2 November 2026.
- **Never two writers.** Until the adoption gate every real decision is written in v1; v2 holds read-only
  mirrors in the validation instance and computes, never writes back. The v2 MCP tools use their own
  namespace, so v1's tools stay the forecast pilot's only write path. Reading the shadow daily is part of
  the pilot's record, and every intervention it causes is recorded for the pilot's analysis (D-039).
- **Real data on a host only after its gate** (DEP-27); until then real history lives only in the
  validation instance on the owner's machine (DEP-23), and from the decision adoption in the production
  instance on the gated host.
- **Nothing for growth.** A requirement without a usage signal or an explicit decision of the author waits.
  The install ladder and the first-day items wait for their named triggers: a decisions file, the
  `personal` profile, the drill between install tiers, the first session with prospective checks and the
  outsider's session (DEC-27, DEP-29, DEP-30, OPS-18, NFR-14; proposed, D-055).
- **Synthetic data only** in the repository, issues, screenshots and episodes; no identifiers of the
  author's infrastructure (host names, addresses, domains, VPN or tunnel ids, SSH users). The real
  snapshot, the case scripts and their reports live only in the validation data root (after the
  adoption, the production data root), never in any repository, public or private; no real v1 decision
  number appears in public text.

## Risks

| Risk | Mitigation |
|---|---|
| The second-system trap: the rewrite grows beyond R1 | R1 scope is fixed by requirement IDs; additions need a usage signal and an owner decision; deployment extras are R2 or Later |
| Stage 0B's delivery work delays the decision core | The decision core is stage 0A, before the delivery pipeline; stage 0B builds only a skeleton against any Linux host; the physical host comes in stage 2, rollback in stage 5 |
| The shadow disturbs the forecast pilot or becomes a second writer | One-way snapshots, read-only mirrors, the mirror guard on every command, its own MCP namespace; daily reading recorded in the pilot's change journal (D-039) |
| v1 needs change during the rewrite | Feature freeze; acceptance fixes only (two exceptions: the decision loop, D-037, and from 1 November 2026 less notification noise outside it, D-055); v2 issues instead |
| Nobody uses it: decisions never reach the record, checks feel unpleasant, the payoff comes late, messages become noise | Capture where decisions are born moves into I2 and the owner's own answer rate gates I2 (D-055); proposed: owner-typed text only, two non-decision rules, one door and one budget for attention, exit rules in the owner's words (SIG-19, OPS-13, BOT-13, DEC-26) |
| Development competes with paid work | One stage per week at most; a stage can slip, the scope cannot grow |
| The production host is unreachable while the owner is away | Remote administration is a precondition; an off-host heartbeat; a tested power-on method after power loss; a second remote path through the relay; the laptop profile, travel mode and up to 7 days of accepted downtime (DEP-14, DEP-26); a travel runbook |
| The host decision changes again | The 30-day gate with recorded measurements; the same image on any fallback host (DEP-27) |
| A second writer appears across dev, validation, drills and production (the v1 collision) | Instance roles, promote/retire with credential rotation, fenced mode, one-way data flow, no sync |
| The CI/CD supply chain delivers malicious code to the host that holds private data | GitHub-hosted runners only; pinned actions and base images; tag rules; keyless signatures verified on the host; only a higher version that descends from the deployed commit; human review of security-sensitive paths; pull-based deploy with owner approval; no CI credential into the home network |
| Cloud AI clients leak data through third-party text or a phished consent | Read-only first, untrusted external text withheld, pairing confirmed in the bot, quotas, alerts in two channels (MCP-5, PRV-14, OPS-17) |
| Personal or third-party data, or infrastructure identifiers, leak into the public repository or episodes | Synthetic fixtures, the literal gate, secret scanning, installation config and the validation data root kept off the repository, review of every episode |
| Tax rules change and a stale pack gives wrong dates or figures | Rules as data with official sources and dates, a quarterly rules-watch, "unverified" marking, tests pinned to a tax year |
| Legal exposure of the money features | No invoicing or filing (D-026), read-only invoice adapters, labelled estimates; a short legal opinion before publishing module 1 that also tests whether LGT art. 29.2.j and 201 bis (accounting and management software) apply to the ledger (REQUIREMENTS §8 question 10) |
| The goals module drifts into model-written content | Approval only in owner-typed channels, the provenance test, rule objects as typed fields and exact quotes |
| Platform terms (Telegram user sessions, Google OAuth for personal accounts) | The collector is an off-by-default plugin with a warning; the OAuth path is verified in stage 0B and documented |
| A single maintainer | Decisions, lessons, module cards and stage specs are public |
