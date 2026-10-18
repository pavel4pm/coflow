# CoFlow 2.0 — Decision core specification

Version 0.1 · 18 October 2026 · **status: draft for owner review.** It implements the decision entries
D-038 to D-049 and follows D-050 to D-053 where the core meets hosting and access. Only what those entries
mark "accepted" is the owner's decision (see "Status of the parts" below). Every other rule, name, number
and default in this document is proposed, and the requirements that implement a proposed part stay
proposals until the owner confirms them.

This is the technical specification of the decision-first core of CoFlow 2.0: the slice built in stage 0A
of [ROADMAP.md](ROADMAP.md), its data model, the values it computes, its API, MCP and CLI surfaces, the
one-way import of the predecessor system's decisions, the decision fields of the ecosystem contracts, the
acceptance tests and the build plan. Requirement IDs refer to [REQUIREMENTS.md](REQUIREMENTS.md) (v0.7),
decisions to [DECISIONS.md](DECISIONS.md), modules and boundaries to [ARCHITECTURE.md](ARCHITECTURE.md) and
[MODULES.md](MODULES.md), hosts and roles to [DEPLOYMENT.md](DEPLOYMENT.md). A coding agent implements
stage 0A from this text together with those documents; where this text is more precise than a requirement
row, this text is the contract, and a disagreement is fixed in the documents first, then in code.

Every example is synthetic: numbers, titles, people, companies and dates are invented. The only real
decision numbers in this document are entries of the project's own public decision log. The owner is "the
owner", they/them.

## How to read this document

**Increment and stage markers.** **[I1]**, **[I2]**, **[I3]** = the three gated increments of stage 0A
(§1.4). **[0B]** = the second part of stage 0. **[Later n]** = specified now so the slice does not block it,
built at stage n ("8.0" is stage 8, module 0; "8.1a" is stage 8, module 1a). A section without a marker
belongs to stage 0A as a whole.

**Normative pseudo-code.** Code blocks in §4, §5 and §10 are Python-like and normative: a test suite can
be written from them, and the independent health oracle (§4.7) is written from the text alone. Names in
code are the names the implementation uses. `T` is the evaluation instant in UTC and `T.date` its date in
the owner's time zone.

**Two kinds of "D" numbers.** The project's decision log uses `D-NNN` with three digits (D-038 is an entry
in [DECISIONS.md](DECISIONS.md)). Product decision ids use four digits: `D-0907` is a decision mirrored from
the predecessor's `D907`, and `D-1001` is the first decision native to v2. Forks are `Q-NNNN` and
commitments `F-NNNNN`.

### Status of the parts

| Part | Where | Entry | Status |
|---|---|---|---|
| The decision is the base entity of CoFlow 2.0; signals, commitments, tasks, meetings, events, goals and learning attach to it; development started on 17 October 2026 | §1, §2 | D-038 | **accepted** (17 October 2026); the stage placement (0A) is proposed |
| Shadow first, then switch-over: one-way snapshots of v1's decisions (v1 → v2 only); v2 computes the waiting list, check dates and health itself; when the owner's 3–5 real cases pass, decisions move to v2 for good and v1's decision module becomes read-only; never two writers; not before 1 December 2026 unless the owner changes that; until then every real record is written in v1 | §10 | D-039 | **accepted** (17 October 2026) |
| Reading the shadow is part of the forecast pilot's record: the pilot's change journal records the start of the v2 shadow, the owner reads the shadow waiting list daily, and every intervention it causes is recorded and taken into account in the pilot's analysis | §10.9 | D-039 | **accepted** (18 October 2026) |
| The shadow's mechanics: mirrors, the daily import, the classified shadow report, the expected-difference rules, the case runner, the gate conditions beyond date and cases | §10 | D-039, D-046 | proposed |
| Build order: a minimal stage-0 kernel plus a vertical slice of the decision core; Docker, CD and backups in the next part of stage 0 | §1.3, §13 | D-040 | **accepted** (17 October 2026); the 0A/0B split and the three increments are proposed |
| The ecosystem stays as separate blocks | §11 | D-041 | **accepted** (17 October 2026); independence from every block, remote access and the contract fields are proposed |
| Links stored by the module whose workflow forces them; the three ports | §3.10, §5 | D-042 | proposed |
| The basis is sealed by a hash when a decision is activated; a revision keeps the number and seals a new edition; it needs a reason (a new fact, a stated change of mind, or the correction of a mistake); a genuinely different decision gets a new number and a link saying it replaces the old one | §4.1, §4.3, §4.10 | D-043 | **accepted** (18 October 2026) |
| The seal's mechanics (CFJ-1, salted per-item hashes, erasure), adjust without an edition, sealing at import, outcome resolutions with a basis, the learning required at closing, related learnings | §4.3, §4.11 | D-043 | proposed |
| Health on two axes, the composite order, the unverifiable share first | §4.7 | D-044 | proposed; not yet put to the owner |
| Numbering: v1 decisions keep their numbers in four digits (`D907` → `D-0907`); new decisions from `D-1001`; `Q` numbers forks; `F` numbers commitments, new ones from `F-10001`; numbers are permanent | §3.2, §10.4 | D-045 | **accepted** (18 October 2026) |
| Widths of `Q` (4) and `F` (5), the foreign and burned registers, scoped codes, aliases and tolerant input | §3.2, §10.4 | D-045 | proposed |
| The `validation` role, real cases on throw-away copies, the project log as native data | §10.1, §10.7, §10.8 | D-046 | proposed |
| Decision kinds instead of parallel hypothesis and event entities | §2.3 | D-047 | proposed |
| The decision link is offered and counted, not required: when a task, a commitment or a meeting is created, up to three likely decisions are offered and "no decision" is a valid answer; a report shows four buckets (linked, deliberately without, not answered, not offered); a commitment may exist without a decision | §4.14 | D-048 | **accepted** (18 October 2026) |
| Deterministic offers, a label beats a guess, a reason on an explicit "none", the offer for ledger entries and time spans, the attachment refusals | §4.14 | D-048 | proposed |
| Append-only and bitemporal evidence, one transaction log, as-of | §3.1, §3.8, §4.15 | D-049 | proposed |
| Production on a dedicated home laptop with a GPU after a measured 30-day gate | §10.10 | D-050 | **accepted** (17 and 18 October 2026); that the decision adoption lands only on a host that passed the gate is proposed |
| Internet access in two steps: the bot and the VPN first; cloud AI clients later as the first stage-8 module, read-only first; the public entry through the owner's relay | §5.5, §11.5 | D-052, D-053 | **accepted** (18 October 2026); the module's security baseline and the relay recipe details are proposed |

### Requirements this document implements

| Stage | IDs |
|---|---|
| 0A (this slice) | P-15, P-16; IDN-1, IDN-2, IDN-9, IDN-10; DEC-1…4, DEC-6, DEC-11…20 (DEC-17 for AI clients); CMT-1; OPS-3, OPS-4, OPS-15 (decisions), OPS-16; PRV-1 (classes), PRV-10; EXT-6; MCP-1 (loopback and the local shim), MCP-2, MCP-3, MCP-4; DEP-2, DEP-23; NFR-6 (canary fixture), NFR-13 |
| 0B | OPS-5 (backups the adoption gate needs), OPS-8 (the evaluation harness refuses a validation data root) |
| Later, specified here so the slice does not block them | DEC-5, DEC-7, DEC-9 (stage 2); DEC-17 for conversations, DEC-21, DEC-22, EXT-5 (stage 3); WRK-3, WRK-8 (stage 1); MTG-1, MTG-2, MTG-4 (stage 5); DEC-23, CMT-5, EXT-4 (stage 6); MCP-5 (stage-8 module 0); DEC-8 and DEC-10 (Later) |
| Gates | the decision adoption gate (OPS-16) with the host gate (DEP-27) |

---

## 1. Scope and the slice

### 1.1 The core in fifteen sentences

1. The **decision is the aggregate root** of CoFlow 2.0. Every other record is evidence a decision rests
   on, execution of a decision, a check of its assumptions, or the frame (goal, direction) it serves, and
   it says which, or says "none" on purpose (P-15).
2. The aggregate is small and closed. It holds the decision, its sealed editions, options, forks,
   assumptions, an append-only check log, readings, facts, reviews, outcome resolutions, learnings, stakes,
   and the links whose enforcement point is a decision workflow. Commitments, tasks, meetings, goals and
   money stay in their own modules and **attach by reference**.
3. **A link is stored by the module whose workflow forces it.** CMT stores "this commitment executes
   D-0042" in its own unit of work; DEC stores decision↔decision links, "serves", "about" and evidence. No
   module writes another module's links (DEC-11).
4. DEC stays in tier 2 and imports nothing above it. Spokes reach it through **`DecisionDirectory`**; DEC
   reads spokes through **`DecisionAttachmentProbe`** and validates evidence through **`EvidenceResolver`**.
5. A decision is **pre-registered** (P-16). Activation seals edition E-01 of its basis by salted SHA-256
   hashes over a float-free canonical JSON (CFJ-1, byte-identical to the forecast pilot's form for its
   records). A revision seals the next edition under the **same number**, and a privacy erasure keeps the
   seal verifiable (DEC-12).
6. **Every check is a row**, and so is every reading. A reading only proposes a state; an owner
   assessment decides it. "Can't judge this time" (UNKNOWN) is distinct from "nothing to check with"
   (UNVERIFIABLE) (DEC-13).
7. Health has **two axes**: ground, from the assumptions the decision rests on, and timeliness, from the
   review, overdue checks and silence. One composite label follows from a fixed table in which a known
   violation comes first, an overdue review is never masked by missing data, stale or overdue checks are
   never "on track", and the **unverifiable share is the first line of every card** (DEC-3).
8. One **waiting list** with reasons serves the CLI and MCP now, and the plan and the bot from stage 2. It
   covers every violated assumption (critical or not, with its criticality shown), reviews due, a goal that
   changed, checks due, open questions past their deadline and proposals (always last). Every item carries
   a **rule-built question context** whose button values come from the same functions the write uses
   (DEC-6, DEC-20).
9. Outcomes are **resolutions with a basis**: resolved (measured), reported, or not confirmed. Outcome
   claims from anyone are evidence, not resolutions. Closing requires a **learning**, and a new decision of
   the same kind, subject or assumption class is shown earlier learnings (DEC-15).
10. **One transaction log** records who wrote each unit of work, through which channel, under which
    approval and in which instance role. The store layer stamps it, never the caller. Event time and
    knowledge time are separate, and `as_of(T)` answers on the knowledge, instance and occurrence axes
    (NFR-13).
11. **Shadow first.** A `validation` instance holds daily one-way snapshots of v1's decisions as read-only
    **mirrors** that keep their numbers (`D907` → `D-0907`). It seals them as imported editions, computes
    health, due dates and the waiting list itself, and writes a **shadow report** per run that classifies
    every difference as same, expected (a numbered rule with a test) or unexpected (OPS-15, OPS-16).
12. Real write paths are exercised **without a second writer**. The owner's scripted real cases run on a
    throw-away copy of the validation database, and decisions the owner selects from the project's public
    decision log become native records whose text the log owns and whose monitoring v2 owns.
13. v2-native decisions are numbered from **`D-1001`**, so v1 and v2 never issue the same number and no id
    changes at the switch-over (IDN-10).
14. **Adoption is gated in code.** Decisions move to v2 for good, and v1's decision module becomes
    read-only, not before 1 December 2026 and only after the owner's real cases pass; the proposed gate
    adds 14 clean consecutive shadow runs, backups with a tested restore, a daily asking channel and a
    target host that passed its own gate (OPS-16, DEP-27).
15. The slice is **model-free and offline**. Every number is computed by code, so the slice needs no model
    gateway, no provider key and no data flow beyond the owner's machine.

### 1.2 Fixed constraints and kept invariants

The owner's decisions this slice must honour (condensed; the entries hold the exact words):

| # | The owner's decision | Entry | Honoured in |
|---|---|---|---|
| C-1 | The decision is the base entity. Signals, commitments, tasks, meetings, events, goals and learning attach to it, so the owner can test and use v2 on themselves systematically. Development starts on 17 October 2026 | D-038 | §2, §3.10, §5 |
| C-2 | Shadow first, then switch-over; v1 → v2 only; v2 computes the waiting list, check dates and health itself so the owner can compare; after the owner's 3–5 real cases pass, decisions move for good and v1's decision module becomes read-only; never two writers; not before 1 December 2026 unless the owner changes that | D-039 | §10 |
| C-3 | Build now: storage with migrations, one numbering tap, events, data classes, CI on Windows and Linux, uv and ruff; plus the decision module (decision, fork, options, assumptions with check dates, facts, reviews, commitments, outcome, learning), CLI and MCP for decisions, and the import of v1 decisions. Docker, CD and backups come next | D-040 | §1.3, §13 |
| C-4 | The ecosystem stays as separate blocks, as they are (a real-time online conversation agent, an offline-event app whose purpose of attending is known upfront, plain uploads of communications, a tool for external work with a team) | D-041 | §11 |
| C-5 | A revision keeps the number and creates a new sealed edition; the basis is sealed by a hash at activation; a revision needs a reason (a new fact, a change of mind, the correction of a mistake); a genuinely different decision gets a new number and supersedes the old one | D-043 | §4.1, §4.3, §4.10 |
| C-6 | v1 decisions keep their numbers (`D907` → `D-0907`); new decisions from `D-1001`; `Q` for forks; `F` for commitments, new ones from `F-10001`; numbers are permanent | D-045 | §3.2, §10.4 |
| C-7 | The link to a decision is offered (up to three likely decisions at creation) and counted in four buckets; "no decision" is valid; a commitment may exist without a decision | D-048 | §4.14 |
| C-8 | Reading the shadow daily is part of the forecast pilot's record, and every intervention it causes is recorded | D-039 | §10.9 |
| C-9 | Internet access is required; data and processing live on a dedicated home GPU laptop that holds real data only after a measured 30-day gate; the bot and the VPN come first, cloud AI clients later and read-only first | D-050, D-052, D-053 | §5.5, §10.10, §11.5 |

Proposed with these, not the owner's words: events are written in the same unit of work as the change, and
the kernel includes the configuration minimum (D-040); CoFlow works without any of the ecosystem blocks
(EXT-6) and remote access is not precluded (D-041).

**Kept invariants:**
- one writer, and modules own their tables (P-14);
- cross-module references are public ids or `<ISSUER>_<id>` refs, never foreign keys;
- events are committed in the same transaction and carry ids and changed field names, never values;
- the principles P-3 (propose, don't act), P-4 (approval cannot be forged by text), P-6 (evidence over
  inference: a source and a quote, "can't judge" is valid, numbers by code), P-7 (compute once, with
  provenance), P-9 (honest freshness), P-10 (third-party text is data), P-12 (no personal literals) and
  P-13 (build only what use proves);
- the journal is a separate class, never indexed or exposed (P-2), and no decision command accepts
  journal-class input;
- one numbering tap and one prefix registry (IDN-1, IDN-2);
- no personal data in the public repository: the real snapshot, the owner's case scripts and the shadow
  reports live only in the validation data root.

### 1.3 The slice against later stages

| Area | Stage 0A (this slice) | Later |
|---|---|---|
| Kernel | STO: writer thread, numbered migrations, a table registry with owner, class and append-only declarations, generated triggers, the transaction log, the instance lock. IDS: the tap, the prefix registry, foreign and burned numbers, aliases, tolerant parsing. EVT: events in the unit of work, in-process dispatch. POL: class declarations, the journal canary fixture. CFG: the owner profile minimum and settings. OPS: `init` with the roles `dev` and `validation`, a basic `doctor`. OBS: usage-signal rows. ADM: the loopback admin API. The minimal literal gate (P-12) | 0B: Docker, Compose, CD, the image, the updater, backups and restore, the scheduler, the model gateway with a fake provider, the secrets store, the exposure test, the full `doctor` |
| Decision core | Decisions, editions and the seal, options, forks, assumptions, the check log, readings, check dates, facts, reviews, outcomes, learnings, stakes, DEC-owned links, health, the waiting list, the question context, history and as-of, integrity, the v1 importer, the shadow report, the case runner, the project-log importer, proposals from MCP, the adoption gate | Stage 2: the chat loop (DEC-5, DEC-7, DEC-9) behind approval cards. Stage 3: capture from conversations, occasions, silence and contradiction questions (DEC-17, DEC-21, DEC-22). Stage 6: external decision references (DEC-23) |
| Commitments | The CMT minimum (CMT-1): debtor, creditor, success criterion, due date, status, actual done time, the decision executed or an explicit "no decision" with a reason, the entry-time link answer, history; CMT implements the attachment probe | Stage 3: inline proposals (CMT-2). Stage 6: delegated commitments from a team tool (CMT-5) |
| Interfaces | MCP over Streamable HTTP on loopback with per-client tokens and a read-only list; a local stdio shim that forwards to it; decision tools in the `dec_` namespace, commitment tools in `cmt_`; the CLI | Stage 1: the SSH bridge. Stage 2: the bot. Stage 6: INT (EXT-4). Stage-8 module 0: internet-facing MCP for cloud AI clients, read-only first (MCP-5, D-052) |
| Ports | `DecisionDirectory` (DEC implements), `DecisionAttachmentProbe` (CMT implements), `EvidenceResolver` (built-ins), `GoalDirectory` (a shadow adapter over mirrored goal context) | Stage 1: SIG uses `DecisionDirectory` and implements `EvidenceResolver`; WRK implements the probe and `GoalDirectory` |
| Projections | `owner` (CLI) and `agent` (MCP) | Stage 3: `event_app` (file). Stage 6: `live_app`, `team_tool`. Stage-8 module 0: the cloud view (PRV-13, PRV-14). Later: `public` tooling |
| Model calls | none | Stage 2: splitting a chat answer (DEC-7). Stage 3: extraction behind an evaluation gate (OPS-13) |

### 1.4 Increments inside stage 0A

Each increment is usable on its own and is a hard gate: the next starts only when its tests are green on
Windows and Linux (proposed, D-040).

| Increment | What the owner can do when it closes | Content |
|---|---|---|
| **I1 · read-only shadow** (first, within days) | Ask v2 "what is waiting and why" about the real v1 decisions, through MCP or the CLI, and compare with v1 | The kernel; the DEC schema for everything an import writes; the date, due, health and waiting functions; the snapshot importer with the rebuilt check log; the shadow report; the `GoalDirectory` shadow adapter; the MCP read tools; `coflow dec waiting / show / shadow / import` |
| **I2 · native loop** | Record, activate, check, read, review, close and learn on the selected project-log decisions and on synthetic decisions; the owner's own new decisions are recorded in v1 until the adoption gate (D-039) | Create, update, activate, seal, integrity; options, forks, assumptions, checks, postponements, readings, facts, stakes; reviews with outcome and learning; completion of reconstructed records; links; publishability; undo; idempotency; MCP and CLI writes; the project-log importer |
| **I3 · execution and evidence** | Attach commitments to decisions, see execution in reviews, ask "what changed and why" over a period, and run the real cases | CMT; the attachment probe; the unlinked report; `decision_history`; loop metrics and usage signals; proposals and their approval in an owner channel; the case runner; the adoption gate (refusing until its conditions hold) |

**Stage 0A closes** when the acceptance tests of §12.1 pass in CI on Windows and Linux, the first real
snapshot has been imported into a validation instance with equal counts, the shadow report has run on at
least 7 daily snapshots, at least three project-log decisions have assumptions and review dates added by
the owner, and the owner's four named cases for stage 0A have passed with the case runner (§12.2).

### 1.5 Not in this document

The chat loop and its approval cards (stage 2, DEC-5, DEC-7, DEC-9) are specified only as far as the
slice must not block them. Capture from conversations and the evaluation gate (stage 3, OPS-13), the
meeting module (stage 5), money (FIN), goals beyond the shadow adapter (WRK, GOL), the delivery pipeline
and backups (stage 0B, [DEPLOYMENT.md](DEPLOYMENT.md)) and internet-facing access (MCP-5) have their own
requirements; this document names only their decision fields and ports.

---

## 2. Ontology

Each term has a definition and an **acceptance test**: a sentence that a record, a candidate or a fixture
must satisfy to be called by that name. Code, an evaluation set or a reviewer can apply each test.

### 2.1 The chain

```
 Signal ──opens──▶ Fork (open question + options) ──choice──▶ DECISION  (status active; edition E-01 sealed:
   │                                                            │  question, statement, chosen option, options,
   │                                                            │  grounds, unknowns, assumptions, success
   │                                                            │  criterion, expected outcome, stake, review date)
   │        new fact, reading, passed date                      │
   └──────▶ Fact / Reading ──▶ Check (assessment, append-only) ◀┤
                                                                ├──▶ Commitments, tasks, meetings, money, time
                                                                │     (attach by their own decision_ref)
                                                                ├──▶ Review: keep · adjust · revise→E-(n+1) ·
                                                                │            supersede · cancel · close
                                                                └──▶ Outcome resolution (resolved | reported |
                                                                     not confirmed) ──▶ Learning ──▶ shown to
                                                                     later decisions of the same kind, subject
                                                                     or assumption class
```

### 2.2 Terms

| Term | Definition | Acceptance test |
|---|---|---|
| **Signal** | A dated observation from a source: a conversation segment, a message, a document, a calendar event, an owner note, an app envelope, a computed reading, or the absence of an expected event | It has a source reference that resolves, or is explicitly an owner statement, and an event time, or the event time is recorded as unknown |
| **Fork** (open question) | A question that someone with authority must settle, opened at a time by a trigger and not yet settled. Statuses: open, decided, dissolved, delegated. A flag "outcome not heard" marks a source that ended before a result | At least two options exist, explicitly or as the implicit "do / don't"; a decider is named; no source states the choice |
| **Option** | One alternative of a fork or a decision, with the time it was recorded and, after the choice, why it was rejected | It has text and a record time. It counts as part of the pre-choice option set only if it was recorded before the choice (`recorded_before_choice = yes`) |
| **Choice** | The option a decision settles on; it may be a refusal to act | The decision's `chosen_option` names exactly one live option, or, for a decision recorded without options, the statement names what was chosen |
| **Decision** | A person or group with authority settles a question: they choose an option, commit money, time or people, or start, stop or change a course of action. The owner's own decisions are stored; other people's are facts or external references | (a) an identifiable decider with authority over what is committed; (b) the source states a settled choice, not only a proposal; (c) it commits resources or changes a course of action; (d) an owner statement, a quote, or an AI-session quote of the owner's own words supports (a)–(c). A candidate that fails (b) is a fork |
| **Registration bar** | What enters the register: choices whose consequences last over a month, commit significant money or time, or are costly to undo. Smaller choices may be recorded at light depth | The record states its reversibility, and its depth matches the activation rule of §4.2 |
| **Basis** | Everything the decision rested on when it became active: kind, decider, depth, reversibility, question, statement, chosen option, options, grounds, context with known, unknowns and what would help, assumptions with thresholds and probabilities, success criterion, expected outcome, confidence, planned stake, what is not done because of it, the decided date and the first review date. Sealed per edition | The seal of every edition verifies (§4.3). A basis field of an active decision changes only through revise, correction or completion |
| **Ground** | A fact known at decision time on which the decision rests (phase `ground`) | Its event time is not later than the decided date (or is unknown). It has an evidence reference or is marked "no source" and counted. Retellings of the same news count once |
| **Unknown** | Something the decider knew they did not know at decision time | It is stored in the basis. A full-depth decision has at least one |
| **Success criterion** | What will count as the decision having worked, separate from any date | Someone who was not there could judge it true or false from a named kind of evidence. "By 1 December" alone is not a criterion |
| **Assumption** | A statement about the world that must stay true for the decision to keep making sense. It carries a metric; a threshold (comparator, value, unit, by-date, or a text fallback); a judge-from date; a data source kind; a check frequency; criticality; and optional scope, check cost, class tag and owner probability | It has a threshold and a data source kind. With kind `none` it is honestly UNVERIFIABLE, is never asked about by date and never counts as a forecast. A probability is present only if the owner stated it. A metric is optional: an assumption without one is allowed (at full depth it still needs a threshold, structured or text, and one with nothing to check it with is UNVERIFIABLE); this is softer than the predecessor's rule "no assumption without a metric" (proposed) |
| **Checkpoint** | An assumption with a structured threshold and a by-date: a binary claim a neutral reader could resolve from the named source on that date | Comparator, value and by-date are present. The first owner assessment observed on or after the by-date resolves it: HOLDING = yes, VIOLATED = no, UNKNOWN or UNVERIFIABLE = unclear |
| **Reading** | A measured value of an assumption's metric, with its unit, source and a state that code proposes from the threshold | It never changes a state; only an owner assessment that accepts it does. Before the judge-from date, or with mismatched units, it proposes nothing |
| **Check** (assessment) | The owner's judgement of an assumption at a time: HOLDING, DRIFTING, VIOLATED, UNVERIFIABLE (nothing to check with) or UNKNOWN (can't judge this time). It carries evidence, a note, the due date it answered and the next date it set | It is an appended row. Two identical "still holding" checks are two rows. The derived "last checked" equals the latest non-voided assessment. A model-proposed or app-proposed state is not a check until an owner action in an owner channel approves it |
| **Postponement** | A move of one assumption's next check date with a reason, without a judgement | It is a check-log row of kind `postponement`. It never answers a due date. There is **no postponement of a review** |
| **Fact** | A dated statement of what happened or what was known, phase `ground` or `monitoring`, possibly bearing on several assumptions of the same decision. Kinds: observation, action, statement, context change, outcome report, external decision | It has text, an event time or "unknown", and an evidence reference or "no source". It never changes an assumption state by itself |
| **Monitoring** | Everything recorded about a decision after it became active: monitoring facts, readings, checks, reviews and attachment activity | Each item's knowledge time is after the first seal, or the item is marked reconstructed |
| **Review** | The owner's verdict on the whole decision at a time, with an action, its trigger, the state before it and the attached execution summary | Keep, adjust and revise carry a next review date in the future, in every channel. Close carries an outcome resolution and a learning. Supersede names its successor. Revise names a trigger fact, a change of mind or a correction |
| Keep | The decision stands as it is | A next review date is set; nothing in the basis changes |
| Adjust | The execution terms change and the decision stands | A next review date is set; nothing in the basis changes; the new terms enter as monitoring facts; **no new edition** |
| Revise | The choice itself, or its basis, changes for the same question | Edition E-(n+1) is sealed; E-n stays unchanged and still verifies; the public id stays. A correction is a revise flagged `is_correction` and does not count as a revision in metrics |
| Supersede | Another decision replaces this one | The successor exists and is not this decision; a `supersedes` link is stored on the successor; this decision becomes terminal |
| Cancel | The decision is dropped before an outcome | A reason is recorded. A learning is asked for but not required |
| Close | The decision is finished and its result is known well enough to judge | An outcome resolution with a basis and a learning are recorded |
| **Edition** | An immutable sealed snapshot of a decision's basis: E-01 at activation or import, then one per revise, correction, completion or change in the source. Referenced as `D-0042_E-02` | Its stored seal recomputes at any later time to `ok` or `ok_with_erasures` |
| **Completion** | Filling a basis field or adding a basis item that a reconstructed (imported) record never had | Allowed only on reconstructed records and only for empty fields or new items. The next review, or an explicit `complete_decision`, seals an edition with reason `completion` |
| **Commitment** | Who owes what to whom by when, by what success criterion, with the source it came from. It executes a decision, or says "no decision" on purpose | Debtor, creditor, object and a due date (or "no date") are set. Either `decision_ref` is set, or `no_decision_reason` is, or the entry-time link answer is `unanswered` or `not_offered`. It settles no fork. Only owner-confirmed `done`, with an actual time or "unknown", counts as done |
| **Action** and **task link** | A step actually performed (a commitment done, a task done, a meeting held), at its event time. A task executes a decision through the task's own `decision_ref` | Its done time is the actual time or explicitly unknown, never the time of a bulk mark. A title that merely mentions a decision number is not a link |
| **Outcome report** | Someone (the owner, a counterpart, an app, an agent) says the decision is done or has a result | It is a monitoring fact of kind `outcome_report`, with its source. It never closes the decision |
| **Outcome resolution** | The owner's act that fixes the outcome: success, failure, mixed or unknown. Its basis is `resolved` (measured from cited checks, readings or evidenced facts), `reported` (only from reports or owner statements) or `not_confirmed` | `unknown` comes only with `not_confirmed`. Only `resolved` shows green. Imported resolutions are marked reconstructed and never enter a score. No system text claims causality from a before/after comparison |
| **Learning** | What was confirmed, what was refuted, the limits of the conclusion, the next step, and the answer to "would you take the same decision knowing what you know today?" | It references the decision, the edition it learns from and the outcome, if any. Later decisions of the same kind, the same `about` or `serves` target, or with an assumption of the same class are shown it, and may cite it (`informed_by`) |
| **Forecast** | A checkpoint with an owner probability recorded before its by-date. Separate forecast records, model probabilities and scoring are research after the forecast pilot's report [Later, DEC-10] | The probability was stated by the owner and recorded before the by-date and before any bearing evidence was known |
| **Non-decision** | A candidate that fails test (a), (b) or (c) of "decision": advice given, advice received, a task or plan, an opinion or description, a procedural act, an intention, a vague agreement, an unsupported claim, or a routine step | It is stored as a fact, a commitment proposal or a fork, or it is dropped; never as a decision. A rejected candidate keeps its class and is never proposed again |
| **Retold decision** | A decision made earlier and told now | If it is the owner's own and registered, it attaches as a fact, and a disagreement with the current edition is flagged. If it is the owner's own and unregistered, it becomes a proposal marked retroactive. If it is someone else's, it becomes a fact about them or an external reference |
| **Routine** | A recurring action carried out under an existing decision or standing rule | No fork exists at that moment. It is a task or commitment linked to the decision that set it up, or answered "none: routine". A weekly recurrence never yields one decision per occurrence |
| **Occasion** | An offline event the owner attends with a purpose known upfront, modelled as a decision of kind `attendance` that owns the window, venue, time zone and role [Later 3] | The attendance decision has a window and at most three expected results with numbers. Sessions, people met and commitments inside the window attach to it |
| **Proposal** | A record the system, an agent or an app inferred and the owner has not approved: a new decision or a fact on an existing one in the slice; checks, reviews, learnings and links later | Nothing it describes is written until an owner action in an owner channel (the CLI now, a bot card from stage 2) approves it. An MCP call can never approve |
| **Mirror** | A read-only copy of a record whose authority is another system: v1 for its decisions during the shadow period (`mirror_scope = full`), or the project's public decision log for the text of its entries (`mirror_scope = basis_only`) | Every command that would change a field the authority owns is refused, with the authority named. Only that authority's importer changes such a field |
| **External decision reference** | A pointer to a decision that lives in another system, such as a team's or a client's, refreshed by pull [Later 6] | It holds the system, external id, title, health, review date and audience only, never the basis, facts or third-party words |
| **Hub link** | A typed reference between a decision and another record, stored by the module whose workflow forces it | Its kind is in the closed registry of §3.10, which names its owner and its enforcement point |

### 2.3 Kind, decider, depth (proposed, D-047)

| Field | Values | Meaning | Default |
|---|---|---|---|
| `kind` | `choice` | An ordinary decision: choose, commit, start, stop, change | `choice` |
| | `test` | A decision to test an approach (a hypothesis). Its assumptions are the validation criteria, and it links `tests` → the goal or decision it informs | — |
| | `pursue` | A decision to pursue a goal. The goal is the frame; the decision holds the why, the stake and the review | — |
| | `attendance` | A decision to attend an occasion with a known purpose [Later 3 for the occasion fields] | — |
| | `advisee` | A decision the owner recorded about a client's own choice while advising. Allowed **only for mirrors**; natively such a record is a fact or an external reference | — |
| | `forecast_container` | An imported decision whose assumptions are sealed predictions about someone else's outcome. Allowed **only for mirrors**; excluded from the owner's own decision metrics | — |
| `decider` | `self` | The owner, resolved from the owner profile (CFG-1), **never by a name lookup** | `self` |
| | `joint` | The owner and a counterpart settled it together; `decider_ref` names the counterpart | — |
| | `other` | Someone else decided. Allowed only for mirrors of kind `advisee` or `forecast_container` | — |
| `depth` | `light` | Cheap and reversible: a statement, a decided date and a review date suffice | computed (§4.2) |
| | `full` | Costly or hard to undo: question, options, an unknown, a success criterion, assumptions with thresholds and a review date | computed; **always `full` for imports** |
| `reversibility` | `cheap`, `costly`, `irreversible`, `unknown` | The owner's estimate of the cost of undoing | `unknown` |

A kind is a shape, not a module. `test` replaces a separate hypothesis entity, so one measure lives in one
assumption (WRK-4). `pursue` connects goals to decisions without moving goals into DEC. `attendance`
replaces a separate event entity in R1. The number of aggregates stays at one. Imported `advisee` records
stay in the waiting list exactly as in v1, and the `goal_changed` question asks about them once, when
their engagement's goal ends.

---

## 3. Data model

### 3.1 Conventions

- **Storage.** One SQLite file with one writer (OPS-3), `STRICT` tables, numbered forward-only migrations
  (OPS-4). Foreign keys are used only inside a module. A cross-module reference is a public-id string or an
  `<ISSUER>_<id>` string, never a foreign key.
- **Types.**
  - Instants: `TEXT`, UTC ISO 8601 with milliseconds and `Z`, for example `2026-11-15T09:30:00.000Z`.
    Imported instants are normalised to this form (`YYYY-MM-DDTHH:MM:SS.sssZ`) at import. Code compares
    instants as parsed datetimes, never as text.
  - Local dates: `TEXT` `YYYY-MM-DD` in the owner's IANA zone (CFG-1). "Today" is always computed in the
    owner's zone, never the host's.
  - Months: `YYYY-MM`.
  - **Decimals are `TEXT`** matching `^-?\d+(\.\d+)?$`. No float column exists in the decision core
    (CFJ-1, §4.3); code compares values as `Decimal`.
  - Booleans: `INTEGER CHECK (x IN (0,1))`.
  - JSON: `TEXT` holding CFJ-1 canonical JSON.
- **Transaction time is stamped by the store, never by the caller.** Every unit of work writes one row in
  `sys_tx_log` (§3.3). Every DEC and CMT row carries `tx` (that row's id) and `recorded_at` (the same
  unit's `committed_at`). STO fills both at insert time; a command that passes either is refused (a
  programming error, tested). `sys_tx_log` is the single place where actor, channel, owner-channel flag,
  approval reference, instance role and code version live (D-049).
- **Origin time for imported rows.** `origin_recorded_at` is when the source system first recorded the row;
  `import_ref` is `<ISSUER>_<source id>`. The **knowledge time** of a row is
  `K(row) = origin_recorded_at if set, else recorded_at`. `as_of` filters on K by default (§4.15).
- **Event time** on every row that describes something that happened is a triple: `<x>_at` (an instant, a
  date, a month, or NULL for unknown), `<x>_precision` (`instant`, `day`, `month`, `unknown`) and
  `<x>_basis`, one of:
  - `live`: the event is the recording itself, for example a check the owner makes now;
  - `stated`: the owner said when;
  - `source_time`: the timestamp of the cited message or segment;
  - `conversation_date`: the date of the conversation it came from;
  - `record_date`: assumed equal to the record time, which is weak;
  - `import`: taken from the source system;
  - `unknown`.

  Every `*_precision` and `*_basis` column carries a `CHECK` over these vocabularies; the listings below
  omit those checks for brevity. **An event time is never defaulted silently to a record time.** Only
  owner-channel commands that state "now" use `live`; imports with no event time store NULL and `unknown`.
  An event time more than one day in the future is refused (`EVENT_TIME_IN_FUTURE`).
- **Append-only by declaration.** `sys_table_registry` declares per table `append_only` (0/1), the
  `set_once_cols` (allowed to change from NULL to a value exactly once), the `erasable_cols` (allowed to be
  blanked by POL's erasure unit, which also sets `erased_tx`) and the `mutable_cols` of a head table. STO
  generates `BEFORE UPDATE` and `BEFORE DELETE` triggers from these declarations at migration time.
  Corrections are new rows that point at the corrected row; undo sets a set-once `voided_at`. Mutable head
  tables (decisions, forks, the scheduling columns of assumptions, proposals' status, commitments) change
  only through commands, and those commands write a version row in the same unit of work.
- **Optimistic concurrency.** Mutable heads carry `version INTEGER`. Commands accept `expected_version` and
  return `Conflict(current_version)` on a mismatch.
- **Data classes** (PRV-1). Every DEC and CMT table is `work`, except `dec_stakes` (`financial`) and the
  import bookkeeping tables of §3.6 (`system`). No DEC table accepts journal-class input: `EvidenceResolver`
  refuses a journal-class source, and STO refuses a unit of work whose inputs are journal-tainted (§3.11).

**Configuration keys** (CFG, per instance; no owner literal in code; every value proposed):

| Key | Default | Used by |
|---|---|---|
| `owner.timezone`, `owner.locale`, `owner.currency` | from `coflow init` | every "today", the date tables, money display |
| `ids.issuer` | set at init (examples use `CF`) | outward references |
| `ids.foreign_issuers` | `V1` (predecessor), `CF2LOG` (the project's decision log) | importers |
| `dec.drift_margin` | `0.15` | `proposed_state_from_reading` |
| `dec.unverifiable_share_limit` | `0.5` | the ground axis, the `bet` badge |
| `dec.no_data_days` | `30` | the timeliness axis |
| `dec.retroactive_days` | `3` | the retroactive flag |
| `dec.full_depth_review_days` | `30` | `proposed_depth` |
| `dec.full_depth_money_threshold` | unset (money never forces full depth) | `proposed_depth` |
| `dec.review_step_days` | `30` | the suggested next date on "keep" and "adjust" |
| `dec.review_max_days` | `730` | the range of next review and next check dates |
| `dec.postpone_max_days` | `90` | `postpone_check` |
| `dec.undo_window_hours` | `24` | undo handlers |
| `dec.drafts_stale_days` | `7` | the "drafts to finish" list |
| `dec.related_learnings_max` | `5` | resurfacing |
| `dec.history_window_days` | `14` | `decision_history` |
| `dec.entry_offers_max` | `3` | `likely_for_entry` (the "up to three" of D-048) |
| `dec.recent_activity_days` | `14` | `likely_for_entry`, the unlinked report |
| `dec.match_overlap_min` | `0.5` | proposal match candidates |
| `dec.class_tags` | demand, payment, timeline, people, technical, cost, other | assumption classes |
| `dec.proposal_switch_off` | `0.2` over the last `30` decided proposals | proposals per origin |
| `dec.import_unit_max_rows` | `5000` | import unit sizing (§10.5) |
| `dec.shadow_clean_runs` | `14` | the adoption gate |
| `dec.case_snapshot_max_age_days` | `7` | the adoption gate |
| `dec.adoption_not_before` | `2026-12-01` | the adoption gate |
| `dec.adoption_override_ref` | unset; a D-entry reference when the owner records another date | the adoption gate |

### 3.2 Identity: prefixes, widths, scoped codes, aliases, issuers

Canonical form follows the identity protocol: each parameter is `prefix-counter` with a fixed-width
counter; a hyphen joins the parts of one parameter, an underscore separates parameters, and there is no
colon anywhere. The entity type is a stored field, never inferred from the id's shape (IDN-2, IDN-9).

| Prefix | Entity | Width | Example | Issued by | Notes |
|---|---|---|---|---|---|
| `D` | decision | 4 | `D-0042` | IDS tap, inside DEC's unit of work | **Accepted (D-045):** v1 numbers are kept (`D907` → `D-0907`); natives start at `D-1001`. While v1 is the system of record, natives come from the block starting at 1001; a v1 number at or above the block start is refused at import (`IMPORT_SOURCE_CONFLICT`) |
| `Q` | fork | 4 (proposed) | `Q-0007` | IDS tap | **Accepted:** `Q` numbers forks |
| `F` | commitment | 5 (proposed) | `F-00042`, `F-10001` | IDS tap, inside CMT's unit of work | **Accepted:** `F` numbers commitments, new ones from `F-10001`. v1 promise numbers are kept when CMT mirrors them (stage 1) |
| `_A-` (scoped) | assumption | 2 | `D-0042_A-03` | DEC, per-decision counter | v1 code `A3` → `A-03` |
| `_O-` (scoped) | option | 2 | `D-0042_O-02`, `Q-0007_O-01` | DEC | |
| `_E-` (scoped) | edition | 2 | `D-0042_E-02` | DEC | the first edition is `E-01` |
| `_R-` (scoped) | review | 2 | `D-0042_R-04` | DEC | |
| `_L-` (scoped) | learning | 2 | `D-0042_L-01` | DEC | citable through `informed_by` |
| `_FT-` (scoped) | fact | 3 | `D-0042_FT-007` | DEC | |
| `_CK-`, `_RD-` (scoped) | check, reading | 3 | `D-0042_A-03_CK-002`, `D-0042_A-03_RD-001` | DEC, per-assumption counter | |
| `_S-` (scoped) | stake | 2 | `D-0042_S-01` | DEC | |
| other | person, company, direction, goal, task, meeting, session | — | — | their modules (stage 1) | registered now so nothing collides, not issued by the slice; v1 forms appear only as foreign refs (`V1_G901`) |

- **Scoped counters** live on the parent row (`a_seq`, `o_seq`, `r_seq`, `l_seq`, `ft_seq`, `s_seq` on the
  decision, `o_seq` on the fork, `ck_seq`, `rd_seq` on the assumption). They only increase, so a code is
  never reused, even after an undo, and a unique index on (parent, `code_n`) in every scoped table enforces
  it. Editions use `current_edition + 1`.
- **Input is tolerant, output is canonical.** `D907`, `d907`, `D 907`, `d-907`, `D0907`, `D-0907` and the
  locale's look-alike letters resolve to `D-0907`. `D907 A2`, `D907_A2`, `D907/A2` and `D-0907_A02`
  resolve to `D-0907_A-02`. Free text in arguments is never parsed for ids; only fields declared as
  references are. The one function is `normalise_ref(s)`:
  1. NFKC, then casefold;
  2. map look-alike letters through the locale pack's explicit table (CFG-3); I1 ships a fixture locale
     pack with the map `д`, `Д` → `d` and `а`, `А` → `a`, so a typed `Д18` resolves (the letters are
     the ones owners type for D and A, not true homoglyphs);
  3. treat space, `-`, `_` and `/` as separators;
  4. parse with the grammar `PREFIX DIGITS (SEP SCOPED_PREFIX DIGITS)*`, where the prefixes are the
     registered ones (§3.3, `sys_id_prefixes`), longest first;
  5. strip leading zeros from each number, check it against the prefix's width, and render the canonical
     form (`D-0907_A-02`).
  A string the grammar does not accept is `NotFound`, never a guess. `sys_id_aliases.alias_norm` stores
  `normalise_ref(alias)` for registered aliases (`V1_D907` is parsed with the issuer prefix `V1_` first).
- **Issuers.** The instance's own issuer code is set at `coflow init` and never changes. The foreign issuers
  of the slice are `V1` (the predecessor system) and `CF2LOG` (the project's public decision log). A
  cross-system reference is `<ISSUER>_<canonical id>`, for example `V1_D907` or `CF2LOG_D-037`. Foreign ids
  are stored as received and never re-issued.
- **Event envelopes.** The CloudEvents `source` keeps its URI (`coflow://<instance>/<mod>`), which the
  envelope requires; `subject`, `sourceref` and every stored reference use plain public ids or
  `<ISSUER>_<id>`. Stored actor values use the colon-free forms `mcp_<client>` and `app_<client>`.
- **The registry is fixed before the first number is issued** (IDN-2): the migration seeds
  `sys_id_prefixes` with `D` (width 4, block start 1001), `Q` (width 4), `F` (width 5, block start 10001),
  the scoped codes and the reserved letters of the later modules.

### 3.3 Kernel tables written by the slice

| Module | Table | Columns (essentials) | Notes |
|---|---|---|---|
| STO | `sys_meta` | `key PK`, `value` | schema and code revision |
| STO | `sys_migrations` | `file PK`, `module`, `checksum`, `applied_at` | numbered, forward-only (OPS-4) |
| STO | `sys_table_registry` | `table_name PK`, `module`, `data_class`, `append_only`, `set_once_cols`, `erasable_cols`, `mutable_cols` | the authorizer and the trigger generator read it; from stage 1 also the text columns that may hold `untrusted_external` text (PRV-14) |
| STO | `sys_tx_log` | `tx PK`, `committed_at`, `actor`, `channel` (`cli`, `mcp`, `bot`, `app`, `import`, `system`), `owner_channel` (0/1), `interaction_id`, `approval_ref`, `instance_role`, `code_version`, `command` | one row per unit of work; append-only |
| IDS | `sys_id_prefixes` | `prefix PK`, `entity`, `width`, `owner_module`, `block_start NULL`, `scoped_under NULL`, `description` | the registry (IDN-2) |
| IDS | `sys_id_sequence` | `prefix PK`, `next_n` | the tap (IDN-1), issued inside the caller's unit |
| IDS | `sys_id_burned` | `prefix`, `n`, `reason` (`rollback`, `undo`, `deleted_in_source`, `numbering_gap`), `issuer NULL`, `tx`; PK (`prefix`, `n`) | never issued again |
| IDS | `sys_id_foreign` | `prefix`, `n`, `issuer`, `source_id`, `tx`; PK (`prefix`, `n`) | numbers taken by another issuing space (v1); never issued |
| IDS | `sys_id_aliases` | `alias_norm PK`, `canonical`, `issuer`, `kind` (`legacy`, `rename`, `merge`, `foreign`), `tx` | `V1_D907 → D-0907`, `CF2LOG_D-037 → D-1004` |
| EVT | `sys_events`, `sys_event_deliveries` | as ARCHITECTURE §6.2 | written in the same unit of work |
| EVT | `sys_command_keys` | `key PK`, `command`, `result_json`, `tx` | idempotency: a retry with the same key returns the first result |
| OPS | `sys_instance` | `instance_id`, `role` (`dev`, `validation`, `drill` in the slice; `staging`, `production` later), `volume_id`, `created_at` | the role is shown in every answer (DEP-2) |
| CFG | `cfg_profile`, `cfg_settings` | owner display name, IANA zone, locale, currency; `key`, `value`, `tx` | `decider = self` resolves here |
| OBS | `sys_usage_signals` | `signal`, `day`, `channel`, `value` (TEXT decimal), `detail_json`; PK (`signal`, `day`, `channel`) | loop metrics and pulls (§12.3) |
| MCP | `mcp_clients`, `mcp_call_log` | `client PK`, `token_hash`, `scopes` (`read`, `write`), `financial` (0/1), `created_at`, `revoked_at`; `at`, `client`, `tool`, `args_hash`, `result_kind`, `interaction_id` | provenance of every MCP call |
| ADM | `adm_tokens` | `token_hash PK`, `scope` (`admin`, `import`), `created_at`, `revoked_at` | the CLI's loopback admin API |

The tap issues the next number of a prefix inside the caller's unit of work: it skips every number in
`sys_id_foreign` and `sys_id_burned` for that prefix and, while a block start is set, every number below
it. A rolled-back unit burns the number it drew (`rollback`).

### 3.4 DEC tables

Common columns, not repeated below:
- every table: `tx INTEGER NOT NULL`, `recorded_at TEXT NOT NULL` (stamped by STO);
- importable tables, marked **[O]**: `origin_recorded_at TEXT NULL`, `import_ref TEXT NULL`;
- tables with erasable columns, marked **[E]**: `erased_tx INTEGER NULL`.

"AO" = append-only; "SO(x)" = column x is set-once. A **salt** column holds 16 random bytes as hex,
generated at insert and erased with the content it protects (§4.3). The listing is grouped by meaning; the
migration creates the tables in dependency order (decisions, forks, options, assumptions, readings,
checks, facts, then the rest).

```sql
-- 1. The decision head. Mutable through commands only; every change versioned in dec_versions. [O][E]
CREATE TABLE dec_decisions (
  id                   INTEGER PRIMARY KEY,
  public_id            TEXT NOT NULL UNIQUE,              -- D-0042
  number               INTEGER NOT NULL UNIQUE,
  title                TEXT NOT NULL,                     -- naming layer, not basis; renames add aliases
  question             TEXT,
  statement            TEXT,                              -- a refusal to act is allowed
  chosen_option        INTEGER,                           -- code_n of the chosen live option; basis
  kind                 TEXT NOT NULL DEFAULT 'choice' CHECK (kind IN
                         ('choice','test','pursue','attendance','advisee','forecast_container')),
  decider              TEXT NOT NULL DEFAULT 'self' CHECK (decider IN ('self','joint','other')),
  decider_basis        TEXT NOT NULL DEFAULT 'stated' CHECK (decider_basis IN ('stated','mapped','assumed')),
  decider_ref          TEXT,
  depth                TEXT NOT NULL DEFAULT 'light' CHECK (depth IN ('light','full')),
  depth_basis          TEXT NOT NULL DEFAULT 'computed' CHECK (depth_basis IN ('computed','owner','import')),
  reversibility        TEXT NOT NULL DEFAULT 'unknown' CHECK (reversibility IN ('cheap','costly','irreversible','unknown')),
  status               TEXT NOT NULL DEFAULT 'draft' CHECK (status IN
                         ('draft','active','closed','cancelled','superseded','withdrawn')),
  manual_flag          TEXT CHECK (manual_flag IN ('ZOMBIE','OFF_TRACK')),
  manual_flag_reason   TEXT,
  context TEXT, known TEXT, would_help TEXT,             -- erasable
  unknowns_json        TEXT NOT NULL DEFAULT '[]',        -- JSON array of strings
  success_criterion    TEXT,
  expected_metric TEXT, expected_target TEXT, expected_unit TEXT, expected_by TEXT, expected_text TEXT,
  confidence           INTEGER CHECK (confidence BETWEEN 0 AND 100),   -- owner-stated only
  not_doing            TEXT,                              -- what is not done because of this decision
  review_due           TEXT,                              -- next review date; NULL when terminal
  review_due_initial   TEXT,                              -- first review date; part of the basis
  decided_at           TEXT,
  decided_precision    TEXT NOT NULL DEFAULT 'unknown',
  decided_basis        TEXT,                              -- NULL = not given yet; 'unknown' = stated unknown
  activated_at TEXT, closed_at TEXT,
  current_edition      INTEGER NOT NULL DEFAULT 0,        -- 0 = never sealed
  completion_pending   INTEGER NOT NULL DEFAULT 0 CHECK (completion_pending IN (0,1)),
  origin_kind          TEXT NOT NULL DEFAULT 'not_recorded' CHECK (origin_kind IN
                         ('owner_note','cli','bot','meeting','session','chat','agent_session','occasion',
                          'app','proposal','fork','import','not_recorded')),
  origin_ref           TEXT,                              -- where it was born (a meeting, session, proposal, fork)
  origin_quote         TEXT,                              -- the owner's words or the source quote; erasable
  publishability       TEXT NOT NULL DEFAULT 'private' CHECK (publishability IN
                         ('private','publishable_abstracted','public')),
  third_party_sensitive INTEGER NOT NULL DEFAULT 0 CHECK (third_party_sensitive IN (0,1)),
  reconstructed        INTEGER NOT NULL DEFAULT 0 CHECK (reconstructed IN (0,1)),
  mirror_of            TEXT,                              -- V1_D907 | CF2LOG_D-037 | NULL (native or adopted)
  mirror_scope         TEXT CHECK (mirror_scope IN ('full','basis_only')),
  notes                TEXT,                              -- erasable
  legacy_json          TEXT,                              -- unmapped source fields, verbatim
  a_seq INTEGER NOT NULL DEFAULT 0, o_seq INTEGER NOT NULL DEFAULT 0, r_seq INTEGER NOT NULL DEFAULT 0,
  l_seq INTEGER NOT NULL DEFAULT 0, ft_seq INTEGER NOT NULL DEFAULT 0, s_seq INTEGER NOT NULL DEFAULT 0,
  version              INTEGER NOT NULL DEFAULT 1,
  CHECK (status <> 'active' OR review_due IS NOT NULL OR mirror_of IS NOT NULL OR reconstructed = 1),
  CHECK (third_party_sensitive = 0 OR publishability = 'private'),
  CHECK (decider = 'self' OR decider_ref IS NOT NULL OR mirror_of IS NOT NULL OR reconstructed = 1),
  CHECK (decider <> 'other' OR kind IN ('advisee','forecast_container')),
  CHECK ((mirror_of IS NULL) = (mirror_scope IS NULL))
);
-- Computed, never stored: retroactive = date(K(d)) - decided_date(d) > dec.retroactive_days.

-- 2. Sealed editions. AO. POL's erasure unit may blank keys of fields_json and field_salts_json and append
--    to erased_fields_json; field_hashes_json, items_json and seal_hash never change. [E]
CREATE TABLE dec_editions (
  decision_id       INTEGER NOT NULL REFERENCES dec_decisions(id),
  n                 INTEGER NOT NULL,                     -- E-01, E-02, ...
  reason            TEXT NOT NULL CHECK (reason IN
                      ('activation','revise','correction','completion','import','source_changed')),
  fields_json       TEXT NOT NULL,                        -- CFJ-1 object: basis field -> value (inline)
  field_salts_json  TEXT NOT NULL,                        -- CFJ-1 object: basis field -> salt
  field_hashes_json TEXT NOT NULL,                        -- CFJ-1 object: basis field -> unit_hash(salt, value)
  items_json        TEXT NOT NULL,                        -- CFJ-1 array of [kind, code, item_hash], sorted
  seal_hash         TEXT NOT NULL,                        -- sha256 over the envelope (§4.3)
  canon_version     INTEGER NOT NULL DEFAULT 1,           -- CFJ-1
  sealed_at         TEXT NOT NULL,
  sealed_by         TEXT NOT NULL,                        -- the actor of the unit
  review_id         INTEGER,                              -- the review that cut it (revise, correction, completion)
  reason_text       TEXT,
  unverifiable_at_seal TEXT,                              -- decimal share at the seal
  reconstructed     INTEGER NOT NULL DEFAULT 0,
  erased_fields_json TEXT NOT NULL DEFAULT '[]',
  PRIMARY KEY (decision_id, n)
);

-- 3. Options of a decision or of a fork. AO; SO(why_rejected, recorded_before_choice, added_in_edition,
--    voided_at, voided_reason). [O][E]
CREATE TABLE dec_options (
  id INTEGER PRIMARY KEY,
  decision_id INTEGER REFERENCES dec_decisions(id),
  fork_id     INTEGER REFERENCES dec_forks(id),
  code_n      INTEGER NOT NULL,                           -- O-01 within its parent
  text        TEXT NOT NULL,                              -- erasable
  why_rejected TEXT,
  recorded_before_choice TEXT CHECK (recorded_before_choice IN ('yes','no','unknown')),
  added_in_edition INTEGER,
  copied_from INTEGER REFERENCES dec_options(id),         -- the fork option this decision option came from
  origin      TEXT NOT NULL DEFAULT 'owner' CHECK (origin IN ('owner','agent','import','app')),
  salt        TEXT NOT NULL,
  voided_at TEXT, voided_reason TEXT,
  CHECK ((decision_id IS NULL) <> (fork_id IS NULL))
);
CREATE UNIQUE INDEX dec_options_code_d ON dec_options(decision_id, code_n) WHERE decision_id IS NOT NULL;
CREATE UNIQUE INDEX dec_options_code_f ON dec_options(fork_id, code_n) WHERE fork_id IS NOT NULL;
-- Live options = options with voided_at IS NULL. A decision's chosen_option must name a live option of it
-- (command rule, tested). why_rejected and recorded_before_choice may be set only while the option is not yet
-- sealed (added_in_edition IS NULL): sealed content never changes (§4.3).

-- 4. Forks (open questions). Mutable head, versioned.
CREATE TABLE dec_forks (
  id INTEGER PRIMARY KEY,
  public_id   TEXT NOT NULL UNIQUE,                       -- Q-0007
  number      INTEGER NOT NULL UNIQUE,
  question    TEXT NOT NULL,
  trigger_text TEXT, trigger_ref TEXT,
  opened_at TEXT, opened_precision TEXT NOT NULL, opened_basis TEXT NOT NULL,
  decider TEXT NOT NULL DEFAULT 'self' CHECK (decider IN ('self','joint','other')), decider_ref TEXT,
  deadline    TEXT,                                       -- local date
  status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','decided','dissolved','delegated','withdrawn')),
  outcome_not_heard INTEGER NOT NULL DEFAULT 0 CHECK (outcome_not_heard IN (0,1)),
  decision_id INTEGER REFERENCES dec_decisions(id),       -- set when decided
  closed_at TEXT, close_reason TEXT, delegated_to_ref TEXT,
  o_seq INTEGER NOT NULL DEFAULT 0,
  version INTEGER NOT NULL DEFAULT 1
);

-- 5. Assumptions. Basis columns, position and legacy_json are immutable after insert (trigger); a change
--    is a successor row. Mutable columns: next_check_at, status, superseded_by, drop_reason, ck_seq,
--    rd_seq, version; SO(added_in_edition, probability_recorded_at). [O][E]
CREATE TABLE dec_assumptions (
  id INTEGER PRIMARY KEY,
  decision_id      INTEGER NOT NULL REFERENCES dec_decisions(id),
  code_n           INTEGER NOT NULL,                      -- A-03
  position         INTEGER NOT NULL,
  statement        TEXT NOT NULL,                         -- erasable
  metric           TEXT,
  comparator       TEXT CHECK (comparator IN ('>=','<=','>','<','=','!=','between')),
  threshold_value  TEXT,                                  -- decimal string
  threshold_value2 TEXT,                                  -- upper bound for 'between'
  unit             TEXT,                                  -- currency codes for money; never summed across units
  threshold_text   TEXT,                                  -- text fallback; every imported threshold starts here
  by_date          TEXT,                                  -- the date by which the threshold must hold
  judge_from       TEXT,                                  -- readings before this date propose nothing (§4.5)
  drift_margin     TEXT,                                  -- decimal fraction; NULL = dec.drift_margin
  data_source_kind TEXT NOT NULL CHECK (data_source_kind IN ('manual','internal_query','external_system','none')),
  data_source_text TEXT,
  data_source_ref  TEXT,                                  -- a stored query or app metric [Later 3]
  check_frequency  TEXT CHECK (check_frequency IN ('weekly','monthly','quarterly','ad_hoc')),
  next_check_at    TEXT,                                  -- explicit next date (mutable, versioned)
  is_critical      INTEGER NOT NULL DEFAULT 1 CHECK (is_critical IN (0,1)),
  scope            TEXT,                                  -- the unit checked separately for behaviour assumptions
  check_cost       TEXT CHECK (check_cost IN ('minutes','hours','day_plus','unknown')),
  class_tag        TEXT,                                  -- from dec.class_tags; drives learning resurfacing
  probability      INTEGER CHECK (probability BETWEEN 0 AND 100),
  probability_by   TEXT CHECK (probability_by IN ('owner','import')),  -- a model never fills it
  probability_recorded_at TEXT,
  shareable        INTEGER NOT NULL DEFAULT 0 CHECK (shareable IN (0,1)),   -- may appear in a team projection [Later 6]
  status           TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','superseded','dropped')),
  superseded_by    INTEGER REFERENCES dec_assumptions(id),
  drop_reason      TEXT,
  added_in_edition INTEGER,                               -- NULL = added after the last seal
  legacy_json      TEXT,                                  -- unmapped source fields (v1 notes), verbatim; set at insert
  ck_seq INTEGER NOT NULL DEFAULT 0, rd_seq INTEGER NOT NULL DEFAULT 0,
  salt             TEXT NOT NULL,
  version          INTEGER NOT NULL DEFAULT 1,
  UNIQUE (decision_id, code_n),
  CHECK (probability IS NULL OR probability_by IS NOT NULL),
  CHECK (comparator IS NULL OR threshold_value IS NOT NULL),
  CHECK (comparator <> 'between' OR threshold_value2 IS NOT NULL)
);
-- There is no stored state column. The effective state is computed (§4.4).

-- 6. The check log: owner assessments and postponements. AO; SO(voided_at, voided_reason). [O][E]
CREATE TABLE dec_checks (
  id INTEGER PRIMARY KEY,
  assumption_id INTEGER NOT NULL REFERENCES dec_assumptions(id),
  decision_id   INTEGER NOT NULL REFERENCES dec_decisions(id),
  code_n        INTEGER NOT NULL,                         -- CK-002
  kind          TEXT NOT NULL CHECK (kind IN ('assessment','postponement')),
  state         TEXT CHECK (state IN ('HOLDING','DRIFTING','VIOLATED','UNVERIFIABLE','UNKNOWN')),
  reading_id    INTEGER REFERENCES dec_readings(id),      -- the reading this assessment accepted
  observed_value TEXT, observed_text TEXT,
  observed_at TEXT, observed_precision TEXT NOT NULL, observed_basis TEXT NOT NULL,
  due_answered  TEXT,                                     -- assumption_due at recording time
  due_source_answered TEXT CHECK (due_source_answered IN ('explicit','by_date','text','review')),
  next_check_set TEXT,                                    -- the next date this row set (NULL = cleared)
  next_check_rule TEXT NOT NULL CHECK (next_check_rule IN
                    ('explicit','frequency','ad_hoc_clear','kept','dropped','none','postpone','import')),
  evidence_kind TEXT, evidence_ref TEXT, evidence_quote TEXT,   -- the quote is erasable
  quote_verified INTEGER CHECK (quote_verified IN (0,1)),
  note          TEXT,                                     -- erasable
  proposed_by   TEXT NOT NULL DEFAULT 'owner' CHECK (proposed_by IN ('owner','model','rule','app','import')),
  reconstructed INTEGER NOT NULL DEFAULT 0,
  voided_at TEXT, voided_reason TEXT,
  UNIQUE (assumption_id, code_n),
  CHECK ((kind = 'assessment') = (state IS NOT NULL)),
  CHECK (kind <> 'postponement' OR next_check_set IS NOT NULL)
);
-- A proposed_by other than 'owner' or 'import' requires the unit's tx to carry an approval_ref from an owner
-- channel (command rule, tested). In the slice only 'owner' and 'import' occur.

-- 7. Readings: measured values that propose a state. AO; SO(accepted_by_check_id, voided_at, voided_reason). [O]
CREATE TABLE dec_readings (
  id INTEGER PRIMARY KEY,
  assumption_id INTEGER NOT NULL REFERENCES dec_assumptions(id),
  decision_id   INTEGER NOT NULL REFERENCES dec_decisions(id),
  code_n        INTEGER NOT NULL,                         -- RD-001
  value TEXT, unit TEXT, value_text TEXT,                 -- decimal string or text
  observed_at TEXT, observed_precision TEXT NOT NULL, observed_basis TEXT NOT NULL,
  source_kind   TEXT NOT NULL CHECK (source_kind IN ('owner_statement','internal_query','app','document','import')),
  source_ref TEXT, quote TEXT,
  proposed_state TEXT CHECK (proposed_state IN ('HOLDING','DRIFTING','VIOLATED')),  -- by code at insert
  no_proposal_reason TEXT CHECK (no_proposal_reason IN ('text_threshold','before_judge_from','unit_mismatch','no_value')),
  proposed_by   TEXT NOT NULL CHECK (proposed_by IN ('owner','rule','app','import')),
  accepted_by_check_id INTEGER,
  voided_at TEXT, voided_reason TEXT,
  UNIQUE (assumption_id, code_n),
  CHECK ((proposed_state IS NULL) <> (no_proposal_reason IS NULL))
);

-- 8. Facts: grounds and monitoring, including outcome reports. AO; SO(added_in_edition, voided_at,
--    voided_reason). [O][E]
CREATE TABLE dec_facts (
  id INTEGER PRIMARY KEY,
  decision_id   INTEGER NOT NULL REFERENCES dec_decisions(id),
  code_n        INTEGER NOT NULL,                         -- FT-007
  phase         TEXT NOT NULL CHECK (phase IN ('ground','monitoring')),
  kind          TEXT NOT NULL DEFAULT 'observation' CHECK (kind IN
                  ('observation','action','statement','context_change','outcome_report','external_decision')),
  claimed_outcome TEXT CHECK (claimed_outcome IN ('success','failure','mixed','done','not_done')),
  text          TEXT NOT NULL,                            -- erasable
  occurred_at TEXT, occurred_precision TEXT NOT NULL, occurred_basis TEXT NOT NULL,
  evidence_kind TEXT NOT NULL CHECK (evidence_kind IN ('segment','message','session','document',
                  'owner_statement','agent_session','app_envelope','foreign','none')),
  evidence_ref TEXT, evidence_quote TEXT,                 -- the quote is erasable
  quote_verified INTEGER CHECK (quote_verified IN (0,1)),
  source_text   TEXT,                                     -- legacy free text (imports)
  reported_by   TEXT NOT NULL DEFAULT 'owner' CHECK (reported_by IN ('owner','counterpart','app','agent','import')),
  added_in_edition INTEGER,                               -- grounds sealed into an edition
  corrects_fact_id INTEGER REFERENCES dec_facts(id),
  salt          TEXT NOT NULL,
  reconstructed INTEGER NOT NULL DEFAULT 0,
  voided_at TEXT, voided_reason TEXT,
  UNIQUE (decision_id, code_n),
  CHECK ((kind = 'outcome_report') = (claimed_outcome IS NOT NULL))
);

-- 9. A fact may bear on several assumptions of the same decision (command rule + test). AO.
CREATE TABLE dec_fact_assumptions (
  fact_id       INTEGER NOT NULL REFERENCES dec_facts(id),
  assumption_id INTEGER NOT NULL REFERENCES dec_assumptions(id),
  bearing       TEXT NOT NULL DEFAULT 'bears_on' CHECK (bearing IN ('bears_on','supports','contradicts')),
  PRIMARY KEY (fact_id, assumption_id)
);

-- 10. Reviews. AO; SO(unverifiable_after, edition_after, voided_at, voided_reason). [O][E]
CREATE TABLE dec_reviews (
  id INTEGER PRIMARY KEY,
  decision_id   INTEGER NOT NULL REFERENCES dec_decisions(id),
  code_n        INTEGER NOT NULL,                         -- R-04
  action        TEXT NOT NULL CHECK (action IN ('keep','adjust','revise','close','cancel','supersede')),
  verdict TEXT, notes TEXT,                               -- erasable
  revise_basis  TEXT CHECK (revise_basis IN ('trigger_fact','change_of_mind','correction')),
  trigger       TEXT NOT NULL DEFAULT 'owner_initiative' CHECK (trigger IN ('scheduled','violated_assumption',
                  'outside_fact','non_occurrence','goal_change','fork','owner_initiative','import')),
  trigger_ref TEXT, trigger_at TEXT,                      -- for latency
  occurred_at TEXT, occurred_precision TEXT NOT NULL, occurred_basis TEXT NOT NULL,
  next_review_due TEXT,
  status_before TEXT, review_due_before TEXT, edition_before INTEGER, edition_after INTEGER,
  health_before TEXT, ground_before TEXT, timeliness_before TEXT,
  unverifiable_before TEXT, unverifiable_after TEXT,      -- decimal shares
  reasons_answered_json TEXT,                             -- the waiting reasons shown when it was asked
  execution_summary_json TEXT,                            -- frozen probe counts and ids only
  successor_ref TEXT,
  is_correction INTEGER NOT NULL DEFAULT 0 CHECK (is_correction IN (0,1)),
  legacy_health_at_review TEXT,                           -- the v1 label at the review, for the shadow report
  reconstructed INTEGER NOT NULL DEFAULT 0,
  voided_at TEXT, voided_reason TEXT,
  UNIQUE (decision_id, code_n),
  CHECK (action <> 'revise' OR revise_basis IS NOT NULL OR reconstructed = 1),
  CHECK (is_correction = 0 OR (action = 'revise' AND revise_basis = 'correction'))
);

-- 11. Outcome resolutions (reports are facts of kind outcome_report). AO; SO(voided_at, voided_reason). [O]
CREATE TABLE dec_outcomes (
  id INTEGER PRIMARY KEY,
  decision_id   INTEGER NOT NULL REFERENCES dec_decisions(id),
  review_id     INTEGER REFERENCES dec_reviews(id),
  kind          TEXT NOT NULL CHECK (kind IN ('success','failure','mixed','unknown')),
  basis         TEXT NOT NULL CHECK (basis IN ('resolved','reported','not_confirmed')),
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',          -- cited checks, readings, facts of this decision
  owner_statement TEXT,                                   -- the owner's own report, when basis is reported
  measured_value TEXT, expected_vs_actual TEXT,
  occurred_at TEXT, occurred_precision TEXT NOT NULL, occurred_basis TEXT NOT NULL,
  resolved_by   TEXT NOT NULL CHECK (resolved_by IN ('owner','import')),
  supersedes_outcome_id INTEGER REFERENCES dec_outcomes(id),
  reconstructed INTEGER NOT NULL DEFAULT 0,
  voided_at TEXT, voided_reason TEXT,
  CHECK (kind <> 'unknown' OR basis = 'not_confirmed'),
  CHECK (resolved_by <> 'import' OR reconstructed = 1)
);

-- 12. Learnings. AO; SO(voided_at, voided_reason). [O][E]
CREATE TABLE dec_learnings (
  id INTEGER PRIMARY KEY,
  decision_id INTEGER NOT NULL REFERENCES dec_decisions(id),
  code_n      INTEGER NOT NULL,                           -- L-01
  edition     INTEGER NOT NULL,                           -- the edition it learns from (0 for imports)
  review_id   INTEGER REFERENCES dec_reviews(id),
  outcome_id  INTEGER REFERENCES dec_outcomes(id),
  confirmed TEXT, refuted TEXT, limits TEXT, next_step TEXT,   -- erasable
  same_again  TEXT CHECK (same_again IN ('yes','no','unsure')),
  legacy_text TEXT,                                       -- v1 free text, verbatim
  salt        TEXT NOT NULL,
  reconstructed INTEGER NOT NULL DEFAULT 0,
  voided_at TEXT, voided_reason TEXT,
  UNIQUE (decision_id, code_n),
  CHECK (coalesce(confirmed,'') <> '' OR coalesce(refuted,'') <> '' OR coalesce(legacy_text,'') <> '')
);

-- 13. Structured stake. AO; SO(added_in_edition, voided_at, voided_reason); data class FINANCIAL. [O]
CREATE TABLE dec_stakes (
  id INTEGER PRIMARY KEY,
  decision_id INTEGER NOT NULL REFERENCES dec_decisions(id),
  code_n      INTEGER NOT NULL,                           -- S-01, from the decision's s_seq
  type        TEXT NOT NULL CHECK (type IN ('money','hours','attention')),
  amount      TEXT,                                       -- decimal string
  currency    TEXT,                                       -- ISO 4217
  period      TEXT CHECK (period IN ('once','week','month','quarter','year')),
  count_periods INTEGER,
  direction   TEXT CHECK (direction IN ('cost','income','at_risk')),
  note TEXT,
  planned     INTEGER NOT NULL DEFAULT 1 CHECK (planned IN (0,1)),   -- the planned stake is basis; actuals come from probes [Later]
  added_in_edition INTEGER,
  salt        TEXT NOT NULL,
  voided_at TEXT, voided_reason TEXT,
  UNIQUE (decision_id, code_n),
  CHECK (type <> 'money' OR currency IS NOT NULL)
);

-- 14. DEC-owned links (§3.10). AO; SO(removed_tx, removed_reason). [O]
CREATE TABLE dec_links (
  id INTEGER PRIMARY KEY,
  decision_id INTEGER NOT NULL REFERENCES dec_decisions(id),
  role        TEXT NOT NULL CHECK (role IN ('follows','supersedes','depends_on','part_of','contradicts',
                'tests','serves','about','informed_by','foreign_attachment')),
  target_ref  TEXT NOT NULL,                              -- public id or <ISSUER>_<id>
  target_kind TEXT NOT NULL CHECK (target_kind IN ('decision','learning','goal','direction','person','company',
                'foreign_task','foreign_goal','foreign_topic','foreign_session')),
  resolution  TEXT NOT NULL CHECK (resolution IN ('resolved','foreign','pending','dangling')),
  note TEXT,
  removed_tx INTEGER, removed_reason TEXT
);
CREATE UNIQUE INDEX dec_links_live ON dec_links(decision_id, role, target_ref) WHERE removed_tx IS NULL;

-- 15. Context of mirrored foreign records (goals, tasks, topics, sessions, people, companies).
--     Mutable, work class (it holds people's and companies' names and titles); written only by importers.
--     foreign_ref is the <ISSUER>_<id> form ('V1_G901'), the same string dec_links.target_ref holds.
CREATE TABLE dec_foreign_context (
  issuer TEXT NOT NULL, kind TEXT NOT NULL, foreign_ref TEXT NOT NULL,
  title TEXT, status TEXT,
  status_changed_at TEXT, status_changed_precision TEXT NOT NULL DEFAULT 'unknown',
  first_seen_status_run_id INTEGER,                       -- the run that first saw the current status
  last_run_id INTEGER,
  PRIMARY KEY (issuer, kind, foreign_ref)
);

-- 16. Proposals: inferred, not approved. Mutable status; payload immutable.
CREATE TABLE dec_proposals (
  id INTEGER PRIMARY KEY,
  type        TEXT NOT NULL CHECK (type IN ('decision_new','fact')),    -- Later 2-3: check, review, learning, link
  decision_id INTEGER REFERENCES dec_decisions(id),       -- the target of a 'fact'
  title       TEXT NOT NULL,                              -- for lists: the payload's title or first line
  payload_json TEXT NOT NULL,
  payload_hash TEXT NOT NULL,                             -- sha256(cfj(normalised payload))
  origin_kind TEXT NOT NULL, origin_ref TEXT, origin_quote TEXT,
  proposed_by TEXT NOT NULL,                              -- mcp_<client> | app_<client> | rule_<id>
  match_candidates_json TEXT NOT NULL DEFAULT '[]',       -- deterministic candidates (§4.12)
  status      TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','approved','rejected','withdrawn','expired')),
  decided_tx INTEGER, reject_class TEXT, reject_reason TEXT, result_ref TEXT,
  version     INTEGER NOT NULL DEFAULT 1
  -- Later 3 (extraction): class, extracted_outcome, decided_by_ref, recounted_by_ref,
  -- made_in_this_conversation, prompt_version, input_hash
);
CREATE UNIQUE INDEX dec_proposals_never_again ON dec_proposals(type, coalesce(decision_id,0), payload_hash)
  WHERE status = 'rejected';

-- 17. Field history of mutable heads. AO. [O]
CREATE TABLE dec_versions (
  id INTEGER PRIMARY KEY,
  entity     TEXT NOT NULL CHECK (entity IN ('decision','assumption','fork','link','proposal')),
  entity_id  INTEGER NOT NULL,
  field      TEXT NOT NULL,
  old_value  TEXT, new_value TEXT,
  reason     TEXT,
  cause_kind TEXT NOT NULL CHECK (cause_kind IN ('command','review','check','import','undo','adoption')),
  cause_ref  TEXT,
  reconstructed INTEGER NOT NULL DEFAULT 0
);
```

A proposal is shown as `proposal <id>` (for example "proposal 12"); proposals are not numbered by the tap.

### 3.5 CMT tables [I3]

```sql
-- Commitments. Mutable head, versioned in cmt_history. [O][E]
CREATE TABLE cmt_commitments (
  id INTEGER PRIMARY KEY,
  public_id   TEXT NOT NULL UNIQUE,                       -- F-10001
  number      INTEGER NOT NULL UNIQUE,
  debtor_ref  TEXT NOT NULL,                              -- 'self' or a person or company ref (foreign allowed before PPL)
  creditor_ref TEXT NOT NULL,
  initiator_ref TEXT,                                     -- who initiated it: 'self', a person or company ref; NULL = unknown (REL-6)
  what        TEXT NOT NULL,                              -- erasable
  success_criterion TEXT,
  due_date    TEXT,                                       -- NULL = "no date" stated
  due_basis   TEXT NOT NULL CHECK (due_basis IN ('stated','inferred','none')),
  status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','suggested_done','done','dropped','unclear','withdrawn')),
  done_at TEXT, done_precision TEXT, done_basis TEXT CHECK (done_basis IN ('stated','live','unknown')),
  decision_ref TEXT,
  no_decision_reason TEXT CHECK (no_decision_reason IN ('routine','personal','admin','not_yet_decided','other')),
  link_answer TEXT NOT NULL CHECK (link_answer IN ('linked','explicit_none','unanswered','not_offered')),
  goal_ref    TEXT,                                       -- frame only
  source_ref TEXT, source_quote TEXT,                     -- the quote is erasable
  origin      TEXT NOT NULL CHECK (origin IN ('cli','mcp','bot','meeting_outcome','app','import')),
  external_ref TEXT,                                      -- a team tool's id [Later 6]
  version     INTEGER NOT NULL DEFAULT 1,
  CHECK ((link_answer = 'linked') = (decision_ref IS NOT NULL)),
  CHECK (link_answer <> 'explicit_none' OR no_decision_reason IS NOT NULL),
  CHECK (status <> 'done' OR done_basis IS NOT NULL),
  CHECK (status <> 'suggested_done' OR origin IN ('meeting_outcome','app'))   -- only from a proposal [Later 3]
);

-- History of every change. AO. [O]
CREATE TABLE cmt_history (
  id INTEGER PRIMARY KEY,
  commitment_id INTEGER NOT NULL REFERENCES cmt_commitments(id),
  field     TEXT NOT NULL CHECK (field IN ('status','due_date','decision_ref','link_answer','no_decision_reason',
                                           'what','debtor_ref','creditor_ref')),
  old_value TEXT, new_value TEXT,
  reason    TEXT,                                         -- required for a due shift, 'dropped' and 'unclear'
  occurred_at TEXT, occurred_precision TEXT NOT NULL, occurred_basis TEXT NOT NULL
);
```

A due-date shift is a history row, so a decision's review sees "shifted" through the probe without CMT
copying anything into DEC. `withdrawn` is the status an undo of a create leaves; the row and the number
stay.

### 3.6 Import, shadow and case bookkeeping (system class)

```sql
CREATE TABLE dec_import_runs (
  id INTEGER PRIMARY KEY,
  source_issuer TEXT NOT NULL,                            -- 'V1' | 'CF2LOG'
  format TEXT, format_version INTEGER,                    -- NULL only on a refused run that could not read them
  synthetic INTEGER CHECK (synthetic IN (0,1)),           -- the snapshot's own flag
  file_hash TEXT NOT NULL,                                -- sha256 hex of the file's bytes
  exported_at TEXT, as_of TEXT, as_of_date TEXT,
  mode   TEXT NOT NULL CHECK (mode IN ('shadow','final','dry_run')),
  status TEXT NOT NULL CHECK (status IN ('applied','noop','partial','refused','failed')),
  counts_json TEXT NOT NULL DEFAULT '{}',                 -- per entity: seen, new, changed, unchanged, absent
  v2_output_json TEXT,                                    -- what v2 computed for as_of_date: waiting, health, due,
                                                          -- with algorithm_version and input_hash (a record, not a cache);
                                                          -- ids, codes, kinds, labels, dates and shares only (§3.11)
  report_status TEXT NOT NULL DEFAULT 'pending' CHECK (report_status IN ('pending','written','blocked')),
  error TEXT,                                             -- the exception class and the failing row key only
  CHECK (status = 'refused' OR (format IS NOT NULL AND format_version IS NOT NULL AND synthetic IS NOT NULL))
);                                                        -- a dry run writes no row
CREATE UNIQUE INDEX dec_import_runs_once ON dec_import_runs(file_hash, mode)
  WHERE status IN ('applied','partial','failed');
-- A repeated file writes a run row with status 'noop'; a refusal after the file was read writes 'refused'.
CREATE TABLE dec_mirror_state (
  issuer TEXT NOT NULL,
  source_kind TEXT NOT NULL CHECK (source_kind IN ('decision','assumption','fact','review','link','version',
                'check_version','check_snapshot')),
  source_id TEXT NOT NULL,                                -- the source's id (v1_id; for links kind:ref)
  local_table TEXT NOT NULL, local_id INTEGER NOT NULL,   -- the current local row (a successor after a change)
  content_hash TEXT NOT NULL,                             -- sha256(cfj(the source object without its nested arrays))
  first_run_id INTEGER NOT NULL, last_run_id INTEGER NOT NULL,
  absent_since_run_id INTEGER,                            -- deleted in the source: a tombstone, never a delete
  adopted_at TEXT,
  PRIMARY KEY (issuer, source_kind, source_id)
);
CREATE TABLE dec_shadow_items (
  run_id INTEGER NOT NULL, decision_ref TEXT NOT NULL,
  aspect TEXT NOT NULL CHECK (aspect IN ('health','waiting_membership','waiting_reasons','due','order','count','basis_drift')),
  subject_ref TEXT,                                       -- an assumption or the decision
  v1_value TEXT, v2_value TEXT,                           -- ids, codes, kinds, labels, dates and shares only;
                                                          -- reasons as {kind, code, date, source}, never text
  classification TEXT NOT NULL CHECK (classification IN ('same','expected','unexpected','finding')),
  rule_id TEXT                                            -- SR-n for 'expected'
);
CREATE TABLE dec_cases (                                  -- the owner's named real cases (D-036)
  case_id TEXT PRIMARY KEY,                               -- the owner's label, for example RC-1
  title TEXT NOT NULL, script_hash TEXT NOT NULL,
  last_result TEXT CHECK (last_result IN ('pass','fail')), last_run_at TEXT,
  source_run_id INTEGER,                                  -- the snapshot run it ran against
  report_json TEXT
);
```

`dec_import_runs` and `dec_mirror_state` are append-and-update system tables written only by importers;
`dec_shadow_items` is append-only. They are system class, so they never hold titles, statements, names
or reason text: `v1_value`, `v2_value` and `v2_output_json` store ids, codes, kinds, labels, dates and
shares, with reasons as `{kind, code, date, source}`, and `error` stores only the exception class and the
failing row key. The v1 label's own reason strings are not stored. `dec_cases` holds the owner's case
labels and results only. The case scripts live in the validation data root, never in any repository.

### 3.7 Tables specified now and built later

- `dec_occasions` **[Later 3]**: `decision_id PK` (kind `attendance`), `window_start`, `window_end`, `tz`
  (IANA), `venue_text`, `role` (`visitor`, `exhibitor`, `speaker`, `organiser`, `other`), `criteria_json`
  (who to look for, worth following up, skip, next-step menu, questions), `external_ref`, `brief_version`.
- `dec_external_decisions` **[Later 6]**: `id`, `system`, `external_id`, `title`, `status`, `health`,
  `review_due`, `audience`, `refreshed_at`, `source_hash`; UNIQUE (`system`, `external_id`) (DEC-23).
- `dec_questions_asked` **[Later 2]**: the asked log behind DEC-7's N-day rule and the intervention
  metrics (`subject_ref`, `reason_kind`, `asked_at`, `channel`, `message_ref`, `answered_at`,
  `result_refs_json`).
- `dec_forecasts`, `dec_forecast_resolutions` **[Later, after the forecast pilot's report]**: separate
  forecast records with owner and sealed model probabilities and their scoring (DEC-10).

### 3.8 Two times on everything that happened (proposed, D-049)

| Record | Event time | Knowledge time | Basis, flags |
|---|---|---|---|
| Decision | `decided_at` (+ precision, basis) | `K = origin_recorded_at ?? recorded_at` | `retroactive` computed; `reconstructed` for imports and back-fills |
| Fork | `opened_at` | K | `outcome_not_heard` |
| Option | — (its record time is what matters) | K | `recorded_before_choice` set once at the choice |
| Fact | `occurred_at` | K | `occurred_basis`; "added after seal" for grounds without `added_in_edition` |
| Check | `observed_at` | K | `observed_basis`; `reconstructed` for checks rebuilt from snapshots |
| Reading | `observed_at` | K | `proposed_by` |
| Review | `occurred_at` | K | `trigger_at` for latency |
| Outcome | `occurred_at` | K | `basis`, `resolved_by` |
| Commitment | `done_at` | K of the history row | `done_basis`; never the time of a bulk mark |
| Any mutable field | — | the K of its `dec_versions` row | `as_of` replays versions and editions |

### 3.9 What is immutable

| Record | Rule | Allowed afterwards |
|---|---|---|
| Edition | never updated or deleted, except erasure of declared fields | a new edition |
| Basis fields of an active decision (including `chosen_option`) | refused by `update_decision` (`SEALED_USE_REVISE`) | revise (or correction); completion for reconstructed records (empty fields only) |
| Assumption basis columns | immutable after insert | `supersede_assumption` creates a successor that keeps its own checks; the old one keeps its checks |
| Check, reading, fact, review, outcome, learning, stake, option, link | append-only | a correcting row; a set-once `voided_at` or `removed_tx`; erasure of declared text columns |
| Option recorded before the choice | text frozen; `recorded_before_choice` set once at the choice | new options, flagged `no` |
| Public ids, scoped codes, aliases | never reused, never changed | renames add aliases |
| Mirrored fields | changed only by their authority's importer | adoption ends the mirror |
| `sys_tx_log`, commitment history, versions | append-only | — |

### 3.10 The hub link registry: every link kind, its owner, its enforcement point (proposed, D-042)

The registry is closed: typed links only, no universal link. The rule that assigns an owner: **a link is
stored by the module whose workflow forces it to be filled**, written in that module's own unit of work at
its enforcement point. No workflow needs two units of work to link what it creates (DEC-11).

| Link kind | From → to | Stored by | Enforcement point | Card. | Stage |
|---|---|---|---|---|---|
| `follows` | decision → earlier decision on the same question or subject | DEC `dec_links` | `create_decision` returns `follows_candidates` when a subject or kind matches | n:1 | I2 |
| `supersedes` | successor → replaced decision | DEC | review action `supersede` (required) | 1:1 | I2 |
| `depends_on` | decision → decision whose outcome it needs | DEC | `create_decision`, `link` | n:n | I2 |
| `part_of` | decision → umbrella decision (a cluster under one gate) | DEC | `create_decision`, `link` (cycles refused) | n:1 | I2 |
| `contradicts` | decision → decision | DEC | owner `link`; later the contradiction detector proposes it | n:n | I2 (manual) |
| `tests` | `test` decision → goal or decision it informs | DEC | `activate_decision` requires it for kind `test` | n:1 | I2 |
| `serves` | decision → goal or direction | DEC | `create_decision` offers likely goals through `GoalDirectory`; "no goal" allowed | n:n | I1 (foreign), I2 |
| `about` | decision → person or company | DEC | `create_decision`; naming a person sets `third_party_sensitive` by default | n:n | I1 (foreign), I2 |
| `informed_by` | decision → learning (`D-0907_L-01`) | DEC | `create_decision` and `activate_decision` return `related_learnings`; the owner links | n:n | I2 |
| `foreign_attachment` | decision → a v1 task, topic or session (v1 goal links become `serves` with `foreign_goal`) | DEC (import) | the v1 importer | n:n | I1 |
| ground and monitoring evidence | fact → segment, message, session, document, app envelope, owner statement | DEC `dec_facts.evidence_*` | `add_fact`, grounds on `create_decision` (through `EvidenceResolver`) | n:1 | I2 (built-ins), 1 (SIG) |
| check and reading evidence | check or reading → evidence | DEC | `record_check`, `record_reading` | n:1 | I2 |
| origin ("decided in") | decision → meeting, session, chat, AI session, occasion, proposal, fork | DEC `origin_ref` | `create_decision`, `approve_proposal`, `decide_fork` | 1:1 | I2 |
| `executes` (commitment) | commitment → decision | CMT `cmt_commitments.decision_ref` | `create_commitment` (offer at entry; `link_answer` required) | n:1 | I3 |
| `executes` (task) | task → decision | WRK `wrk_tasks.decision_ref` | `create_task` (WRK-3, WRK-8) | n:1 | 1 |
| `prepares` / `reviews` | meeting → decision | MTG `mtg_meeting_decisions` | `plan_meeting` (a decision is a valid link to work, MTG-1) | n:n | 5 |
| `cites` | decision → centre item | DEC | `link` (GOL-13) | n:n | 3 |
| `stake_actual` | ledger entry → decision | FIN `fin_entries.decision_ref` | `post_entry` | n:1 | 8.1a |
| `hours` | time span → decision | RHY `rhy_activity_spans.decision_ref` | span rule or the owner | n:1 | 6 |
| `pursued_by` | goal → `pursue` decision | WRK, then GOL | goal activation offers "record the decision to pursue it?" | 1:1 | 1 |
| attendance window | occasion → `attendance` decision | DEC `dec_occasions` | `create_decision` of kind `attendance` | 1:1 | 3 |
| `about_external` | decision → external decision reference | DEC | owner `link`, or a team-tool pull proposing it | n:n | 6 |
| delegated | commitment → team-tool item | CMT `external_ref` | the team-tool pull | 1:1 | 6 |

Rejected alternatives: **every decision link in one DEC table** (entry-time linking would need two units
of work, because a command may not call another module's command inside its unit, and a failure between
them leaves an unlinked record nobody notices); **a kernel link ledger** (atomic, but it re-creates the
generic link graph the project dropped and moves domain meaning into the kernel).

### 3.11 Data classes and where they are enforced

| Data | Class | Rule |
|---|---|---|
| `dec_*`, `cmt_*` rows, including `dec_foreign_context` | work | third-party names may appear in text; held under PRV-1 |
| `dec_stakes` | financial | leaves the instance only where a destination's financial flag allows it (an MCP client token with `financial = 1`) |
| `dec_import_runs`, `dec_mirror_state`, `dec_shadow_items`, `dec_cases` | system | ids, codes, kinds, labels, dates and shares only, never titles, statements, names or reason text (§3.6); reports stay in the validation data root; never copied into an agent's memory index |
| `sys_events` for DEC and CMT | envelope only | ids and changed field names, never values (schema test, canary) |
| Journal | — | no DEC or CMT command accepts journal-class input; `evidence_kind` has no journal value; `EvidenceResolver` refuses a journal-class ref (`JOURNAL_CLASS_INPUT`) |
| Publishability (PRV-10) | a column, not a class | `private` by default; `third_party_sensitive = 1` forces `private`; `public` only from an owner channel; public projections draw only from `public` decisions or the owner's abstracted text |
| Text written by other people [Later 1] | sub-class `untrusted_external` (PRV-14) | the text columns that may hold it (`dec_facts.text`, every `*_quote`, `source_text`, `origin_quote`, `cmt_commitments.what` when it came from a source) are declared in the table registry when PRV-14 lands; such text is never an instruction, and cloud AI clients do not receive it by default (MCP-5) |

The mark `third_party_sensitive` may be set at any time. It may be cleared only while the decision is a
draft and only in an owner channel; once active it stays (PRV-10).

---

## 4. State machines and computed values

Every computed value is a **pure function** of the rows visible at `T` (§4.15), of `T.date` and of the
configuration version. Nothing computed is stored as a cache. Snapshots taken at a review
(`dec_reviews.*_before`) and the per-run record of what v2 said (`dec_import_runs.v2_output_json`) are
records, never read back as current answers.

Refusals use the typed errors of ARCHITECTURE §6.1, `Refused(code, detail, missing[] | allowed[])`, with
the codes catalogued in §7.1.

### 4.1 Decision lifecycle

```
                    activate (missing_for_activation() == []; seals E-01)
   draft ─────────────────────────────────────────────────────────▶ active ◀──┐ keep | adjust (next date)
     │  │ cancel (reason)                                            │  │  │  │ revise | correction (next date;
     │  └──────────────▶ cancelled ◀──── cancel (reason) ────────────┘  │  │ ─┘   seals E-(n+1))
     │                      │                                           │  └──── supersede (successor) ──▶ superseded
     │ undo of create       └── close (outcome + learning) ──▶ closed ◀─┴─────── close (outcome + learning)
     ▼   (no later writes)                                     │  ▲
  withdrawn                                                    └──┘ close again: a new resolution supersedes the old
```

| From | Command or review action | Requires | Effect |
|---|---|---|---|
| — | `create_decision` | a title; `activate = false` by default | `draft`; number issued; `related_learnings` and `follows_candidates` returned |
| `draft` | `update_decision` | — | any field except mirror-owned ones; versioned |
| `draft` | `add_option(chosen = true)` or `activate_decision(chosen_option)` | the option is live and belongs to this decision | `chosen_option` set (versioned) |
| `draft` | `activate_decision` | `missing_for_activation(d) == []` | `active`; every live option gets `recorded_before_choice = 'yes'` where unset; E-01 sealed (reason `activation`); `activated_at` |
| `draft` | review `cancel` | a reason | `cancelled` |
| `draft` | undo of `create_decision` | no later writes, inside the undo window | `withdrawn`; the number stays taken |
| `active` | `update_decision` | non-basis fields only (`title`, `notes`) | versioned; a basis field (including `chosen_option`) → `SEALED_USE_REVISE`; `review_due` → `USE_A_REVIEW` |
| `active` | `set_manual_flag` | a reason | `ZOMBIE`, `OFF_TRACK` or cleared |
| `active` | review `keep` / `adjust` | `T.date < next_review_due ≤ T.date + dec.review_max_days` | `review_due := next`; basis untouched; **no new edition** |
| `active` | review `revise` | the next date as above; a revision touching at least one basis field or item; `revise_basis` = `trigger_fact` (an existing, non-voided fact of this decision), `change_of_mind` (with a reason in the verdict or notes) or `correction` | E-(n+1) sealed (reason `revise`, or `correction` when `is_correction`) |
| `active` | review `close` | an outcome resolution (§4.11) and a learning with `confirmed` or `refuted` | `closed`; `review_due := NULL`; `closed_at` |
| `active` | review `cancel` | a reason | `cancelled`; `review_due := NULL`; a learning is asked for, not required |
| `active` | review `supersede` | the successor exists, is not this decision, and is `draft`, `active` or `closed` | `superseded`; a `supersedes` link stored on the successor |
| `cancelled` | review `close` | as for close | `closed` (the "cancelled, then it turned out" path) |
| `closed` | review `close` | an outcome resolution; the learning is optional | a new resolution supersedes the previous one |
| any reconstructed | completion (§4.10) | the field is empty, or the item is new | `completion_pending := 1`; the next review, or `complete_decision`, seals E-(n+1) with reason `completion` |
| terminal | `keep`, `adjust`, `revise`, `cancel`, `supersede` | — | `TERMINAL_DECISION`, with `allowed = ['close']` for cancelled and closed decisions, `[]` otherwise |
| mirror, scope `full` | every command | — | `MIRRORED` ("mirrored from V1; V1 is the system of record until adoption"); only the importer writes |
| mirror, scope `basis_only` | commands touching log-owned fields | — | `MIRRORED`; the other fields are owned by v2 (§10.1) |

There is **no "postpone the review" action**. Postponing exists only for one assumption's check (§4.6).
**Accepted (D-043):** a revision keeps the number and seals a new edition, with a reason; a genuinely
different decision is a new decision that supersedes the old one.

### 4.2 Activation, depth, missing fields

```python
def proposed_depth(d):                               # computed; the owner may override (depth_basis = 'owner')
    if d.mirror_of or d.reconstructed: return 'full'  # imports are always full
    if d.reversibility in ('costly', 'irreversible'): return 'full'
    money = once_equivalent(planned_stakes(d, 'money'), CFG.owner.currency)   # None when currencies differ
    if CFG.dec.full_depth_money_threshold is not None and money is not None \
       and money >= CFG.dec.full_depth_money_threshold: return 'full'
    if d.review_due and decided_date(d) and (d.review_due - decided_date(d)).days > CFG.dec.full_depth_review_days:
        return 'full'
    return 'light'

def missing_for_activation(d, T):
    m = []
    if not d.title: m.append('title')
    if not (d.statement or d.chosen_option): m.append('statement')
    if not d.review_due or d.review_due <= T.date: m.append('review_due')          # a future date
    if d.decided_at is None and d.decided_basis != 'unknown': m.append('decided_at')  # a date, or an explicit "unknown"
    if d.kind == 'test' and not live_links(d, ('tests',)): m.append('tests_link')
    if d.kind == 'attendance' and not occasion(d): m.append('occasion_window')     # Later 3
    if d.depth == 'full':
        if not d.question: m.append('question')
        if len(live_options(d)) < 2: m.append('options')        # the chosen one plus one other; "do nothing" counts
        if not d.unknowns: m.append('unknown')
        if not d.success_criterion: m.append('success_criterion')
        if not active_assumptions(d): m.append('assumption')
        for a in active_assumptions(d):
            if a.comparator is None and not a.threshold_text: m.append(f'{a.code}.threshold')
    return m

ADVISORY = ['expected', 'stake', 'confidence', 'ground', 'reversibility', 'not_doing']   # listed on the card, never blocking
```

- `decided_at` is given as a date (`stated`, precision `day`), as "today" (`live`), or as the literal
  `unknown`, which stores `decided_at = NULL`, precision `unknown` and basis `unknown`. A decision created
  without it keeps `decided_basis = NULL` ("not given") and cannot be activated until one of the three is
  given.
- `depth` starts as `proposed_depth(d)` and is recomputed on every draft update until the owner sets it
  (`depth_basis = 'owner'`).
- `create_decision(..., activate=true)` runs the same rules and returns `Refused('ACTIVATION_GATE',
  missing=[…])` without writing anything.
- Native records of kind `advisee` or `forecast_container`, or with `decider = other`, are refused
  (`NATIVE_OTHER_DECIDER`, "record it as a fact about them, or later as an external reference") (DEC-4).

### 4.3 Canonical form (CFJ-1), the seal, integrity, erasure

**Accepted (D-043):** the basis is sealed by a hash when the decision is activated. **Proposed:** the
form below.

```python
import json, unicodedata, hashlib, secrets
from decimal import Decimal
from datetime import date, datetime

def normalise(x):
    if isinstance(x, str): return unicodedata.normalize('NFC', x)
    if isinstance(x, bool) or x is None or isinstance(x, int): return x
    if isinstance(x, float): raise TypeError('CFJ-1 refuses floats; use Decimal strings or int')
    if isinstance(x, Decimal): return format(x, 'f')
    if isinstance(x, (date, datetime)): return x.isoformat()
    if isinstance(x, (list, tuple)): return [normalise(v) for v in x]
    if isinstance(x, dict): return {str(k): normalise(v) for k, v in x.items()}
    raise TypeError(type(x))

def cfj(obj) -> bytes:                               # CFJ-1
    return json.dumps(normalise(obj), sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')

def new_salt() -> str: return secrets.token_hex(16)
def unit_hash(salt: str, content) -> str:
    return hashlib.sha256(salt.encode('ascii') + cfj(content)).hexdigest()
```

For an object of string keys and integer values, `cfj` is byte-identical to the forecast pilot's
canonicalisation (`json.dumps(…, sort_keys=True, ensure_ascii=False, separators=(',', ':'))`), and
`unit_hash` has the pilot's `sha256(salt + canonical)` shape, so the pilot's seals verify with these
functions (AT-K8).

```python
BASIS_FIELDS = ['kind', 'decider', 'decider_ref', 'depth', 'reversibility', 'question', 'statement',
  'chosen_option', 'context', 'known', 'unknowns', 'would_help', 'success_criterion', 'expected_metric',
  'expected_target', 'expected_unit', 'expected_by', 'expected_text', 'confidence', 'not_doing',
  'review_due_initial', 'decided_at', 'decided_precision', 'decided_basis', 'reconstructed']

ITEM_FIELDS = {   # content of each basis item; every item row carries its own salt
  'option':     ('code', 'text', 'why_rejected', 'recorded_before_choice', 'origin'),
  'ground':     ('code', 'text', 'occurred_at', 'occurred_precision', 'occurred_basis',
                 'evidence_kind', 'evidence_ref', 'evidence_quote'),
  'assumption': ('code', 'statement', 'metric', 'comparator', 'threshold_value', 'threshold_value2', 'unit',
                 'threshold_text', 'by_date', 'judge_from', 'data_source_kind', 'data_source_text',
                 'check_frequency', 'is_critical', 'scope', 'class_tag', 'probability', 'probability_by'),
  'stake':      ('code', 'type', 'amount', 'currency', 'period', 'count_periods', 'direction', 'note'),
}

# row.code = the rendered scoped code without the decision prefix: 'O-01', 'FT-007', 'A-03', 'S-01'
# (from code_n and the prefix width of §3.2); it is part of the hashed content.

def item_content(kind, row):
    return {k: getattr(row, k) for k in ITEM_FIELDS[kind]}

def basis_items(d):   # what an edition seals: live options, non-voided grounds, active assumptions, live planned stakes
    return ([('option', o) for o in live_options(d)]
          + [('ground', f) for f in facts(d, phase='ground', voided=False)]
          + [('assumption', a) for a in active_assumptions(d)]
          + [('stake', s) for s in stakes(d, planned=True, voided=False)])

def seal(d, n, reason, review_id, ctx):
    fields = {k: basis_value(d, k) for k in BASIS_FIELDS}
    salts  = {k: new_salt() for k in BASIS_FIELDS}
    hashes = {k: unit_hash(salts[k], fields[k]) for k in BASIS_FIELDS}
    items  = sorted([kind, row.code, unit_hash(row.salt, item_content(kind, row))] for kind, row in basis_items(d))
    env = {'cv': 1, 'decision': d.public_id, 'edition': n, 'field_hashes': hashes, 'items': items,
           'sealed_at': ctx.now_iso, 'sealed_by': ctx.actor}
    insert_edition(decision_id=d.id, n=n, reason=reason, fields_json=cfj(fields), field_salts_json=cfj(salts),
                   field_hashes_json=cfj(hashes), items_json=cfj(items),
                   seal_hash=hashlib.sha256(cfj(env)).hexdigest(), sealed_at=env['sealed_at'], sealed_by=ctx.actor,
                   review_id=review_id, unverifiable_at_seal=share_text(d, ctx.now), reconstructed=d.reconstructed)
    for kind, row in basis_items(d): set_once(row, added_in_edition=n)        # only where NULL
    set_head(d, current_edition=n, completion_pending=0)
    publish('coflow.dec.edition.sealed', d, changed=['current_edition'])

def integrity(d):                                    # run on every full read of a decision card
    out = []
    for e in editions(d):
        env = {'cv': e.canon_version, 'decision': d.public_id, 'edition': e.n,
               'field_hashes': loads(e.field_hashes_json), 'items': loads(e.items_json),
               'sealed_at': e.sealed_at, 'sealed_by': e.sealed_by}
        if hashlib.sha256(cfj(env)).hexdigest() != e.seal_hash:
            out.append((e.n, 'changed', ['seal'])); continue
        bad, erased = [], 0
        fields, salts, hashes = loads(e.fields_json), loads(e.field_salts_json), loads(e.field_hashes_json)
        for k, h in hashes.items():
            if k in loads(e.erased_fields_json): erased += 1; continue
            if unit_hash(salts[k], fields[k]) != h: bad.append(k)
        for kind, code, h in loads(e.items_json):
            row = load_item(d, kind, code)           # voided rows are still loaded: voiding never breaks a seal
            if row.erased_tx: erased += 1; continue
            if unit_hash(row.salt, item_content(kind, row)) != h: bad.append(f'{kind} {code}')
        out.append((e.n, 'changed' if bad else ('ok_with_erasures' if erased else 'ok'), bad))
    if d.status == 'active' and d.current_edition > 0:
        cur = loads(current_edition(d).fields_json)
        drift = [k for k in BASIS_FIELDS if basis_value(d, k) != cur.get(k)]
        if drift: out.append(('live', 'drift', drift))          # changed outside revise: only by bypassing the api
    if d.completion_pending: out.append(('live', 'completion_pending', pending_completion_items(d)))
    return out          # the card shows the first 12 hex characters of each seal; 'changed' and 'drift' first
```

- **Sealed items never change content.** Assumptions, options, grounds and stakes added after the last
  seal have `added_in_edition IS NULL`; they appear on the card as "added after seal", are not drift, and
  enter the basis at the next edition. Once sealed, an item's hashed content is never updated: a revise
  that changes an option's text or reason, a ground or a stake voids the row and appends a successor
  (`copied_from` for options), and an assumption change is `supersede_assumption`. Voided rows keep their
  content, so older editions still verify.
- **Erasure.** POL's erasure unit, which arrives with PRV-7 in stage 0B or 1, blanks an item's content and
  its salt, or one inline field value and its salt, and records the erasure. The seal still verifies the
  rest (`ok_with_erasures`), and the erased text cannot be confirmed by guessing, because its salt is
  gone. The slice implements the hashing so erasure needs no migration later.
- The seal is **protection from oneself**: it makes a rewrite visible, not impossible. A
  `coflow.dec.integrity.mismatch` event is emitted at most once per edition and day.
- **Imported records are sealed at import** (E-01, reason `import`, `reconstructed = 1`) when they are
  active or terminal. A later snapshot whose basis differs seals E-(n+1) with reason `source_changed`, so
  the shadow period measures how often v1 records are rewritten after the fact (§10.6).

### 4.4 Assumption states

Stored, owner-approved, in `dec_checks.state`: `HOLDING`, `DRIFTING`, `VIOLATED`, `UNVERIFIABLE`
("nothing to check with"), `UNKNOWN` ("can't judge this time": a source exists but gave no answer).
Computed only: `NOT_YET_DUE`, `UNCHECKED`.

```python
def latest_assessment(a, T):          # non-voided, visible at T; ordered by assessment_order
    return last(sorted((c for c in checks(a) if c.kind == 'assessment' and visible(c, T) and not voided_by(c, T)),
                       key=assessment_order))

def assessment_order(c):              # day-precision rows hold a local date in observed_at, used as is
    end = c.observed_at if c.observed_precision == 'instant' else end_of_day_utc(observed_date(c))
    return (observed_date(c), end, K(c), c.id)          # end_of_day_utc(d) = d 23:59:59.999 owner zone, in UTC

def effective_state(a, T):
    c = latest_assessment(a, T)
    if c: return c.state                              # the last known state, however old (freshness is the timeliness axis)
    if a.data_source_kind == 'none': return 'UNVERIFIABLE'
    due, _ = assumption_due(a, T)
    if due is None or due > T.date: return 'NOT_YET_DUE'
    return 'UNCHECKED'                                # its date has come and nobody checked
```

An UNVERIFIABLE assumption becomes checkable without rewriting history: `supersede_assumption` with a
data source creates a successor (same decision, next code) that starts fresh, and the predecessor keeps
its checks. A scoped assumption (`scope` set) is checked per scope unit, and its state is the worst
unit's (VIOLATED > DRIFTING > UNKNOWN > HOLDING). The slice stores units in the check `note`; per-unit
entry is [Later 3].

### 4.5 Readings propose; assessments decide

```python
def default_judge_from(a):            # "reach a target by a date" is not judged before the date; caps and bands always are
    return a.by_date if (a.comparator in ('>=', '>') and a.by_date) else None

def proposed_state_from_reading(a, value, unit, observed_date):     # → (state | None, reason | None)
    if a.comparator is None: return (None, 'text_threshold')        # the owner judges
    if value is None:        return (None, 'no_value')
    if a.unit and unit and unit != a.unit: return (None, 'unit_mismatch')
    jf = a.judge_from or default_judge_from(a)
    if jf and observed_date < jf: return (None, 'before_judge_from')
    x = Decimal(value)
    if not compare(x, a.comparator, Decimal(a.threshold_value), dec_or_none(a.threshold_value2)):
        return ('VIOLATED', None)
    m = Decimal(a.drift_margin or CFG.dec.drift_margin)
    return ('DRIFTING' if near_limit(x, a, m) else 'HOLDING', None)

def compare(x, cmp, v, v2):           # 'between' is inclusive at both ends
    return {'>=': x >= v, '<=': x <= v, '>': x > v, '<': x < v, '=': x == v, '!=': x != v,
            'between': v2 is not None and v <= x <= v2}[cmp]

def near_limit(x, a, m):              # still holds, but within the margin on the bad side
    v = Decimal(a.threshold_value)
    if a.comparator in ('>=', '>'): return x - v <= abs(v) * m
    if a.comparator in ('<=', '<'): return v - x <= abs(v) * m
    if a.comparator == 'between':
        v2 = Decimal(a.threshold_value2); return min(x - v, v2 - x) <= (v2 - v) * m
    return False                      # '=' and '!=' have no drift band
```

`record_reading` stores the value with its proposal and never changes a state. `record_check(...,
accept_reading=RD)` writes an assessment whose state is the reading's proposal, unless the owner states
another, with `reading_id` set and the reading's `accepted_by_check_id` set once. An app with the
`dec:evidence` scope may write readings but never assessments [Later 6].

### 4.6 Check dates

The date table is ported unchanged from v1, and its test vectors are acceptance tests (DEC-6). Locale
formats are added through CFG-3 as new versioned rows, each with its own vectors.

```python
DATE_PATTERNS = [                                       # applied after HTML unescaping
  r'(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)',               # 2026-11-15
  r'(?<![\d.,])(\d{1,2})\.(\d{1,2})\.(20\d{2})(?!\d)',     # 15.11.2026, 5.11.2026
  r'(?<![\d.,])(\d{2})\.(\d{2})(?![\d.,])',                # 15.11: the year of `base`; next year if earlier than base
]
# Never dates: "1.5", "0.80", "12.5 %".

def make_date(y, mo, d):                                 # None for an invalid calendar date ("31.02")
    try: return date(int(y), int(mo), int(d))
    except ValueError: return None

def dates_in(text, base):                                # base = the decision's decided date, else its K date
    t = html.unescape(text or '')
    hits, spans = [], []
    for m in re.finditer(DATE_PATTERNS[0], t):           # ISO: year, month, day
        d = make_date(m[1], m[2], m[3])
        if d: hits.append((m.start(), d)); spans.append(m.span())
    for m in re.finditer(DATE_PATTERNS[1], t):           # day.month.year
        d = make_date(m[3], m[2], m[1])
        if d: hits.append((m.start(), d)); spans.append(m.span())
    for m in re.finditer(DATE_PATTERNS[2], t):           # day.month, never inside a date already found
        if any(a <= m.start() < b for a, b in spans): continue
        d = make_date(base.year, m[2], m[1])
        if d and d < base:                               # strictly earlier than base: the next year
            d = make_date(base.year + 1, m[2], m[1])
        if d: hits.append((m.start(), d))
    return [d for _, d in sorted(hits)]                  # in order of position in the text
```

"In order of appearance" is the position in the text, not the pattern order; `assumption_due` takes the
first returned date after the floor, so the order is part of the contract. A synthetic vector table
(`tests/fixtures/synthetic/dates_in_vectors`: text, base, floor, expected) is part of AT-D1, and it is
checked once against v1's own function privately; a difference found there is fixed in this text first.

```python
def floor_date(a, T):                                    # a date counts only if strictly later than this
    last = latest_assessment(a, T)
    return max(observed_date(last) if last else date.min, local_date(K(a)))   # K(a) = v1 created_at for imports

def assumption_due(a, T):                                # → (date | None, source)
    if a.status != 'active': return (None, None)
    if a.next_check_at: return (a.next_check_at, 'explicit')
    floor = floor_date(a, T)
    if a.by_date and a.by_date > floor: return (a.by_date, 'by_date')   # structured beats text
    d = decision(a); base = decided_date(d) or local_date(K(d))
    for text in (a.threshold_text, a.statement):
        for dt in dates_in(text, base):
            if dt > floor: return (dt, 'text')
    if d.review_due: return (d.review_due, 'review')
    return (None, None)

def assessed_since(a, day, T):
    return any(c.kind == 'assessment' and visible(c, T) and not voided_by(c, T) and observed_date(c) >= day
               for c in checks(a))

# Helpers used here and in §4.7 to §4.16 (all over rows visible at T, voided rows excluded):
# K(row)                      = row.origin_recorded_at or row.recorded_at                       (§3.1)
# local_date(t)               = the owner-zone date of the instant t
# observed_date(c)            = the owner-zone date of c.observed_at; for an unknown time, local_date(K(c))
# active_assumptions(d)       = assumptions of d with status 'active', ordered by position
# live_options(d)             = options of d with voided_at IS NULL, ordered by code
# live_links(d, roles)        = dec_links of d with removed_tx IS NULL and role in roles
# reviewed_on_or_after(d, day, T) = any non-voided review of d whose occurred date ≥ day
# last_activity_date(d, T)    = the latest event date (fallback: the K date) of d's facts, assessments, readings
#                               and reviews; if none, the activation date (or the decided date for mirrors)
# decided_date(d)             = the owner-zone date of d.decided_at, or None when unknown

def check_due(a, T):                                     # → (date, source) | None; used by timeliness and waiting
    if effective_state(a, T) in ('VIOLATED', 'UNVERIFIABLE'): return None    # violated → review; nothing to check with
    due, src = assumption_due(a, T)
    if src not in ('explicit', 'by_date', 'text') or due is None or due > T.date: return None
    if assessed_since(a, due, T): return None            # review-sourced dates are covered by the review reason
    return (due, src)

STEP = {'weekly': 7, 'monthly': 30, 'quarterly': 90}

def next_check_after(a, observed_date, explicit=None):   # THE one function: record_check, buttons and cards use it
    if explicit:
        if not (observed_date < explicit <= observed_date + timedelta(days=CFG.dec.review_max_days)):
            raise Refused('NEXT_CHECK_OUT_OF_RANGE')
        return (explicit, 'explicit')
    if a.check_frequency in STEP: return (observed_date + timedelta(days=STEP[a.check_frequency]), 'frequency')
    if a.check_frequency == 'ad_hoc': return (None, 'ad_hoc_clear')       # no hidden default step
    if a.next_check_at and a.next_check_at > observed_date: return (a.next_check_at, 'kept')
    return (None, 'dropped' if a.next_check_at else 'none')
```

- `record_check` stores the due date it answered (`due_answered`, `due_source_answered` from
  `assumption_due` before the write), writes the assessment, and sets `a.next_check_at` (a versioned field)
  from `next_check_after`. No channel adds a default step.
- `postpone_check(a, until, reason)` accepts `T.date < until ≤ T.date + dec.postpone_max_days` and needs a
  reason. It writes a check-log row of kind `postponement` (`next_check_rule = 'postpone'`) and sets
  `a.next_check_at := until`. It answers no due date, and the number of postponements since the last
  review is shown at the review.
- "Not yet due" is computed from the due date, never stored. Changes of check dates, review dates and
  statuses are kept as versions.

### 4.7 Health: two axes, one composite, reasons (proposed, D-044)

The whole of this section is proposed and has not yet been put to the owner (§14). It implements DEC-3.

```python
def pool(d):                                       # the assumptions the decision rests on
    act = active_assumptions(d); crit = [a for a in act if a.is_critical]
    return crit or act

def unverifiable_share(d, T):                      # ALWAYS the first line of every decision view
    p = pool(d)
    return None if not p else Decimal(sum(effective_state(a, T) == 'UNVERIFIABLE' for a in p)) / len(p)

def ground(d, T):                                  # → (value, reasons[])
    act = active_assumptions(d)
    if not act:
        return ('NOT_MONITORED', ['light decision: review date only']) if d.depth == 'light' \
          else ('NO_ASSUMPTIONS', ['no assumption recorded'])
    p = pool(d); s = {a: effective_state(a, T) for a in act}
    viol = [a for a in p if s[a] == 'VIOLATED']
    if viol: return ('VIOLATED', [f'{a.code} violated: {short(a.statement)}' for a in viol])
    share = unverifiable_share(d, T)
    if share > Decimal(CFG.dec.unverifiable_share_limit):
        return ('INSUFFICIENT', [f'{pct(share)} of the assumptions it rests on cannot be checked'])
    drift = [f'{a.code} drifting' for a in p if s[a] == 'DRIFTING'] \
          + [f'{a.code} (non-critical) violated' for a in act if a not in p and s[a] == 'VIOLATED']
    if drift: return ('DRIFTING', drift)
    checkable = [a for a in p if s[a] != 'UNVERIFIABLE']
    if checkable and all(s[a] == 'HOLDING' for a in checkable):
        return ('HOLDING', ['every checkable assumption it rests on holds'])
    n = sum(s[a] in ('NOT_YET_DUE', 'UNCHECKED', 'UNKNOWN') for a in p)
    return ('AWAITING', [f'{n} assumptions without a result yet'])

def timeliness(d, T):                              # → (set of kinds, reasons[]); every applicable reason is listed
    k, r = set(), []
    def add(kind, text): k.add(kind); r.append(text)
    rd = d.review_due
    if rd is None:
        add('NO_REVIEW_DATE', 'no review date')
    elif rd < T.date and not reviewed_on_or_after(d, rd, T):
        add('REVIEW_OVERDUE', f'review was due {rd}, {(T.date - rd).days} days ago')
    elif rd == T.date and not reviewed_on_or_after(d, rd, T):
        add('DUE_TODAY', 'review today')
    for a in active_assumptions(d):
        cd = check_due(a, T)
        if cd and cd[0] < T.date: add('CHECK_OVERDUE', f'{a.code} check was due {cd[0]} (from {cd[1]})')
    last = last_activity_date(d, T)
    if last and (T.date - last).days > CFG.dec.no_data_days: add('NO_DATA_SINCE', f'nothing recorded since {last}')
    return (k or {'ON_SCHEDULE'}, r)

def health(d, T):                                  # composite label; THE EVALUATION ORDER IS THE CONTRACT
    if d.status == 'closed':     return ('CLOSED', outcome_badge(d))      # "success · resolved" green; reported, not confirmed grey
    if d.status == 'cancelled':  return ('CANCELLED', [])
    if d.status == 'superseded': return ('SUPERSEDED', [f'by {successor(d)}'])
    if d.status == 'withdrawn':  return ('WITHDRAWN', [])
    if d.status == 'draft':      return ('DRAFT', [f'missing: {", ".join(missing_for_activation(d, T))}'])
    g, gr = ground(d, T); t, tr = timeliness(d, T); reasons = gr + tr
    if d.manual_flag:                     return (d.manual_flag, ['set by the owner'] + reasons)   # 1
    if g == 'VIOLATED':                   return ('REVIEW_REQUIRED', reasons)                      # 2
    if 'REVIEW_OVERDUE' in t:             return ('STALE', reasons)                                # 3
    if g in ('INSUFFICIENT', 'NO_ASSUMPTIONS'): return ('INSUFFICIENT_DATA', reasons)              # 4
    if g == 'DRIFTING' or t & {'NO_REVIEW_DATE', 'CHECK_OVERDUE'} \
       or ('NO_DATA_SINCE' in t and g == 'HOLDING'):
                                          return ('WATCH', reasons)                                # 5
    if g in ('HOLDING', 'NOT_MONITORED'): return ('ON_TRACK', reasons)                             # 6
    return ('AWAITING_CHECKS', reasons)                                                            # 7

def is_bet(d, T):                                  # a badge; informative only
    s = unverifiable_share(d, T); return s is not None and s > Decimal(CFG.dec.unverifiable_share_limit)
```

**The composite table** for an active decision, evaluated top to bottom; the first row that holds gives
the label. Terminal statuses and drafts are labelled by their status first, as in the code.

| Order | Condition | Label | Why this place |
|---|---|---|---|
| 1 | the owner set a manual flag | `ZOMBIE` or `OFF_TRACK` (computed reasons kept) | the owner's judgement wins |
| 2 | ground is VIOLATED (an assumption of the pool is violated) | `REVIEW_REQUIRED` | a known violation beats fog and the calendar |
| 3 | timeliness has REVIEW_OVERDUE | `STALE` | an overdue review is never masked by missing data |
| 4 | ground is INSUFFICIENT (unverifiable share above the limit) or NO_ASSUMPTIONS (full depth, none recorded) | `INSUFFICIENT_DATA` | fog, but on schedule |
| 5 | ground is DRIFTING (a pool assumption drifting, or a non-critical one violated); or timeliness has NO_REVIEW_DATE or CHECK_OVERDUE; or NO_DATA_SINCE while ground is HOLDING | `WATCH` | an overdue check or a stale "holding" is not on track |
| 6 | ground is HOLDING or NOT_MONITORED (light, no assumptions) | `ON_TRACK` | — |
| 7 | anything else (ground AWAITING: assumptions not yet due, unchecked or unknown) | `AWAITING_CHECKS` | replaces a "watch" that carries no signal |

**Reasons.** Every result carries its reasons in words and in structure (`kind`, `code`, `date`,
`source`). The card's first line is the unverifiable share ("2 of 5 assumptions it rests on cannot be
checked"), then ground and timeliness, then the label. A failure is worded "did not happen as expected",
never as an error.

**Named health vectors** (hand-checked, kept as fixtures; "crit" = critical; review dates are relative to
`T.date`):

| # | Assumptions (effective states) | Review | Other | Label | Ground | Share |
|---|---|---|---|---|---|---|
| H1 | none, depth full | in 10 d | — | INSUFFICIENT_DATA | NO_ASSUMPTIONS | — |
| H2 | none, depth light | in 10 d | — | ON_TRACK | NOT_MONITORED | — |
| H3 | crit VIOLATED, crit HOLDING | overdue | — | REVIEW_REQUIRED | VIOLATED | 0 |
| H4 | crit UNVERIFIABLE ×2 | overdue | — | STALE | INSUFFICIENT | 1 |
| H5 | crit UNVERIFIABLE ×2, crit HOLDING | in 5 d | — | INSUFFICIENT_DATA | INSUFFICIENT | 0.67 |
| H6 | crit UNVERIFIABLE, crit HOLDING | in 5 d | fresh | ON_TRACK | HOLDING | 0.5 |
| H7 | crit NOT_YET_DUE ×3 | in 20 d | fresh | AWAITING_CHECKS | AWAITING | 0 |
| H8 | crit UNCHECKED (text date yesterday), crit NOT_YET_DUE | in 20 d | — | WATCH (CHECK_OVERDUE) | AWAITING | 0 |
| H9 | crit HOLDING, weekly, checked 10 d ago | in 20 d | — | WATCH (CHECK_OVERDUE) | HOLDING | 0 |
| H10 | crit HOLDING ×2, ad hoc | in 60 d | last activity 45 d ago | WATCH (NO_DATA_SINCE) | HOLDING | 0 |
| H11 | crit DRIFTING, crit HOLDING | today | — | WATCH (reason DUE_TODAY) | DRIFTING | 0 |
| H12 | crit HOLDING ×2 | in 20 d | manual ZOMBIE | ZOMBIE (computed reasons kept) | HOLDING | 0 |
| H13 | non-crit VIOLATED, crit HOLDING | in 20 d | fresh | WATCH; the waiting list shows `violated` (non-critical), urgency rank 1 | DRIFTING | 0 |
| H14 | mirror, crit HOLDING | none | fresh | WATCH (NO_REVIEW_DATE); the waiting list shows `incomplete` | HOLDING | 0 |
| H15 | — | — | closed, success, basis reported | CLOSED · success · reported (grey) | — | — |
| H16 | crit UNKNOWN, crit HOLDING | in 20 d | fresh | AWAITING_CHECKS | AWAITING | 0 |
| H17 | no criticals: VIOLATED, HOLDING | in 20 d | — | REVIEW_REQUIRED (the pool is all assumptions) | VIOLATED | 0 |
| H18 | crit NOT_YET_DUE ×2 | in 20 d | last activity 40 d ago | AWAITING_CHECKS (reason NO_DATA_SINCE) | AWAITING | 0 |

**Exhaustive agreement test.** A second implementation of this section is written independently from the
text as a test oracle (`tests/oracle/health_oracle.py`, by a different agent than the module, without
reading the module's code). Its input is an abstract tuple:

```python
oracle(depth ∈ {light, full},
       manual_flag ∈ {None, ZOMBIE, OFF_TRACK},
       review ∈ {none, future, today, overdue, overdue_but_reviewed},
       activity ∈ {fresh, stale},
       assumptions = [(critical ∈ {True, False},
                       state ∈ {HOLDING, DRIFTING, VIOLATED, UNVERIFIABLE, UNKNOWN, NOT_YET_DUE, UNCHECKED},
                       check_due ∈ {none, today, past})])          # 0 to 3 assumptions
# check_due is forced to none for VIOLATED, UNVERIFIABLE and NOT_YET_DUE.
```

One shared fixture builder turns each tuple into the module's input views (in memory, no database), so
both sides see the same inputs. They are compared on `(label, ground value, set of timeliness kinds,
share as the pair n/m)`, never on reason text. Each assumption has 30 shapes (15 state and check-due
combinations, critical or not); the assumptions are a multiset (order changes only the reason order,
which is not compared), so there are 5,456 assumption sets and 5,456 × 2 × 3 × 5 × 2 = 327,360 cases.
The named vectors pin the intent; agreement between two independent implementations pins the code. A
disagreement is resolved by correcting this text first, then the losing side.

### 4.8 The waiting list

One list serves the CLI and MCP now, and the plan and the bot from stage 2 (DEC-6, RHY-1).

```python
KIND_RANK = ['violated', 'review_overdue', 'review_today', 'goal_changed', 'check_due', 'incomplete',
             'fork_due', 'proposal_waiting']
SUBJECT_ORDER = {'decision': 0, 'fork': 1, 'proposal': 2}

def waiting(T):
    items = []
    for d in decisions(status='active'):
        if mirror_absent_in_source(d): continue                  # tombstoned mirrors never wait
        rs = []
        for a in active_assumptions(d):                          # EVERY assumption, critical or not
            if effective_state(a, T) == 'VIOLATED':
                rs.append(R('violated', observed_date(latest_assessment(a, T)), a.code, critical=(a in pool(d))))
        rd = d.review_due
        if rd and rd <= T.date and not reviewed_on_or_after(d, rd, T):
            rs.append(R('review_overdue' if rd < T.date else 'review_today', rd))
        for g in goal_changes_unanswered(d, T):                  # §4.13: asked once, until a review answers it
            rs.append(R('goal_changed', g.changed_date, g.ref, status=g.status))
        for a in active_assumptions(d):
            cd = check_due(a, T)
            if cd: rs.append(R('check_due', cd[0], a.code, due_source=cd[1], critical=(a in pool(d))))
        if d.mirror_of and rd is None:
            rs.append(R('incomplete', local_date(K(d))))         # an imported active record without a review date
        if rs:
            rs.sort(key=lambda r: (KIND_RANK.index(r.kind), r.due or date.max, r.code or ''))
            items.append(Item('decision', d.public_id, d.number, d.title, health(d, T), rs))
    for f in forks(status='open'):
        if f.deadline and f.deadline <= T.date:
            items.append(Item('fork', f.public_id, f.number, f.question, None, [R('fork_due', f.deadline)]))
    for p in proposals(status='proposed'):
        items.append(Item('proposal', f'proposal {p.id}', p.id, p.title, None,
                          [R('proposal_waiting', local_date(K(p)))]))

    def urgency(i):
        if i.subject_kind == 'proposal': return (2, i.reasons[0].due, 0, i.number)       # always last
        critical_violation = any(r.kind == 'violated' and r.critical for r in i.reasons)
        dues = [r.due for r in i.reasons if r.due]
        return (0 if critical_violation else 1, min(dues) if dues else date.max, SUBJECT_ORDER[i.subject_kind], i.number)
    return sorted(items, key=urgency)

def drafts_to_finish(T):          # a separate short list, never mixed into the waiting list
    return [(d, missing_for_activation(d, T)) for d in decisions(status='draft')
            if (T.date - local_date(K(d))).days >= CFG.dec.drafts_stale_days]
```

- **Ported from v1:** the reasons `violated`, `review_overdue`, `review_today` and `check_due`; the review
  reason independent of health; the order "a critical violation first, then the oldest due date, then the
  number".
- **Changed from v1:** a non-critical violation now waits, with its criticality shown, so health and the
  waiting list agree.
- **New:** `goal_changed` (DEC-16), `incomplete`, `fork_due` (DEC-14), `proposal_waiting` (DEC-17).
- Every reason is rendered in words, with its date and the source of the date ("A-02: check due 15 Nov,
  from its threshold date").
- **Reserved [Later 3, DEC-22]:** `expectation_missed` (a dated expectation passed with no fact) and
  `contradiction` (a new fact or reading crosses an active assumption). In the slice an assumption with a
  by-date already becomes `check_due` on that date ("expected by D: did it happen?").

### 4.9 Question context and likely actions (no model)

No waiting item is ever shown without its context, built by rules (DEC-20):

```python
def question_context(item, T):
    d = decision(item) if item.subject_kind == 'decision' else None
    return {
      'one_line':   f'{item.ref} · {item.title} — {short(d.statement or d.question, 120)}' if d else item.title,
      'share_line': unverifiable_line(d, T) if d else None,                  # always first for decisions
      'health':     health(d, T) if d else None,
      'reasons':    item.reasons,                                            # each with its date and date source
      'last_fact':  last_fact(d, T) if d else None,  # {code, text≤120, occurred_at, age_days, evidence} or "no fact recorded"
      'passed':     [(label, day) for label, day in (('review date', d.review_due), ('expected by', d.expected_by),
                     *[(f'{a.code} by-date', a.by_date) for a in active_assumptions(d)]) if day and day <= T.date] if d else [],
      'goals':      [{'ref': g.ref, 'title': g.title, 'status': g.status, 'since': g.changed_date}
                     for g in served_goals(d, T)] if d else [],
      'asked':      asked_part(item, T),      # the assumption with threshold, due date and source; or the review
      'execution':  {p.kind: p.summary(d.public_id, as_of=T).counts() for p in attachment_probes()} if d else {},
      'postponements_since_review': count_postponements(d, T) if d else 0,
      'likely_actions': likely_actions(item, T),
    }

def likely_actions(item, T):          # values come from the SAME functions the writes use
    k = item.reasons[0].kind; step = T.date + timedelta(days=CFG.dec.review_step_days)
    if k == 'violated':        return ['revise', f'adjust · next review {step}', 'close', 'cancel']
    if k in ('review_overdue', 'review_today'):
                               return [f'keep · next review {step}', f'adjust · next review {step}', 'close', 'cancel', 'supersede']
    if k == 'goal_changed':    return ['close', 'cancel', f'keep (give a reason) · next review {step}']
    if k == 'check_due':
        a = assumption(item, item.reasons[0].code); nxt, _ = next_check_after(a, T.date)
        return [f'holding · next check {nxt or "none (falls back)"}', 'drifting', 'violated',
                "can't judge this time", 'nothing to check with', f'postpone to {T.date + timedelta(days=7)}']
    if k == 'incomplete':      return ['set a review date (keep)', 'complete fields', 'cancel']
    if k == 'fork_due':        return ['decide (pick an option)', 'move the deadline', 'dissolve', 'delegate']
    if k == 'proposal_waiting': return ['approve (owner channel)', 'edit and approve', 'reject with a class']
```

Acceptance: on a stale fixture (review 31 days overdue, last fact 45 days old, a served goal dropped 20
days ago, two commitments overdue) the card shows all of it, and the owner can answer without opening
anything else (AT-N23). Every date shown in an action equals what the write would store (AT-N11).

### 4.10 Reviews, revisions, corrections, completion

**Accepted (D-043):** revise keeps the number and seals a new edition, and needs a trigger fact, a stated
change of mind or the correction flag. **Proposed:** adjust cuts no edition; corrections and completions
are not counted as revisions.

A `revision` argument holds any of: `fields{}` (basis fields, including `chosen_option`),
`add_options[]`, `replace_options[]` (an option code and its new text or reason: the old row is voided and
a successor appended), `void_options[]`, `add_grounds[]`, `void_grounds[]`, `supersede_assumptions[]`,
`add_assumptions[]`, `drop_assumptions[]`, `add_stakes[]` and `void_stakes[]`. `touches_basis(revision)`
is true when at least one of them changes the basis.

```python
def review_decision(ref, action, *, verdict=None, notes=None, next_review_due=None, trigger=None, trigger_ref=None,
                    revision=None, revise_basis=None, is_correction=False, outcome=None, learning=None,
                    successor_ref=None, occurred_at=None, expected_version=None, ctx):
    d = load(ref); guard_mirror(d, op='review'); check_version(d, expected_version); T = ctx.now; basis = None
    if d.status in ('superseded', 'withdrawn'): raise Refused('TERMINAL_DECISION', allowed=[])
    if d.status in ('closed', 'cancelled') and action != 'close': raise Refused('TERMINAL_DECISION', allowed=['close'])
    if d.status == 'draft' and action != 'cancel': raise Refused('DRAFT_ACTIVATE_FIRST', allowed=['cancel'])
    if action in ('keep', 'adjust', 'revise'):                                # in every channel
        if not next_review_due: raise Refused('REVIEW_DATE_REQUIRED')
        if not (T.date < next_review_due <= T.date + timedelta(days=CFG.dec.review_max_days)):
            raise Refused('REVIEW_DATE_OUT_OF_RANGE')
    if action == 'revise':
        if not revision or not touches_basis(revision): raise Refused('REVISION_EMPTY')
        basis = 'correction' if is_correction else revise_basis
        if basis == 'trigger_fact':
            f = fact(trigger_ref)
            if not f or f.decision_id != d.id or f.voided_at: raise Refused('TRIGGER_FACT_REQUIRED')
        elif basis == 'change_of_mind':
            if not (verdict or notes): raise Refused('REASON_REQUIRED')
        elif basis != 'correction':
            raise Refused('REVISE_BASIS_REQUIRED', allowed=['trigger_fact', 'change_of_mind', 'correction'])
    if action == 'close':
        validate_outcome(d, outcome)                                          # §4.11
        if d.status != 'closed' and not (learning and (learning.confirmed or learning.refuted)):
            raise Refused('LEARNING_REQUIRED')
    if action == 'cancel' and not (verdict or notes): raise Refused('REASON_REQUIRED')
    if action == 'supersede':
        s = load(successor_ref)
        if not s or s.id == d.id or s.status not in ('draft', 'active', 'closed'): raise Refused('SUCCESSOR_INVALID')
    trigger = trigger or ('scheduled' if d.review_due and d.review_due <= T.date else 'owner_initiative')
    before  = snapshot(d, T)                       # status, review date, edition, health, ground, timeliness, share
    shown   = [r.kind for r in waiting_reasons_of(d, T)]
    summary = {p.kind: p.summary(d.public_id, as_of=T).counts_and_ids() for p in attachment_probes()}  # read BEFORE the unit
    with unit_of_work('dec', ctx):
        r = insert_review(d, action, verdict, notes, trigger, trigger_ref, trigger_at(trigger, trigger_ref, d),
                          occurred_at or live(T), next_review_due, before, shown, summary,
                          revise_basis=basis if action == 'revise' else None, is_correction=is_correction,
                          successor_ref=successor_ref)
        if action in ('keep', 'adjust'): set_head(d, review_due=next_review_due)
        if action == 'revise':
            apply_revision(d, revision)             # basis fields set; changed items voided and appended; assumptions superseded
            set_head(d, review_due=next_review_due)
            seal(d, d.current_edition + 1, 'correction' if is_correction else 'revise', r.id, ctx)
        if d.completion_pending and action != 'revise':
            seal(d, d.current_edition + 1, 'completion', r.id, ctx)
        if action == 'close':
            o = insert_outcome(d, outcome, r, resolved_by='owner')          # supersedes the previous resolution, if any
            if learning: insert_learning(d, learning, r, o)
            if d.status != 'closed': set_head(d, status='closed', review_due=None, closed_at=T)
        if action == 'cancel':
            if learning: insert_learning(d, learning, r, None)
            set_head(d, status='cancelled', review_due=None, closed_at=T)
        if action == 'supersede':
            insert_link(s, 'supersedes', d.public_id); set_head(d, status='superseded', review_due=None, closed_at=T)
        set_once(r, unverifiable_after=share_text(d, T), edition_after=d.current_edition)
        publish('coflow.dec.decision.reviewed', d, changed=changed_fields(d))
        if d.status != before.status: publish(f'coflow.dec.decision.{d.status}', d, changed=['status'])
    return ReviewResult(r.ref, d.status, d.current_edition, health(d, T))
```

- A review never changes assumption states. Checks are recorded by `record_check`; from stage 2 they may
  sit on the same approval card, each item its own unit of work.
- Every review records its trigger, the state and the unverifiable share before and after, the waiting
  reasons that were shown, and the attached execution summary (counts and ids from the probes, DEC-11).
- Review latency is a query: `occurred_at(review) − trigger_at`, where the trigger time is the violating
  check's `observed_at`, the review date, or the goal change date.
- **Completion** applies to reconstructed records only: adopted v1 mirrors and project-log records, for
  the fields v2 owns. `update_decision` may fill a basis field that is empty; `add_option`, `add_fact`
  with `phase = 'ground'`, `add_assumption` and `update_decision(add_stakes=[…])` may add items. Each sets
  `completion_pending`, and the next review of any action, or `complete_decision`, seals one edition with
  reason `completion`. Changing a non-empty basis field is a revise. Completions and corrections do not
  count as revisions in any metric.
- **A different decision** is not a revision: the owner creates a new decision and supersedes the old one
  (accepted, D-043).

### 4.11 Outcome and learning (proposed, D-043)

```python
def validate_outcome(d, o):
    if not o or o.kind not in ('success', 'failure', 'mixed', 'unknown'): raise Refused('OUTCOME_REQUIRED')
    if o.basis not in ('resolved', 'reported', 'not_confirmed'): raise Refused('OUTCOME_BASIS_REQUIRED')
    if o.kind == 'unknown' and o.basis != 'not_confirmed': raise Refused('OUTCOME_UNKNOWN_NEEDS_NOT_CONFIRMED')
    refs = [load_evidence(d, x) for x in o.evidence_refs]                     # checks, readings, facts of THIS decision
    if any(x is None for x in refs): raise Refused('FOREIGN_EVIDENCE')
    if o.basis == 'resolved' and not any(x.kind in ('check', 'reading') or
                                         (x.kind == 'fact' and x.evidence_kind != 'none') for x in refs):
        raise Refused('RESOLVED_NEEDS_EVIDENCE')
    if o.basis == 'reported' and not any(x.kind == 'fact' and x.fact_kind in ('outcome_report', 'statement') for x in refs) \
       and not o.owner_statement:
        raise Refused('REPORTED_NEEDS_A_REPORT')
```

- **Display.** `CLOSED · success · resolved` shows green; `reported` and `not_confirmed` show grey. No
  system text claims causality from a before/after comparison.
- **Outcome reports** come from anyone: the owner, a counterpart quoted in a source, an agent, or later an
  app. They are monitoring facts of kind `outcome_report`, they are evidence, and they never close
  anything.
- **Resurfacing.** `create_decision` and `activate_decision` return `related_learnings[]`: the
  non-voided learnings of closed or cancelled decisions that share the same `kind`, an overlapping `about`
  or `serves` target, or an assumption with the same `class_tag`. They are ordered by the number of
  matching criteria, then by the newest closing, then by number, and capped at
  `dec.related_learnings_max`. Each comes with the fate of those assumptions ("2 of 3 earlier `demand`
  assumptions were violated"). The owner may link one as `informed_by`. The same data gives the same list.
- **Scoring eligibility** is stored data; the scoring itself is not built before the forecast pilot's
  report (DEC-10). A checkpoint is eligible when its probability was stated by the owner and recorded (K)
  before its by-date and before the K of any evidence bearing on it; the decision is neither
  reconstructed nor retroactive; the resolving assessment or outcome was recorded in an owner channel
  (`sys_tx_log.owner_channel = 1`); and nothing in the chain is voided. Imported (`resolved_by = import`)
  and MCP-recorded resolutions are never eligible.

### 4.12 Forks and proposals

```
open ── decide(option, decision fields) ──▶ decided    creates the decision (draft, or active if the gate passes)
  ├── dissolve(reason) ──▶ dissolved                    the question disappeared
  ├── delegate(to_ref) ──▶ delegated                    someone else decides (a fact or an external reference later)
  └── undo of open (no decision, no later writes) ──▶ withdrawn
```

- **Deciding** inserts one decision option per live fork option (`copied_from` set), with
  `recorded_before_choice = 'yes'` when the fork option's K is earlier than the decide instant and `'no'`
  otherwise, sets the decision's `chosen_option` to the copy of the chosen option, stores `origin_kind =
  'fork'` and `origin_ref` = the fork's id, and sets the fork's `decision_id` (DEC-14). Options added to the
  decision later are flagged `no`.
- A fork whose source ended before a result keeps `outcome_not_heard = 1` and stays open. An open fork past
  its deadline waits (`fork_due`). The latencies from signal to fork (`opened_at − trigger time`) and from
  fork to decision (`decided_at − opened_at`) are queries.

```python
def propose_decision(payload, origin, ctx):            # MCP; never writes a decision
    refuse_if(origin_switched_off(origin.kind), 'PROPOSAL_ORIGIN_SWITCHED_OFF')
    h = hashlib.sha256(cfj(normalise_payload(payload))).hexdigest()
    kind = 'fact' if payload.get('decision_ref') else 'decision_new'
    refuse_if(rejected_before(kind, payload.get('decision_ref'), h), 'PROPOSAL_REJECTED_BEFORE')   # never proposed again
    cands = match_candidates(payload)                   # deterministic, below
    insert_proposal(type=kind, title=title_of(payload), payload_json=cfj(payload), payload_hash=h,
                    origin_kind=origin.kind, origin_ref=origin.ref, origin_quote=origin.quote,
                    proposed_by=ctx.actor, match_candidates_json=cfj(cands))

def match_candidates(payload):                         # shown at approval; no automatic classification in the slice
    named = labels_in(payload)                         # "D-0042", "D42", aliases: a label beats a guess (IDN-7)
    recent = [d for d in decisions(status=('active', 'closed'))
              if d.status == 'active' or age_days(d.closed_at) <= 90]
    scored = [(d, tokens_overlap(payload.statement or payload.question, d.statement or d.question))
              for d in recent if overlaps(targets(d, ('about', 'serves')), payload.targets) and d.kind == payload.kind]
    best = sorted(scored, key=lambda x: (-x[1], x[0].number))
    return ([{'ref': x, 'why': 'named'} for x in named]
            + [{'ref': d.public_id, 'why': f'same subject and kind, overlap {o}'}
               for d, o in best if o >= Decimal(CFG.dec.match_overlap_min)][:3])

def approve_proposal(pid, edits=None, *, ctx):         # owner channel only: the CLI now, a bot card from stage 2
    require(ctx.owner_channel, 'OWNER_CHANNEL_REQUIRED')      # an MCP call can never approve (P-4)
    p = load_proposal(pid); require(p.status == 'proposed', 'NOT_PROPOSED')
    if p.type == 'decision_new':
        result = create_decision(**merge(p.payload, edits), origin={'kind': 'proposal', 'ref': f'proposal {pid}'})
    else:
        result = add_fact(p.decision_id, **merge(p.payload, edits))
    set_proposal(p, status='approved', decided_tx=ctx.tx, result_ref=result.ref)
```

- `reject_proposal(pid, class, reason)` stores the class (the non-decision classes of §2.2, or
  `duplicate`, `wrong`, `other`) and the reason; the rejected payload is never proposed again (P-7).
- The decision rate per `origin_kind` is a usage signal. An origin whose approved share over its last 30
  decided proposals falls below `dec.proposal_switch_off` (20 %) switches itself off and says so, which is
  the CMT-2 rule applied to decisions (DEC-17).
- Classifying a match as new, update, retelling or contradiction is [Later 3], when extraction from
  conversations exists.

### 4.13 Goal and occasion propagation

```python
ENDED = {'dropped', 'paused', 'achieved', 'abandoned', 'superseded', 'closed'}

def goal_changes_unanswered(d, T):
    for link in live_links(d, roles=('serves', 'tests')):
        st = GoalDirectory.state(link.target_ref, as_of=T)        # the slice: the shadow adapter over dec_foreign_context
        if st is None or st.status not in ENDED: continue
        changed = st.status_changed_date or st.first_seen_date    # unknown change date → the first run that saw it
        if changed <= (decided_date(d) or local_date(K(d))): continue   # already ended when decided: the owner knew
        if reviewed_on_or_after(d, changed, T): continue           # any later review answers it (its card showed the goal)
        yield GoalChange(link.target_ref, st.title, st.status, changed)
```

- `first_seen_date` is the `as_of_date` of the import run named by `first_seen_status_run_id` (the first
  run that saw the current status).
- In the slice, `GoalDirectory.state(ref, as_of)` reads `dec_foreign_context`, which is mutable and keeps
  no history: it returns the current row only when its first-seen run's `as_of` is at or before `as_of`,
  and otherwise `None` with the coverage note "goal status at that time is not known".
- `ENDED` holds the v2 status words; imported goal statuses are mapped to them at import (§10.3).

It is a question, never a state change (DEC-16). The review that answers it records `trigger =
'goal_change'` when it is asked for that reason. Two directions are [Later]:
- **Stage 1:** closing a `pursue` decision proposes the goal's state, on WRK's (later GOL's) side.
- **Stage 3:** for an `attendance` decision, the window's end plus 2 days proposes the review date, and
  plus 30 days a second checkpoint (DEC-21).

### 4.14 Entry-time offers, attachment acceptance and the unlinked report

**Accepted (D-048):** when a task, a commitment or a meeting is created, up to three likely decisions are
offered and "no decision" is a valid answer; a report shows four buckets; a commitment may exist without
a decision. **Proposed:** the deterministic rules below, the reason on an explicit "none", the same offer
for ledger entries and time spans, and the refusals of `accepts_attachment`.

```python
def accepts_attachment(ref, attachment_kind):                  # DecisionDirectory
    d = resolve(ref)
    if d is None: return Refused('NOT_FOUND')
    if d.mirror_scope == 'full':
        return Refused('MIRRORED', detail='record it in the system of record of this decision until adoption')
    if d.status in ('closed', 'cancelled', 'superseded', 'withdrawn'):
        return Refused('DECISION_ENDED',
                       detail=f'ended on {local_date(d.closed_at)}; link to {successor(d) or "another decision"} or choose none')
    return Accept()                                            # drafts and active decisions accept; existing links stay

def likely_for_entry(ctx):        # ctx = {kind, text, person_refs, company_refs, goal_ref, occasion_time, reply_to_decision}
    exact = ([ctx.reply_to_decision] if ctx.reply_to_decision else []) + labels_in(ctx.text)   # a label beats a guess
    if exact:
        return [Offer(resolve(x), reason='named', preselected=True) for x in dedupe(exact)][:CFG.dec.entry_offers_max]
    scored = []
    for d in decisions(status='active'):
        if d.mirror_scope == 'full': continue
        s, why = 0, []
        if overlaps(targets(d, ('about',)) + [d.decider_ref], ctx.person_refs + ctx.company_refs):
            s += 4; why.append('same person or company')
        if ctx.goal_ref and ctx.goal_ref in targets(d, ('serves',)): s += 3; why.append('serves the same goal')
        if 'same person or company' in why and any(due_within(a, 14) for a in active_assumptions(d)):
            s += 2; why.append('a check is due soon')
        if days_since(last_activity_date(d)) <= CFG.dec.recent_activity_days: s += 1; why.append('recently active')
        if s >= 3: scored.append((-s, d.number, d, why))
    return [Offer(d.public_id, reason='; '.join(why), preselected=False)
            for _, _, d, why in sorted(scored)[:CFG.dec.entry_offers_max]]
```

The owner answers with one action. Picking an offer stores `link_answer = linked`. "No decision" with a
reason stores `explicit_none`. "New decision" creates a draft and links it. Giving no answer stores
`unanswered`. A record created by a path that never offered (an import, an app before INT) stores
`not_offered`. Every spoke stores its own bucket: CMT now; WRK, MTG, FIN and RHY later. There is never a
background queue (DEC-19, WRK-8).

```python
def unlinked_report(period):      # a DEC query over every registered probe; no copies
    rows = [p.unlinked(period) for p in attachment_probes()]          # per kind: totals per bucket + refs per bucket
    total = sum(r.total for r in rows)
    return {'by_kind': rows,
            'shares': {b: (sum(getattr(r, b) for r in rows) / total if total else None)
                       for b in ('linked', 'explicit_none', 'unanswered', 'not_offered')},
            'goal_only': sum(r.goal_only for r in rows),               # framed by a goal, serving no decision
            'decisions_without_execution': [d.public_id for d in decisions(status='active')
                                            if all_probe_totals(d) == 0
                                            and days_since(d.activated_at) > CFG.dec.recent_activity_days],
            'decisions_without_goal': [d.public_id for d in decisions(status='active')
                                       if not live_links(d, ('serves', 'tests'))],
            'decisions_without_origin': [d.public_id for d in decisions(status='active')
                                         if d.origin_kind == 'not_recorded'],
            'voids': assumptions_without_source_by_decision(),         # data_source_kind = 'none', per decision
            'items': refs_behind_each_number(rows)}                    # every number opens to its items
```

### 4.15 As-of and the decision history (proposed, D-049)

```python
def visible(row, T, axis='knowledge'):
    if axis == 'knowledge':  return K(row) <= T                    # what the system of record knew at T (default)
    if axis == 'instance':   return row.recorded_at <= T           # what this instance held at T (debugging)
    if axis == 'occurrence': return event_time(row) is not None and event_time(row) <= T   # unknown times excluded, counted
def voided_by(row, T): return row.voided_at is not None and row.voided_at <= T

def as_of(ref, T, axis='knowledge'):
    rows = load_all_rows(ref)                                      # every DEC table for this decision
    head = replay_head(current_head(ref), [v for v in versions(ref) if not visible(v, T, axis)])   # undo later versions
    view = DecisionView(head, [r for r in rows if visible(r, T, axis) and not voided_by(r, T)],
                        editions=[e for e in editions(ref) if visible(e, T, axis)])
    return AsOf(view, computed=compute_all(view, local_date(T)),    # health, due dates, waiting reasons at T.date
                coverage=coverage_notes(rows, axis))                # e.g. "before the first snapshot only v1's last state is known";
                                                                    # "3 rows with unknown event time excluded"

def decision_history(scope, period, window=CFG.dec.history_window_days):   # "what changed and why"
    out = []
    for d in decisions_in(scope):                                  # a decision, a subject ref, a kind, or all
        for a in assumptions_of(d):
            prev = None
            for c in assessments(a, voided=False, observed_in=period):
                if prev is None or c.state != prev.state:
                    nxt = next_state_change_time(a, c) or period.end
                    since = prev.observed_at if prev else c.observed_at - timedelta(days=window)
                    out.append({'assumption': a.ref, 'from': prev.state if prev else None, 'to': c.state,
                                'at': c.observed_at, 'check': c.ref, 'evidence': c.evidence_ref or 'owner statement',
                                'preceding': [f.ref for f in facts_bearing_on(a, between=(since, c.observed_at))]
                                           + [x.ref for x in readings(a, between=(c.observed_at - timedelta(days=window),
                                                                                  c.observed_at))],
                                'following_actions': [ev for p in attachment_probes()
                                                      for ev in p.timeline(d.public_id, between=(c.observed_at, nxt))],
                                'following_reviews': [r.ref for r in reviews_between(d, c.observed_at, nxt)]})
                prev = c
        out += [{'edition': e.ref, 'reason': e.reason, 'at': e.sealed_at} for e in editions_sealed_in(d, period) if e.n > 1]
    outcomes = [o.ref for d in decisions_in(scope) for o in outcomes_of(d) if in_period(o.occurred_at, period)]
    return {'changes': out, 'outcomes': outcomes, 'coverage': coverage_note(scope, period)}   # "no data in stored history" is valid
```

Every element carries a reference that opens to its source, with the transaction's actor and channel
(DEC-18). Nothing in the answer is phrased by a model. A record made more than `dec.retroactive_days`
after its decided date is flagged retroactive (DEC-13).

### 4.16 Loop metrics (computed from rows; stored daily as usage signals)

| Metric | Definition | Split by |
|---|---|---|
| Checks answered on their due day | assessments with `observed_date = due_answered` ÷ checks that fell due in the period | native · mirror (reconstructed, labelled) |
| Checks answered within 7 days | `observed_date − due_answered ≤ 7` ÷ due | same |
| Violation → review latency | median days from a VIOLATED assessment to the next review | trigger |
| Reviews overdue | count and median age of active decisions past `review_due` without a review | — |
| Closed with an outcome and a learning (**headline**) | per month, by outcome basis | basis |
| Unverifiable share | median over active decisions; the list of critical assumptions without a source | — |
| Revisions | editions by reason; corrections, completions, imports and source changes listed apart | reason |
| Retroactive share | new decisions recorded more than N days after their decided date | origin |
| Writes by channel | units of work per channel and owner-channel flag; **MCP-origin decisions and checks are counted separately** | channel |
| Waiting-list pulls | `waiting` calls per day by channel (CLI, MCP): the only usage measure before the bot exists | channel |
| Proposals | proposed, approved, rejected, waiting over 7 days, per origin | origin |
| Link buckets | linked, explicit none, unanswered, not offered, per spoke kind | kind |
| Shadow | unexpected differences per run; runs since the last unexpected one | run |

`coflow dec metrics --store` writes the day's values into `sys_usage_signals`; from 0B the supervisor
runs it daily. The same data gives the same numbers (AT-H2).

---

## 5. Module placement and ports (proposed, D-042)

### 5.1 Modules in the slice, and the tiers

The tier diagram of ARCHITECTURE §5.1 does not change. DEC stays in tier 2: it cannot move to tier 1,
because modules in one tier are independent and tier 1 holds PPL, which DEC refers to. Three edges change:

| Change | Why |
|---|---|
| Remove "DEC depends on WRK" from the DEC card | It was a cycle (WRK already depends on DEC) and an upward import. The DEC-9 card (a fact, an adjustment and a task) is orchestrated by the interface, each item its owner's own unit of work |
| Add `aln` as tier 8 in the `domain` import contract | ALN depends on GOL (tier 7) and was missing from the contract |
| DEC reads spokes only through `DecisionAttachmentProbe`; spokes and same-tier modules reach DEC through `DecisionDirectory` | DEC imports nothing above tier 2. SIG (same tier) and PPL and CAL (tier 1) can offer and show decisions without importing DEC |

| Layer | Module | In the slice | Notes |
|---|---|---|---|
| kernel | STO, IDS, EVT, POL, CFG, OPS, OBS, `kernel.context`, `kernel.ports` | the minimal parts of §1.3 | the rest in 0B |
| domain, tier 2 | **DEC** | all of §3.4 and §3.6 | never imports above tier 2 |
| domain, tier 3 | **CMT** (minimum) | §3.5 | imports `dec.api` or uses the port; implements the probe |
| interfaces | MCP (Streamable HTTP on loopback; the local stdio shim), ADM (the admin API and the CLI) | yes | the card composer lives in `interfaces/views` and joins DEC and CMT only through their `api` |
| contracts | `import_decisions_v1.schema.json` | yes | the v1 exporter writes it; any other exporter may |
| — | PPL, SIG, WRK, MTG, GOL, BOT, ACT, MDL, SRC, TML | no | people, goals, tasks and sessions are foreign refs with a context cache until their modules land |

### 5.2 The ports

#### `DecisionDirectory`, implemented by DEC [I1; offers in I3]

Used by SIG (quick logs naming a decision, from stage 1), PPL (the dossier line "open decisions about
this person"), CAL (a decision label in an event title), MTG (briefs), RHY (the plan) and the kernel
renderers. CMT, WRK, MTG, RHY, GOL, FIN and INT could import `dec.api` directly; they use the port so that
their suites run with a fake.

```python
class DecisionDirectory(Protocol):
    def resolve(self, text_or_ref: str) -> Resolved | Ambiguous | NotFound          # "D42", "D-0042", "V1_D42", aliases
    def info(self, ref: str) -> DecisionInfo | None                                 # public_id, title, kind, status, mirror, edition
    def state(self, ref: str, as_of: datetime | None = None) -> DecisionState       # label, ground, timeliness, reasons, share, review_due
    def accepts_attachment(self, ref: str, attachment_kind: str) -> Accept | Refused  # §4.14
    def open_for(self, subjects: list[str], *, kinds: list[str] | None = None, limit: int = 10) -> list[DecisionInfo]
    def likely_for_entry(self, ctx: EntryContext) -> list[Offer]                     # §4.14, at most 3 [I3]
    def waiting(self, today: date | None = None) -> list[WaitingItem]               # §4.8, each with question_context
    def projection(self, ref: str, audience: str) -> dict                           # §5.4: 'owner' | 'agent' in the slice
    def assumptions_to_probe(self, subjects: list[str], *, limit: int = 5) -> list[ProbeItem]   # §11.4 [Later 3]
```

#### `DecisionAttachmentProbe`, implemented by each spoke and used by DEC [I3: CMT]

```python
class DecisionAttachmentProbe(Protocol):
    kind: str                                    # 'commitment' | 'task' | 'meeting' | 'ledger_entry' | 'time_span'
    def summary(self, decision_ref: str, as_of: datetime) -> AttachmentSummary
        # total, open, done, dropped, overdue, shifted (count of due shifts), last_activity_at, refs (ids only)
    def timeline(self, decision_ref: str, between: tuple[datetime, datetime]) -> list[AttachmentEvent]
        # (occurred_at, recorded_at, ref, change), e.g. ('2026-11-19', …, 'F-10003', 'done'); ids and change names only
    def unlinked(self, period: Period) -> UnlinkedCounts
        # total, linked, explicit_none (by reason), unanswered, not_offered, goal_only, refs per bucket
```

The composition root registers every installed spoke's probe, and DEC iterates over the registered
probes. A missing module simply has no probe (EXT-6). Probes return ids, counts and change names, the same
discipline as events, so DEC stores another module's data only as frozen counts in
`dec_reviews.execution_summary_json`. This port is what lets `decision_history`, the review card and the
loop metrics show commitments without DEC importing CMT.

#### `EvidenceResolver`, implemented by evidence owners and used by DEC [I2: built-ins]

```python
class EvidenceResolver(Protocol):
    kinds: set[str]                                   # 'segment', 'message', 'session', 'document', 'app_envelope', …
    def resolve(self, ref: str) -> Evidence | None    # kind, occurred_at, data_class, text (for the quote check), offset
    def quote_matches(self, ref: str, quote: str) -> bool   # exact substring after NFC and whitespace normalisation
```

DEC calls it in the prepare phase of `add_fact`, `record_check`, `record_reading` and grounds, as reads
before the unit of work. The rules:
- a `journal`-class source → `Refused('JOURNAL_CLASS_INPUT')` (P-2);
- a quote that does not match → `Refused('QUOTE_NOT_IN_SOURCE')` for owner input, `quote_verified = 0` for
  imports;
- an unresolvable ref → stored with `quote_verified = 0` and counted as "source not resolvable".

Built-ins in the slice: `owner_statement` (no ref, always valid); `agent_session` (a client name plus a
session label as text; never resolvable, quote unverified); `foreign` (V1 refs, unresolvable until SIG
imports them). SIG implements segments, messages and sessions at stage 1; MTG outcomes at stage 5; GOL
centre spans at stage 3; FIN entries at 8.1a.

#### `GoalDirectory`, an existing port used by DEC [I1: shadow adapter]

DEC uses `state(ref, as_of)` (status, `status_changed_date`, `first_seen_date`, title) and, from stage 1,
`likely_goals(ctx)`. In the slice the implementation reads `dec_foreign_context` (v1 goals from the
snapshot, keyed by `V1_G…`), with the as-of rule of §4.13; at stage 1 WRK implements it, and at 8.2 GOL
does.

### 5.3 How each spoke and each app attaches, without cycles

| Spoke | Tier | Stores the link | Reads the decision through | Enforcement point | Stage |
|---|---|---|---|---|---|
| CMT commitments | 3 | `decision_ref`, `link_answer` | `DecisionDirectory` | `create_commitment`, `link_commitment`; `open_commitments` annotates each item whose decision ended ("decision ended: keep, drop or move?") by a query-time `info()` call, so no event handler is needed in the slice | I3 |
| WRK tasks | 4 | `wrk_tasks.decision_ref`, `link_answer` (WRK-3, WRK-8) | the port | `create_task`, `link_task` | 1 |
| WRK, then GOL, goals | 4 / 7 | `pursued_by_decision_ref`; DEC stores `serves` | the port | goal activation; decision creation | 1 / 8.2 |
| MTG meetings | 5 | `mtg_meeting_decisions(meeting, decision_ref, role)` | the port; the brief uses `open_for` and `assumptions_to_probe` | `plan_meeting` (a decision counts as a link to work, MTG-1) | 5 |
| MTG outcomes | 5 | nothing new: approved items become DEC facts, checks or proposals | DEC commands, orchestrated by the interface after the outcome card (MTG-4) | the outcome card | 5 |
| SIG sessions, notes | 2 | nothing: a DEC fact's `evidence_ref` points at the session or segment | the port (`resolve` for labels in quick logs) | a quick log "D-0042: …" routes to the DEC fact path | 1 |
| PPL people | 1 | nothing: DEC stores `about` | the port (`open_for(person)`) | — | 1 |
| RHY plan, spans | 6 | `rhy_activity_spans.decision_ref` | `dec.api.waiting` (a direct import is allowed) | a span rule or the owner | 2 / 6 |
| FIN entries | 3 | `fin_entries.decision_ref` | the port | `post_entry` | 8.1a |
| Interfaces (MCP, CLI; later the bot, INT) | — | nothing | may import every `api` | they orchestrate cards that span modules, each item in its owner's unit | 0A / 2 / 6 |
| LIVE app (a real-time online conversation agent) | — | its own ids; CoFlow stores refs | the INT projection `live_app` | envelope → proposals (§11) | 6 |
| EVENT app (offline events with a purpose known upfront) | — | its own ids; the attendance decision's ref travels in the brief | the projection `event_app` | batch import → proposals; commitments with `decision_ref` = the attendance decision | 3 (file), 6 (API) |
| UPLOAD (plain uploads of communications) | — | — | — | SIG; decisions only through outcomes and proposals | 4 / 6 |
| TEAM tool (external work with a team) | — | external refs | the projection `team_tool` | pull → external decision references, delegated commitments | 6 |
| AGENT (AI working sessions) | — | — | the MCP `agent` projection | `dec_create` when the owner asked for it (with the owner's quoted words), else `dec_propose` | 0A |

### 5.4 One decision, many projections

The card the owner sees and the brief an app reads are the same deterministic assembly (P-7) under
different audience profiles. Each profile is a versioned function with golden files, a privacy canary and
a `DATA_FLOWS.md` row. There is never "the internal record with fields hidden".

| Audience | Contains | Never contains | Stage |
|---|---|---|---|
| `owner` (CLI; the bot later) | everything; money per the destination's financial flag | the journal | 0A |
| `agent` (`mcp_<client>`) | statement, question, the share line, health with reasons, assumptions with due dates and sources, facts with refs, reviews, outcome, learnings, the attachment summary, editions with integrity, links, the instance role and the mirror authority | money amounts unless the client token has `financial = 1`; the journal | 0A |
| `event_app` | from an `attendance` decision: dates, role, venue, time zone, expected results (at most 3, with numbers), critical assumptions as hypotheses (at most 3), criteria, next-step menu, questions, the decision ref; the owner profile | money, other decisions, people from the registry unless the owner opts in per occasion | 3 (file), 6 (API) |
| `live_app` | per decision: ref, statement, review date, health in words; per probe: assumption ref, statement, metric, threshold, due date and its source, what counts as a violation, a probe question from a template | probabilities, money, the grounds' text, other people's dossiers, learnings | 6 |
| `team_tool` | statement, success criterion, review date, assumptions marked `shareable` | grounds, probabilities, `about` links, learnings, the journal, dossiers, money | 6 |
| cloud view (MCP-5) | owner-authored fields and structure of the `agent` profile, plus a count of withheld fragments | `untrusted_external` text unless enabled per client (PRV-14); journal tools; financial data unless enabled per client | 8.0 |
| `public` (build-in-public material) | only decisions with `publishability = public`, or the owner's abstracted text for `publishable_abstracted` | anything with `third_party_sensitive = 1` | the flag in 0A; tooling later |

### 5.5 One writer, processes and remote access

- `coflow run` starts `core`, the only process that opens the database for writing. It takes an OS-level
  instance lock on the data root, and runs the writer thread, the in-process event dispatcher, the MCP
  listener (Streamable HTTP on loopback, per-client tokens, Host and Origin checks) and the admin API.
- The CLI is a thin client of the admin API. If `core` is not running, the CLI starts an ephemeral core
  in-process for the duration of the command, under the same lock, so there is never a second writer.
- `coflow mcp-stdio` is a shim for local AI clients that forwards stdio to the loopback endpoint and never
  resolves the database path. Two AI clients on the same machine therefore share one core (MCP-1).
- Nothing in DEC depends on where the host is. Times are UTC plus the owner's zone; data roots are
  relative (CFG-4); a GPU is irrelevant to a model-free slice. Every write carries an actor, a channel, an
  interaction id and an idempotency key from day one, so remote clients and satellites retry safely.
- **Access, accepted (D-052):** the first step is the bot and the VPN; the owner's devices reach the
  instance over the private network (the SSH bridge from stage 1). Cloud AI clients come later, as the
  first stage-8 module, read-only first (MCP-5), through a separate `edge` container (PRV-13) behind the
  owner's relay (D-053). The core's own listener is never internet-facing.

---

## 6. Events

Envelope as ARCHITECTURE §6.2. `subject` is the public id; `data` holds `entity` and `changed` (field
names only); `dataversion = 1`. Events are emitted inside the unit of work that makes the change. A
time-driven change (a review becomes overdue at midnight) emits nothing in the slice and is visible
through `waiting` (pull). The scheduler's `check_due` event arrives in 0B.

| Type | Emitted by | `changed` (examples) | Declared consumers | Incr. |
|---|---|---|---|---|
| `coflow.dec.decision.created` | `create_decision`, proposal approval, fork decide | `["status","kind"]` | OBS; SRC, TML (1) | I2 |
| `coflow.dec.decision.updated` | `update_decision`, `set_manual_flag`, `set_publishability` | field names | SRC (1) | I2 |
| `coflow.dec.decision.activated` | `activate_decision` | `["status","current_edition"]` | BOT (2) | I2 |
| `coflow.dec.decision.reviewed` | `review_decision` | `["review_due"]`, `["current_edition"]` | the MTG brief refresh (5), RHY (2) | I2 |
| `coflow.dec.decision.closed` / `cancelled` / `superseded` / `withdrawn` | review, undo | `["status"]` | WRK (1), GOL (8.2), BOT (2) | I2 |
| `coflow.dec.decision.imported` | importer | field names | OBS | I1 |
| `coflow.dec.decision.adopted` | `adopt_mirrors` | `["mirror_of"]` | OBS | I3 |
| `coflow.dec.edition.sealed` | `seal` | `["current_edition"]` | — | I1 |
| `coflow.dec.assumption.added` / `superseded` / `dropped` | assumption commands | field names | — | I2 |
| `coflow.dec.assumption.checked` | `record_check` | `["state","next_check_at"]` | BOT (2) | I2 |
| `coflow.dec.assumption.state_changed` | `record_check`, when the effective state changes | `["state"]` | BOT: "violated" asks at once (2); RHY (2) | I2 |
| `coflow.dec.assumption.postponed` | `postpone_check` | `["next_check_at"]` | — | I2 |
| `coflow.dec.reading.recorded` | `record_reading` | `["proposed_state"]` | BOT (2) | I2 |
| `coflow.dec.fact.added` / `voided` | `add_fact`, `correct_fact`, undo | `["phase","kind"]` | TML (1) | I2 |
| `coflow.dec.link.added` / `removed` | `link`, `unlink` | `["role"]` | — | I2 |
| `coflow.dec.fork.opened` / `decided` / `dissolved` / `delegated` | fork commands | `["status"]` | — | I2 |
| `coflow.dec.proposal.proposed` / `approved` / `rejected` | proposal commands | `["status"]` | BOT: an inline card (2) | I3 |
| `coflow.dec.import.completed` | importer | `[]` (the subject is the run id) | OBS | I1 |
| `coflow.dec.integrity.mismatch` | `integrity()` on read, at most once per edition and day | `["edition"]` | OBS | I2 |
| `coflow.dec.assumption.check_due` | the daily scheduler, once per (assumption, due date) | `[]` | BOT (2) | 0B |
| `coflow.cmt.commitment.created` / `status_changed` / `due_shifted` / `linked` | CMT commands | `["status"]`, `["due_date"]`, `["decision_ref"]` | SRC (1), BOT (2) | I3 |

The event schema snapshot test fails on any payload field other than ids, entity type and changed names.
A canary value written into a decision never appears in `sys_events` (AT-K6).

---

## 7. API

All decision behaviour sits behind `dec.api`, and commitment behaviour behind `cmt.api`. MCP tools, the
CLI and later the bot and INT endpoints are thin adapters over them (D-041).

### 7.1 Conventions and refusal codes

- Every command takes a context: `actor` (`owner`, `cli`, `mcp_<client>`, `import_v1`, `import_log`,
  `app_<client>`, `bot`), `channel`, `owner_channel` (set by the interface, never by the caller: the local
  CLI is an owner channel, MCP is not), `interaction_id`, `source_ref`, an `idempotency_key` (given by the
  client, or derived from the interaction id and a payload hash) and an optional `expected_version`. It
  runs as one unit of work and returns its result plus the ids of its events. A retry with the same key
  returns the first result (`sys_command_keys`).
- Inside a unit of work a command calls only kernel services (`IDS.issue_id`, `EVT.publish`), never
  another module's command. Reads it needs from other modules or ports (probes, `EvidenceResolver`,
  `GoalDirectory`) happen before the unit opens.
- Errors are typed: `NotFound(ref)`, `Ambiguous(candidates[])`, `Refused(code, detail, missing[] |
  allowed[])` and `Conflict(current_version)`. Over MCP they are returned as `{"error": {"type", "code",
  "detail", "missing", "allowed", "candidates"}}`. Every `Refused` names what would make the call valid.
- Queries carry `as_of` (and an axis), `coverage`, `stale` and **the instance role**. Answers about
  mirrors say "mirrored from V1, snapshot exported at …; read-only here". Money is withheld per
  destination, with the coverage note "amounts withheld (financial flag off)".
- Dates in arguments are `YYYY-MM-DD`. Free-text dates are never parsed from command arguments; only
  thresholds and statements are, and only by the documented table (§4.6).

**Refusal codes** (the `RefusalCode` enumeration):
- activation and seal: `ACTIVATION_GATE`, `SEALED_USE_REVISE`, `USE_A_REVIEW`, `NATIVE_OTHER_DECIDER`,
  `COMPLETION_NOT_PENDING`;
- lifecycle: `NOT_FOUND`, `TERMINAL_DECISION`, `DRAFT_ACTIVATE_FIRST`, `MIRRORED`, `DECISION_ENDED`,
  `FORK_NOT_OPEN`;
- review dates: `REVIEW_DATE_REQUIRED`, `REVIEW_DATE_OUT_OF_RANGE`;
- revise: `REVISION_EMPTY`, `REVISE_BASIS_REQUIRED`, `TRIGGER_FACT_REQUIRED`;
- closing and outcomes: `REASON_REQUIRED`, `OUTCOME_REQUIRED`, `OUTCOME_BASIS_REQUIRED`,
  `OUTCOME_UNKNOWN_NEEDS_NOT_CONFIRMED`, `RESOLVED_NEEDS_EVIDENCE`, `REPORTED_NEEDS_A_REPORT`,
  `LEARNING_REQUIRED`, `SUCCESSOR_INVALID`;
- assumptions and checks: `FOREIGN_ASSUMPTION` ("A-03 belongs to D-0907"), `FOREIGN_EVIDENCE`,
  `GROUNDS_ARE_BASIS`, `ASSUMPTION_NOT_ACTIVE`, `STATE_NOT_ALLOWED`, `NEXT_CHECK_OUT_OF_RANGE`,
  `POSTPONE_OUT_OF_RANGE`, `DATA_SOURCE_KIND_REQUIRED`, `PROBABILITY_NOT_OWNER`,
  `PROBABILITY_OUT_OF_RANGE`, `EVENT_TIME_IN_FUTURE` (beyond one day of tolerance);
- evidence: `JOURNAL_CLASS_INPUT`, `QUOTE_NOT_IN_SOURCE`;
- links: `LINK_ROLE_UNKNOWN`, `LINK_SELF`, `LINK_CYCLE`;
- proposals and MCP-origin writes: `OWNER_CHANNEL_REQUIRED`, `OWNER_QUOTE_REQUIRED`,
  `PROPOSAL_REJECTED_BEFORE`, `PROPOSAL_ORIGIN_SWITCHED_OFF`, `NOT_PROPOSED`;
- publishability: `PUBLISHABILITY_LOCKED`;
- undo: `UNDO_WINDOW_PASSED`, `UNDO_HAS_LATER_WRITES`, `NOT_UNDOABLE`;
- import: `IMPORT_ROLE`, `IMPORT_NOT_SYNTHETIC`, `IMPORT_FORMAT_UNSUPPORTED`, `IMPORT_SOURCE_CONFLICT`,
  `IMPORT_HASH_MISMATCH`, `IMPORT_ADOPTED`;
- cases and adoption: `CASE_ROLE`, `ADOPTION_GATE`, `NATIVE_IN_VALIDATION`;
- commitments: `DONE_NEEDS_TIME`, `SHIFT_NEEDS_REASON`, `EXPLICIT_NONE_NEEDS_REASON`,
  `SUGGESTED_DONE_FROM_PROPOSAL_ONLY`;
- store (programming errors): `STORE_STAMPED_FIELD` (a caller passed `tx` or `recorded_at`).

### 7.2 DEC commands

| Command | Key arguments | Result | Errors (besides NotFound, Conflict, MIRRORED) | Incr. |
|---|---|---|---|---|
| `create_decision` | `title`; optional `question`, `statement`, `kind`, `decider`, `decider_ref`, `depth`, `reversibility`, `context`, `known`, `unknowns[]`, `would_help`, `success_criterion`, `expected{metric,target,unit,by,text}`, `confidence`, `stakes[]`, `not_doing`, `review_due`, `decided_at` (a date, `today` or `unknown`), `origin{kind,ref,quote}`, `options[]` (one may be `chosen`), `grounds[]`, `assumptions[]`, `links[]`, `publishability`, `third_party_sensitive`, `activate=false` | `public_id`, `status`, `missing_for_activation[]`, `advisory[]`, `proposed_depth`, `related_learnings[]`, `follows_candidates[]` | `ACTIVATION_GATE` when `activate=true`; `Ambiguous` for person or company refs; `NATIVE_OTHER_DECIDER`; over MCP, an empty `origin.quote` → `OWNER_QUOTE_REQUIRED` ("quote the owner's words, or use dec_propose"); `NATIVE_IN_VALIDATION` in the validation role (§10.1) | I2 |
| `update_decision` | `ref`, `fields{}`, `add_stakes[]?`, `reason?` | `changed[]`, `completion_pending` | `SEALED_USE_REVISE` for basis fields of an active native decision (and for a non-empty basis field of a reconstructed one); `USE_A_REVIEW` for `review_due` | I2 |
| `activate_decision` | `ref`, `chosen_option?`, `decided_at?` | `edition`, `seal` (12 hex characters), `health`, `related_learnings[]` | `ACTIVATION_GATE` | I2 |
| `complete_decision` | `ref` | `edition` (reason `completion`) | `COMPLETION_NOT_PENDING` | I2 |
| `add_option` | `decision_ref` or `fork_ref`, `text`, `chosen?`, `why_rejected?` | `code` | `chosen` on an active decision → `SEALED_USE_REVISE`; on an active decision the option is allowed, flagged `recorded_before_choice = no` and outside the edition | I2 |
| `add_assumption` | `ref`, `statement`, `metric?`, `threshold{comparator,value,value2,unit,by_date,text}?`, `judge_from?`, `data_source{kind,text,ref}`, `frequency?`, `next_check_at?`, `critical=true`, `scope?`, `check_cost?`, `class_tag?`, `probability?` | `code`, `due`, `due_source`, `added_after_seal`, `completion_pending` | `DATA_SOURCE_KIND_REQUIRED` ("use `none` to record that nothing can check it"); `PROBABILITY_NOT_OWNER` when the call is not in an owner channel and does not carry the owner's quoted words; `PROBABILITY_OUT_OF_RANGE` | I2 |
| `supersede_assumption` | `assumption_ref`, changed fields, `reason` | the new `code` | `REVISION_EMPTY` if nothing changes | I2 |
| `drop_assumption` | `assumption_ref`, `reason` | — | `REASON_REQUIRED` | I2 |
| `record_check` | `assumption_ref`, `state`, `observed_value?`, `observed_text?`, `observed_at?` (default live), `evidence{kind,ref,quote}?`, `note?`, `next_check_at?`, `accept_reading?` | `check_ref`, `next_due`, `due_source`, `decision_state` (+ "review now" when VIOLATED) | `STATE_NOT_ALLOWED`; `TERMINAL_DECISION` ("add a fact instead"); `ASSUMPTION_NOT_ACTIVE`; `JOURNAL_CLASS_INPUT`; `QUOTE_NOT_IN_SOURCE`; `NEXT_CHECK_OUT_OF_RANGE`; `EVENT_TIME_IN_FUTURE` | I2 |
| `record_reading` | `assumption_ref`, `value` or `value_text`, `unit?`, `observed_at?`, `source{kind,ref,quote}` | `reading_ref`, `proposed_state`, `no_proposal_reason` | as for `record_check` | I2 |
| `postpone_check` | `assumption_ref`, `until`, `reason` | `next_due` | `POSTPONE_OUT_OF_RANGE`, `REASON_REQUIRED` | I2 |
| `add_fact` | `ref`, `text`, `phase='monitoring'`, `kind='observation'`, `claimed_outcome?`, `occurred_at?`, `evidence{kind,ref,quote}?`, `assumption_refs[]?`, `bearing?` | `fact_ref` | `FOREIGN_ASSUMPTION` in every channel; `JOURNAL_CLASS_INPUT`; `QUOTE_NOT_IN_SOURCE`; `GROUNDS_ARE_BASIS` for `phase='ground'` on an active native decision | I2 |
| `correct_fact` | `fact_ref`, `text`, `reason` | a new `fact_ref` (the old one voided, the new one pointing at it) | — | I2 |
| `review_decision` | `ref`, `action`, `verdict?`, `notes?`, `next_review_due?`, `trigger?`, `trigger_ref?`, `revision{…}?`, `revise_basis?`, `is_correction?`, `outcome{kind,basis,evidence_refs[],measured_value,expected_vs_actual,owner_statement}?`, `learning{confirmed,refuted,limits,next_step,same_again}?`, `successor_ref?`, `occurred_at?` | `review_ref`, `status`, `edition`, `health` | §4.10 | I2 |
| `set_manual_flag` | `ref`, `flag` or `null`, `reason` | — | `REASON_REQUIRED`; refused unless active | I2 |
| `set_publishability` | `ref`, `value`, `reason`; or `third_party_sensitive` | — | `PUBLISHABILITY_LOCKED` for `third_party_sensitive = 1`, and for clearing that mark on an active decision; `OWNER_CHANNEL_REQUIRED` for `public` and for clearing the mark | I2 |
| `link` / `unlink` | `ref`, `role`, `target_ref`, `note?` / `link_id`, `reason` | `link_id`, `resolution` | `LINK_ROLE_UNKNOWN`, `LINK_SELF`, `LINK_CYCLE` (in `part_of`, `supersedes`) | I2 |
| `open_fork` | `question`, `trigger{text,ref}?`, `opened_at?`, `decider?`, `deadline?`, `options[]?` | `Q-…` | — | I2 |
| `decide_fork` | `fork_ref`, `chosen_option`, decision fields, `activate?` | `D-…` | `FORK_NOT_OPEN`; `ACTIVATION_GATE` when `activate` | I2 |
| `dissolve_fork` / `delegate_fork` / `move_fork_deadline` | `fork_ref`, `reason` / `to_ref` / `deadline` | — | `FORK_NOT_OPEN`; `REASON_REQUIRED` | I2 |
| `propose_decision` | `payload`, `origin{kind,ref,quote}` | `proposal_id`, `match_candidates[]` | `PROPOSAL_REJECTED_BEFORE`, `PROPOSAL_ORIGIN_SWITCHED_OFF` | I3 |
| `approve_proposal` / `reject_proposal` | `proposal_id`, `edits?` / `class`, `reason` | the result ref | `OWNER_CHANNEL_REQUIRED` (an MCP call can never approve); `NOT_PROPOSED` | I3 |
| `import_snapshot` | `file`, `mode=shadow\|final\|dry_run` | the run report | `IMPORT_ROLE`, `IMPORT_NOT_SYNTHETIC`, `IMPORT_FORMAT_UNSUPPORTED`, `IMPORT_HASH_MISMATCH`, `IMPORT_SOURCE_CONFLICT`, `IMPORT_ADOPTED` | I1 |
| `import_decision_log` | `file`, `only[]` (the entry ids the owner selects) | the run report | `IMPORT_FORMAT_UNSUPPORTED` | I2 |
| `run_case` | `case_file` | the case result (§10.7) | `CASE_ROLE` (the role must be `validation`, `production` after the adoption, or `dev` for synthetic cases) | I3 |
| `adopt_mirrors` | `issuer`, `confirm_phrase` | counts | `ADOPTION_GATE` (names every missing condition) | I3 |
| `undo` | `undo_entry` | — | `UNDO_WINDOW_PASSED`, `UNDO_HAS_LATER_WRITES`, `NOT_UNDOABLE` | I2 |

### 7.3 DEC queries

| Query | Arguments | Returns | Incr. |
|---|---|---|---|
| `decision_context` | `ref`, `detail=brief\|full`, `as_of?`, `axis?`, `audience='owner'` | the card, in this order: the integrity line, when not `ok`; the share line; health with ground, timeliness and every reason; the statement; why it waits; `question_context`; assumptions with effective state, due date and source, last check and readings; facts split into ground and monitoring with refs; reviews; the outcome; learnings; editions with integrity; links; the attachment summary from every probe; the mirror status and the instance role | I1 |
| `list_decisions` | `status?`, `kind?`, `health?`, `linked_to?`, `mirror?`, `limit` | one line each: id, title, label, share, review date, first reason | I1 |
| `waiting` | `today?` | §4.8, each item with its `question_context` | I1 |
| `drafts_to_finish` | — | §4.8 | I2 |
| `assumption_due` | `assumption_ref`, `at?` | `(date, source)` and the last assessment | I1 |
| `health` | `ref`, `as_of?` | label, ground, timeliness, reasons, share, `bet` | I1 |
| `integrity` | `ref` or `all` | per edition `ok` / `ok_with_erasures` / `changed`; live `drift`; completion pending | I1 |
| `as_of` | `ref`, `t`, `axis` | the record as known at `t` | I1 |
| `decision_history` | `scope` (a decision, a subject ref, a kind, or `all`), `period` | §4.15 | I3 |
| `related_learnings` | `kind?`, `subjects[]`, `class_tags[]` | §4.11 | I2 |
| `forks` | `status?` | open questions with age and deadline | I2 |
| `proposals` | `status?`, `origin_kind?` | with the approval rate per origin | I3 |
| `unlinked_report` | `period` | §4.14 | I3 |
| `loop_metrics` | `period` | §4.16 | I3 |
| `shadow_report` | `run_id?` | §10.6 | I1 |
| `cases` | — | the named cases with their last result | I3 |

### 7.4 CMT commands and queries [I3]

| Command or query | Arguments | Errors |
|---|---|---|
| `create_commitment` | `debtor_ref`, `creditor_ref`, `initiator_ref?`, `what`, `success_criterion?`, `due_date?`, `due_basis`, one of `decision_ref` / `no_decision_reason` / nothing (= `unanswered`), `goal_ref?`, `source{ref,quote}?` | the `DecisionDirectory.accepts_attachment` refusal (`DECISION_ENDED`, `MIRRORED`); `EXPLICIT_NONE_NEEDS_REASON` |
| `change_commitment_status` | `ref`, `to`, `reason` (required for `dropped`, `unclear`), `done_at` (a date, `now` or `unknown`) | `DONE_NEEDS_TIME`; `SUGGESTED_DONE_FROM_PROPOSAL_ONLY`; `REASON_REQUIRED` |
| `shift_commitment_due` | `ref`, `new_due`, `reason` | `SHIFT_NEEDS_REASON` |
| `link_commitment` | `ref`, `decision_ref` or `no_decision_reason` | as for create |
| `open_commitments` | `debtor?`, `creditor?`, `decision_ref?`, `due_before?` | — (each item is annotated "decision ended" when its decision is terminal) |
| `commitment` | `ref` | — (returns it with its history) |
| the probe: `summary`, `timeline`, `unlinked` | §5.2 | — |

A commitment entered through MCP or the CLI is offered its likely decisions at entry (`likely_for_entry`,
§4.14); the answer is stored with it. A commitment without a decision is valid (accepted, D-048).

### 7.5 Wire format and the local transport (proposed)

MCP, the admin API and the CLI serve **the same view functions** (`interfaces/views`), so AT-M1 compares
JSON, not prose. Each view has a JSON Schema generated from the definitions below and checked in CI.

**Envelope.** Every answer is

```json
{"server": "coflow-v2", "view": "waiting", "instance_role": "validation",
 "as_of": "2026-11-15T05:00:00.000Z", "axis": "knowledge", "timezone": "Europe/Berlin",
 "coverage": [], "stale": false, "authority": "mirrored from V1; read-only here", "value": {}}
```

An error keeps `server`, `instance_role` and `view: "error"` and adds the error object of §7.1.

**Scalars.** Instants as stored (§3.1); dates `YYYY-MM-DD`; decimals as strings; sets as sorted lists.
The unverifiable share is the exact pair `{"n": 2, "m": 5}` (n of the m pool assumptions cannot be
checked), `null` without a pool; a decimal, where one is shown, is n/m rounded to 2 places with
`ROUND_HALF_EVEN`. `short(s, k)` is the first k code points of `NFC(s)`, followed by `…` when cut.

**Waiting.** `value = {"today": date | null, "count": int, "items": [WaitingItem], "drafts": [Draft]}`;
`drafts` is always `[]` in I1 and holds `drafts_to_finish` from I2, so `dec_waiting` returns the same
shape in every increment.

| Object | Fields |
|---|---|
| `WaitingItem` | `position` (1-based), `subject_kind` (`decision`, `fork`, `proposal`), `ref`, `number`, `title`, `health` (a `State` or null), `reasons` ([`Reason`]), `question_context` (a `QuestionContext` or null), `authority` |
| `State` | `ref`, `label`, `ground`, `timeliness` (sorted kinds), `reasons` (words), `share` (`{n, m}` or null), `review_due`, `bet`, `badge` |
| `Reason` | `kind`, `due` (date or null), `code` (or null), `critical` (bool or null), `due_source` (or null), `status` (or null), `text` |
| `QuestionContext` | `one_line`, `share_line`, `health`, `reasons`, `last_fact` (`{ref, text, occurred_at, age_days, evidence}` or null), `passed` ([`{what, date}`]), `goals` ([`{ref, title, status, since}`]), `asked` (`{kind, ref, statement, threshold_text, due, due_source}` or null), `execution` (counts per probe kind), `postponements_since_review`, `likely_actions` ([words]) |
| `Draft` | `ref`, `title`, `missing` ([field names]) |

`decision_context` and `health` use the same `State`, `Reason` and share forms. `coflow dec waiting
--json` (the global `--json` flag) prints exactly the payload that `dec_waiting` returns, and AT-M1
compares those two and the query's own result. `--brief` renders the same payload as text: a header
`Waiting on <date> (<n> items)`, at most 8 lines `<position>. <ref> <title cut to 40> | <first reason>
[(+k)] -> <first likely action>`, a line `... <n> more` when cut, and a footer with the instance role and
the authority.

**The local transport.**
- `coflow mcp token new --client NAME --scope read|write [--financial]` prints the token once: `cfm_`
  followed by 64 hex characters (256 random bits from the kernel's one source of randomness). Only its
  SHA-256 hex is stored (`mcp_clients.token_hash`); a new token for a client replaces the old one.
- `coflow run` serves one listener on `127.0.0.1:<port>` (default 8741; per-instance configuration,
  PRV-5): `/mcp` (Streamable HTTP, a bearer token on every request), `/admin/v1/<operation>` and
  `/healthz`. Every route checks the Host header against `127.0.0.1:<port>`, `localhost:<port>` and
  `[::1]:<port>` (else 421), and an `Origin`, when present, against the same origins with `http://`
  (else 403).
- `coflow mcp-stdio [--url URL] [--token-file PATH]` takes the endpoint from `--url`, else
  `COFLOW_MCP_URL`, else `http://127.0.0.1:8741/mcp`, accepting loopback URLs only, and the token from
  `--token-file` or `COFLOW_MCP_TOKEN`, never from the command line. It never resolves a data root.
- The CLI reads the admin and import tokens and the listener URL from `<data-root>/run/core.json`, which
  `coflow run` writes at start with owner-only permissions (mode 0600 where the OS supports it) and
  removes at shutdown; those tokens are valid for that run only. With no core running, the CLI starts an
  ephemeral core in process under the same lock (§5.5).

---

## 8. MCP tools

Every decision tool lives in the **`dec_` namespace** and every commitment tool in `cmt_`. While the
forecast pilot runs, the owner's AI clients may have both the v1 server and the v2 server connected, so
v1's tool names are not reused and an agent cannot confuse the two systems by name. The v2 server
advertises a distinct name (`coflow-v2`), and every answer states the instance role and, for mirrors, the
authority. The mirror guard refuses writes to v1-authority records, so a confused agent cannot change the
pilot's data in either system.

A new tool is a write tool by default (MCP-1). Every write tool has an undo handler or is marked "not
undoable" (MCP-4). No tool approves anything (P-4). The tool descriptions tell agents the rule: write only
what the owner said or typed, quote the owner's words in `origin.quote` or the check's note, and use
`dec_propose` for anything inferred. The catalogue is generated from code and checked in CI (MCP-3).

| Tool | R/W | Maps to | Undo handler | Incr. |
|---|---|---|---|---|
| `dec_list` | R | `list_decisions` | — | I1 |
| `dec_context` | R | `decision_context` (audience `agent`, `as_of`) | — | I1 |
| `dec_waiting` | R | `waiting` with `drafts` (`drafts_to_finish`, empty in I1), in the shape of §7.5; OBS records a "pull" usage signal | — | I1 |
| `dec_integrity` | R | `integrity` | — | I1 |
| `dec_shadow_report` | R | `shadow_report` | — | I1 |
| `dec_history` | R | `decision_history` | — | I3 |
| `dec_related_learnings` | R | `related_learnings` | — | I2 |
| `dec_forks` | R | `forks` | — | I2 |
| `dec_proposals` | R | `proposals` | — | I3 |
| `dec_link_report` | R | `unlinked_report` | — | I3 |
| `dec_metrics` | R | `loop_metrics` | — | I3 |
| `cmt_list` | R | `open_commitments` | — | I3 |
| `dec_create` | W | `create_decision` (origin `agent_session`; the owner's quoted words required) | a draft with no later writes inside the window → `withdrawn` (the row and the number stay) | I2 |
| `dec_update` | W | `update_decision` | restore the previous values from `dec_versions` if no later version of the same field exists | I2 |
| `dec_activate` | W | `activate_decision` | **not undoable** (a seal is a commitment; cancel or revise instead) | I2 |
| `dec_complete` | W | `complete_decision` | not undoable | I2 |
| `dec_add_option` | W | `add_option` | void the option while the decision is a draft; otherwise not undoable | I2 |
| `dec_add_assumption` | W | `add_assumption` | drop it (reason "undo") if it has no checks | I2 |
| `dec_supersede_assumption` | W | `supersede_assumption` | drop the successor if it has no checks, and reactivate the predecessor | I2 |
| `dec_record_check` | W | `record_check` | void the check and restore `next_check_at` | I2 |
| `dec_record_reading` | W | `record_reading` | void the reading if no check accepted it | I2 |
| `dec_postpone_check` | W | `postpone_check` | void the postponement and restore `next_check_at` | I2 |
| `dec_add_fact` | W | `add_fact` | void the fact | I2 |
| `dec_review` | W | `review_decision` | keep, adjust, close, cancel, supersede: void the review (and the outcome and learning it wrote) and restore status, review date and the previous outcome from its `before` snapshot, if it is the latest write within the window; revise and correction: **not undoable** (record a correcting review) | I2 |
| `dec_link` | W | `link` / `unlink` | the inverse | I2 |
| `dec_open_fork`, `dec_decide_fork`, `dec_settle_fork` | W | `open_fork`; `decide_fork`; `dissolve_fork`, `delegate_fork`, `move_fork_deadline` | a fork with no decision and no later writes → `withdrawn`; `decide_fork` is not undoable once the decision is active | I2 |
| `dec_set_flag` | W | `set_manual_flag` | restore the previous flag | I2 |
| `dec_propose` | W | `propose_decision` | withdraw the proposal | I3 |
| `cmt_create`, `cmt_set_status`, `cmt_shift_due`, `cmt_link` | W | the CMT commands | a commitment with no history → `withdrawn` / restore the previous status, due date or link | I3 |

**Not exposed over MCP**: `approve_proposal`, `reject_proposal`, `import_snapshot`,
`import_decision_log`, `run_case`, `adopt_mirrors`, and `set_publishability` (the slice has no MCP tool
for it, so `public` is never set over MCP: publication is an outward consequence, and clearing the
third-party mark is an owner-channel action). These are owner-channel or
admin actions. A read-only token sees only the R tools. Decisions and checks created over MCP are real
writes (MCP-4), and the metrics count them separately (§4.16), so whether the owner's own words or an
agent's inference produced them stays visible.

**Cloud AI clients** (stage-8 module 0, MCP-5, accepted as a later step in D-052) receive the R tools
only, through the cloud view of §5.4: `untrusted_external` text withheld by default (PRV-14), no journal
tools, financial data off unless enabled per client. Writes for cloud clients come later as a separate
resource with its own audience, off by default.

---

## 9. CLI

All writes go through the core's loopback admin API with a scoped token (ARCHITECTURE §6.8, scopes
`admin` and `import`). The local CLI is an owner channel and may approve proposals.

```
coflow init --role dev|validation [--data-root PATH] [--timezone ZONE] [--issuer CODE]
coflow doctor                                       # role, lock, data root outside any repository, schema revision
coflow run [--port 8741]                            # core: writer, MCP listener, admin API
coflow mcp-stdio [--url URL] [--token-file PATH]    # shim for local AI clients (no database access, §7.5)
coflow mcp token new --client NAME --scope read|write [--financial]

coflow dec import v1 SNAPSHOT.json [--final | --dry-run]       # validation role only; dev: synthetic files only
coflow dec import log docs/DECISIONS.md --only D-036,D-037      # the project's decision log, selected entries
coflow dec shadow [--run latest|N]                  # totals per class; every unexpected line with both values
coflow dec waiting [--date YYYY-MM-DD] [--drafts] [--brief]
coflow dec show D-0042 [--full] [--as-of 2026-11-01T12:00Z] [--axis knowledge|instance|occurrence]
coflow dec list [--status active] [--health WATCH] [--kind test] [--mirror V1]
coflow dec new "<title>" [--light|--full] [--kind test|pursue] [--review YYYY-MM-DD] [--decided YYYY-MM-DD|today|unknown] [--from FILE.yaml]
coflow dec activate D-0042 [--option O-02] [--decided YYYY-MM-DD|today|unknown]
coflow dec complete D-0042
coflow dec option D-0042 "<text>" [--chosen] [--why-rejected "<text>"]     # --chosen on drafts only
coflow dec assume D-0042 "<statement>" --metric "<m>" --cmp ">=" --value 3 --unit signed --by 2026-11-20 \
       --source manual [--every weekly|monthly|quarterly|ad_hoc] [--not-critical] [--class demand] [--p 70]
coflow dec supersede-assumption D-0042_A-02 --source internal_query --reason "<why>"
coflow dec check D-0042_A-01 holding|drifting|violated|unverifiable|unknown [--value 4] [--observed 2026-11-15] \
       [--next YYYY-MM-DD] [--note "<…>"] [--accept RD-001]
coflow dec read  D-0042_A-01 --value 4 --unit signed [--observed …] [--source owner_statement]
coflow dec postpone D-0042_A-01 --until 2026-11-22 --reason "<why>"
coflow dec fact D-0042 "<text>" [--on A-01,A-02] [--bearing supports|contradicts] [--ground] \
       [--kind outcome_report --claims done] [--occurred …] [--quote "<…>" --ref <ref>]
coflow dec review D-0042 keep|adjust --next 2026-12-01 [--verdict "<…>"]
coflow dec revise D-0042 --next 2026-12-15 (--trigger-fact FT-007 | --change-of-mind "<why>" | --correction) \
       --set statement="<…>" [--choose O-03]
coflow dec close D-0042 --outcome success|failure|mixed|unknown --basis resolved|reported|not_confirmed \
       [--evidence CK-003,RD-002] --confirmed "<…>" [--refuted "<…>"] --limits "<…>" --next-step "<…>" [--same yes|no|unsure]
coflow dec cancel D-0042 --reason "<…>"   |   coflow dec supersede D-0042 --by D-1007
coflow dec flag D-0042 zombie|off_track|clear --reason "<…>"
coflow dec publish D-0042 private|abstracted|public --reason "<…>"   |   coflow dec third-party D-0042 on|off
coflow dec link D-0042 follows D-1003     |   coflow dec unlink <link-id> --reason "<…>"
coflow dec fork open "<question>" [--option "<a>" --option "<b>"] [--deadline YYYY-MM-DD]
coflow dec fork decide Q-0007 --option O-01 [--activate]   |   coflow dec fork dissolve Q-0007 --reason "<…>"
coflow dec proposals [--status proposed]  |  coflow dec proposals approve 12 [--edit field=value]  |  … reject 12 --class advice_given --reason "<…>"
coflow dec history D-0042 --from 2026-09-01 --to 2026-12-01   |   coflow dec metrics [--period 30d] [--store]
coflow dec links-report --period 2026-W46
coflow dec integrity D-0042 | --all
coflow dec undo <undo-entry>
coflow dec case run CASE.yaml             |   coflow dec cases
coflow dec adopt --issuer V1 --confirm "<phrase>"
coflow cmt new "<what>" --from self --to <ref> --due 2026-11-20 (--decision D-1002 | --none routine) [--criterion "<…>"]
coflow cmt list [--decision D-1002]  |  coflow cmt done F-10003 --at 2026-11-19|now|unknown  |  coflow cmt shift F-10003 --due … --reason …
```

The CLI prints the share line and, when it is not `ok`, the integrity line first on every `show`. Without
`--decision` or `--none`, `cmt new` prints the offers of §4.14 and stores the answer the owner gives (or
`unanswered`). The global flag `--json` prints the view payload of §7.5 instead of text.

**A daily pull before the bot exists.** v2 cannot push anything before stage 2, so it would otherwise serve
only for comparison until December. `coflow dec waiting --brief` prints a compact, deterministic morning
list: at most 8 items, one line each, with the reason and the likely first action. A documented recipe
runs it every morning from an AI client's scheduled prompt that calls `dec_waiting`. Until the stage-0B
supervisor exists, an owner-side operating-system scheduler entry that only runs the read-only `coflow
dec waiting --brief` is a documented exception to OPS-2 (all periodic jobs in one supervisor), removed in
0B. Every pull is recorded as a usage signal by channel, so the owner's real daily use is measurable from
the first week.

---

## 10. Import, shadow, real cases and adoption

**Accepted (D-039):** shadow first; snapshots flow from v1 to v2 only; v2 computes the waiting list, check
dates and health itself so the owner can compare; when the owner's real cases pass, decisions move to v2
for good and v1's decision module becomes read-only; never two writers; not before 1 December 2026 unless
the owner changes that; until then every real record is written in v1. **Proposed:** everything below
that goes beyond those sentences (D-039, D-046).

### 10.1 Where real data may live: the `validation` role, mirrors and authority

DEP-4 allowed only fakes and synthetic data in development, and the staging host arrives at stage 2, so
the real snapshot needs its own home. A fifth instance role holds it (DEP-23, D-046, proposed):

| Role | Holds | Outward actions | Bot polling | Where | Its data reaches production |
|---|---|---|---|---|---|
| `validation` | the owner's real snapshot (mirrors) and the monitoring layer of the selected project-log decisions (numbered from `D-1001`); no other native decision until adoption, because every real record is written in v1 until then (D-039); it accepts only snapshots not marked synthetic | never (the slice has none; the role refuses them by construction) | never | the owner's own machine, until the adoption gate; the data root must lie outside any repository working tree (`init` and `doctor` refuse otherwise) | only at the adoption gate, by a restore onto a host that passed its gate (DEP-27) and a promote there (§10.10) |
| `dev` | synthetic data only: it accepts only snapshots marked `"synthetic": true` and refuses any other with `IMPORT_NOT_SYNTHETIC` | never | never | anywhere, including CI | never |
| `drill` | a throw-away copy, for the case runner (§10.7) and restore drills; it imports no snapshot (`IMPORT_ROLE`) | never | never | a temp directory | never |
| `production` | from the adoption gate: the adopted decisions, and one-way mirrors of the kinds v1 still owns until stage 6; a snapshot here may carry only context (§10.5) | as DEP-2 | as DEP-2 | the host | — |

- **A data root outside any repository** is checked by `init` and `doctor`: they resolve the data root
  (following symlinks) and refuse when it, or any of its ancestors, contains a `.git` entry (a directory
  or a file).
- The validation data root is never used by CI, never by the evaluation harness (OPS-8 refuses it as it
  refuses production, except a named private evaluation set from stage 2, OPS-13), and never copied into
  an AI assistant's memory index or a repository. The canary suite runs against it as it does against
  production. Before the first real import the AI coding agents' operating-system account cannot read it,
  and the development disk is encrypted (PRV-15; precondition P0.6 of §13.0).
- **Proposed:** in the validation role, `create_decision`, `decide_fork` and `approve_proposal` of a new
  decision refuse with `NATIVE_IN_VALIDATION` ("record it in v1 until the adoption"), so the owner's own
  new decisions cannot start a second register there. The project-log importer (§10.8) and case copies
  (the `drill` role, §10.7) are not affected.
- The instance role is shown in every answer (DEP-2), so a reader always knows whether an answer comes
  from mirrored data.

**Authority map.** Every mirrored decision carries `mirror_of` (the authority's ref) and `mirror_scope`.
The guard in every command checks the field it would change against this map, so there is one writer per
field, always.

| Source | `mirror_scope` | Owned by the source | Owned by v2 |
|---|---|---|---|
| `V1` (the shadow period) | `full` | every field and every child row | nothing: v2 only computes health, due dates and the waiting list, and writes the shadow report |
| `CF2LOG` (the project's public decision log) | `basis_only` | `title`, `context`, `statement`, the option texts from the Alternatives bullet, and `decided_at` (from the heading) | everything else: question, unknowns, success criterion, assumptions, checks, facts, reviews, outcome, learning, links, review dates, `publishability` (always `public`) |

### 10.2 The snapshot format `coflow.import.decisions`, version 1

The format is JSON, UTF-8, one file per run, documented by the JSON Schema `import_decisions_v1.schema.json`
in the contracts package, with synthetic fixtures in the public repository, so others can write exporters
from their own tools. The owner's exporter lives in the owner's **private** repository. It reads v1's
database read-only, changes nothing in v1, and excludes the journal, diary tables, private session kinds
and chat summaries. It computes the `v1_computed` block by calling v1's own functions at export time, so
the comparison uses what v1 really said, and v2 never runs v1 code. `kind` and `decider_mapping` come from
an explicit mapping file the owner keeps in the private repository; they are never inferred from names.

Synthetic example (abridged; §10.2.1 lists every field):

```json
{
  "format": "coflow.import.decisions",
  "format_version": 1,
  "synthetic": true,
  "exported_at": "2026-11-15T05:00:12Z",
  "as_of": "2026-11-15T05:00:00Z",
  "as_of_date": "2026-11-15",
  "source": {"issuer": "V1", "schema_revision": "<v1 schema>", "exporter_version": "1.0.0", "timezone": "Europe/Berlin"},
  "id_space": {"decision": {"highest_issued": 910, "deleted_without_trace": [901, 902]}},
  "context": {
    "goals":    [{"ref": "G901", "title": "Cut fixed costs", "status": "dropped", "status_changed_at": "2026-11-05"}],
    "tasks":    [{"ref": "K9001", "title": "Draft the new template", "status": "done"}],
    "topics":   [{"ref": "T901", "title": "Newsletter", "status": "active"}],
    "sessions": [{"ref": "S90001", "communication_type": "chat", "started_at": "2026-10-30T08:00:00Z"}],
    "people":   [{"ref": "P901", "display_name": "Person A", "is_self": false}],
    "companies":[{"ref": "C-901", "name": "Example Print Co"}]
  },
  "decisions": [{
    "v1_id": 907, "v1_ref": "D907",
    "kind": "choice", "decider_mapping": "self",
    "title": "Move the team newsletter to a fortnightly cadence for one quarter",
    "statement": "Publish every second Tuesday from 1 Dec to 28 Feb", "context": "…",
    "alternatives": [{"option": "Keep the weekly issue", "why_rejected": "cost"}],
    "investment": "about 6 hours of template work", "expected_result": "print costs down by a third",
    "confidence": 70, "decided_at": "2026-11-02", "review_due": "2026-11-12",
    "owner_person": null, "executor_person": null, "about_person": null, "about_company": "C-901",
    "context_known": "…", "context_unknown": "whether readers notice the gap", "context_would_help": "…",
    "status": "active", "manual_health": null, "outcome": null, "learning": null,
    "process_type": null, "folder_path": null,
    "source_session": null, "created_at": "2026-11-02T19:02:11Z", "closed_at": null,
    "assumptions": [{"v1_id": 9071, "code": "A1", "statement": "The printer confirms the new slot by 10.11",
                     "metric": "written confirmation", "threshold": "confirmation by 10.11", "data_source": "mail",
                     "check_frequency": "ad-hoc", "is_critical": 1, "state": "NOT_YET_DUE",
                     "next_check_at": null, "last_checked_at": null, "position": 1, "notes": null,
                     "created_at": "2026-11-02T19:03:00Z"}],
    "facts":   [{"v1_id": 90701, "assumption_v1_id": 9071, "phase": "monitoring", "occurred_at": "2026-11-09",
                 "fact": "The printer asked for one more week", "source": "chat", "session": "S90001",
                 "created_at": "2026-11-09T10:00:00Z"}],
    "reviews": [],
    "links":   [{"kind": "goal", "ref": "G901", "source": "mcp", "created_at": "2026-11-02T19:05:00Z"},
                {"kind": "task", "ref": "K9001", "source": "app", "created_at": "2026-11-03T09:00:00Z"}],
    "versions":[]
  }],
  "v1_computed": {
    "today": "2026-11-15",
    "health":  {"907": {"label": "WATCH", "reasons": ["1 assumption not yet checked"]}},
    "waiting": [{"v1_id": 907, "reasons": [{"kind": "review_overdue", "due": "2026-11-12"},
                                          {"kind": "check_due", "due": "2026-11-10", "assumption_v1_id": 9071}]}],
    "assumption_due": {"9071": {"due": "2026-11-10", "source": "text"}}
  },
  "counts": {"decisions": 1, "assumptions": 1, "facts": 1, "reviews": 0, "links": 2, "versions": 0},
  "content_hash": "sha256:<hash of the CFJ-1 form of this document without content_hash>"
}
```

**Format rules:**
- Instants are UTC with `Z`; source dates are as v1 stored them, in `source.timezone`; text is verbatim
  (the v2 date parser unescapes HTML, as v1's does).
- An unknown field is an error, so schema drift is visible. Every key is present; an empty value is
  `null`. The `synthetic` flag is mandatory.
- **Every number is a JSON integer.** The file is parsed with a `parse_float` and a `parse_constant` that
  raise `IMPORT_FORMAT_UNSUPPORTED`, so `70.0`, `1e3` or `NaN` never reaches CFJ-1 (which refuses floats).
- **The content hash** is `"sha256:" + sha256(cfj(document without content_hash)).hexdigest()`. It is
  verified right after parsing and before the schema validation (`IMPORT_HASH_MISMATCH`).
- `id_space.decision.highest_issued` must stay below the native block start (1001).
- `reviews[]` items carry `v1_id`, `action`, `reviewed_at`, `verdict`, `notes`, `next_review_due`,
  `health_at_review` and `created_at`; `versions[]` items carry `v1_id`, `entity` (`decision` or
  `assumption`), `entity_v1_id`, `field`, `old_value`, `new_value`, `source`, `changed_by` and
  `changed_at`.
- Personal fields stay inside the receiving instance's data root.
- After the decision adoption a snapshot for the production instance carries an empty `decisions` array
  and updates only the `context` block (§10.5).

#### 10.2.1 Field types (normative)

The contract file `import_decisions_v1.schema.json` implements this table; a disagreement is fixed here
first. Types:
- **instant**: `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$`, UTC; normalised to milliseconds at
  import (§3.1).
- **source date**: `^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?(Z|[+-]\d{2}:?\d{2})?)?$`, a
  date as the source stored it. A value with an offset is converted to `source.timezone`; a value with a
  time and no offset is local to `source.timezone` (the exporter converts columns it knows to be UTC); the
  importer keeps the local date, precision `day`.
- **date**: `^\d{4}-\d{2}-\d{2}$`. **int**: a JSON integer; ids are at least 1. **text**: a string or
  `null`, verbatim. **ref**: `^[A-Za-z][A-Za-z0-9-]{0,31}$` (a source ref such as `G901` or `C-901`),
  stored as `V1_<ref>`.

| Object · field | Type | Null | Values | v2 target |
|---|---|---|---|---|
| top · `format`, `format_version` | string, int | no | `coflow.import.decisions`, 1 | the run |
| top · `synthetic` | bool | no | — | the role check (§10.5) |
| top · `exported_at`, `as_of` | instant | no | — | the run; `T = as_of` |
| top · `as_of_date` | date | no | the date of `as_of` in `source.timezone` | the run; `T.date` |
| top · `source` | object | no | `issuer` (`^[A-Z][A-Z0-9]{0,9}$`), `schema_revision`, `exporter_version`, `timezone` (IANA; equal to `owner.timezone`) | the run |
| top · `id_space.decision` | object | no | `highest_issued` (int below 1001), `deleted_without_trace` ([int], unique) | `sys_id_foreign`, `sys_id_burned` |
| top · `counts` | object | no | `decisions`, `assumptions`, `facts`, `reviews`, `links`, `versions` (int) | §10.6 |
| top · `content_hash` | string | no | `^sha256:[0-9a-f]{64}$` | verification |
| context · `goals[]` | object | no | `ref`, `title` (text), `status` (string, mapped by §10.3), `status_changed_at` (source date, null) | `dec_foreign_context` |
| context · `tasks[]`, `topics[]` | object | no | `ref`, `title`, `status` (text) | `dec_foreign_context` |
| context · `sessions[]` | object | no | `ref`, `communication_type` (text), `started_at` (instant) | `dec_foreign_context`; `origin_kind` |
| context · `people[]`, `companies[]` | object | no | `ref`, `display_name`, `is_self` (bool) / `ref`, `name` | `dec_foreign_context` (work class) |
| decision · `v1_id` | int | no | — | `number`, the mirror key |
| decision · `v1_ref` | string | no | `^D[1-9][0-9]*$` | an alias |
| decision · `kind` | string | no | `choice`, `test`, `pursue`, `attendance`, `advisee`, `forecast_container` | `kind` |
| decision · `decider_mapping` | string | yes | `self`, `joint`, `other` | `decider`; `joint` takes `decider_ref` from `about_person`, else `about_company`, else NULL (allowed for mirrors); null → `self` with basis `assumed` |
| decision · `title` | string | no | — | `title` |
| decision · `statement`, `context`, `investment`, `expected_result`, `context_known`, `context_unknown`, `context_would_help`, `learning`, `process_type`, `folder_path` | text | yes | — | §10.3 |
| decision · `alternatives[]` | object | no | `option` (string), `why_rejected` (text) | options |
| decision · `confidence` | int | yes | 0 to 100 | `confidence` |
| decision · `decided_at`, `review_due` | source date | yes | — | §10.3 |
| decision · `owner_person`, `executor_person`, `about_person`, `about_company`, `source_session` | ref | yes | — | §10.3 |
| decision · `status` | string | no | `draft`, `active`, `closed`, `cancelled`, `superseded`, `withdrawn` | `status` |
| decision · `manual_health` | string | yes | `ZOMBIE`, `OFF_TRACK` | `manual_flag` |
| decision · `outcome` | string | yes | `success`, `failure`, `mixed` | §10.3 |
| decision · `created_at` / `closed_at` | instant / instant | no / yes | — | `origin_recorded_at` / `closed_at` |
| assumption · `v1_id`, `position` | int | no | `position` ≥ 1 | the mirror key, `position` |
| assumption · `code` | string | yes | `^A[1-9][0-9]*$` | `code_n` (null → the next free code) |
| assumption · `statement` | string | no | — | `statement` |
| assumption · `metric`, `threshold`, `data_source`, `notes` | text | yes | — | `metric`, `threshold_text`, `data_source_text`, `legacy_json.notes` |
| assumption · `check_frequency` | string | yes | `weekly`, `monthly`, `quarterly`, `ad-hoc`, `ad_hoc` | `check_frequency` (`ad-hoc` → `ad_hoc`) |
| assumption · `is_critical` | int | no | 0, 1 | `is_critical` |
| assumption · `state` | string | no | `HOLDING`, `DRIFTING`, `VIOLATED`, `UNVERIFIABLE`, `NOT_YET_DUE` | `map_state` (§10.5) |
| assumption · `next_check_at`, `last_checked_at` | source date | yes | — | `next_check_at`; rebuilt checks |
| assumption · `created_at` | instant | no | — | `origin_recorded_at` |
| fact · `v1_id` / `assumption_v1_id` | int | no / yes | — | the mirror key / `dec_fact_assumptions` |
| fact · `phase` | string | no | `grounding`, `monitoring` | `ground`, `monitoring` |
| fact · `occurred_at` | source date | yes | — | `occurred_at`, precision `day` |
| fact · `fact` / `source` / `session` | string / text / ref | no / yes / yes | — | `text` / `source_text` / `evidence_ref` |
| fact · `created_at` | instant | no | — | `origin_recorded_at` |
| review · `v1_id` | int | no | — | the mirror key |
| review · `action` | string | yes | `keep`, `adjust`, `revise`, `close`, `cancel`, `supersede` | `action`; null → `keep`, counted in the report as "action not recorded" |
| review · `reviewed_at`, `next_review_due` | source date | yes | — | `occurred_at`, `next_review_due` |
| review · `verdict`, `notes`, `health_at_review` | text | yes | — | `verdict`, `notes`, `legacy_health_at_review` |
| review · `created_at` | instant | no | — | `origin_recorded_at` |
| link · `kind` | string | no | `goal`, `task`, `topic` | §10.3 |
| link · `ref` / `source` | ref / text | no / yes | — | `target_ref` / `note` |
| link · `created_at` | instant | no | — | `origin_recorded_at` |
| version · `v1_id`, `entity_v1_id` | int | no | — | the mirror key |
| version · `entity` | string | no | `decision`, `assumption` | `dec_versions.entity` |
| version · `field`, `old_value`, `new_value` | string, text, text | no, yes, yes | `field` is the v1 column name | `dec_versions`; `state` rows drive rule 1 of `rebuild_checks` |
| version · `source`, `changed_by` | text | yes | — | `dec_versions.reason` as `<source>, <changed_by>` |
| version · `changed_at` | instant | no | — | `origin_recorded_at` |
| v1_computed · `today` | date | no | equal to `as_of_date` | the run |
| v1_computed · `health` | object keyed by v1 id | no | `label` ∈ `ON_TRACK`, `WATCH`, `REVIEW_REQUIRED`, `STALE`, `INSUFFICIENT_DATA`, `ZOMBIE`, `OFF_TRACK`, `DRAFT`, `CANCELLED`, `SUPERSEDED`, `WITHDRAWN`, `CLOSED`, `CLOSED_<OUTCOME>`; `reasons` [string] | compared; the reason strings are not stored |
| v1_computed · `waiting[]` | object | no | `v1_id`; `reasons[]` with `kind` ∈ `violated`, `review_overdue`, `review_today`, `check_due`, `due` (date, null), `assumption_v1_id` (int, null), `critical` (bool, null) | compared, in order |
| v1_computed · `assumption_due` | object keyed by v1 id | no | `due` (date, null), `source` ∈ `next_check`, `explicit`, `by_date`, `text`, `review`, null | compared (`next_check` ≡ `explicit`) |

### 10.3 Field mapping v1 → v2

| v1 field | v2 field | Rule |
|---|---|---|
| decision `id` | `number`, `public_id = D-%04d` | aliases `V1_D<id>` and the input forms; `sys_id_foreign(D, id, V1)` |
| `title`, `statement`, `context` | same | — |
| — | `question`, `success_criterion` | NULL; the card lists them as fields v1 did not have; filling them after adoption is a completion (§4.10) |
| — | `depth` | `full`, `depth_basis = 'import'` (so a mirror without assumptions shows INSUFFICIENT_DATA, exactly like v1) |
| `statement` + `alternatives[]` | `dec_options`: `O-01` from the statement, with `chosen_option = 1`, plus one per alternative with its `why_rejected` | `origin = import`, `recorded_before_choice = 'unknown'`, `origin_recorded_at = created_at`; a later change follows the mirror change rules (§10.5) |
| `investment` | `legacy_json.investment`; no `dec_stakes` row | money is never parsed from text; the owner structures it later |
| `expected_result` | `expected_text` | dates in it are not parsed |
| `confidence` | `confidence` | owner-stated in v1; **never turned into a forecast** (the meaning differs, and reconstructed records are not eligible) |
| `decided_at` / `created_at` | `decided_at` (precision `day`, basis `import`) / `origin_recorded_at` | `reconstructed = 1`; `retroactive` computed from K |
| `review_due` | `review_due`; `review_due_initial` | `review_due_initial` := the `old_value` of the earliest v1 version row with field `review_due`, else the `review_due` seen at the decision's first import; set once and never recomputed by later snapshots, so a keep or adjust in v1 never looks like a basis change |
| `owner_person` + `decider_mapping` | `decider`, `decider_basis`, `decider_ref` | mapping present → `mapped`; absent → `self`, `assumed`; `joint` as §10.2.1; never a name lookup |
| `kind` (mapping file) | `kind` | `choice` by default; `advisee` or `forecast_container` only from the mapping |
| `executor_person` | `legacy_json.executor` | execution is a spoke's business in v2 |
| `about_person`, `about_company` | `dec_links(about, foreign)` with `target_ref = V1_<ref>` | resolved when PPL mirrors people (stage 1) |
| `context_known` / `context_unknown` / `context_would_help` | `known` / `unknowns_json` (one item; never split by guessing) / `would_help` | — |
| `status` | `status` | identical vocabulary |
| `manual_health` | `manual_flag` | — |
| `outcome` on a closed mirror | `dec_outcomes` (`basis = 'reported'`, `resolved_by = 'import'`, `reconstructed = 1`); `occurred_at := closed_at` (basis `import`, precision `instant`), else NULL with precision and basis `unknown` | v1 recorded no basis; the owner may add a `resolved` resolution after adoption |
| `outcome` NULL on a closed mirror | no `dec_outcomes` row | health `CLOSED` with the badge "no outcome recorded"; v1's bare `CLOSED` label maps to it |
| `learning` | `dec_learnings.legacy_text` (the whole text), `edition = 0`, `reconstructed = 1` | confirmed, refuted, limits and next step stay empty |
| `process_type`, `folder_path` | `legacy_json` | meaningless in v1 data |
| `source_session` | `origin_kind = 'session'` or `'chat'` (by communication type), `origin_ref = V1_<ref>` | otherwise `not_recorded` |
| assumption `code`, `statement`, `metric`, `position` | `code_n` (`A1` → `A-01`), same | `dec_mirror_state(V1, assumption, v1_id)` lets the pilot's numeric assumption ids resolve |
| assumption `threshold` | `threshold_text` | the structured threshold stays empty, so the due date still comes from the text, identical to v1 |
| assumption `data_source` | `data_source_text`; kind: empty → `none` (v1 stored UNVERIFIABLE for it), otherwise `manual` | never inferred from the wording, so the shadow matches v1; the owner may supersede the assumption later |
| assumption `check_frequency`, `is_critical` | same (`ad-hoc` → `ad_hoc`) | — |
| assumption `notes` | `dec_assumptions.legacy_json.notes` | verbatim; not part of the basis |
| assumption `state`, `last_checked_at` | the rebuilt check log (§10.5, `map_state`): `NOT_YET_DUE` with no `last_checked_at` → no row; `UNVERIFIABLE` with an empty source and no `last_checked_at` → no row (kind `none`); a checked state (`HOLDING`, `DRIFTING`, `VIOLATED`, or `UNVERIFIABLE` with a source) → one assessment observed at `last_checked_at`, or, with `last_checked_at` null, one with `observed_at` NULL, precision `unknown` and `origin_recorded_at` = the assumption's `created_at`; `NOT_YET_DUE` with a `last_checked_at` (a state reset in v1) → one assessment of state `UNKNOWN`, noted "state reset in v1". All carry `proposed_by = 'import'` and `reconstructed = 1` | each state change in v1's versions adds one more reconstructed assessment (§10.5) |
| assumption `next_check_at` | `next_check_at` (rule `import`) | the v1 value is kept, including a default step a v1 button set |
| facts | `dec_facts`: phase grounding → `ground`, monitoring → `monitoring`; `evidence_kind = 'foreign'` with `V1_<session>` when a session is named, else `none`; `source_text` | `assumption_v1_id` → `dec_fact_assumptions` |
| reviews | `dec_reviews` (`occurred_at` = `reviewed_at`, precision `day`, basis `import`; `trigger = 'import'`; `legacy_health_at_review`; `origin_recorded_at` = `created_at`; `reconstructed = 1`) | an action of `null` is stored as `keep` and counted as "action not recorded" |
| goal links | `dec_links(serves)`, `target_kind = 'foreign_goal'`, `resolution = 'foreign'`, `target_ref = V1_<ref>`, `note` = the link's `source` | goal states feed `goal_changed` |
| task and topic links | `dec_links(foreign_attachment)`, `target_kind = 'foreign_task'` or `'foreign_topic'`, `resolution = 'foreign'`, `target_ref = V1_<ref>`, `note` = the link's `source` | the context block fills `dec_foreign_context` |
| context goal `status` | `dec_foreign_context.status`, compared lower-case | `candidate`, `active` → not ended; `paused`, `achieved`, `abandoned`, `dropped`, `superseded`, `closed` → the same word, in `ENDED` (§4.13); anything else → `IMPORT_FORMAT_UNSUPPORTED` |
| decision rows in v1's versions | `dec_versions` (`cause_kind = 'import'`, `reconstructed = 1`, `reason` = `<source>, <changed_by>`) | the full history, not only the last values; head changes without a version row follow the mirror change rules (§10.5) |
| deleted decision numbers | `sys_id_burned(D, n, numbering_gap, V1)` | never issued again |
| task kind "decision", task comments of kind decision | not imported in the slice | [Later: when the owner asks to see them as proposals] |
| bot decision settings | not imported | CFG at stage 2 |

### 10.4 How v1 numbers survive

**Accepted (D-045):** v1 decisions keep their numbers in four digits, new decisions start at `D-1001`,
and numbers are permanent. **Proposed:** the mechanics.

1. A mirrored decision keeps its v1 number: `D907` becomes `D-0907`, and `V1_D907`, `D907` and `d-907`
   resolve to it. The owner's habit of using ids as conversation keys survives, and the forecast pilot's
   references stay resolvable.
2. Every number v1 issued is registered in `sys_id_foreign`, and every number it deleted in
   `sys_id_burned`, so the tap never issues them (IDN-10).
3. During the shadow period v1 keeps issuing in its own space. v2-native decisions come from the block
   that starts at `D-1001` (`sys_id_prefixes.block_start`), so the two cannot collide. Each issuing space
   has one source: the low range belongs to `V1` until adoption, the block to the instance.
4. At adoption the instance becomes the only tap for `D` and continues after the highest number in use in
   either range (gaps are normal). Ids never change: a native `D-1004` stays `D-1004`.
5. Review action names, assumption codes and states are imported verbatim or by a lossless map, and CFJ-1
   reproduces the pilot's canonicalisation, so the pilot's rounds remain verifiable against v2 data later.

### 10.5 Idempotent daily re-import (one unit of work per snapshot)

```python
def import_snapshot(path, mode='shadow', *, ctx):
    raw = read_bytes(path); h = hashlib.sha256(raw).hexdigest()
    prior = run_of(h, mode)                                      # the applied, partial or failed run of this file
    if prior and prior.status == 'applied':                      # the same file twice
        if mode != 'dry_run': insert_run(h, prior.snapshot_meta, mode, status='noop')   # a noop row, nothing else
        return report(prior, noop=True)
    try:
        doc = json.loads(raw, parse_float=refuse_number, parse_constant=refuse_number)  # → IMPORT_FORMAT_UNSUPPORTED
        verify_content_hash(doc)                                  # → IMPORT_HASH_MISMATCH, before the schema
        snap = validate(doc, schema='import_decisions_v1')        # unknown fields → IMPORT_FORMAT_UNSUPPORTED
        check_role_and_source(snap)                               # below
    except Refused as r:
        if mode != 'dry_run': insert_run(h, meta_or_none(doc), mode, status='refused', error=r.code)
        raise
    T = snap.as_of; T_date = snap.as_of_date                     # the shadow's evaluation instant and day
    # PREPARE (reads only, outside any unit): per-object content hashes, the diff against dec_mirror_state,
    # and the planned row operations under the mirror change rules below; nothing is written yet.
    plan = diff(snap, mirror_state_for('V1'))
    if any(st.adopted_at for st in plan.touched_states): raise Refused('IMPORT_ADOPTED')   # adopted records are v2's now
    if mode == 'dry_run': return report_plan(plan)                              # writes nothing, not even a run row
    chunks = [plan] if plan.row_count <= CFG.dec.import_unit_max_rows else plan.split_by_decision(CFG.dec.import_unit_max_rows)
    run = prior if prior and prior.status in ('partial', 'failed') else None   # resume: the plan skips what is applied
    if run is None: run = insert_run(h, snap, mode, status='partial')            # its own small unit (system class)
    for i, chunk in enumerate(chunks):
        try:
            with unit_of_work('dec', ctx.with_actor('import_v1', channel='import')):
                if i == 0:
                    register_foreign_and_burned(snap.id_space)                   # sys_id_foreign, sys_id_burned
                    upsert_foreign_context(snap.context, run)                    # goals with mapped status and change dates
                for op in chunk.ops: apply(op)                                   # keyed by v1 ids; the rules below
                rebuild_checks(chunk, snap)                                      # below
                for key in chunk.absent_keys: mark_absent(key, run)              # a tombstone; listed in the report
                if i == len(chunks) - 1:
                    set_run(run, status='applied', error=None); publish('coflow.dec.import.completed', run)
        except Exception as e:                                                   # the failed unit rolled back
            set_run_unit(run, status='partial' if any_chunk_applied(run) else 'failed',
                         error=error_key(e))                                     # the class and the row key only
            raise
    write_shadow_report(run, T, T_date) # after commit: reads only, then one small unit for dec_shadow_items + v2_output_json
    return report(run)

def check_role_and_source(snap):
    role = instance.role
    if role == 'dev' and not snap.synthetic: raise Refused('IMPORT_NOT_SYNTHETIC')
    if role == 'validation' and snap.synthetic:
        raise Refused('IMPORT_ROLE', detail='synthetic snapshots belong in a dev instance')
    if role == 'production' and not adopted('V1'):
        raise Refused('IMPORT_ROLE', detail='production imports only after the decision adoption')
    if role not in ('dev', 'validation', 'production'): raise Refused('IMPORT_ROLE')     # staging, drill
    if (adopted('V1') or has_final_run('V1')) and snap.decisions:
        raise Refused('IMPORT_ADOPTED', detail='after the final import a snapshot carries context only')
    if snap.as_of_date != local_date_in(snap.as_of, snap.source.timezone): raise Refused('IMPORT_FORMAT_UNSUPPORTED')
    if snap.source.timezone != CFG.owner.timezone or snap.v1_computed.today != snap.as_of_date:
        raise Refused('IMPORT_SOURCE_CONFLICT')                                  # v1 and v2 must count the same days
    if block_start('D') and snap.id_space.decision.highest_issued >= block_start('D'):
        raise Refused('IMPORT_SOURCE_CONFLICT')

MAP_STATE = {'HOLDING': 'HOLDING', 'DRIFTING': 'DRIFTING', 'VIOLATED': 'VIOLATED',
             'UNVERIFIABLE': 'UNVERIFIABLE', 'NOT_YET_DUE': 'UNKNOWN'}   # NOT_YET_DUE: note "state reset in v1"

def map_state(s):                     # anything else is a format error
    if s not in MAP_STATE: raise Refused('IMPORT_FORMAT_UNSUPPORTED', detail='assumption state')
    return MAP_STATE[s]

def state_versions(a, snap):          # versions[] rows with entity 'assumption', field 'state', entity_v1_id = a.v1_id
    return sorted((v for v in versions_of(a, snap) if v.entity == 'assumption' and v.field == 'state'),
                  key=lambda v: (v.changed_at, v.v1_id))

def rebuild_checks(chunk, snap):      # v1 has no check log; v2 builds one from what the snapshots show
    tz = snap.source.timezone
    for a in chunk.assumptions:
        for v in state_versions(a, snap):                                        # 1. explicit history
            if not mirrored(('V1', 'check_version', v.v1_id)):
                append_reconstructed(a, state=map_state(v.new_value), note=reset_note(v.new_value),
                                     observed_at=v.changed_at, observed_precision='instant',
                                     origin_recorded_at=min(v.changed_at, snap.as_of))
        latest = latest_assessment(a, snap.as_of)
        if a.last_checked_at:                                                    # 2. the snapshot's own state
            d = local_date_in(a.last_checked_at, tz)
            if not has_assessment_on(a, d, tz) or map_state(a.state) != latest.state:
                append_reconstructed(a, state=map_state(a.state), note=reset_note(a.state),
                                     observed_at=d, observed_precision='day',
                                     origin_recorded_at=min(end_of_day(d, tz), snap.as_of))
        elif checked_state(a) and (latest is None or map_state(a.state) != latest.state):
            append_reconstructed(a, state=map_state(a.state), observed_at=None, observed_precision='unknown',
                                 origin_recorded_at=a.created_at if latest is None else snap.as_of)

# checked_state(a)  = a.state in (HOLDING, DRIFTING, VIOLATED), or UNVERIFIABLE with a data source.
# append_reconstructed writes kind 'assessment', proposed_by 'import', reconstructed 1, next_check_rule
# 'import', and due_answered, due_source_answered and next_check_set NULL; it records the row in
# dec_mirror_state as check_version (by v1 id) or check_snapshot (by assumption v1 id and day).
# end_of_day(d, tz) = d 23:59:59.999 in tz, converted to UTC.
```

**Mirror change rules.** One rule per kind of change in the source, applied by `apply(op)`:

| Change in the source | What the importer writes |
|---|---|
| A new decision | the mirror with its children; E-01 sealed (reason `import`) if it is active or terminal |
| A decision head field (title, status, review date, manual flag, closed time, context fields) | the head is updated; a `dec_versions` row (`cause_kind = 'import'`) is written only when no v1 version row in this snapshot covers that change, so the history is never doubled |
| The statement | `O-01` (or the current chosen option) is voided, the next option code is appended with the new text, and `chosen_option` points to it |
| The alternatives | matched by text: a removed one is voided (`deleted_in_source`), a new one appended, a changed reason voids the option and appends a successor with `copied_from` |
| An assumption's basis field (§4.3 `ITEM_FIELDS`) or position | the old row gets status `superseded` and `superseded_by`; a successor takes the next `a_seq` code; `dec_mirror_state(V1, assumption, v1_id)` points to the successor, and the alias `V1_D<id>_A<n>` resolves to it |
| An assumption's `next_check_at` | the mutable column is updated and versioned as for a head field |
| An assumption absent from the snapshot | status `dropped`, `drop_reason = 'deleted_in_source'` |
| A changed fact, review, option or link | the old row is voided (a link gets `removed_tx`) and a new one appended; a fact's successor sets `corrects_fact_id` |
| A child absent from the snapshot | voided with reason `deleted_in_source` (a link: `removed_reason`) |
| A decision absent from the snapshot | a tombstone (`absent_since_run_id`), never a delete |
| Any change to `BASIS_FIELDS` values or to the set of basis items of an active or terminal mirror | exactly one `source_changed` edition per decision per run, and one `basis_drift` finding; a draft changes in place |

`dec_mirror_state.source_kind` is one of `decision`, `assumption`, `fact`, `review`, `link`, `version`,
`check_version`, `check_snapshot`, and `content_hash` is `sha256(cfj(the source object without its nested
arrays))`, so a changed fact does not mark its decision as changed.

- **Atomicity.** A realistic snapshot (tens of decisions, a few hundred rows) is applied in **one unit of
  work**: all of it or nothing (the run row is bookkeeping, written in its own small unit before, and
  marked `failed` after a failure that applied nothing). Only when it exceeds `dec.import_unit_max_rows` is
  it split by decision. The run then stays `partial` until its last chunk commits; the shadow report
  refuses to run on a `partial` run (`report_status = 'blocked'`); and the next import of the same or a
  newer file re-applies idempotently through the content hashes and completes it. A `partial` run's file
  hash does not count as "already imported" until the run is `applied`.
- **Run rows.** A repeated file writes a run row with status `noop` and nothing else; a refusal after the
  file was read writes one with status `refused` (its format fields are NULL when the file could not be
  read that far). Mode `final` has the semantics of `shadow` plus `run.mode = 'final'`; after a final run,
  every later V1 snapshot whose `decisions` array is not empty is refused with `IMPORT_ADOPTED`.
- **After the decision adoption** (proposed, D-046) the production instance accepts V1 snapshots whose
  `decisions` array is empty: the `context` block keeps `dec_foreign_context` fresh, so `GoalDirectory`
  and `goal_changed` keep working on the decisions v2 now owns. The other kinds v1 still owns arrive in
  their own formats from stage 1 (OPS-15).
- **The comparison is outside the write unit.** It is computed after the commit from read connections, at
  `T = snap.as_of` with `T.date = snap.as_of_date`, on the knowledge axis, so it is deterministic. If the
  process dies before it is stored, `coflow dec shadow --run N` recomputes the same result.
- **Knowledge time of imported rows.** Every imported row gets `origin_recorded_at`, capped at
  `snap.as_of`: decisions, options, assumptions, facts and links take their `created_at`; reviews take
  `reviews[].created_at`; outcomes and learnings take the decision's `closed_at`, else its `created_at`;
  `dec_versions` rows and rule-1 checks take `changed_at`; rule-2 checks take
  `min(end_of_day(last_checked_at), as_of)`; a `dec_fact_assumptions` row takes its fact's K. So a check or
  a review dated `as_of_date` is visible to that run's shadow (AT-S9).
- **Coverage is stated honestly.** Before the first snapshot only v1's last known state exists, and checks
  between two snapshots that leave no version row and repeat the same date are invisible. The history
  query says both.
- **A record deleted in the source** becomes a tombstone (`absent_since_run_id`), never a delete; it
  leaves the waiting list and keeps its number.
- **Scheduling.** The exporter runs on the v1 machine and drops the file into the receiving instance's
  `inbox/snapshots/`. In 0A the owner runs `coflow dec import v1 <file>`; from 0B the supervisor imports
  daily (OPS-15).

### 10.6 Comparing the shadow with v1

For every mirrored active decision, at the snapshot's `as_of_date` (OPS-16):

| Aspect | v1 value | v2 value | Classification |
|---|---|---|---|
| Assumption due date and source (`next_check` ≡ `explicit`) | `v1_computed.assumption_due` | `assumption_due()` | must be `same` |
| Waiting membership, reason kinds and due dates | `v1_computed.waiting` | `waiting()` (decision items only) | `same`, or `expected` under a rule |
| Relative order of decisions present in both lists with the same reasons | the v1 list | the v2 list | must be `same` |
| Health label | `v1_computed.health` | `health()`, mapped | `same`, or `expected` under a rule |
| Counts | `counts` per entity | the number of `dec_mirror_state` rows of that `source_kind` (decision, assumption, fact, review, link, version) with `last_run_id` = this run and `absent_since_run_id` NULL; derived rows (`O-01`, `about` links, rebuilt checks) are not counted | must be equal |
| Basis drift | — | a `source_changed` edition in this run | a `finding`, not a difference |

Label mapping v1 → v2: `ON_TRACK`, `WATCH`, `REVIEW_REQUIRED`, `STALE`, `INSUFFICIENT_DATA`, `ZOMBIE` and
`OFF_TRACK` are the same; v1's `CLOSED_<OUTCOME>` is `CLOSED` with the outcome badge, and v1's bare
`CLOSED` is `CLOSED` with the badge "no outcome recorded"; `CANCELLED` and `SUPERSEDED` are the same.

**Expected-difference rules.** Each rule is a documented change from v1 with its own test. A difference is
classified by the first rule whose condition holds on v2's own computed values; anything else is
**unexpected**.

| Rule | v1 shows | v2 shows | Condition on v2's values | Why |
|---|---|---|---|---|
| SR-1 | WATCH | AWAITING_CHECKS | ground AWAITING, timeliness without NO_REVIEW_DATE or CHECK_OVERDUE | v1's "not yet checked" WATCH carried no signal |
| SR-2 | INSUFFICIENT_DATA | STALE | review overdue, ground NO_ASSUMPTIONS or every pool assumption UNVERIFIABLE | v1 masked an overdue review |
| SR-3 | WATCH | INSUFFICIENT_DATA | ground INSUFFICIENT with a share above the limit but below 1, review not overdue | a mostly uncheckable ground is fog, not "watch" |
| SR-4 | WATCH | ON_TRACK | ground HOLDING with at least one UNVERIFIABLE in the pool (share ≤ limit), timeliness clean | v1 called holding plus unverifiable "0 not yet checked" |
| SR-5 | ON_TRACK | WATCH | ground HOLDING, timeliness CHECK_OVERDUE | a holding state with an overdue check is not on track |
| SR-6 | ON_TRACK | WATCH | ground HOLDING, timeliness NO_DATA_SINCE | a stale "holding" is not on track (P-9) |
| SR-7 | no `violated` reason; ON_TRACK or WATCH | a non-critical `violated` reason; WATCH unless a higher label applies | a non-critical assumption VIOLATED, critical ones present | health and waiting agree in v2; v1 ignored non-critical violations |
| SR-8 | no reason; the label from the ground | an `incomplete` reason; WATCH unless a higher label applies | an active mirror without a review date | an active record without a review date waits in v2 |
| SR-9 | no reason | a `goal_changed` reason | a served or tested goal ended after the decided date and after the last review | the question about a decision whose goal ended |
| SR-10 | no `violated` reasons | `violated` reasons | a manual flag is set and an assumption is VIOLATED | v1 listed violations only under REVIEW_REQUIRED, which a manual flag hides |

Several rules may apply to one decision, for example SR-7 together with SR-9. Waiting-membership
differences are explained by the rules that produced the extra v2 reasons. Ordering differences among
common items with identical reasons are always unexpected. The rules SR-1 to SR-10 depend on the health
order of §4.7, which is proposed (D-044); a different order changes them.

`coflow dec shadow` prints the totals (same, expected by rule, unexpected, findings) and every unexpected
line with both values and the inputs behind them. An unexpected line is either a v2 defect (fix it) or a
v1 behaviour not yet in the table (add a rule with a test, through a recorded change to this table).
**Shadow readiness** for the adoption gate is `dec.shadow_clean_runs` (14) consecutive daily runs with
zero unexpected lines, with every expected rule that occurred reviewed once by the owner. The daily run
of an `as_of_date` is the latest `applied` run with that date and `report_status = 'written'`; a missing
`as_of_date` breaks the streak. The report stays
in the validation data root and is never summarised into an agent's memory.

### 10.7 Real cases on real decisions, without a second writer (proposed, D-046)

The owner's named cases (§12.2; D-036) are run this way. Each case is a small YAML script kept in the
validation data root (after the adoption, the production data root), never in any repository, public or
private. A synthetic example:

```yaml
case: RC-1                       # the owner's label
title: "Context change on a supplier slot"
decision: D-0907                 # a mirrored decision, or a native one
as_of: snapshot                  # run against the latest applied snapshot
steps:
  - expect: {waiting_reason: review_overdue, due: "2026-11-12"}
  - expect: {question_context: {last_fact_age_days_max: 10, goals_status: [dropped]}}
  - do: add_fact {text: "Moved to a later slot on new terms", on: [A-01], occurred: "2026-11-14"}
  - do: review {action: adjust, next: "2026-12-15", verdict: "moved"}
  - do: cmt_create {what: "Send the revised artwork", to: V1_P901, due: "2026-11-20", decision: D-0907}
  - expect: {waiting_reason_absent: review_overdue, execution: {commitment: {open: 1}}}
```

A step is either `expect` (a query result that must hold) or `do` (a command through `dec.api` or
`cmt.api`, with the CLI's argument names). `coflow dec case run CASE.yaml`:
1. asks the core for a consistent copy of the source database (the validation instance; production after
   the adoption; a `dev` instance for synthetic cases) through the SQLite backup API, a read;
2. opens the copy as an ephemeral instance in the `drill` role under its own lock, in a temp directory;
   the mirror guard is lifted only there, and only for the case's decision;
3. runs the steps through the same `api` commands, checks every expectation, and records the result as a
   `dec_cases` row in the source instance (a system record, not a mirrored field);
4. deletes the copy.

The source database is byte-identical before and after, apart from the case row (AT-R1). The real write
paths are thus exercised on real decisions before adoption, and the adoption gate can require the cases
to pass. After the adoption the same runner copies the production database (proposed, D-046), so the
real cases of stages 3–5 run without touching the record.

### 10.8 The project's own decision log as native data (proposed, D-046)

The project's public decision log holds real, dated, owner-approved decisions without personal data. It
has no assumptions and no review dates.

`coflow dec import log docs/DECISIONS.md --only D-036,D-037` parses the selected
`## D-NNN · Title — status (date)` headings and their Context / Decision / Alternatives / Consequences
bullets. Each becomes a **draft** mirror with `mirror_scope = 'basis_only'`:
- issuer `CF2LOG` and the alias `CF2LOG_D-037`;
- a number from the native block (from `D-1001`);
- `publishability = 'public'` and `reconstructed = 1`;
- `decided_at` from the heading date (precision `day`, basis `import`).

Accepted entries get a note "accepted in the log on <date>"; proposed entries are imported only when the
owner names them, and keep a note "proposed in the log". The owner then adds the question, assumptions, a
success criterion and a review date in v2, and activates. This is the first real use of every native
write path, with no second writer (the log owns the text, v2 owns the monitoring) and no collision with
the forecast pilot, which uses v1's register.

Only selected entries are imported, so the waiting list is not flooded with unmonitored records. A
re-import that finds changed log text updates the log-owned fields: a draft changes in place with
versions, and an active record gets a `source_changed` edition. Because this data is public, the same
records can become a third evaluation tier in CI, next to synthetic fixtures and a public corpus, once
the owner approves.

Example: a decision "one question a day closes the decision loop" gets the assumption "the share of
assumption checks answered within 7 days of their due date is at least 0.6 by 2026-12-31" (`>=`, `0.6`, a
by-date; source `internal_query` [Later], `manual` until then).

### 10.9 Constraints that hold until the forecast pilot reports (1 December 2026)

- The exporter reads v1 read-only. v1's decision schema, its decision tool names and arguments, its
  review action names and its assumption states do not change.
- v2 keeps the same review action names, assumption codes and states, and a canonical form that
  reproduces the pilot's, so the pilot's rounds remain resolvable and its seals verifiable later. The
  pilot's sealed numbers are never opened or imported before their reveal dates.
- Shadow reports stay inside the validation instance and are never pasted into an AI assistant's memory
  index that a memory-free forecaster could see.
- **Accepted (D-039, 18 October 2026):** reading v2's shadow is part of the pilot's record. The pilot's
  change journal records that the v2 shadow started; the owner reads the shadow waiting list daily; every
  intervention it causes (a review, a check or a change in v1 prompted by the shadow) is recorded and taken
  into account in the pilot's analysis.
- The v2 MCP server uses the `dec_` namespace (§8), and v1's own write path for assumption states stays
  the pilot's only write path in v1.

### 10.10 Adoption: decisions move to v2 for good

**Accepted (D-039):** decisions move to v2 for good after the owner's real cases pass, not before
1 December 2026 unless the owner changes that, and v1's decision module then becomes read-only.
**Accepted (D-050):** a host holds real data only after its measured gate. **Proposed:** the
snapshot-freshness rule of condition 2, conditions 3 to 6 below, the procedure, the production role that
follows it, and that adoption lands on a host that passed its gate (DEP-27).

The gate is enforced in code: `adopt_mirrors` refuses with `ADOPTION_GATE` and names every condition that
is missing. All of these must hold:

1. The date is on or after `dec.adoption_not_before` (1 December 2026, the forecast pilot's report date).
   The owner may move it only by a recorded decision (a D-entry reference stored in
   `dec.adoption_override_ref`).
2. The owner's named cases (§12.2) have passed (`dec_cases.last_result = 'pass'` for each, against a
   snapshot no older than `dec.case_snapshot_max_age_days`).
3. The last `dec.shadow_clean_runs` (14) consecutive daily runs have zero unexpected lines.
4. Stage 0B is done: backups with a tested restore and an off-host copy (OPS-5).
5. A daily asking channel exists in v2: the stage-2 chat loop (DEC-7), or a recorded owner decision to
   accept a pull-only loop (CLI and MCP) for decisions until the bot exists (an open choice, §14).
6. The target host has passed its gate (DEP-27): at least 30 days in the staging role with every
   measurement recorded; the restored instance can be promoted there (DEP-3).

**Procedure (proposed):**
1. The owner switches v1's decision module to read-only and turns off v1's decision questions. This is a
   v1-side change in the private repository; D-006 already allows decision-loop changes in v1.
2. A final export, then `coflow dec import v1 <file> --final` on the validation instance.
3. The host's staging instance is retired: it stops, its synthetic data root is removed, and the shared
   test credentials are released (DEP-4).
4. A consistent backup of the validation instance is restored onto the target host, where it starts as
   non-production (DEP-3, DEP-23). The validation instance on the owner's machine is retired and never
   written again.
5. `coflow dec adopt --issuer V1 --confirm "<phrase>"` runs on the restored instance in one unit of work.
   For every V1 mirror it sets `mirror_of := NULL` and `mirror_scope := NULL`, sets `adopted_at := now` in
   `dec_mirror_state`, and writes a version row each (`cause_kind = 'adoption'`). The records keep their
   editions, which were sealed at import, and stay `reconstructed = 1`, so filling their empty basis
   fields is a completion. The tap takes over `D`, continuing after the highest number in use, and the
   block start is cleared. Project-log mirrors (`basis_only`) are not touched.
6. `coflow promote` (DEP-3, which also requires the host gate): the restored instance becomes production
   with decisions only, and production credentials are issued.

From that moment there is one writer for decisions, and there is no staging instance: pre-releases are
checked in CI and by `coflow drill` before the owner approves a production deploy. v1 keeps writing
everything else until stage 6; the kinds it still owns (people, sessions, commitments, tasks, goals) are
imported one way into production as read-only mirrors (context-only decision snapshots, §10.5, and the
formats of stage 1), and the real cases of stages 3–5 run on throw-away drill copies of the production
database (§10.7). At stage 6 everything else is imported into this production instance; a promote
happens there only if the adoption has not.

**Rollback** before any native write on adopted records: restore the pre-adoption backup and switch v1's
decision module back to writable. After native writes, fix forward (DEP-10).

---

## 11. Ecosystem contracts (the decision part)

**Accepted (D-041):** the ecosystem stays as separate blocks. **Proposed:** CoFlow works without any of
them (EXT-6), remote access is not precluded, and the contract fields below. The apps are named by role:
- **LIVE**: a real-time online conversation agent;
- **EVENT**: an offline-event app whose user knows the goal of attending upfront;
- **UPLOAD**: a plain upload of communications;
- **TEAM**: a tool for external work with a team, candidates or distributed tasks;
- **AGENT**: AI working sessions in coding or chat clients.

### 11.1 Principles

1. **Independence** (EXT-6). Every core scenario works with no app connected. An app's absence is never an
   error, only a coverage note ("no live-session data for this meeting").
2. **Apps are sensors around decisions.** They read a projection of the decisions that concern them and
   send evidence back. They never own a decision of the owner.
3. **Everything an app sends is a proposal or evidence** (P-3, P-10): probe answers become check
   proposals; numbers become readings, which only propose a state; recounted decisions become fact
   proposals or new-decision proposals. The owner approves on one card per conversation or batch, decision
   items first (stage-2 cards; the CLI before that). An app's own "confirmed" is evidence, not the owner's
   approval in CoFlow (P-4).
4. **Apps never number and never create people** (IDN-1, IDN-4, IDN-8). They use a read-only lookup and
   send unknown people as candidates.
5. **References, not copies, across a team boundary.** Other people's decisions are external references
   (DEC-23). The owner's own decisions about a team or client, and the owner's own and delegated
   commitments, are stored (DEC-4, CMT-5).
6. **Decision refs travel as labels.** The envelope echoes the `decision_ref`, `assumption_ref` and
   `occasion_ref` the app received in the brief, so evidence attaches by label, not by a model's guess
   (IDN-7).
7. **Schemas come with their first consumer.** The decision parts of the brief and of the envelope (EXT-5)
   are versioned JSON Schemas built when the first consumer exists (stage 3, the EVENT file adapter).
   They are documented here so the slice does not block them.
8. **Text written by other people is untrusted** (PRV-14, from stage 1): satellite payloads and pulled
   items carry the sub-class `untrusted_external`, are never treated as instructions, and wait in a
   quarantine as proposals.

### 11.2 Decision-referencing fields of the signal envelope (`coflow.int.session`, version 1) [Later 3/6]

| Field | Content | Class | Lands in | Rule |
|---|---|---|---|---|
| `refs.decisions[]` | decision ids the app received in the brief | system | the session's context (SIG) and the outcome card's "decisions in play" | ids only; unknown ids are dropped and counted |
| `refs.occasion` | the `attendance` decision of the occasion | system | session ↔ decision evidence | a session inside the window is offered, never linked silently |
| `owner_marks[]` `{slot: m_decision \| m_probe, decision_ref?, assumption_ref?, segment_idx}` | the owner tapped "a decision is being made or reopened now" or "this answers a probe" | work (an owner observation) | `dec_proposals` (`decision_new` or `fact`) with the segment as evidence | an owner tap is still a proposal: it was not bound to a server-issued preview (P-4) |
| `probes[]` `{decision_ref, assumption_ref, status: asked \| answered \| not_reached, owner_assessment: held \| violated \| cannot_check \| null, segment_idx, quote}` | live probe results | work (the quote may hold third-party speech, `untrusted_external`) | check proposals | `owner_assessment` only when the owner tapped it, never set by a model; a quote must be an exact substring of a sent segment or it is dropped and counted |
| `measurements[]` `{assumption_ref, value, unit, definition, segment_idx?}` | numbers relevant to an assumption | work | `record_reading` (scope `dec:evidence`) | numbers only; the definition is shown with the reading |
| `candidates[]` `{type: decision_new \| decision_fact \| outcome_report \| context_change \| commitment, decision_ref?, assumption_ref?, statement, decided_by, recounted_by, made_in_this_conversation, extracted_outcome, quote, segment_idx}` | the app's own extraction | work, proposal | `dec_proposals`, outcome-report facts (evidence), CMT proposals | merged with CoFlow's own outcome by segment and type; capped; the decision rate per type is measured |
| `app_interpretation.decisions[]` | the app's summary lines about decisions | work, an external interpretation | stored with provenance, never as the record | CoFlow computes the outcome once, from segments |
| `consent` | jurisdiction, mode, purposes | work | the session (PRV-6) | no decision proposal is made from a session without consent for analysis |
| never in an envelope | owner probabilities, money figures, the journal, other people's dossiers, sealed forecasts | — | — | rejected by the schema |

**The brief's decision part** (EXT-5, MTG-2) carries the decisions in play, each with why it is there
(the meeting prepares or reviews it; a participant or their company is `about` or decider; the occasion
contains the meeting) and up to five assumptions to probe (§11.4), each with its threshold, due date, the
source of the due date, and what counts as violated.

### 11.3 Per app: what it reads and what it sends

| App | Reads (projection, §5.4) | Sends | Lands as | Scopes | Stage |
|---|---|---|---|---|---|
| LIVE | a brief per meeting or person: decisions where a participant or their company is `about` or decider, plus the meeting's `prepares` and `reviews` decisions; for each, up to 5 assumptions to probe (§11.4) | the envelope: probes, owner marks, measurements, candidates | check proposals, readings, fact proposals and decision proposals on one outcome card, decision items first; "violated" asks for the review at once (stage 2) | `dec:brief`, `dec:evidence` | 6 |
| EVENT | the brief of an `attendance` decision in the app's brief shape (results ≤ 3 with numbers, hypotheses ≤ 3, who to look for, worth following up, skip, the next-step menu, questions, the decision ref), plus the owner profile | a batch per occasion: confirmed people (through the resolver), confirmed conversations, confirmed commitments both ways, event numbers, hypothesis verdicts the owner set in the app, "next time" notes | sessions (SIG), people (PPL), commitments (CMT, `decision_ref` = the attendance decision), readings on its assumptions, check proposals, a learning proposal at close | the file adapter, then `dec:brief`, `dec:evidence` | 3 (file), 6 (API) |
| UPLOAD | nothing | files and normalised inbox JSON | SIG; decisions only through the meeting outcome (MTG-4) and the proposals it creates | ingestion | 4 / 6 |
| TEAM | a read-only identity lookup (public id and display name only); optionally the owner's own open commitments to that team | by pull: external decision references `{system, external_id, title, health, review_due, audience}`; the owner's own and delegated commitments `{number, title, owner, requested_by, due, status, shifts}`; numbers-only readings for the owner's assumptions | `dec_external_decisions` (linked by `about_external`); CMT commitments with `external_ref` (status one-way from the tool) | `registry:read` | 6 (R2) |
| AGENT | the MCP R tools with the `agent` projection | `dec_create` when the owner asked for it (the owner's quoted words), otherwise `dec_propose`; facts, checks and readings the owner states | decisions, proposals, evidence | `read`, `write` | 0A |

Apps hosted on a third-party platform never push into the home network and never hold a credential of the
instance: `core` pulls from them outbound with a read-only export token the app issues for one workspace
the owner owns, by cursor, with size limits and a schema check (EXT-4, D-051). Pulled items are
`untrusted_external` and become proposals.

### 11.4 Assumptions to probe: the selection rule (deterministic) [Later 3, used by MTG and INT]

```python
def assumptions_to_probe(subjects, limit=5, T=now):
    items = []
    for d in open_for(subjects):                              # active decisions touching the participants
        if d.mirror_scope == 'full': continue                 # never probe records v2 does not own
        for a in active_assumptions(d):
            if a.data_source_kind == 'none': continue
            s = effective_state(a, T); cd = check_due(a, T); due, src = assumption_due(a, T)
            rank = 0 if s == 'VIOLATED' else 1 if cd else \
                   2 if (a.is_critical and s in ('UNCHECKED', 'NOT_YET_DUE', 'UNKNOWN')) else None
            if rank is not None:
                items.append((rank, due or date.max, d.number, a.code_n,
                              ProbeItem(d.public_id, a.ref, a.statement, a.metric, threshold_text(a), due, src,
                                        violation_text=render_threshold_negation(a), question=probe_template(a))))
    return [x[-1] for x in sorted(items, key=lambda x: x[:4])[:limit]]
```

### 11.5 Remote access is not precluded

- All decision behaviour sits behind `dec.api`. MCP tools, the CLI and later the INT endpoints are thin
  adapters.
- **Accepted (D-052):** the bot and the VPN come first; cloud AI clients come later, as the first stage-8
  module, read-only first. The internet-facing MCP (MCP-5) exposes the R tools through the cloud view
  (§5.4) with a per-client allow-list; `untrusted_external` text is withheld by default (PRV-14); writes
  for cloud clients are a separate resource with its own audience, off by default; approval never. The
  `edge` container holds no database (PRV-13), and the public entry is the owner's relay that never
  decrypts (D-053).
- Every write takes an actor, a channel, an interaction id and an idempotency key, so a remote client or a
  satellite retrying over a bad connection never duplicates anything.
- Satellites calling the ingestion API (DEP-16) meet DEC only through `propose_from_signal(envelope_part)`,
  which creates proposals and readings [Later 3/6].
- The snapshot importer reads a file. The same file may later arrive through the ingestion API with an
  `import` scope.

### 11.6 What never crosses

| Direction | Never |
|---|---|
| CoFlow → any app | the journal or anything derived from it; owner probabilities; sealed forecasts; money unless that app's financial flag allows it; the grounds' text of decisions about third parties; people's dossiers to TEAM; decisions marked `private` to a public or team audience |
| any app → CoFlow | raw audio by default; a team's forecasts before their reveal; records whose audience in the team tool excludes the owner's role; data the owner processes for a client as a processor without the client's agreement to this purpose; app events, audio levels, debug ticks |

---

## 12. Acceptance tests and usage signals

### 12.1 Slice acceptance tests

All tests are synthetic, offline and use temp data roots, on Windows and Linux. The fixture world:
- the owner profile "Owner", zone `Europe/Berlin`, a fake clock with today = 2026-11-15;
- foreign people `V1_P901` ("Person A") and `V1_P902`;
- goals `V1_G901` "Cut fixed costs" (dropped on 2026-11-05) and `V1_G902` "Grow the training line"
  (active);
- the synthetic snapshot family S1, S1′ and S1″ (v1 numbers 903 to 910, tombstones 901 and 902).

**Increment I1: read-only shadow**

| # | Scenario | Expected | Req. |
|---|---|---|---|
| AT-K1 | 1,000 concurrent issues of `D` from 8 threads after registering `sys_id_foreign` 903 to 910 and burning 901 and 902 | no duplicates, no reuse, no foreign or burned number issued; the first native is `D-1001` | IDN-1, IDN-10 |
| AT-K2 | `parse(render(id)) = id` for every prefix and scoped code; an unregistered prefix | the identity holds; `Refused` | IDN-2 |
| AT-K3 | the inputs `D907`, `d907`, `D 907`, `d-907`, `D0907`, `Д907` and `д907` (through the fixture locale pack of §3.2), `D907 A1`, `D907_A1`, `D907/A1`, `D-0907_A01`; `D907 Z1`; `D12345` | `D-0907` / `D-0907_A-01`; the output is always canonical; `NotFound` for the unknown scoped prefix and for a number wider than the prefix allows | IDN-9 |
| AT-K4 | `UPDATE dec_checks SET state='HOLDING'`; set `voided_at` once, then again; blank an erasable column with `erased_tx` | fails; the first succeeds, the second fails; succeeds | DEC-13, NFR-13 |
| AT-K5 | fault injection after every statement of a unit of work; a command that passes `recorded_at` | its rows and events both exist or neither; `tx` and `recorded_at` are set by STO; `STORE_STAMPED_FIELD` | P-14, NFR-13 |
| AT-K6 | an event schema scan over every DEC and CMT event; canary values written into a decision | payloads hold only ids, entity and changed names; no canary in `sys_events` | P-14 |
| AT-K7 | `coflow run` twice; a CLI write with the core running and with it stopped; `coflow mcp-stdio` | the second core refuses; CLI writes go through the admin API or an ephemeral core under the same lock; the shim cannot resolve the database path | OPS-3, MCP-1 |
| AT-K8 | `cfj({"q1": 70, "q2": 20})` against the pilot's canonical bytes; `sha256(salt + canonical)` of a fixture seal; a float in a basis | byte-identical; the seal verifies; `TypeError` | DEC-12 |
| AT-K9 | importing S1 without `"synthetic": true` into a dev instance; S1 into dev; a validation instance whose data root, or an ancestor of it, holds a `.git` directory or a `.git` file (also through a symlink); S1 into a validation instance outside any working tree; any snapshot into a drill instance | `IMPORT_NOT_SYNTHETIC`; accepted; `doctor` and `init` refuse the data root; `IMPORT_ROLE` ("synthetic snapshots belong in a dev instance"); `IMPORT_ROLE` | DEP-23 |
| AT-D1 | the v1 date vectors, ported: ISO, day.month.year, day.month in order of appearance; "1.5", "0.80", "12.5 %", "31.02"; HTML-escaped text; the year rollover; the floor rule (a date equal to the creation day is not due; after a check on day 7, "by 07.11 or after 11.11" moves to the 11th); `by_date` beats text; explicit beats both; the synthetic `dates_in` vector table of §4.6 (dates in order of their position in the text) | all as stated | DEC-6 |
| AT-D2 | `next_check_after` after a check on 2026-11-01: weekly, monthly, quarterly, ad hoc, explicit, no frequency with a future and with a past `next_check_at` | 11-08, 12-01, 2027-01-30, none, the explicit date, kept, dropped | DEC-6 |
| AT-D3 | the named vectors H1 to H18; the oracle agreement over the enumerated space (§4.7) | 100 % | DEC-3 |
| AT-D4 | a synthetic month of due checks across 6 decisions | each check due appears on its due day and only then; review-sourced dates never duplicate the review reason; a review overdue appears even when the ground is INSUFFICIENT; the order is: a critical violation first, then the oldest due date, then the number | DEC-6 |
| AT-S1 | import S1 (8 decisions: one closed, one with every assumption unverifiable and an overdue review, one serving the dropped `V1_G901`, one active without a review date, one with no assumptions, one with a non-critical violated assumption, one HOLDING with a weekly check overdue, one with a state reset) | counts equal; mirrors `D-0903` to `D-0910`, depth `full`, `reconstructed = 1`; the active and terminal ones sealed E-01 (reason `import`); `V1_D907` resolves; the closed one has a `reported` resolution with `resolved_by = import`; the reset assumption has an UNKNOWN assessment; S1 with `source.timezone` other than the owner's zone, and S1 with `v1_computed.today` other than `as_of_date`, are refused with `IMPORT_SOURCE_CONFLICT`; S1 with a float in any number is refused with `IMPORT_FORMAT_UNSUPPORTED` | OPS-15, DEC-12 |
| AT-S2 | import S1 again; then S1 with `--final` | a run row with status `noop`, and no mirrored row, version or event; then a run row in mode `final`, after which S1′ is refused with `IMPORT_ADOPTED` | OPS-15 |
| AT-S3 | import S1′ (one fact text changed, one decision removed, one statement changed, one `last_checked_at` moved without a version row) | a version row; the removed decision tombstoned (`absent_since_run_id`), not deleted, and absent from `waiting`; for the changed statement, O-01 voided, the next option appended and chosen, E-02 with reason `source_changed` and one `basis_drift` finding, while E-01 still verifies; exactly one reconstructed assessment | OPS-15, OPS-16 |
| AT-S4 | any write command on a V1 mirror, over MCP and over the CLI | `MIRRORED`, naming V1 as the system of record | OPS-15 |
| AT-S5 | the shadow report on S1 with a planted `v1_computed` | each of SR-1 to SR-10 classified `expected` at least once; every due date `same`; an injected v1 due-date mismatch → `unexpected`; an injected order swap → `unexpected` | OPS-16 |
| AT-S6 | a fault injected in the middle of the S1 import; then the unit bound lowered to force chunks, with a fault in chunk 2 | nothing applied, the run `failed`; then the run stays `partial`, `shadow_report` is `blocked`, the re-run completes and the report is written | OPS-16 |
| AT-S7 | `V1_G901` dropped on 11-05 after the decided date 11-02, no review since; then an imported review on 11-10 | exactly one `goal_changed` reason dated 11-05; after the review, none | DEC-16 |
| AT-S8 | a mirror created in v1 on day 2 and imported on day 30 | `as_of(day 5, knowledge)` contains it; `as_of(day 5, instance)` does not | DEC-13 |
| AT-S9 | a snapshot whose assumption has `last_checked_at = as_of_date` and whose decision has a review with `reviewed_at = as_of_date` | both the rebuilt check and the review are visible to that run's shadow (K capped at `as_of`); no `check_due`, `review_overdue` or `STALE` against them | OPS-16, DEC-13 |
| AT-S10 | a snapshot that differs from S1 only in one decision's `review_due` (a keep in v1) | the head updated with one version row; `review_due_initial` unchanged; no `source_changed` edition and no `basis_drift` finding | OPS-15, DEC-12 |
| AT-M1 | `dec_waiting`, `dec_context` over MCP; `coflow dec waiting --json` and `show --json` on the CLI; the `waiting` query | identical JSON payloads (§7.5), items and order; every answer states the instance role and the mirror authority; no token → 401; a foreign Host header refused; a read-only token cannot call a write tool; every pull is recorded as a usage signal | MCP-1, DEC-6 |

**Increment I2: native loop**

| # | Scenario | Expected | Req. |
|---|---|---|---|
| AT-N1 | `create_decision("Adopt a weekly release train", light, review 2026-12-01, statement, decided today)`, then `activate` | `D-1001`, active, E-01, ON_TRACK (NOT_MONITORED); the `created`, `activated` and `edition.sealed` events in their units | DEC-1, DEC-12 |
| AT-N2 | `create_decision("Hire a part-time bookkeeper", full, review 2026-12-15, decided 2026-11-14)` without question, options, unknown, success criterion or assumption; `activate` | `ACTIVATION_GATE(missing=[question, options, unknown, success_criterion, assumption])`; still a draft | DEC-1 |
| AT-N3 | complete AT-N2 and activate; `update_decision(statement=…)`; `update_decision(title=…)` | `SEALED_USE_REVISE`; the title changed with a version row | DEC-12 |
| AT-N4 | edit the statement of `D-1002` directly in the database; then also edit `fields_json`; then erase a ground fact through the POL test hook | `live: drift` with E-01 `ok`; E-01 `changed`; after restoring, `ok_with_erasures (1)` | DEC-12 |
| AT-N5 | revise `D-1002` without a `revise_basis`; with `trigger_fact` naming another decision's fact; with `trigger_fact` FT-001 of D-1002 and next 2026-12-20; a correction | `REVISE_BASIS_REQUIRED`; `TRIGGER_FACT_REQUIRED`; E-02 (reason `revise`), E-01 still `ok`, the public id unchanged; E-03 (reason `correction`), not counted as a revision | DEC-12 |
| AT-N6 | `adjust` with next 2026-12-10 | `review_due` moved; no new edition | DEC-7 |
| AT-N7 | `keep` without a date, over MCP and over the CLI; `keep` 800 days ahead | `REVIEW_DATE_REQUIRED` in both channels; `REVIEW_DATE_OUT_OF_RANGE` | DEC-7 |
| AT-N8 | close `D-1001` with success / reported and no learning; with a learning; close again with basis resolved and no evidence; with evidence CK-002 | `LEARNING_REQUIRED`; `CLOSED · success · reported` (grey); `RESOLVED_NEEDS_EVIDENCE`; a second resolution supersedes the first and shows green | DEC-15 |
| AT-N9 | `add_fact(D-1003, assumption_refs=['D-1004_A-01'])` over MCP and the CLI; one fact bearing on A-01, A-02 and A-03 of D-1003 | `FOREIGN_ASSUMPTION` in both channels; three bearing rows | DEC-2 |
| AT-N10 | `add_fact` with an evidence ref that a fake resolver reports as journal class | `JOURNAL_CLASS_INPUT`; no row; the canary is absent from every DEC table, `sys_events`, the logs and MCP answers | P-2, DEC-2 |
| AT-N11 | weekly A-02 checked HOLDING twice, a week apart; ad hoc A-04 checked HOLDING; the `likely_actions` shown for A-02 before the second check | two rows, "last checked" derived; A-04's due date falls back to the review (no default step); the next date shown equals the date written | DEC-13, DEC-20 |
| AT-N12 | A-05 `>= 150` by 2026-11-15: a reading of 92 on 11-10, then on 11-16. A-06 `<= 16` (a cap): a reading of 18 mid-period. Units "h" against "days" | no proposal (`before_judge_from`); `VIOLATED` proposed; `VIOLATED` proposed; `unit_mismatch`; the state changes only through `record_check(accept_reading=…)` | DEC-13 |
| AT-N13 | an UNKNOWN check, and then an UNVERIFIABLE check, on a critical assumption of a two-assumption pool | UNKNOWN leaves the share at 0 and the label AWAITING_CHECKS; UNVERIFIABLE raises the share to 0.5 | DEC-3 |
| AT-N14 | `open_fork("Which venue for the workshop?")` with options A and B on 11-10, deadline 11-14; `waiting` on 11-15; `decide_fork(O-02)`; `add_option(C)` on 11-16 | `fork_due` on 11-15 (dated 11-14); a decision whose options A and B are `recorded_before_choice = yes`, `chosen_option` the copy of B, and C `no`; the fork `decided`; the fork → decision latency in the history | DEC-14 |
| AT-N15 | supersede `D-1002` by `D-1005`; supersede by itself | `superseded`; a `supersedes` link on D-1005; `SUCCESSOR_INVALID` | DEC-7, DEC-11 |
| AT-N16 | create a decision about `V1_P901` with an assumption of class `demand`, when a closed decision with the same subject and a violated `demand` assumption exists | `related_learnings[0]` names it with "1 of 1 earlier demand assumptions violated"; `informed_by` links them | DEC-15 |
| AT-N17 | decided 2026-10-01 and recorded 2026-10-11; decided 2026-10-01 and recorded 2026-10-03 | retroactive; not retroactive (N = 3) | DEC-13 |
| AT-N18 | undo `dec_record_check`; undo a `keep`; undo `dec_activate`; undo `dec_create` on a draft | the check voided and the due date restored; the previous review date restored; `NOT_UNDOABLE`; the status `withdrawn`, and the number is never issued again | MCP-4 |
| AT-N19 | every command retried with the same idempotency key | the first result returned; one row; one event | P-14 |
| AT-N20 | `import log` of a synthetic three-entry log with `--only` two entries; add an assumption, a success criterion and a review date to one, and activate it; `update_decision(statement)` on it; re-import with the entry's Context changed; on a reconstructed active mirror after a fake adoption, add an assumption and run a `keep` review | two drafts, issuer `CF2LOG`, numbers from the block, public; activation seals E-01; `MIRRORED` (log-owned); a `source_changed` edition; `completion_pending`, then the keep seals an edition with reason `completion`, not counted as a revision | OPS-15, DEC-12 |
| AT-N21 | `set_publishability(public)` on a `third_party_sensitive` decision; `public` over the admin API with a non-owner channel; clearing the mark on an active decision; a money stake in an MCP answer to a token without `financial` | `PUBLISHABILITY_LOCKED`; `OWNER_CHANNEL_REQUIRED`; `PUBLISHABILITY_LOCKED`; the amount withheld with a coverage note | PRV-10 |
| AT-N22 | `drafts_to_finish` with an owner draft 8 days old, a draft 2 days old and a pending proposal | the old draft listed with its missing fields; the young draft and the proposal not listed (the proposal is in `waiting`, last) | DEC-6 |
| AT-N23 | a stale fixture: review 31 days overdue, last fact 45 days old, a served goal dropped 20 days ago, two commitments overdue (through the fake probe) | the card shows the one-line decision, the share line, the last fact with its age, "review date passed", the goal as dropped with its date, "2 overdue", and likely actions led by keep and adjust with their dates, then close and cancel | DEC-20 |
| AT-N24 | `add_option(chosen=true)` on an active decision; a revise with `--choose O-03`; a revise that replaces the reason of O-02 | `SEALED_USE_REVISE`; the next edition with `chosen_option = 3`, every earlier edition still `ok`; O-02 voided, O-04 appended with `copied_from` O-02, every earlier edition still `ok` | DEC-12 |
| AT-N25 | `create_decision` without `decided_at`, then `activate`; with `decided_at = unknown`; with `decided_at = today` | `ACTIVATION_GATE(missing=[decided_at])`; activates with precision and basis `unknown`; activates with basis `live` | DEC-1, DEC-13 |

**Increment I3: execution and evidence**

| # | Scenario | Expected | Req. |
|---|---|---|---|
| AT-C1 | `create_commitment(self → V1_P901, "send the draft", due 2026-11-20, decision D-1002)`; another with `no_decision_reason=routine`; a third with neither | `F-10001` linked; `F-10002` explicit none; `F-10003` unanswered; `unlinked_report` shows 1/1/1 with refs | CMT-1, DEC-19 |
| AT-C2 | shift F-10001's due date with a reason; then review `D-1002` keep | `execution_summary_json` says total 1, open 1, shifted 1; DEC holds no CMT data beyond those counts and ids | DEC-7, DEC-11 |
| AT-C3 | cancel `D-1002` | `open_commitments` annotates F-10001 "decision ended: keep, drop or move?"; F-10001's status is unchanged | DEC-11 |
| AT-C4 | `create_commitment(decision=D-1001)` after D-1001 closed; `create_commitment(decision=D-0907)` (a V1 mirror) | `DECISION_ENDED` with the successor hint; `MIRRORED` ("record it in its system of record until adoption") | DEC-11 |
| AT-C5 | `done` without `--at`; `--at unknown`; a `suggested_done` from the CLI | `DONE_NEEDS_TIME`; accepted with `done_basis = unknown`; `SUGGESTED_DONE_FROM_PROPOSAL_ONLY` | CMT-1 |
| AT-C6 | a commitment created through MCP whose text names `D-1003`; one for `V1_P901` while an active decision is about `V1_P901` | the first is offered D-1003 preselected ("named"); the second is offered that decision ("same person or company"); at most three offers; the same data gives the same offers | DEC-19, P-15 |
| AT-P1 | `dec_propose` over MCP naming D-1003 in its text; `approve_proposal` over MCP; over the CLI; a rejected payload proposed again; 30 proposals from one origin with 5 approved | `match_candidates` lists D-1003 as "named"; `OWNER_CHANNEL_REQUIRED`; a decision with `origin_kind = proposal`; `PROPOSAL_REJECTED_BEFORE`; the origin switches itself off (`PROPOSAL_ORIGIN_SWITCHED_OFF`) and says so | DEC-17 |
| AT-H1 | `decision_history(D-1003, October to November)` on a fixture where A-01 goes HOLDING → VIOLATED after a fact, then a commitment is done and a review follows | one change, with its preceding fact ref, the following commitment `done` event (through the probe) and the review ref, all with refs and transaction provenance; a coverage line; on an empty period, "no data in stored history" | DEC-18 |
| AT-H2 | `loop_metrics` on a fixture month | checks on the due day and within 7 days, violation → review latency, closed with outcome and learning by basis, MCP-origin writes counted apart, pulls per channel; the same data gives the same numbers | DEC-18 |
| AT-R1 | `coflow dec case run RC-1.yaml` against S1 in a dev instance (it adds a fact, an adjust and a commitment on the mirror D-0907) | the expectations pass; a `dec_cases` row `pass`; apart from that row, the source database is byte-identical before and after | OPS-16 |
| AT-R2 | `adopt_mirrors` on 2026-11-20 with every other condition faked true; on 2026-12-02 with 13 clean runs; on 2026-12-02 with every condition but the host gate; with every condition true | `ADOPTION_GATE(missing=['date >= 2026-12-01'])`; `ADOPTION_GATE(missing=['14 clean shadow runs'])`; `ADOPTION_GATE(missing=['host gate'])`; mirrors adopted, ids unchanged, writes now allowed, the next native number follows the highest in use | OPS-16, IDN-10, DEP-27 |
| AT-X1 | the import-linter contracts | DEC imports nothing from tier 3 or above; CMT imports DEC only through `api` or the port; `aln` is tier 8 | DEC-11 |
| AT-X2 | the whole suite with every app adapter absent | passes | EXT-6 |
| AT-X3 | the MCP catalogue | every write tool has an undo handler or the "not undoable" mark; every tool name starts with `dec_` or `cmt_`; the catalogue matches the generated file | MCP-3, MCP-4 |

**Quality thresholds** (the DEC card of [MODULES.md](MODULES.md)): health vectors and oracle agreement
100 %; the date table 100 %; identical waiting items across the CLI, MCP and the query; 0 editions that
fail to verify without a database bypass and 0 bypass edits undetected; 0 closings without an outcome
basis or a learning; 0 keep, adjust or revise without a next date in any channel; 0 facts naming another
decision's assumption; 0 journal-class evidence accepted; 0 changes after re-importing an unchanged
snapshot; 0 writes accepted on a mirror; 0 imports from DEC into a higher tier; 0 values in event
payloads; `waiting` over 200 active decisions at p95 ≤ 500 ms and a command at p95 ≤ 300 ms.

### 12.2 The owner's real cases

On 17 October 2026 the owner named four cases for stage 0A and a fifth for stage 5 (D-036). They run in
the validation instance, through the shadow and through the case runner; their scripts, their results and
the snapshot live only in the validation data root, never in any repository, public or private. This
document names only their shapes. Shapes 1–4 are the four; their scripts must pass at the 0A exit. Shape 5
is not an owner case but the project-log exit criterion of §1.4 (proposed, D-046). The fifth owner case
belongs to stage 5: a meeting whose commitments execute a decision (MTG-1, MTG-2, MTG-4).

1. **A context change on an existing arrangement.** The shadow shows the right due dates, waiting reasons
   and context; the case script adds a fact, an adjust with a new review date and a commitment, and the
   reason disappears.
2. **A decision whose goal was dropped.** The shadow shows `goal_changed` once with the goal's title and
   date, the label does not hide the overdue review, and the case script closes or cancels it with a
   learning.
3. **A decision with computable assumptions.** Structured thresholds are added as successors on a
   completed record, readings propose states, and the review card shows the numbers.
4. **A half-filled cluster under one gate.** `incomplete` items and `part_of` links; the card lists the
   gaps one at a time.
5. **A project decision from the public log.** The owner adds assumptions with by-dates and a review date,
   activates, checks on the due day and reviews: the full loop on publishable data.

Proposed, for the owner to confirm: in 0A shape 1 passes in its scripted form (a fact, an adjust and a
commitment), and its one-sentence chat form ("one sentence, one card") is a stage-2 exit criterion
(DEC-9); in shape 3 the owner enters the readings, and computing them from CoFlow's own records waits for
the `internal_query` trigger of §12.4.

### 12.3 Usage signals (P-13)

| Signal | Source | Floor and action |
|---|---|---|
| **Closed decisions with an outcome and a learning per month** (headline) | `dec_outcomes`, `dec_learnings` | below 1 a month for two months after adoption → the close card is redesigned |
| Checks answered within 7 days of their due date (share) | `dec_checks.due_answered` | below 50 % over 4 weeks → the question rhythm is re-examined (stage 2) |
| Days from a VIOLATED check to a review (median) | checks, reviews | above 7 → the "violated asks at once" rule is checked |
| Waiting-list pulls per day by channel | `sys_usage_signals` | no pull for 7 days before the bot exists → the owner is asked once whether the pull loop serves them |
| Share of new commitments (and tasks from stage 1) linked at entry; the four buckets | the probes | `not_offered` above 0 for owner-channel entries → a defect; `unanswered` above 50 % → the offer is redesigned |
| Unexpected shadow differences per run | `dec_shadow_items` | any → fixed or turned into a rule before the next run |
| Proposals approved per origin | `dec_proposals` | below 20 % over the last 30 → the origin switches itself off |
| MCP-origin decisions and checks (share) | `sys_tx_log` | reported, no floor; a sharp rise with a falling approval of proposals → the tool descriptions are reviewed |
| Drafts older than 14 days | `drafts_to_finish` | above 3 → the activation gate is too heavy |
| Shadow report opened | the CLI and MCP call logs | not opened for 14 days → the owner is asked once whether to keep it daily |
| Integrity failures | `integrity()` | any → an incident |
| Learnings cited by later decisions | `informed_by` links | below 1 a quarter → the related-learnings surface is redesigned |

### 12.4 Deferred mechanisms and the signal that brings each one in

| Mechanism | Not in the slice because | Brought in when |
|---|---|---|
| Bot questions, approval cards, the asked log | the bot is stage 2 | stage 2 (planned) |
| Automatic checks from stored queries over CoFlow data or app metrics | no source module yet | at least 5 active assumptions carry `data_source_kind = internal_query`, or the owner records the same reading by hand at least 3 times |
| The contradiction detector ("this fact changes decision X") and non-occurrence items | needs conversations and a capped card | stage 3 (DEC-22) |
| Separate forecast records, model probabilities, scoring | the forecast pilot reports on 1 December 2026 | the pilot's report recommends it, or at least 30 owner probabilities exist on resolved checkpoints |
| Occasion fields and the event brief | an `attendance` kind is enough until the first event case | stage 3 (DEC-21), or earlier if an occasion becomes a named real case |
| Proposal match classification (new, update, retelling, contradiction) | needs extraction | stage 3 |
| Decision-graph views (follows, depends on, part of) | links exist; views do not | at least 10 decision↔decision links in use |
| A cap on business hypotheses and an opportunity-filter form | the `test` kind and its assumptions carry it; the wording is the owner's content (CFG-4) | at least 3 active `test` decisions, or the owner asks for the cap check |
| Per-unit entry for scoped assumptions | no measured need | an assumption about several sites or people recorded at least 3 times |
| A trace detector ("an action happened, no decision recorded") | needs WRK, FIN and CAL data | stage-1 data and a pre-registered rule set |
| Monthly, quarterly and annual review slots | the weekly review (RHY-4) comes first | two weekly reviews that produced decision reviews |
| Projections for team tools and publication tooling | publishability is a column; no export yet | the first episode or team share that needs a decision |
| Importing v1 task-kind "decision" items as proposals | small value, noisy | the owner asks |
| The erasure command (PRV-7) | arrives in 0B or stage 1 | the hashing already supports it |
| A checkpoint's failure action (what is done when a gate fails) | the review records it in words | the owner writes a failure action in words on at least 3 checkpoints |
| Observations → a decision proposal with "what is missing to say for sure", capped and extinguished on dismissal | needs capture from conversations | stage 3 (DEC-17, DEC-22) |
| Decision classes, assumption templates, playbooks, a premortem sentence | no measured need | at least 3 decisions of one class recorded with the same assumptions |

---

## 13. Build plan (proposed, D-040)

**Accepted (D-040):** build now a minimal stage-0 kernel and a vertical slice of the decision core;
Docker, CD and backups in the next part of stage 0. **Proposed:** the increments, tracks and sizes below.

The plan suits 3–4 coding agents working in parallel on disjoint files after a shared skeleton. Each
increment closes with its tests green on Windows and Linux before the next starts. Paths are relative to
`src/coflow/`, except those that start with `tests/`, `tools/`, `contracts/` or `.github/`, which are
relative to the repository root.

### 13.0 Preconditions, before the first code pull request

| # | Item | Who |
|---|---|---|
| P0.1 | The documentation commit that adds D-038 to D-053, the requirement rows of REQUIREMENTS 0.7 and the ROADMAP, ARCHITECTURE and MODULES edits, with `python tools/check_docs.py` green | an agent; the owner reviews |
| P0.2 | No owner data lives inside the repository working tree; data roots live outside it (DEP-23) | **the owner** |
| P0.3 | `.gitignore` covers tool state, dependency folders, archives, exported chat files and any validation or data-root directory | an agent |
| P0.4 | Repository protection (a protected `main`, a DCO check, secret scanning, pinned actions, a read-only default token) is on before the first code pull request (DEP-7, DEP-8) | **the owner** (settings), an agent (workflows) |
| P0.5 | The commit identity for the public history | **the owner** |
| P0.6 | Before the first real snapshot enters the validation instance: the agents' operating-system account cannot read the validation data root, and the development disk is encrypted (PRV-15; proposed) | **the owner** |

### 13.1 Shared skeleton (one agent, first; small)

| File or directory | Content |
|---|---|
| `pyproject.toml`, `uv.lock` | Python ≥ 3.12; runtime: `mcp` (the official SDK), `starlette`, `uvicorn`, `jsonschema`, `pyyaml`; dev: `pytest`, `hypothesis`, `import-linter`, `ruff`. Everything pinned through the lock (DEP-22) |
| `.github/workflows/ci.yml` | a matrix of `windows-latest` and `ubuntu-latest`: `uv sync --frozen`, `ruff check`, `ruff format --check`, `lint-imports`, `pytest -q`, `python tools/literal_gate.py`, `python tools/check_docs.py`; actions pinned by commit (DEP-7) |
| `.importlinter` | the contracts `top`, `kernel`, `domain` (with `aln` as tier 8, an empty package), `api-only` (custom), `adapters` |
| `tools/literal_gate.py` | the minimal P-12 detector: e-mail addresses, phone numbers, non-example domains, IP addresses outside documentation ranges, private host names, names outside the fixture allow-list |
| `kernel/context.py` | `CommandContext(actor, channel, owner_channel, interaction_id, source_ref, idempotency_key, expected_version)`, the `Clock` protocol, `FakeClock` |
| `kernel/errors.py` | `NotFound`, `Ambiguous`, `Refused(code, detail, missing, allowed)`, `Conflict`; the `RefusalCode` enumeration of §7.1 |
| `kernel/ports/` | `decision_directory.py`, `attachment_probe.py`, `evidence_resolver.py`, `goal_directory.py`, `undo.py`: protocols and their DTO dataclasses, each with a fake in `tests/fakes/` |
| `kernel/store/api.py` | the signatures every track codes against: `unit_of_work(owner_module, ctx)`, `read_connection()`, `insert(table, row)`, `set_once(table, id, **cols)`, `update_head(table, id, version, **cols)` |
| `modules/dec/domain/model.py` | frozen dataclasses: `DecisionView`, `AssumptionView`, `CheckView`, `ReadingView`, `FactView`, `ReviewView`, `OutcomeView`, `LinkView`, `GoalState`, `WaitingItem`, `Reason`, `HealthResult` |
| `modules/dec/api.py`, `modules/cmt/api.py` | the public facade: every command and query of §7 as a stub that delegates to the file the owning track implements |
| `tests/conftest.py`, `tests/fakes/` | the temp data root, the fake clock (2026-11-15, `Europe/Berlin`), the fixture loader, the fake ports |
| module cards | the DEC and CMT cards in [MODULES.md](MODULES.md) (NFR-10) |

### 13.2 Increment I1: read-only shadow (4 tracks)

| Track | Owns (files) | Delivers | Tests |
|---|---|---|---|
| **K: kernel** | `kernel/store/{db,writer,unit,migrations,registry,triggers,authorizer,txlog,lock}.py`; `kernel/ids/{registry,tap,codes,aliases}.py`; `kernel/events/{publish,dispatch}.py`; `kernel/policy/{classes,canary}.py`; `kernel/config/{profile,settings}.py`; `kernel/ops/{instance,init,doctor}.py`; `kernel/obs/usage.py`; `migrations/kernel/0001_kernel.sql` | the kernel tables of §3.3; triggers generated from the registry; the instance lock; `init` (dev, validation); a `doctor` that checks the role, the lock, a data root outside any repository working tree and the schema revision | AT-K1, AT-K2, AT-K3, AT-K4, AT-K5, AT-K6, AT-K7, AT-K9 |
| **D: decision domain (pure)** | `modules/dec/domain/{cfj,dates,due,states,health,waiting,context_card,goals}.py`, `modules/dec/queries.py` (assembling views → computed results) | §4.3 (CFJ-1 and the hash functions), §4.4, §4.6, §4.7, §4.8 (decisions only), §4.9, §4.13; `decision_context`, `waiting`, `health`, `assumption_due`, `integrity` (read side), `as_of` | AT-K8, AT-D1, AT-D2, AT-D3 (vectors), AT-D4 |
| **S: store, import, shadow** | `modules/dec/migrations/0001_dec.sql` (**all** DEC tables of §3.4 and §3.6); `modules/dec/store/{repo,versions,mirror}.py`; `modules/dec/importer/{snapshot,apply,rebuild_checks}.py`; `modules/dec/shadow/{compare,rules}.py`; `modules/dec/goals_shadow.py`; `contracts/import_decisions_v1.schema.json`; `tests/fixtures/synthetic/snapshots/`; **`tests/oracle/health_oracle.py`** (written independently from §4.7, without reading track D's code) | the importer (§10.5) with sealing at import (using D's hash functions), the rebuilt check log, the foreign context, the shadow report (§10.6) | AT-S1 to AT-S8, AT-D3 (oracle agreement) |
| **X: interfaces** | `interfaces/admin/{api,cli,render}.py`; `interfaces/mcp/{server,auth,stdio_shim,catalogue,tools_dec}.py` (read tools); `interfaces/views/card.py`; `app/{composition,supervisor}.py` | `coflow init`, `doctor`, `run`, `mcp-stdio`, `mcp token new`, `dec import v1`, `dec waiting` (with `--brief` and the documented morning-pull recipe, §9), `dec show`, `dec list`, `dec shadow`, `dec integrity`; MCP `dec_list`, `dec_context`, `dec_waiting`, `dec_integrity`, `dec_shadow_report`; usage-signal pulls | AT-M1 |

**I1 is done when** the owner can import a real snapshot into a validation instance, see equal counts,
and ask "what is waiting and why" over MCP and the CLI with the shadow report beside it.

### 13.3 Increment I2: native loop (4 tracks)

| Track | Owns (files) | Delivers | Tests |
|---|---|---|---|
| **D** | `modules/dec/domain/{seal,activation,review_rules,readings,learnings}.py` | `seal`, `integrity` (full), `missing_for_activation`, `proposed_depth`, the review validation of §4.10, `proposed_state_from_reading`, `related_learnings` | AT-N4 (domain part), AT-N12, AT-N13, AT-N16, AT-N17, AT-N24 (domain part), AT-N25 |
| **S** | `modules/dec/commands/{decisions,assumptions,checks,readings,facts,reviews,forks,links,flags}.py`; `modules/dec/undo.py` | every DEC command of §7.2 marked I2, with versions, events, idempotency keys and the mirror guard (both scopes) | AT-N1, AT-N2, AT-N3, AT-N5 to AT-N10, AT-N14, AT-N15, AT-N18, AT-N19, AT-N21, AT-N24 |
| **K** | `modules/dec/importer/project_log.py`; `modules/dec/evidence.py` (the `EvidenceResolver` built-ins); `kernel/policy/erasure_hook.py` (a test-only erasure hook) | `import_decision_log` with `--only`; completion handling with S's review command; the built-in resolvers; the journal-class refusal | AT-N4 (erasure part), AT-N10 (resolver part), AT-N20 |
| **X** | `interfaces/mcp/tools_dec.py` (write tools), `interfaces/admin/cli.py` (write commands), `interfaces/views/card.py` (question context, drafts to finish) | the MCP write tools of §8 marked I2, with undo registration; the CLI write commands of §9; the `dec_` namespace | AT-N11, AT-N22, AT-N23, the MCP parts of AT-N7 and AT-N9 |

### 13.4 Increment I3: execution and evidence (3–4 tracks)

| Track | Owns (files) | Delivers | Tests |
|---|---|---|---|
| **C: commitments** (K's agent) | `modules/cmt/{api,commands,queries,probe}.py`; `modules/cmt/migrations/0001_cmt.sql`; `modules/dec/directory.py` (`accepts_attachment`, `likely_for_entry`) | §3.5, §7.4; the probe; the entry-time offers | AT-C1 to AT-C6 |
| **D** | `modules/dec/domain/{history,metrics}.py`; `modules/dec/queries_reports.py` (`unlinked_report`, `loop_metrics`) | the report of §4.14, the history of §4.15, the metrics of §4.16 | AT-H1, AT-H2 |
| **S** | `modules/dec/commands/proposals.py`; `modules/dec/shadow/cases.py`; `modules/dec/importer/adopt.py`; `kernel/obs/jobs.py` (`dec metrics --store`) | proposals and their approval in an owner channel; the case runner; the adoption gate | AT-P1, AT-R1, AT-R2 |
| **X** | `interfaces/mcp/tools_cmt.py`, the remaining `tools_dec.py` entries, `interfaces/admin/cli.py` (cmt, proposals, history, metrics, links-report, case, adopt); `tests/interfaces/test_catalogue.py` | the remaining MCP and CLI surface; the catalogue test | AT-X1, AT-X2, AT-X3 |

### 13.5 Conventions every track follows

- **Contracts first.** Tracks code against the skeleton's signatures. A signature change is a pull request
  to the skeleton files, reviewed before either side merges.
- **File ownership.** No track edits another track's files. Shared fixtures live in
  `tests/fixtures/synthetic/` and are only appended to.
- **Synthetic data only** in the repository. The real snapshot, the case scripts and the case reports live
  in the validation data root.
- **Determinism.** Every computed function takes `T` and the configuration explicitly. There is no
  wall-clock call outside `kernel.context.Clock`, and no randomness outside `new_salt()`.
- **Independent oracle.** Track S writes `tests/oracle/health_oracle.py` from §4.7 without reading
  `modules/dec/domain/health.py`. A disagreement is resolved by correcting this text first, then the
  losing side.
- **This document leads.** A behaviour this document does not describe is not built in the slice; a gap
  found while coding is fixed here first, with the owner's review where it changes a decision.

### 13.6 Sizing (forecasts, recalculated after I1 with the measured speed)

| Part | Agent tokens | Workflow hours | Owner hours |
|---|---|---|---|
| P0 and the skeleton | 0.5–1M | 1–2 | 0.5 (P0.2, P0.4, P0.5, P0.6) |
| I1: read-only shadow | 4–6M | 8–12 | 1 (the first real snapshot, reading the first report) |
| I2: native loop | 4–6M | 8–12 | 1 (selecting and completing project-log decisions) |
| I3: execution and evidence | 3–4M | 6–9 | 1–2 (scripting the four named cases) |
| **Stage 0A** | **11.5–17M** | **23–35** | **3.5–4.5** |

### 13.7 Where the rest of the core lands

| Stage | What of the decision core it builds |
|---|---|
| 0A | this document's slice |
| 0B | the daily snapshot import and the daily usage-signal job in the supervisor; backups with a tested restore (a condition of the adoption gate) |
| 1 | tasks store `decision_ref` and the link answer (WRK-3, WRK-8); SIG uses `DecisionDirectory` and implements `EvidenceResolver`; WRK implements the probe and `GoalDirectory`; a quick log "D-0042: …" becomes a fact proposal; the `untrusted_external` sub-class (PRV-14) |
| 2 | the decision loop in the chat (DEC-5, DEC-7, DEC-9) behind approval cards; the waiting list heads the morning plan (RHY-1); the asked log |
| Adoption gate | not before 1 December 2026 (§10.10) |
| 3 | proposals from conversations behind the evaluation gate (DEC-17, OPS-13); occasions (DEC-21); silence and contradiction questions (DEC-22); the decision parts of the brief and the envelope (EXT-5) |
| 5 | meetings that prepare or review decisions, and outcomes that propose decision items first (MTG-1, MTG-2, MTG-4) |
| 6 | external decision references (DEC-23); delegated commitments by reference (CMT-5); the decision anchors in the integration contract (EXT-4) |
| 8.0 | the cloud view for cloud AI clients, read-only first (MCP-5) |
| Later | the decisions view (DEC-8); calibration research after the forecast pilot's report (DEC-10) |

---

## 14. Open choices

### 14.1 Answered by the owner on 18 October 2026

| Question | Answer | Entry |
|---|---|---|
| Does a revision keep the number with a new sealed edition, or become a new decision? | The same number and a new sealed edition; the basis is sealed by a hash at activation; a revision needs a reason (a new fact, a change of mind, the correction of a mistake); a genuinely different decision gets a new number and supersedes the old one | D-043 |
| How are decisions, forks and commitments numbered? | v1 numbers kept in four digits; new decisions from `D-1001`; `Q` for forks; `F` for commitments, new ones from `F-10001`; numbers permanent | D-045 |
| Is the decision link at entry mandatory? | No: offered (up to three likely decisions) and counted in four buckets; "no decision" is a valid answer; a commitment may exist without a decision | D-048 |
| How does reading the shadow interact with the forecast pilot? | The pilot's change journal records the start of the v2 shadow; the owner reads the shadow daily; every intervention is recorded and taken into account in the pilot's analysis | D-039 |

### 14.2 Still proposed and waiting for the owner

The build proceeds on the stated default until the owner answers. A different answer changes only the
named parts.

| # | Choice | Default the build uses | What a different answer changes |
|---|---|---|---|
| 1 | The health order: the owner's flag → a known violation → an overdue review → insufficient data → watch (including overdue checks and a stale "holding") → on track → awaiting checks, with the unverifiable share always the first line (D-044) | as §4.7 | `health()`, the named vectors, the shadow rules SR-1 to SR-10 |
| 2 | Does the adoption gate require the stage-2 chat loop, or may decisions move to v2 with a pull-only loop (the CLI, MCP and the morning pull)? (D-039) | require the chat loop; a pull-only adoption only by a recorded owner decision | the order of stage 2 against the adoption date; condition 5 of §10.10 |
| 3 | Where adopted decisions live: restored onto the production host once it has passed its gate, which retires its staging instance and runs production with decisions only (DEP-23, DEP-27) | as §10.10; if stage 2 and the 30 gate days are not done by 1 December 2026, adoption waits | an interim production host, recorded by the owner |
| 4 | The 14 clean shadow runs and the 7-day freshness of the case results (D-039) | as §10.10 | the gate's conditions 2 and 3 |
| 5 | The cases in their scripted form at the 0A exit, the chat form of the context-change case at stage 2, and readings entered by the owner (§12.2) | as §12.2 | the 0A and stage-2 exit criteria |

### 14.3 Decided by default, not asked (each reversible, each proposed in its D-entry)

- the project's public log as the first native dataset, with selected entries only (D-046);
- the `validation` role on the owner's machine, `dev` accepting only synthetic snapshots and `validation`
  only real ones (D-046);
- kinds instead of parallel hypothesis and event entities (D-047);
- probabilities optional, owner-only and never filled by a model;
- depth computed with an owner override, and always `full` for imports;
- advisee mirrors kept, with the `goal_changed` question asking about them once their engagement's goal
  ends;
- the `dec_` and `cmt_` MCP namespaces and the server name `coflow-v2`;
- one unit of work per snapshot import, chunked only above a bound;
- the widths of `Q` (4) and `F` (5), the scoped codes and the alias forms (D-045).

---

## Appendix A. Enumerations in one place

| Enumeration | Values |
|---|---|
| Decision `status` | draft, active, closed, cancelled, superseded, withdrawn |
| Decision `kind` | choice, test, pursue, attendance; advisee and forecast_container (mirrors only) |
| `decider` / `decider_basis` | self, joint, other (mirrors of advisee or forecast_container only) / stated, mapped, assumed |
| `depth` / `depth_basis` / `reversibility` | light, full / computed, owner, import / cheap, costly, irreversible, unknown |
| Manual flag | ZOMBIE, OFF_TRACK |
| Origin kind | owner_note, cli, bot, meeting, session, chat, agent_session, occasion, app, proposal, fork, import, not_recorded |
| Edition reason | activation, revise, correction, completion, import, source_changed |
| Check state (stored) | HOLDING, DRIFTING, VIOLATED, UNVERIFIABLE, UNKNOWN |
| Computed assumption state | NOT_YET_DUE, UNCHECKED |
| Check kind | assessment, postponement |
| Next-check rule | explicit, frequency, ad_hoc_clear, kept, dropped, none, postpone, import |
| Data source kind | manual, internal_query, external_system, none |
| Check frequency | weekly (+7), monthly (+30), quarterly (+90), ad_hoc (clears) |
| Check cost | minutes, hours, day_plus, unknown |
| Comparator | `>=`, `<=`, `>`, `<`, `=`, `!=`, `between` (inclusive) |
| Due source | explicit, by_date, text, review |
| Reading proposal / no-proposal reason / source kind | HOLDING, DRIFTING, VIOLATED / text_threshold, before_judge_from, unit_mismatch, no_value / owner_statement, internal_query, app, document, import |
| Event-time precision / basis | instant, day, month, unknown / live, stated, source_time, conversation_date, record_date, import, unknown |
| Fact phase / kind / reported by | ground, monitoring / observation, action, statement, context_change, outcome_report, external_decision / owner, counterpart, app, agent, import |
| Claimed outcome (outcome reports) | success, failure, mixed, done, not_done |
| Evidence kind | segment, message, session, document, owner_statement, agent_session, app_envelope, foreign, none |
| Fact bearing | bears_on, supports, contradicts |
| Ground axis | VIOLATED, INSUFFICIENT, DRIFTING, HOLDING, AWAITING, NOT_MONITORED, NO_ASSUMPTIONS |
| Timeliness axis | REVIEW_OVERDUE, NO_REVIEW_DATE, CHECK_OVERDUE, NO_DATA_SINCE, DUE_TODAY, ON_SCHEDULE |
| Composite health | DRAFT, ZOMBIE, OFF_TRACK, REVIEW_REQUIRED, STALE, INSUFFICIENT_DATA, WATCH, ON_TRACK, AWAITING_CHECKS, CLOSED (+ outcome badge), CANCELLED, SUPERSEDED, WITHDRAWN |
| Waiting reasons | violated (critical flag), review_overdue, review_today, goal_changed, check_due, incomplete, fork_due, proposal_waiting; reserved: expectation_missed, contradiction |
| Review actions / revise basis | keep, adjust, revise, close, cancel, supersede / trigger_fact, change_of_mind, correction |
| Review triggers | scheduled, violated_assumption, outside_fact, non_occurrence, goal_change, fork, owner_initiative, import |
| Outcome kind / basis / resolved by | success, failure, mixed, unknown / resolved, reported, not_confirmed / owner, import |
| Same again | yes, no, unsure |
| Stake type / period / direction | money, hours, attention / once, week, month, quarter, year / cost, income, at_risk |
| Fork status | open, decided, dissolved, delegated, withdrawn |
| Option origin / recorded before the choice | owner, agent, import, app / yes, no, unknown |
| Proposal type / status | decision_new, fact (later: check, review, learning, link) / proposed, approved, rejected, withdrawn, expired |
| Link roles (DEC) | follows, supersedes, depends_on, part_of, contradicts, tests, serves, about, informed_by, foreign_attachment; later cites, about_external |
| Link target kind / resolution | decision, learning, goal, direction, person, company, foreign_task, foreign_goal, foreign_topic, foreign_session / resolved, foreign, pending, dangling |
| Link answer (spokes) / no-decision reason | linked, explicit_none, unanswered, not_offered / routine, personal, admin, not_yet_decided, other |
| Commitment status / due basis / done basis / origin | open, suggested_done, done, dropped, unclear, withdrawn / stated, inferred, none / stated, live, unknown / cli, mcp, bot, meeting_outcome, app, import |
| Publishability | private, publishable_abstracted, public |
| Instance roles | production, staging, validation, dev, drill |
| Transaction channel | cli, mcp, bot, app, import, system |
| Mirror scope | full, basis_only |
| Integrity result | ok, ok_with_erasures, changed, drift, completion_pending |
| Import mode / run status / report status | shadow, final, dry_run (writes no run row) / applied, noop, partial, refused, failed / pending, written, blocked |
| Mirror source kind | decision, assumption, fact, review, link, version, check_version, check_snapshot |
| Imported goal status (lower-case) | not ended: candidate, active; ended: paused, achieved, abandoned, dropped, superseded, closed |
| Shadow aspect / classification | health, waiting_membership, waiting_reasons, due, order, count, basis_drift / same, expected (SR-n), unexpected, finding |
| Burned reason / alias kind | rollback, undo, deleted_in_source, numbering_gap / legacy, rename, merge, foreign |
| Version cause | command, review, check, import, undo, adoption |

## Appendix B. Predecessor defects this specification does not repeat

Generic findings from a private study of v1 (aggregates only):

| # | v1 defect | Fixed by |
|---|---|---|
| 1 | Bot-approved writes were labelled as MCP writes | the transaction log stamped by STO; `channel`, `owner_channel` and `approval_ref` per unit of work |
| 2 | An ad hoc assumption answered "holds" by a button got a default step instead of falling back | one `next_check_after` for every channel, and button values from it |
| 3 | A repeated check with the same state left no history; "last checked" was overwritten | the append-only check log, one row per check |
| 4 | Health ignored non-critical assumptions while the waiting list included them; "no data" masked an overdue review | one pool rule; a non-critical violation is a WATCH reason and also waits; STALE before INSUFFICIENT_DATA |
| 5 | "Not yet due" was a stored default, so decisions sat in WATCH for ever | NOT_YET_DUE and UNCHECKED computed; the AWAITING_CHECKS label |
| 6 | Keep, adjust and revise accepted no next review date over MCP | required in every channel |
| 7 | A fact could name another decision's assumption over MCP | refused in every channel; facts may bear on several assumptions of the same decision |
| 8 | Assumption codes were "count + 1" and could collide after a delete | per-parent counters that only increase; fixed-width scoped codes |
| 9 | Review dates had no time; several reviews on one day were ordered by insertion | event time with precision, plus knowledge time |
| 10 | Decision numbers were autoincrement ids; deleted ones left no trace | the IDS tap; foreign and burned numbers; tombstones |
| 11 | UTC and local times were mixed | UTC storage; the owner's zone for dates and "today" |
| 12 | MCP could not postpone a check or edit options and people | `dec_postpone_check`, `dec_add_option`, `dec_link`, `dec_set_flag` |
| 13 | Thresholds were free text only, so no reading could be compared | comparator, decimal value, unit, by-date and judge-from, with text as a fallback; readings that propose |
| 14 | An UNVERIFIABLE assumption could never become checkable | `supersede_assumption` with a source; the predecessor keeps its checks |
| 15 | Goal status never reached decisions (half of the goal links pointed to ended goals while the decisions stayed active) | `goal_changed`, asked once until a review answers it |
| 16 | The first review question carried no context and could not be answered | the rule-built question context (DEC-20) |
