# CoFlow 2.0 — Requirements

Version 0.5 · 5 October 2026 · **status: draft for owner review**

Changes since 0.4, from what the private v1 showed on 5 October (a meeting whose outcome lost every
agreement, and conference links that were never created): the owner picks the model tier per function
group with the monthly cost of each tier in front of them (OPS-11, D-033); no silent truncation
of a model answer (OPS-12); private evaluation sets from the owner's own recordings (OPS-13); quotes
extracted where the segments are visible (MTG-12); honest outcome messages (MTG-13); context assembled
by rules (MTG-14); a record mode and an owner-facing analysis mode (MTG-15); online meetings that carry
their conference link (MTG-16); import of an external transcript with speaker labels (SIG-16); effective
option values on approval cards (BOT-8); time to outcome measured (NFR-12). From the same day's bot
session: behaviour written down as scenario files with tests (BOT-9), one question at a time (BOT-10),
a capability gap turned into a scenario change approved in the chat (LRN-7, D-034 proposed), a meeting
that creates the people it needs on one card (MTG-17), and honest provider errors (OPS-14).

Changes since 0.3: self-hosted deployment on a separate production machine with CI/CD and Docker
(§5.21, [DEPLOYMENT.md](DEPLOYMENT.md)); the journal under the owner's control (P-2, PRV-9); money for a
tax resident with several books through country packs (§5.16); a Centre and goals module (§5.17);
alignment, relationship and conductivity analysis moved to research (§5.19–5.20); a modular architecture
with per-module acceptance (P-14, [ARCHITECTURE.md](ARCHITECTURE.md), [MODULES.md](MODULES.md)).

**How to read decisions in this document:** a requirement that implements a decision marked
"proposed" in [DECISIONS.md](DECISIONS.md) (for example pull-based releases, D-021; instance roles,
D-022; books, taxpayers and country packs, D-027) is itself a proposal until the owner confirms
that decision.

Sources: an inventory of the private v1 (code v3.87.3, ~47k lines, 96 MCP tools, ~60 tables), its usage
data for the last 30 days (aggregates only), its specifications and external audits, research on
deployment, Spanish tax rules and goal-setting methods, and the owner's decisions of 4 October 2026 (see
[DECISIONS.md](DECISIONS.md)). Personal data of the owner and of third parties is deliberately absent from
this document.

Priorities used below:

- **R1** — first public release (roadmap stages 0–5).
- **R2** — after the first release (stages 6–8).
- **Plugin** — optional module, off by default, may ship in any release.
- **Later** — recorded direction, not planned yet; includes the research modules (D-029). Inclusion here
  is not an owner decision unless a D-entry says so.

---

## 1. Product thesis

CoFlow is a **personal decision system**: a self-hosted assistant that turns the signals of one person's
working life into decisions, commitments, actions, outcomes and learning — and keeps the chain between
them traceable.

```
Signal → Decision → Commitment → Action → Outcome → Learning
```

| Link | What CoFlow does |
|---|---|
| Signal | Collects conversations (recordings, chats, mail), calendar and notes; resolves who said what |
| Decision | Keeps decision records with grounds, alternatives and assumptions to monitor |
| Commitment | Keeps who owes what to whom by when, with the quote it came from |
| Action | Plans the day, prepares meetings, proposes concrete next steps; executes external actions only after approval |
| Outcome | Records what happened: meeting outcomes, closed commitments, decision results, money in and out |
| Learning | Helps the owner form and version their own centre and goals, computes progress and drift against them, runs weekly to yearly reviews, and remembers the owner's corrections. Deeper analysis (alignment, relationships, change over time) is research built on the same data |

The value is not the code — code becomes a commodity. The value is the evidence the system accumulates:
real decision cases, their grounds, commitments and outcomes.

## 2. Who it is for

**Owner persona (R1):** an independent professional — founder, consultant, freelancer — who runs many
conversations, commitments and decisions in parallel, works in more than one language, and is comfortable
creating API keys and an OAuth client by following documentation and either running Docker Compose on a
Linux host reached over SSH or installing natively for development. The owner may run more than one money
contour (household, own practice, a company) that must never mix, and is tax resident in one country;
country-specific tax rules come from a country pack, with Spain as the reference pack.

**Not for (now):** teams and shared workspaces, companies as users, non-technical consumers, mobile-only
users.

**Release ladder:**

1. The author's private v1 (exists).
2. **R1** — a technical user installs CoFlow with Docker Compose on a Linux host (the reference production
   install; the same image runs on a rented server) or natively for development, connects their own
   accounts, and the author's identity appears nowhere. The author's own production runs this way,
   delivered by CI/CD.
3. **R2** — a `doctor`-guided installer, a hardened recipe for an external server, moving an instance
   between hosts.
4. Later — a prebuilt image for a home mini-PC.

## 3. Evidence from v1 (last 30 days, aggregates)

| Capability | Use | Evidence |
|---|---|---|
| Telegram bot: questions, answers, approval cards | daily | 138 incoming messages on 13 of 13 days; 64 approved actions on 10 days |
| MCP from AI clients | weekly, in bursts | 1,464 calls on 12 days, 69 of 96 tools; top: task status, person search, task create/update, memory search |
| Recorder pipeline (local transcription, summaries) | daily, automatic | 38 new recordings on 8 days; an archive of 359 old recordings processed |
| Telegram collector (read-only) | daily, automatic | new messages on 14 of 14 days |
| Calendar copy, free slots, meetings | daily / weekly | 16 meetings created, 12 held, 13 linked to a recording |
| Decision records | weekly | 17 decisions, 102 facts and assumptions |
| Tasks and goals | daily | 235 tasks created, 476 status changes |
| Private journal through the bot | weekly | entries on 9 days |
| Activity tracking (Windows) | daily | spans on 9 of 9 days since launch |
| Web UI (20 Streamlit pages) | almost never | ≈ 1 hour in 30 days outside the recorder status page; 6 pages never opened in 90 days |
| Background suggestion queues | almost never reviewed | recording links: 10 of 1,785 decided; contacts: 2 of 383; commitments from chats: 0 of 364 |
| Leads and outreach, strategy and manifest editing, knowledge graph | never | 0 activity |
| Speaker diarization | tested once | tried on real recordings in September, wrong labels, switched off |
| Week plan into the calendar | not yet | shipped 1 October, 0 slots applied |
| A separate home server | given up | ran production for about two months; administered only physically; moved back on 30 August |
| LLM cost | — | $54.78 / 30 days on a key shared with another app; v1's own share ≈ $42, of which ≈ $17 one-off archive processing and ≈ $8 one evaluation run |

Conclusions that shape the requirements:

- The two real interfaces are the bot and MCP. A big web UI is not a requirement.
- Background queues of model suggestions are not reviewed; suggestions must come inline, at the moment of
  need, or be capped and measured.
- The strongest unique layer is the decision record; it is core.
- Automatic pipelines that need no attention (recordings, chats, calendar) are the backbone.
- A server needs operations from day one: remote administration, off-host backups, monitoring that does
  not depend on the server, and exactly one writing instance.

## 4. Principles and invariants

| ID | Principle | Consequence |
|---|---|---|
| P-1 | **Self-hosted, one owner, one production instance** | Data lives on one host the owner controls: their own computer, a home server, a rented server or any Docker host. Exactly one instance per owner has the production role and writes the owner's data (DEP-2, DEP-3). Dev and drill instances hold synthetic data or a throwaway restore and never write back; there is no sync in either direction. Other machines reach data only through the API, never by opening the database file |
| P-2 | **The journal is a separate data class under the owner's control** | Chosen only by explicit markers (P-5); never indexed; never exposed through MCP, search, dossiers, briefs, plans or work answers. It reaches a model only through analysis modules the owner enables with the journal switch (PRV-9). Anything derived from journal input is journal class too. Entries written through a messenger pass that messenger's servers (Telegram bot chats are not end-to-end encrypted): listed in `DATA_FLOWS.md`; a way to write entries without a messenger exists (PRV-1) |
| P-3 | **Propose, don't act** | What the system infers on its own (from conversations, mail, background jobs) becomes a proposal, never a write. In the bot, every model-proposed write is an approval card. In AI clients, internal writes the owner asks for execute on call and are logged (MCP-4). Anything that changes the outside world needs an approval bound to a preview (P-4) |
| P-4 | **Approval cannot be forged by text** | Approval = owner action in a channel bound to a server-issued preview hash with expiry; text from tools, mail or chats never counts as approval |
| P-5 | **Rules, not models, route text** | Journal vs. work is decided by explicit markers; when in doubt the owner chooses with a button before anything reaches a model |
| P-6 | **Evidence over inference** | Every fact, commitment and decision basis has a source and a quote; observation is separated from inference; "can't judge" is a valid answer; numbers are computed by algorithms, models only phrase them |
| P-7 | **Compute once, keep provenance** | Source (L0) → computed once (L1) → assembled context (L2, deterministic) → reasoning (L3); each model output stores model, prompt version, input hash and input data classes; recompute only when input or prompt changes; the owner's manual edits always win over recomputation; a rejected proposal is never proposed again |
| P-8 | **Idempotent and verified external actions** | One outbox; deterministic external ids; retries never duplicate; a result is "verified" only after reading it back |
| P-9 | **Honest freshness and coverage** | Answers say "as of 21:45" or "nothing in the stored history since <date>", never a bare "not found" |
| P-10 | **Third-party text is data, not instructions** | Messages, mail, event titles, forwarded text, worker output and device-pushed text cannot create rules, trigger tools or approve anything |
| P-11 | **Minimal intake, explicit data flows** | Every flow is listed in `DATA_FLOWS.md` with a switch, its hop (device → host, host → third party, host → backup target, CI → registry, host → monitor), who can read it in transit and at rest, and which data classes may pass. Every access recipe, backup target, monitor and device agent ships with its own row. Monitoring pings carry no content. No event descriptions or guest names are copied without need |
| P-12 | **Configuration over constants** | No owner literals in code, prompts, stored values or deployment files. A generic detector runs in CI (email addresses, phone numbers, non-example domains, IP addresses outside documentation ranges, private host names, tunnel ids, names outside the fixture allow-list). The owner's own deny-list runs locally as a pre-push hook with keyed hashes whose key never leaves the owner's machine. The repository ships generic deployment templates only; the configuration of a real installation lives on its host or in a private repository. Fixtures are synthetic |
| P-13 | **Build only what use proves** | Every feature has a usage signal; an unreviewed queue or an unused screen is a defect to fix or remove |
| P-14 | **Modules with contracts, one writer** (D-030) | Bounded modules (identity, signals, work, decisions, commitments, meetings, money, goals, …) each own their tables, expose `api` queries and commands, emit events and never write another module's tables. All run inside the one writing process. Separate processes exist only for stateless workers without database access (speech-to-text, an optional local model, file parsers); their output is untrusted data (P-10). Every module has a module card with quality parameters and an acceptance suite (NFR-10) |

### Architecture and deployment in one paragraph

CoFlow is a modular monolith (D-030; [ARCHITECTURE.md](ARCHITECTURE.md), cards in
[MODULES.md](MODULES.md)):
the organisation of microservices — bounded modules, contracts, events, per-module quality gates — without
their deployment, because one SQLite writer and one numbering tap cannot be split across services. In
production it runs as one Docker Compose stack on a separate always-on Linux machine: a `core` container
that is the only writer and a stateless `stt` worker. Releases are built, signed and published by CI on
GitHub; the host pulls and verifies them itself, and the owner approves each production deploy
([DEPLOYMENT.md](DEPLOYMENT.md)). Development happens natively on the owner's computer with fakes and
synthetic data.

## 5. Functional requirements

### 5.1 Owner profile and configuration (CFG)

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| CFG-1 | One owner profile is the single answer to "who is the owner": name and aliases, languages, contacts, time zone, currency, booking hours, ritual times (morning, evening, weekly review), tax residence and regime (enabling a country pack) | R1 | No owner literal in code, prompts or stored values; the literal gate test passes |
| CFG-2 | Prompts and bot texts are templates filled from the profile and the locale | R1 | Changing the profile changes every prompt; no rebuild |
| CFG-3 | Locales: English and Russian in R1; journal markers, date parsing and bot texts per locale | R1 | The same scenario passes in both locales |
| CFG-4 | Personal content (centre documents, brand, templates) lives in the owner's data root, never in the repository; a clean install starts with empty templates of the centre document types and a configurable list of life domains. One data root has fixed subfolders (`db/`, `inbox/`, `media/`, `work/`, `models/`, `backups/`, `logs/`); stored paths are relative; secrets live elsewhere (PRV-4); in a container the data root is a volume and the image holds nothing stateful | R1 | A fresh install contains no personal content; deleting and recreating the containers loses nothing; moving the data root needs no path rewrite in the database |
| CFG-5 | Directions with special roles (e.g. "outside directions", "ideas inbox") are configured by role, not by number | R1 | — |

### 5.2 Identity and registry (IDN)

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| IDN-1 | One numbering tap: every public id (person, company, …) is issued atomically from one sequence table in the production instance; ids are permanent, never reused, may be burned | R1 | 1,000 concurrent issues: no gaps reused, no duplicates |
| IDN-2 | One registry of id prefixes without collisions (person, company, direction, goal, task, decision, meeting, session) | R1 | Documented registry; tests reject unknown prefixes |
| IDN-3 | `resolve_or_create_person`: match by strong keys (email, phone, messenger id, profile URL), then exact name, then alias; ambiguity returns candidates and creates nothing; a found person only gets empty fields filled | R1 | No silent duplicates; namesakes go to review |
| IDN-4 | Background pipelines never create people; explicit owner or agent requests may create with `needs_review` | R1 | A pipeline run on unknown senders creates 0 people |
| IDN-5 | Merge duplicates keeping aliases and history; undo a wrong merge | R2 | Merge and undo restore the original state |
| IDN-6 | A content-hash identity for files: the same recording imported twice is one source | R1 | — |
| IDN-7 | A machine-readable label in external artifacts (event titles, folder names) links them back to records; the label beats a model guess | R1 | An event titled with a label links to its meeting without a model |
| IDN-8 | **A lookup never writes, and a name is not a key:** the resolve path has a read-only form used before any approval - it creates nothing and fills nothing in on a person it found. A match on name or alias alone is a candidate, never a hit: the card asks "is this them?" and the "no" branch asks for a distinguishing name. Every person on an approval card is resolved again immediately before the write, after the people that same approval created, so a person added between the card and the approval is used instead of duplicated | R1 | A lookup leaves every table byte-identical (test over the registry suite); a name-only match never writes a contact key; creating the same person twice from one card is impossible |

### 5.3 People (PPL)

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| PPL-1 | A person profile: wants, fears, constraints, figures, open questions — each a temporal fact with source, quote and date; contradictions are shown, not resolved silently | R1 | Every fact links to its source |
| PPL-2 | A person dossier (L2): a deterministic text within a size budget for prompts and briefs; never includes the journal | R1 | Same input → same dossier |
| PPL-3 | Contacts found in conversations are proposed, not written; accepted only by the owner; the owner's own contacts are never proposed for others; a rejected value is never proposed again | R1 | — |
| PPL-4 | Companies: name, aliases, public id, people | R1 | Same strong-key and no-silent-duplicate rules as people (IDN-3) |
| PPL-5 | Birthdays: reminders to the owner N days before and on the day; unknown year and 29 February handled; no duplicates; no automatic greetings | R2 | — |
| PPL-6 | Third-party rights: export everything about a person; forget a person across tables with a deletion log. Records the owner keeps under a legal retention duty, with the retention date computed by the country pack (invoices, tax documents), are hidden from search, dossiers and briefs and deleted when their retention date passes | R2 | After "forget", search returns nothing about the person; retained tax records stay only in the archive and the advisor export |
| PPL-7 | Client view: a company's goals across directions, money by currency | R2 | — |

### 5.4 Signals: conversations and sources (SIG)

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| SIG-1 | A conversation (session) is the unit of signal: participants, time, channel, source, summary; a session is not a meeting. A chat becomes sessions split at a silence gap (default 6 h); summaries are computed once after silence (chats 6 h, mail 12 h); a long summary is never replaced by a shorter one | R1 | Re-running the summary job changes nothing when the input did not change |
| SIG-2 | **Recorder pipeline:** audio reaches a watched inbox folder on the host through an encrypted folder sync from the owner's devices, or through the bot for short voice notes; from stage 6 also through the upload API (DEP-16). A file registers only after complete arrival (temporary name + rename, or a stable-size check), within ≤ 2 min → local transcription → summary and suggested name → searchable. Adjacent parts of one recording (device splits) form one session; fresh files go before archive; archive runs in a night window | R1 | A fresh file is searchable without human action; a half-copied file is not registered; an interrupted sync registers the file exactly once after it completes |
| SIG-3 | Pipeline resilience: transient vs. final errors; retries 15 min → 1 h → night, up to 4; chunking long audio at silences; retry one recording; visible "why it waits". Transcription runs in a separate worker with its own memory and CPU limits read from the container's limits; an out-of-memory kill of the worker is a transient error and never stops the bot or the scheduler; background work yields to interactive work. Work files are deleted when a job completes and are never backed up | R1 | A simulated out-of-memory recovers without a human; a killed worker recovers while the bot keeps answering |
| SIG-4 | Recorder profile: file-name pattern, device time zone, clock drift, source device, transport; a label in a file name gives an exact link; recordings keep the device's time zone, never the server's | R1 | The same file on a host in UTC and on one in the profile zone gets the same absolute start time |
| SIG-5 | **Connector contract:** a source adapter produces normalized inbox JSON (format version, account, external refs, participants with external ids, messages, media, raw meta). Pull with a cursor on the host; from stage 6 also push from device agents through the ingestion API (DEP-16) with an idempotency key. Adapters never create people; schema drift is a visible error | R1 | Two adapters (Telegram export, recorder) use the contract; the same input twice imports once |
| SIG-6 | Telegram Desktop export (JSON) import, placed in the inbox or pushed from the desktop | R1 | A chat export appears exactly once as sessions with resolved participants |
| SIG-7 | **Telegram user-session collector:** read-only, only marked chats, explicit warning about account access and Telegram's terms (including first logins from a server address). The session is created on the host that uses it, stored encrypted in the secrets store, excluded from backups and never copied between instances; only the production role runs it | Plugin | Cannot send (test); off by default; `doctor` reports a session found on two instances |
| SIG-8 | Voice notes and video notes from collected chats transcribed locally into the message text | Plugin | — |
| SIG-9 | Google Calendar copy, read-only: window −14…+60 days, every 15 min; no descriptions and no guest names, and no conference link except the join link of an event linked to a CoFlow meeting, which is stored on the meeting (MTG-16); mass-disappearance guard; `synced_at` and `stale` in every answer. Access: a separate token per purpose (read, write), minimal scopes, re-login never starts by itself; `coflow login google` works on a headless host (consent URL plus a loopback port forwarded over SSH); tokens are per environment | R1 | A test fails on any forbidden scope; a headless login completes in the install drill |
| SIG-10 | Gmail read: threads where the owner wrote or the counterpart is in the registry; newsletters and promos dropped; quotes stripped; no attachments; never sends | Plugin | Forbidden scopes fail a test |
| SIG-11 | Archive processing is budgeted: cost estimated on a sample before a bulk run | R1 | — |
| SIG-12 | "Who said what" inside a recording (diarization) — only after a measured pass on real recordings; anonymous speakers named by the owner; **no voice prints** | Later | — |
| SIG-13 | Google Meet recordings and transcripts as a source | Later | — |
| SIG-14 | **Transcript segments:** transcripts are stored as segments with offsets and absolute time (recording start + offset, corrected by the recorder profile's time zone and clock drift, originals kept); quotes, facts and commitments point to a segment | R1 | Every quote resolves to a segment and a playable offset |
| SIG-15 | **Quick log and notes:** the owner logs a call, a meeting or a note in one sentence (bot or MCP); it becomes a session or a note with resolved participants and a link to work, without a model call for the record itself | R1 | A one-line log creates exactly one session and no new person without approval |
| SIG-16 | **External transcript import:** the owner may attach a transcript produced elsewhere to a recording; when it carries speaker labels it is preferred for attribution over the local transcription, both are kept, and the flow is listed in `DATA_FLOWS.md` as the owner's own choice (PRV-2). Segments, offsets and quotes follow SIG-14 | R1 | An imported labelled transcript yields segments with speakers and keeps the local one; every quote resolves to a segment |

### 5.5 Decisions (DEC)

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| DEC-1 | Decision record: statement, context, alternatives, stake (including money), expected outcome, confidence, owner/executor/about-whom | R1 | — |
| DEC-2 | Facts split into grounds and monitoring; assumptions with metric, threshold, source and check frequency | R1 | — |
| DEC-3 | Health is computed from assumption states, not set by hand (except explicit "zombie"/"off track"); closing requires an outcome; cancel and supersede are explicit | R1 | — |
| DEC-4 | A decision is created from a meeting outcome or by the owner; decisions of teams and clients live outside CoFlow | R1 | — |
| DEC-5 | Morning surfacing: decisions that need the owner today, with the reason | R2 | — |

### 5.6 Commitments (CMT)

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| CMT-1 | A commitment is a record: who → to whom, what, due date, status, link to goal/decision, source quote; closing keeps history | R1 | A reminder read is not "done"; closing needs a reason |
| CMT-2 | Commitments are proposed from meeting outcomes and conversations **inline** (in the bot or the outcome card), capped (default: 5 per proposal type per day); the decision rate is measured per proposal type; a type whose decision rate over its last 30 proposals falls below 20% switches itself off and says so (defaults are configurable) | R1 | The decision rate per proposal type is available through an MCP read tool and, from stage 4, on the status page |
| CMT-3 | "Send material" as the first carried-through commitment: draft message, located material, reminder on the due date; "sent" by the owner's confirmation or a found outgoing message; no auto-send | R2 | — |
| CMT-4 | Errands with state (new / in progress / waiting for me / waiting for them / done / failed / cancelled) that survive restarts; escalation after silence; at most two reminders. "Waiting for me / for them" is the ball holder of the underlying task (WRK-2) — one source of truth | Later | — |

### 5.7 Meetings and calendar (MTG)

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| MTG-1 | A meeting is an intent: plan, participants 1..n, link to work (direction/goal/task required unless the owner says "no link"), calendar event | R1 | A meeting without a link to work is refused unless the owner says "no link" |
| MTG-2 | Brief before the meeting at a configured time: per participant profile, last conversation, open commitments, decisions — with sources; missing history is named as a gap | R1 | Every fact in a brief links to its source |
| MTG-3 | A recording finds its meeting by time overlap (≥ 50% → link; otherwise an inline proposal); a label in the file name gives an exact link; the recording inherits participants and links | R1 | On 30 consecutive meetings with a recording, ≥ 90% link without manual work; reprocessing creates no duplicates |
| MTG-4 | Outcome: what each side said; agreements (who/what/to whom/when/quote) become commitment and task proposals; nothing is created without approval | R1 | Every quote is an exact substring of a transcript segment (SIG-14) |
| MTG-5 | **Reliable calendar writes:** create/move/cancel through the outbox, executed only by the production instance; states proposed → approved → executing → applied → verified (+ partial, unknown, failed, needs_refresh); deterministic event id from the operation key; on timeout/409 read back before retrying; read-back verification; one path for bot and MCP | R1 | Lost response, double approval and a crash between steps leave exactly one meeting and one event; a non-production instance executes nothing |
| MTG-6 | Fresh preflight before a write: calendar copy ≤ 60 s old, busy time exactly as the provider reports, booking hours, frame days, buffer between meetings with people (both busy and free meetings; template windows are not meetings); a new buffer never moves existing meetings | R1 | — |
| MTG-7 | Time model: UTC in logs and storage, IANA zone from the profile, half-open intervals; DST gaps and overlaps are refused or asked; no code path uses the host's or container's local zone; the host clock is NTP-synced and `doctor` reports skew | R1 | The suite passes with the machine zone set to UTC and to a zone different from the profile |
| MTG-8 | Negotiation with the counterpart through the owner's messenger account (e.g. Telegram Business): only on the owner's explicit instruction for that contact; every message goes through the outbox; proposes 2–3 slots, never reveals busy-event titles, counterpart text is untrusted, final card to the owner, then MTG-5 | Plugin | — |
| MTG-9 | Reschedule and cancel policy for created meetings | Later | — |
| MTG-10 | Week plan as calendar windows and slots, approved with one card | Plugin | Shipped in v1 but unused; ships only after use is proven |
| MTG-11 | **Calendar write safety:** CoFlow moves or cancels only its own events (label, organizer, not recurring, id equal to the computed one); on other people's events it can only answer an invitation; an event the owner moved by hand is never moved back; invitation emails are sent only when the card says so (default: none); writes use their own token with minimal scopes | R1 | A foreign or recurring event is never changed (test with a recording fake calendar) |
| MTG-12 | **Quotes come from the stage that sees the source:** agreements and commitments are extracted per transcript chunk with verbatim quotes from segments (SIG-14); a merge stage only de-duplicates and ranks and never writes a new quote; the quote check runs against segments, and a quote that fails it is reported as dropped (OPS-12), not silently removed | R1 | On a fixture with planted agreements in every chunk, including the last, each one reaches the outcome card with its quote |
| MTG-13 | **Honest outcome messages** (P-9): "nothing found" appears only when the pipeline ran whole and found nothing; otherwise the message says how many items were dropped and why, or that the analysis was truncated or failed, and offers a retry. The owner receives the decisions and commitments themselves, not only a context line, and a long outcome is delivered in full | R1 | A truncated or filtered run never produces a "nothing found" message (a fixture for each case) |
| MTG-14 | **Outcome analysis gets context:** a deterministic context within a budget - the meeting plan and agenda, the linked goal with its numbers, earlier meetings in the chain, open commitments with these people, the owner's profile - assembled by rules, not by a model (SRC-1) | R1 | The same meeting and history produce the same context; the context is in the trace (OPS-10) |
| MTG-15 | **Two outcome modes:** a record mode (neutral - what each side said, agreements, next steps) and an owner-facing analysis mode (risks with numbers against the owner's own plan, each side's position, options and what to change), the second on the tier the owner chose for it (OPS-11). Every claim cites its segment, and "can't judge" is a valid answer | R1 | Analysis-mode claims without a segment reference: 0; the mode used is recorded on the outcome |
| MTG-16 | **Online meetings carry their link:** a meeting with other people is online unless the owner says in person or gives an address; the calendar write then asks for a conference with a request id derived from the operation key (MTG-5), the approval card always states "with video link" or "in person", and the join link is stored on the meeting and shown in the confirmation, the brief and the meetings view. When the provider created no conference, the result says so; adding a link to an existing event is a separate approved action. The join link is read from the linked event on every calendar sync, whichever path created that event, so a meeting booked through MCP or by the owner in the calendar carries its link too | R1 | A repeated write leaves one event with one conference; no card omits the online-or-in-person line (test over the card catalogue) |
| MTG-17 | **A meeting creates the people it needs:** "create a meeting" resolves every person named in the message through `resolve_or_create_person` (IDN-3) - strong keys first (email, messenger handle, phone), then exact name or alias; one match is used, several become candidates on the card, none becomes a new person proposed with the keys taken from the message. A single approval card creates the new people (`needs_review`, IDN-4), the meeting and the calendar event together, each person resolved once more at approval time (IDN-8). The owner is never sent to another interface to create a person | R1 | A message carrying an unknown contact with an email and a handle produces one card that creates one person and one meeting; a repeat of the same command creates no duplicates |

### 5.8 Work: directions, goals, tasks (WRK)

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| WRK-1 | Directions: long lines of work, with an optional rank and time and money envelopes. Goals: result, deadline, company, period, type, review date, a required direction link; optional reason, attainment levels −2…+2 and a money target (owned by the money module from stage 8, FIN-1). Tasks: status, ball holder, next step with date, comments, folder | R1 | A goal without a direction is refused unless the "outside directions" role is used (CFG-5) |
| WRK-2 | Status changes only through one operation with a status log; the ball holder is explicit ("my move" / "waiting for them") | R1 | — |
| WRK-3 | Tasks and meetings store their goal; the direction is resolved through the goal when read, so moving a goal moves everything attached to it without copies | R1 | After a goal moves, its tasks and meetings report the new direction |
| WRK-4 | Hypotheses as optional children of goals | R2 | — |
| WRK-5 | A sales pipeline as an optional template | Later | v1 lead tools had 0 use in 30 days |
| WRK-6 | Control view (the only place task-level signals are computed): overdue items, "waiting for me" and "waiting for them", items without movement for N days, goals without a next step. A goal without a next step offers two exits: a dated next step, or "take to the next deliberation slot" (GOL-10). Shown in the morning plan, the weekly review and through MCP | R1 | Same data → same list; every item says why it is there; no daily message offers to pause or drop a goal |
| WRK-8 | **Goal link at the moment of entry:** when a task, meeting, commitment, ledger entry or time span is created, the bot or MCP offers the likely goal inline (deterministic: same person, company or direction), accepted with one action; "no goal" is allowed; never a queue | R1 | The share of unlinked items per week is available through MCP; no background link queue exists |

WRK-7 is not used; the number is retired and will not be reissued.

### 5.9 Rhythm: day and week (RHY)

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| RHY-1 | Morning plan at a configured time: meetings, top items with reasons (deterministic ranking: priority, deadlines, date windows, ball, commitments, goals), fresh overdue, who waits for an answer; a model only phrases the top lines | R1 | Same data → same order |
| RHY-2 | The plan is saved as a snapshot; replies to the plan refine it | R1 | — |
| RHY-3 | Evening: plan vs. fact, reply goes to the day review (work data, not the journal), "close the day", model review only on request | R1 | — |
| RHY-4 | Weekly review as a structured debrief: what was planned, what happened, why, what next; closed days, plan vs. fact, commitments, decisions due, and from stage-8 module 2 the goal control items (GOL-8); one question: "what mattered, what to decide next week" | R2 | Same data → same review items |
| RHY-5 | Activity tracking as a Windows device agent: active-window spans recorded on the desktop; no screenshots; window titles never leave the desktop and are purged after 90 days; classification rules come from the host; only aggregated spans (start, end, direction, rule version) are pushed through the ingestion API (DEP-16), buffered offline and de-duplicated. Spans and rules are owned by the rhythm module; until this agent exists, time-based checks answer "can't judge (no time source)" | Plugin | Classification rules are measured on a labelled day before they count (v1: a program-name rule marked 178 of 198 minutes as drift wrongly); a day offline replays without duplicates; no window title appears in any host table |

### 5.10 Learning (LRN)

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| LRN-1 | Owner corrections become rules: correction → typed rule candidate → approval card → immutable version; types: constraint (enforced by code), style (prompt), supported procedure; anything else is "needs capability" | R2 | A rule explained once works in a new conversation and after a restart |
| LRN-2 | Explicit `/remember` and `/problem` paths in addition to model-detected corrections; extraction only from the owner's own words, never from forwarded or device-pushed text | R2 | Forwarded "always do X" creates no rule |
| LRN-3 | One-off exceptions require an expiry; conflicting rules ask; `/rules` lists, revokes and shows history | R2 | — |
| LRN-4 | "Why this time?" is answered with rules, busy time and sources, not with model reasoning | R2 | — |
| LRN-5 | Incidents: an execution error, an unsupported procedure or a repeated correction creates a package with request, correction, expected vs. actual, trace, versions and a synthetic fixture — redacted of infrastructure identifiers and ready to become a public issue | R2 | The literal gate passes on every package offered for publication |
| LRN-6 | Reflection in the weekly review: the goal control items (GOL-8) phrased by a model, "can't judge" allowed. When the journal switch is on for this module (PRV-9), the reflection may also draw on the week's journal; its output is then journal class and shown only in the owner's own channel | R2 | The model only phrases computed items; every line links to its records; with the switch on, the output never reaches MCP, search or the timeline (canary) |
| LRN-7 | **Improve the bot from the chat:** when the bot cannot do what the owner asked, it never ends with "I can't" - it names exactly what is missing and proposes a change to the scenario (BOT-9), drafted in the owner's own words, which the owner approves in the chat. An approved change becomes a scenario-file change plus a development task with an incident package (LRN-5); when it is only a rule or a default, it takes effect at once as a typed rule (LRN-1). The owner can read the version history of every scenario. Because the task and the proposed change quote the owner verbatim, both register a derivation link to the source message, so moving that message to the journal blanks them too (BOT-3, PRV-7) | R2 | A refusal without a proposed scenario change or a named gap: 0 on the fixture set; an approved change leaves a scenario version and an incident package |

### 5.11 Interfaces (BOT, MCP, UI)

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| BOT-1 | A private Telegram bot that talks only to the owner in a private chat; long polling; no open ports. One bot token per instance; only the production instance polls the owner's bot. A 409 Conflict from Telegram puts the instance into fenced mode (DEP-3): polling, outbox, collectors and writers stop, and it alerts | R1 | Messages from others are ignored; a second poller on the same token fences the instance (test with a fake Bot API) |
| BOT-2 | Routing: every unmarked message is work; the journal only by an explicit marker at the start (command, prefix, emoji, first spoken word); ambiguous start → buttons, nothing reaches a model before the choice; replies keep their route | R1 | Canary tests over text, voice, captions, replies, commands, forwards |
| BOT-3 | "This was journal" moves a message to the journal and blanks every record derived from it (answers, model calls, traces, plan lines); the moved entry then follows PRV-9 like any journal entry | R1 | Afterwards the canary text appears in no table, log, plan or index outside the journal, also after a restore from an earlier backup (PRV-7); the reply says that text already sent to the model provider cannot be recalled |
| BOT-4 | Answers use read tools in a compact mode with dossiers; model-proposed writes become approval cards executed once within 24 h by the owner only; cost shown under the answer | R1 | — |
| BOT-5 | Notifications (brief, recording state, evening, weekly) once each, with a daily cap and quiet hours; critical health alerts bypass quiet hours | R1 | — |
| BOT-6 | Sources under answers and a "wrong" button | R2 | — |
| BOT-7 | Voice messages to the bot are transcribed by the speech-to-text worker on the CoFlow host before routing; the journal marker may be the first spoken word; the audio is never sent to the model provider or a cloud transcription service by default; the transcript of a voice journal entry follows PRV-9 | R1 | Switch off: a voice journal entry reaches no model call; switch on: it reaches no routing or work call (canary) |
| BOT-8 | **Effective values on cards:** behaviour that changes the outside world never depends on a model setting an optional flag - defaults live in code, and every approval card shows the effective value of each option it will apply (MCP-4, P-4) | R1 | A model answer that omits every optional field still produces the documented default behaviour and the card states it (test over the card catalogue) |
| BOT-9 | **Scenarios as versioned files:** the bot's behaviour for each request type (create a meeting, move or cancel one, log a call, a new contact in a message, a recording is ready, a provider or balance error, a capability gap) is described in owner-readable scenario files - trigger, steps, branches, what is asked and when, what the approval card shows and does when it is approved, the failures the owner sees, and the tests that cover it. When a scenario and the code disagree the scenario is right, and a change goes scenario first, then code, then test, then the prompt version. Prompts and tool descriptions are generated from these files or checked against them, and each scenario carries a version the owner can read | R1 | A scenario without a covering test fails CI; a prompt or tool description that drifts from its scenario fails CI |
| BOT-10 | **One question at a time, only what is missing:** the bot asks only for what it cannot take from the message or the context, one question per turn; a direction counts as a valid link to work; a contact already resolved earlier in the same command is never asked about again. A message that is not a reply continues the thread of the last model answer within a configurable window (default 15 minutes), but only after routing has placed it in work (BOT-2), and system messages - plans, briefs, notifications - never become the root of a thread | R1 | On the fixture conversations the bot asks at most one question per turn and never repeats a resolved question (test over the scenario set) |
| MCP-1 | MCP server over the same service layer: context-oriented tools, an explicit read-only list (a new tool is "write" by default). Streamable HTTP inside the container network or on loopback; owner devices reach it through an access recipe (DEP-12) or a stdio bridge over SSH with a forced-command key (DEP-11). Per-client tokens with a scope (read or read-write) and revocation; tokens for coding-capable clients are read-only on production by default; a token on every request; Host and Origin allow-list (DNS-rebinding protection on); every call logged with its client; every response states the instance role | R1 | No token → 401; a foreign Host header is refused; a read-only token cannot call a write tool |
| MCP-2 | No journal tools; rule writes not exposed; the docs tell owners not to auto-approve write tools in their clients — CoFlow cannot enforce client settings, so external writes never rely on them (MCP-4) | R1 | — |
| MCP-3 | A tool catalogue generated from code and checked in CI | R1 | — |
| MCP-4 | **Approval model over MCP:** internal writes the owner asks for (tasks, notes, decisions, people through `resolve_or_create_person`) execute on call, are logged with the channel and can be undone through the owning module's undo handler; tools that change the outside world only return a preview with a server-issued hash, and execution needs that hash plus an approval in an owner channel (a bot card) | R1 | An external write without a valid approval reference is refused; every write tool has an undo handler or is marked not undoable (test over the catalogue) |
| MCP-5 | Internet-facing MCP for cloud AI clients and the owner's other apps, through an explicit recipe: a separate listener that exposes only the MCP and OAuth paths, TLS terminating on the owner's host by default; OAuth as the MCP specification defines it; read-only by default; a tool allow-list per client; rate limits; every call logged; never journal tools | R2 | A client without a valid token gets nothing; a read-only client cannot call a write tool; the ingestion API, journal endpoints and status page are unreachable through this listener |
| UI-1 | A status page — the only R1 web screen: health, instance role and id, version and image digest, deploy history, queues, freshness, costs, journal-switch state. Served through the same access recipe, token and host check as MCP-1; `/healthz` and `/readyz` return no data and answer only on loopback or the container network; a bot `/status` command gives the same content in short | R1 | It refuses without a token; `/healthz` is unreachable from a non-loopback address |
| UI-2 | Further screens (people, tasks, review queue) one by one, only when use is measured | Later | — |

### 5.12 Search and context (SRC)

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| SRC-1 | Full-text search over transcripts, summaries, messages, facts, decisions, tasks, meetings; prefix words; case-insensitive for non-Latin scripts; every hit links to its source; journal-class rows are never indexed | R1 | — |
| SRC-2 | Index kept by triggers with deterministic row ids (kind code × 10¹² + id); rebuild only explicit and in batches | R1 | A message update takes < 50 ms under load |
| SRC-3 | Entities extracted by rules from messages (address, map link, URL, phone, email, amount, handle) | R1 | — |
| SRC-4 | Script variants: transliteration (Latin ↔ Cyrillic) and spelling variants for search and person matching, with tables shipped in the locale pack | R1 | A name typed in one script finds the person and the messages written in the other |
| SRC-5 | Semantic search (embeddings + rank fusion) | Later | v1 never needed it |
| SRC-6 | Export of the memory as Markdown (Obsidian-compatible) | Later | — |

### 5.13 Privacy and security (PRV)

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| PRV-1 | Data classes, declared per table and per file area: journal (separate store; not indexed; not in tools, search or work answers; to a model only under PRV-9; includes formation-session transcripts and anything derived from journal input), work data with a financial sub-class (FIN-5), system data. A way to write journal entries without a messenger: `coflow journal add` on the host or over SSH with a journal-append key, reading only from stdin or an editor, never from command-line arguments | R1 | Every table and file area declares its class (test); a journal canary written from the desktop appears in no log, index, shell history or model call outside an enabled module |
| PRV-2 | `DATA_FLOWS.md`: data class × destination × purpose × retention × switch, generated from code declarations. Destinations include the model provider, MCP clients, the messenger, backup targets and monitors. Every model function declares the data classes it may receive; checks run in the model gateway, the MCP response layer and bot rendering | R1 | A test fails when a model function is not listed or receives a class it did not declare; financial and journal canaries pass over MCP responses and bot answers |
| PRV-3 | Retention: full prompts ≤ 30 days, costs kept; detailed traces ≤ 30 days; prompts carrying journal text are not retained, and their calls are logged by hash. Processes never print message or journal text to stdout or stderr: structured logs carry ids only, with rotation, and are never shipped to a third-party log service by default | R1 | The canary suite reads container logs; a service without log rotation fails a Compose lint |
| PRV-4 | Secrets per instance in one store with an inventory per environment; never in git, logs, the database, backups, images, build arguments or CI logs. Static secrets (bot token, OAuth client, model key, backup key) may be kept in the owner's password manager and re-entered on a new host; runtime tokens (OAuth refresh tokens, messenger sessions, device and MCP tokens) live in an encrypted secrets volume excluded from backups and are always re-created after a move or restore; `secrets.example` documents every key | R1 | `doctor` checks the inventory and file permissions and lists what must be re-created after a restore; CI scans images and logs for secrets |
| PRV-5 | Network defaults: a native install binds loopback only; the shipped Compose file publishes no ports, or only on 127.0.0.1; nothing listens on a public interface by default, and no plaintext HTTP listens on any non-loopback address. Ports, service names and data roots are per-instance configuration. Remote access only through a documented recipe (DEP-12) that states who can see plaintext and which data classes may pass | R1 | A CI test starts the Compose stack and asserts that no port answers on a non-loopback address; a native test asserts the same |
| PRV-6 | Recording consent: a consent field on each recording source and documentation of jurisdiction rules | R1 | — |
| PRV-7 | Delete a source (recording, chat, message) together with every record derived from it. The deletion and blanking log (ids and hashes only) is an append-only file outside the database snapshot, copied off-host, and re-applied before any restored instance serves. Deleted data leaves backups within the documented maximum retention. Documents under legal retention (FIN-14) are refused until their retention date | R1 | After deletion, search and dossiers return nothing from the source — also after restoring an earlier backup; a retained document's deletion is refused with its date |
| PRV-8 | Full export (JSON with an inventory) | R2 | — |
| PRV-9 | **Journal switch** (design proposed, D-025): a per-installation setting, per analysis module, that decides whether journal text may go to a destination — the configured model provider, or a local model endpoint if the owner configured one. `coflow init` asks with no preselected answer, explains the trade-off and records the answer in `DATA_FLOWS.md`; (proposed) the init text explains that other people named in the journal did not choose this. Single entries can be sealed ("never analyse"). Turning it off stops future sends; text already sent cannot be recalled, and the bot says so. The switch state shows on the status page and in the morning health line. No local-model-only mode is built; the provider interface (EXT-2) lets others add one | R1 | Canary entries (one normal, one sealed) under both settings: off — no model call contains either; on — only calls of enabled modules contain the normal entry, none contains the sealed one; no prompt log or trace holds the text |

### 5.14 Operations (OPS)

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| OPS-1 | `coflow init --role production\|staging\|dev` creates an instance: data root, instance id, profile, database, model download into the models volume (pinned to a revision and a checksum that `doctor` verifies), service logins (headless flow, SIG-9), checklist. It runs natively or as a one-off container; answers may come from a config file. `coflow doctor` verifies the instance and serves as the container health check | R1 | A clean Linux host with Docker reaches a working instance by following the docs; a clean Windows machine reaches a native dev instance with fakes |
| OPS-2 | One supervisor process runs all periodic jobs (no OS scheduler entries); single-instance locks are held by the OS on the local data volume. The platform's service manager starts it at boot and restarts it after a crash (Docker restart policy, a systemd unit, or a logon task for native dev). On SIGTERM it stops taking jobs, returns in-flight work to the queue, checkpoints the database and exits within 30 s | R1 | SIGTERM mid-transcription loses nothing and the job resumes; the instance survives an unattended reboot and a power cut (drill) |
| OPS-3 | SQLite discipline: WAL; no network or model call inside a write transaction; short idempotent writes retried on "locked"; a watchdog logs writers holding > 10 s; init once per code and schema revision; a long-lived process started on an older revision detects it and never runs schema or index maintenance. The database sits on a local filesystem of the host that runs the writer — never on a network share or a cross-OS bind mount. The command line writes through the core's admin API; only migrate, restore and drill run with the core stopped | R1 | `doctor` refuses network and VM-shared filesystems for the data root (test with mocked mounts) |
| OPS-4 | Numbered SQL migrations with `user_version`, forward-only; a snapshot before migrating; migrations run once as a deploy step in a one-off container, never on service start. Expand-only migrations and accepted schema ranges are R2 | R1 | CI compares the schema of a clean install with the schema after upgrading from the previous release; they are equal |
| OPS-5 | Backups: a daily consistent snapshot plus a snapshot before every deploy; an encrypted off-host copy is required for the production role — by default an append-only repository in EU object storage, written with credentials that cannot delete, its key kept in the owner's password manager and never only on the host; pruning runs monthly from another machine; a documented maximum retention. A restore stops all processes, handles WAL files, re-applies the deletion log (PRV-7) and starts as non-production unless explicitly promoted | R1 | CI restores a backup into a fresh volume and a clean native folder; an off-host snapshot from the last 24 h restores on a different machine; `doctor` and the morning plan warn when the off-host copy is older than 48 h |
| OPS-6 | Health: tick, workers, bot heartbeat, source freshness and errors, backup and off-host copy age, disk space, memory, queue sizes, transcription backlog, token expiry, clock skew, instance role and id — on the status page, in bot `/status` and as a line in the morning plan. A content-free heartbeat with a rotating check id goes every 5 minutes to an external dead-man-switch service that alerts through its own channel | R1 | Unplugging the host's network raises an alert on the owner's phone within 30 min (drill); an expiring token is reported ≥ 14 days ahead |
| OPS-7 | Cost ledger: every model call with cost; daily budget with deferral of background work; monthly report | R1 | — |
| OPS-8 | Evaluation harness: offline by default (fake model, fake Google and Telegram, no network, temp data folder); live model only with an explicit flag and a budget; it refuses to run against a production data root, production tokens or the production bot | R1 | A run changes no file outside its temp folder; a run pointed at a production data root refuses |
| OPS-10 | **Interaction trace:** every request (bot, MCP, worker, device agent) carries an interaction id, a channel and a source reference; model calls store a step trace (tools, normalized arguments and results, truncation flags, rules applied, sources, input data classes) and the behaviour version (in production the image digest and release version; in native dev the commit with a dirty flag), model id, mode, tool schema version and rule versions; traces follow PRV-3 and are blanked by BOT-3 | R1 | Any bot answer can be traced to its steps and to the image digest that produced it |
| OPS-11 | **Model tier per function group, chosen by the owner, with a cost forecast:** for each model-backed function group (bot answers, conversation summaries, meeting outcomes, analysis modules) the owner picks a tier of the configured provider (small / medium / large). `coflow init`, the status page and a bot command show the expected monthly cost of each tier, computed from the owner's own measured volumes in the cost ledger (OPS-7) and the provider's price table, next to the measured quality of that tier on the evaluation set for that function (OPS-8). A tier never changes by itself | R1 | Changing a tier changes the forecast immediately; after a month the forecast is within 20 % of the actual cost; the evaluation result per tier is shown next to its price |
| OPS-12 | **No silent truncation:** every structured model call checks the provider's stop reason; a truncated answer is logged as an error, retried once with a larger output budget, and if it truncates again is surfaced as "incomplete" together with what was parsed - never stored as an empty or partial result that reads as complete. The rule holds at every stage of a multi-step pipeline, chunk summaries included, and a stage that drops items records how many and why | R1 | A fake provider that truncates on command yields an "incomplete" result with one retry, never an empty list; the number of dropped items and the reason are in the trace (OPS-10) |
| OPS-13 | **Private evaluation sets from the owner's own material:** the owner may label commitments, dates and decisions in a few real recordings and keep that set inside the instance's data root - never in the repository - to measure recall of the outcome pipeline per model tier before a change ships. The set that ships publicly is synthetic | R1 | A tier or prompt change that drops recall below the configured target (default 80 %) fails the evaluation gate; the private set never leaves the data root (canary) |
| OPS-14 | **Honest provider errors:** a provider error (no credit, overload, rate limit, timeout) reaches the owner as a short explanation of what happened and what to do, never as a raw payload; an exhausted balance or an expired key raises at most one alert a day, and only while no later call has succeeded, so a single failure followed by working calls stays silent; it shows on the status page and in `doctor`; the raw error stays in the logs | R1 | A fake provider returning each error class produces an owner-readable message and no raw payload in any channel; the balance alert fires once a day, not per call |

OPS-9 (update procedure) moved to the deployment requirements DEP-8…DEP-10 and is now R1.

### 5.15 Extensibility (EXT)

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| EXT-1 | Plugin interface in two kinds. Host plugins: optional modules enabled by configuration, included in the image or a documented derived image, never installed at run time; they never open a database connection — they submit work to the writer or return data that the core validates. Device agents: run on an owner device and talk to the host only through the ingestion API with a device token. Each plugin manifest declares where it runs, its data flows, what leaves the device, its permissions, and the ports, volumes or devices it needs | R1 | The Telegram collector ships as a host plugin; a plugin entry point cannot resolve the database path (test); a manifest without "runs on" and "leaves device" fails CI |
| EXT-2 | LLM provider interface; Anthropic is the reference provider; others can be added, including a model endpoint the owner controls (on the CoFlow host in an optional local-model profile without published ports, or on another owner computer over an encrypted private channel, listed in `DATA_FLOWS.md`) | R1 | The test suite runs with a fake provider |
| EXT-3 | Calendar provider interface; Google is the reference provider | R1 | — |
| EXT-4 | Public integration contract for external apps (live conversation assistants, event apps): read a brief, write a session, highlights and an outcome, idempotently, through the API listener with per-app tokens and scopes and an app → host row in `DATA_FLOWS.md` | R2 | The reference consumer of the contract passes against an instance on another machine before the switch-over |

### 5.16 Money (FIN)

Money is an outcome like any other: decisions and commitments carry a financial stake, goals carry
targets. CoFlow is the **planning and evidence layer** for money. Each money contour (household, own
practice, a company) is a separate book; each book belongs to a taxpayer (a tax id with its own calendar
and records). Entries are append-only. Invoices issued and received sit in a register, imported read-only
from a compliant invoicing tool or recorded after the fact. A country pack supplies the tax calendar,
labelled reserve estimates, retention rules and exports for an advisor. **CoFlow never issues invoices,
never files returns, never keeps statutory company accounts and never holds bank credentials**
(proposed, D-018, D-026). Every tax figure is an estimate for planning, not tax advice. v1 had no ledger;
this domain is new. Nothing in this section is tax advice.

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| FIN-1 | **Financial goals and planning** per book: targets per period (income, revenue by direction and client, savings, runway, coverage of the tax reserve), keyed by goal (the money module owns money targets); a cash-flow forecast from open issued invoices, recurring expenses and tax obligations (FIN-12); runway = available cash minus the tax reserve, divided by average monthly spend; runway shows the reserve's label and pack version | R2 | Progress and runway are computed numbers that link to their entries, never a model's estimate; runway excludes the reserved tax |
| FIN-2 | **Ledger** of real money, append-only. Each entry: booking and value date, amount, currency, FX rate with source and date, account, book, counterparty (person or company), category, links to goal, direction, decision or commitment, source document. A posted entry is never edited or deleted: corrections are reversal entries with a reason. One-line entry in the bot or through MCP. Accounts carry institution country, currency, opening balance and pack-defined attributes | R2 | A balance equals the opening balance plus its entries; a retried request creates no duplicate; editing a posted entry is refused and offers a reversal; the full history exports |
| FIN-3 | **Bank statements from files only**, as importer plugins (file in, normalized rows out): Norma 43 and camt.053 first (they carry opening and closing balances), then CSV with per-bank mapping profiles and OFX. Identity key in order: the format's own id, a content fingerprint, an occurrence index. Category rules run after de-duplication; the raw line and the file hash are kept. CoFlow never stores or uses bank logins or bank API credentials | Plugin | Same file twice, an overlapping statement and a re-exported file change nothing; two identical genuine same-day payments are both kept; opening balance + movements = closing balance, and a mismatch is shown, not forced |
| FIN-4 | **Reports per book:** income, expenses and balance per month and currency; runway; plan vs. fact against financial goals; money by client and direction; receivables ageing; decisions with a financial stake: expected vs. actual money; obligations and the reserve (FIN-12, FIN-13) | R2 | Every number links to its entries; no report crosses books by default (FIN-6) |
| FIN-5 | **Financial data switches**, per purpose (the owner's money questions, weekly review, goal control, reminders), each a row in `DATA_FLOWS.md`; default: only the owner's own money questions. At any setting: tax figures never go to a model (the model phrases a template with placeholders and the renderer inserts each figure with its label and pack version); third-party identifiers (tax ids, IBANs, invoice numbers) are masked; credentials, API keys and certificates never reach a model; raw financial documents go to a provider only under a separate switch, off by default, after redaction | R2 | With defaults, the weekly review is generated with amounts as placeholders and no amount appears in the model call; no unmasked third-party tax id or IBAN and no secret appears in any call (canary) |
| FIN-6 | **Books and taxpayers.** Every account, entry, invoice record, document and financial goal belongs to exactly one book; every book belongs to one taxpayer. A household and a sole-trader practice may share a taxpayer; a company subject to corporate tax is always its own taxpayer. Entities taxed under attribution of income and joint returns of a family unit are pack-defined groupings that the income-tax estimate can span; until the pack supports them, such estimates are marked "incomplete". An account may be marked "mixed use" and shared only between books of the same taxpayer; each of its entries is assigned to one book or split by percentage with a reason. No report sums across books unless asked, and never across currencies without a stated rate and its source | R2 | The schema rejects a row without a book; on a three-book fixture every default report stays inside one book; per-book balances of a mixed account add up to the bank balance; an unassigned entry on a mixed account blocks the period's reports; sharing an account between two taxpayers is refused |
| FIN-7 | **Money between books.** Within one taxpayer (household ↔ own practice: draws, contributions) a transfer is two linked entries that are neither income nor expense. Between taxpayers (the owner's practice ↔ the owner's company), salary, director's pay and invoiced services are income in one book and expense in the other, each backed by payroll or an invoice. Dividends are income in the recipient's book and a distribution of profit (not an expense) in the company's book, backed by a dividend record with its withholding. All carry a related-party flag and a "market value documented?" field; only capital contributions and loans (with interest terms) are transfers across taxpayers | R2 | A same-taxpayer transfer changes both balances and no income or expense total; an invoice from the practice to the owner's company increases practice income and VAT output and company expense; a dividend increases the recipient's income and no company expense; an unpaired transfer leg is flagged |
| FIN-8 | **Invoice register** (issued and received), as records, not as an invoicing system; fields use EN 16931 business-term names: book and taxpayer; series and number; issue and accrual dates; parties with tax id, id type, country and business-or-consumer flag; VAT-number check result with date and evidence; place-of-supply rule and tax qualification code (from the pack); base, rate, tax and withholding amounts in the reporting currency; invoice currency with FX rate; mandatory mention; link to a corrected invoice; payments matched to ledger entries; issuing system and its record id, QR or hash; the original document with its hash. A record without a source in a compliant invoicing system is marked "manual, outside register". Received invoices add deductibility flags | R2 | Validation warns on series gaps or duplicates, a missing client tax id, a missing reverse-charge mention, a tax amount not in the reporting currency, a corrective invoice without its original; the Spanish golden matrix passes (FIN-11) |
| FIN-9 | **CoFlow does not issue invoices or file returns:** it assigns no invoice numbers or series, renders no document as an invoice, builds no official register from invoices it drafted, submits nothing to a tax authority and handles no tax certificate. Quotes and pro-formas are labelled "not an invoice". Exports are working papers for the owner or their advisor. Records marked "manual, outside register" feed only plain lists with totals, labelled as working papers. They feed no per-form figures, no register-book layout and no box mapping. The VAT estimate (FIN-13) marks any figure that depends on such records as "incomplete: invoices outside a compliant invoicing system" | R2 | A test asserts that no code path allocates invoice series numbers or produces a document titled as an invoice; every export carries the "working papers, not a filing" label |
| FIN-10 | **Country packs.** The core knows no country. A pack supplies, as data: tax qualification codes, withholding rules, filing obligations and their windows, rules for moving deadlines off non-working days, applicability rules, mapping to form boxes, export layouts, rate and scale tables, retention rules and thresholds. Every row has effective dates and an official source URL; the pack version is stored with every computed figure. Tax residence and regime are profile settings (CFG-1); CoFlow never infers them | R2 | The core suite passes with no pack installed; every pack row has a source and dates (schema check); a new pack version recomputes figures and keeps the old ones with their version |
| FIN-11 | **Spain reference pack** (sole trader in direct estimation; company optional): tax qualification codes; withholding rules; the filing calendar, for example 303, 390, 130, 349, 347, 111/190 and 115/180 when a withholding agent, 100, 720/721, and for a company 200 and 202 (202 only when the pack's applicability rule says so); the full list of obligations and their applicability rules comes from the pack, each row with its official source; applicability tests (the 130 exemption by the 70 %-withheld rule; 349 whenever there are intra-EU operations with businesses, meaning supplies of goods or services to EU business clients or acquisitions of goods or services from EU businesses; monthly 349 when intra-EU supplies and services in the quarter or any of the four previous quarters exceed EUR 50,000); register layouts for the advisor; rate tables per tax year. Shipped per tax year, as a separate package. Rules listed here are examples to be encoded with an official source per row (FIN-10); they are not a statement of anyone's obligations | Plugin | Golden files per tax year: the client-type matrix (Spanish B2B, EU B2B, EU B2C, non-EU B2B, non-EU B2C, EU purchase, non-EU purchase); the calendar equals the official one for that year, including moves off non-working days; the reserve formulas |
| FIN-12 | **Tax calendar and reminders** per taxpayer, generated from the pack; each obligation links to its input entries and invoices and has a status (not started / prepared / filed / paid, with the receipt as a document); reminders in the morning plan and the bot N days before the window closes, earlier for direct-debit payment. Every calendar entry, reminder, applicability decision and warning is rendered with the pack version and "estimate, not tax advice; confirm with your advisor". An obligation judged not to apply is listed as "considered not applicable: <rule>, <source>", never silently left out | R2 | Same data gives the same calendar; each reminder is sent once; a year without a pack shows "no calendar for <year>", never a guessed date; an obligation judged not to apply is listed as "considered not applicable" with its rule and source; no entry or reminder appears without the label and pack version |
| FIN-13 | **Tax reserve and quarterly estimates** per taxpayer, computed from every book of that taxpayer (the only default aggregation across books, listed in the figure's inputs): VAT due this quarter from the invoice register, the income-tax instalment by the pack formula, the annual top-up from the pack scale with an individual or joint filing setting, the social-security quota and its regularisation risk. Each figure shows its formula, inputs, pack version and "estimate, not tax advice; confirm with your advisor"; it is marked "incomplete" while any of the taxpayer's books has unclassified income, and "incomplete: invoices outside a compliant invoicing system" while it depends on records marked "manual, outside register" (FIN-9). After filing, the owner records the filed amount and the difference is shown | R2 | No tax figure appears anywhere without the label and pack version (canary); the VAT figure on the golden fixture is exact; with practice income and savings interest in the household book the income-tax estimate includes both and names both books; until the owner sets a tolerance, an estimate more than 10 % off the filed amount is flagged |
| FIN-14 | **Document archive with retention:** originals kept as received, with a content hash, a type and links to entries, invoices and obligations; fields are extracted locally (structured files first, then local PDF text or OCR in a stateless worker); the retention date is computed by the pack as the latest applicable rule; deletion before it is refused, including through PRV-7 and PPL-6; phone scans are marked "copy, keep the paper"; nothing is auto-deleted | R2 | A deletion before the retention date is refused with the reason and the date; canary documents with a synthetic tax id and IBAN are ingested with no model call containing either value |
| FIN-15 | **Export pack for the advisor**, quarterly and annual per taxpayer (default format: a spreadsheet workbook plus a ZIP of PDFs with a manifest): register drafts in the pack's layout (an issued-invoice register only from records with a compliant source; manual records go only to a plain working list with totals, FIN-9), working figures per form with formulas (never from manual records), obligations with their statuses, a ZIP of source documents with a manifest and hashes — all labelled as drafts | R2 | Same data gives byte-identical content (timestamps aside); every row links to its source; on a fixture of manual issued invoices no output uses the official issued-register layout, a per-form figure or a box mapping |
| FIN-16 | **Invoice adapters**, strictly read-only: a file import first (the invoicing tool's CSV/XLSX export or structured e-invoice XML, plus PDFs), an API adapter per tool as an option using read-only scopes. Records are idempotent by source system and record id; status and payments are mirrored, never changed in the source tool. API keys live in the secrets store and never reach a model | Plugin | Invoice count and totals per period equal the source tool's; re-import changes nothing; a contract test with a fake API fails on any write call |
| FIN-17 | **Thresholds and warnings from the pack**, for example: foreign assets approaching an information-return threshold, per the pack's categories (for Spain: 720 per category, including the re-filing increase rule, and 721 for crypto held abroad); intra-EU supplies crossing the monthly-filing threshold; an EU business invoice while the owner's registration for intra-EU operations is missing or unknown; an EU business invoice without a valid VAT-number check dated on or before accrual; any cash payment toward an operation of EUR 1,000 or more (the pack's limit, adding up split payments for the same supply) where either party acts as a business or professional, in any book; foreign tax withheld; related-party flows (FIN-7). Every warning is rendered with the pack version and "estimate, not tax advice; confirm with your advisor" | R2 | Synthetic fixtures crossing each threshold raise exactly one warning each, with the rows behind it, the label and the pack version |
| FIN-18 | **Rules-watch:** every pack carries a quarterly task listing pending rule changes and their sources; a pack year not yet verified against the official source is marked "unverified" wherever its figures appear | R2 | A calendar or estimate built from an unverified pack year shows "unverified" |
| FIN-19 | Structured e-invoices (UBL, CII, Facturae) imported into the register, plus status and payment state from the country's business e-invoicing system once it applies (for Spain: Ley 18/2022 and Real Decreto 238/2026, in phases by turnover above or below EUR 8M, counted from its technical ministerial order; the pack tracks the dates through the rules-watch, FIN-18) | Later | — |
| FIN-20 | Plain-text ledger export per book (Beancount format) for an independent view in third-party tools; GPL tools are reached only through files or command-line subprocesses, never imported (a conservative project rule, not a legal opinion on GPL boundaries) | Later | — |

### 5.17 Centre and goals (GOL)

The module helps the owner **form** their centre — values and manifest, life vision, directions with
quality criteria, period goals — and **control** whether their time, money, commitments and decisions
follow it. The owner writes every sentence: the system asks questions, gives structure and feedback
against fixed criteria, and versions what the owner approves. Owners who already have such documents can
start by importing them unchanged. Control is computed by algorithms over data CoFlow already holds; a
model only phrases results. There are no composite scores, no model-written goals and no goal dashboards
(method proposed, D-028). In R1 only the data hooks exist (WRK-1 goal fields, WRK-8).

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| GOL-1 | **The centre:** typed documents the owner writes (for example values and manifest, professional core, strategy, life vision, directions), each with a configurable type, a precedence rank (which document wins on a conflict), a stability level and sections. Never generated or seeded by code; versioned; every analysis and control run records the version it used. Approved versions are work data readable through an MCP read tool | R2 | Changing a section creates a new version with a diff; past findings keep their version; a fresh install contains no centre content |
| GOL-2 | **Import first:** existing documents are split into sections without rewriting a word; the owner assigns type, precedence and stability; version 1 is created | R2 | Imported text is byte-identical to the source; nothing changes without an owner edit |
| GOL-3 | **Rule objects** that control runs on: typed fields the owner fills or edits — priority order of directions with time and money envelopes, caps on active goals and hypotheses, allowed calendar-block types, opportunity-filter questions, backlog return conditions, metrics with what they do not capture, horizon targets, review cadence. Any free text in a rule is an exact quote of a centre section stored as a reference; a model may only point to the section, never rephrase it. Control never runs on prose | R2 | Each rule links to its source section; a planted model paraphrase in a rule candidate cannot be confirmed; free text in a confirmed rule equals a centre span byte for byte |
| GOL-4 | **Formation sessions**, as versioned protocols: values (a public-domain card sort, then importance and consistency per life domain); life vision (writing at a horizon the owner picks, plus three alternative paths before converging); directions (boundaries, what is out of scope, quality criteria in the owner's words, envelopes); period goals (GOL-6). On request or at quarterly and yearly reviews, labelled as reflection aids. Session transcripts and unapproved drafts are journal class (PRV-1) | R2 | A session pauses and resumes; each session records its protocol version; session duration is logged and its median reported as a usage signal |
| GOL-5 | **Authorship:** the assistant asks questions, reflects back and gives feedback on the owner's drafts against fixed criteria (clarity, fit to the goal type, conflicts with other goals, links up the hierarchy, feasibility against the owner's own planned-vs-actual history). When the owner asks or agrees, it may offer draft wording for values, vision or goals, always clearly marked as a suggestion and never inserted into a draft by itself; a sentence the owner adopts from a suggestion is recorded as "adopted from suggestion" in the version history (owner's decision, 4 October 2026); generic examples come from a fixed, published list. Drafts become immutable versions only through an approval card with a diff in an owner-typed channel (the bot or a local command); drafts arriving over MCP are marked "origin: MCP client" and treated as non-owner text | R2 | Provenance test: every sentence of an approved version traces to an owner message or edit; a sentence that nearly matches a model output of the session fails unless it is recorded as "adopted from suggestion" or "adopted from reflection" by an owner action; the share of adopted sentences is reported as an ownership signal (GOL-12); a planted model sentence pasted back or arriving through MCP never enters an approved version silently |
| GOL-6 | **Goal card:** period; type (outcome / learning / behaviour / open); a reasons rating recorded before selection and the "why" in the owner's words linked to a centre item; measurable criteria where they fit (attainment levels −2…+2 written in advance; a metric with "what this number does not capture" and an optional counter-metric; a money target, FIN-1); the main obstacle and one if-then plan that becomes a dated task, a calendar block or a reminder; review date; links to a direction and a centre item | R2 | Activation is refused without a direction link and a review date; an if-then plan creates exactly one checkable item |
| GOL-7 | **Hierarchy, states, caps:** centre → vision → directions → period goals → hypotheses or projects → tasks, commitments, decisions, meetings, money and time. Goal states: draft, active, paused, dropped, superseded, achieved, closed; pause, drop and supersede need a reason and happen only in a deliberation review (GOL-10) or through a decision record; dropping is a valid, logged outcome. Caps on active goals and hypotheses are configurable; activating over a cap requires pausing one in the same action | R2 | The cap test passes; no goal leaves "active" without a reason; no active goal lacks a parent link |
| GOL-8 | **Weekly control**, computed by algorithms: it cites the control view's task-level items (WRK-6) and adds declaration-level checks — active goals without direction or centre links; share of hours and money not linked to any goal; neglect (directions or life domains with zero time or money in the period); allocation against declared priorities and envelopes (hours from the calendar and activity spans, money from the ledger, meetings and commitments per direction); caps and focus rules. Items are worded at task level, never as a judgement of the person; each names its coverage, and a layer below the coverage threshold gives "can't judge" | R2 | Same data gives the same list and order; on a synthetic year with planted problems, recall is measured and published, and the false-alarm rate stays under a published ceiling |
| GOL-9 | **Three verdicts per closing goal**, stored separately: output (computed from tasks and commitments); outcome (the attainment level, proposed from linked evidence and confirmed by the owner); path (were the assumptions and the route right, given what was known; linked to decision assumptions) | R2 | The three fields are separate; an outcome without owner confirmation shows as "proposed" |
| GOL-10 | **Review cadence and modes:** structured debriefs on dates the owner configures — weekly (GOL-8 plus RHY-4), monthly (outcomes and envelopes), quarterly (deliberation: goals re-planned), yearly (the centre re-evaluated, producing a new version). Daily and weekly messages never reopen the goal choice: "change the goal?" goes to the next deliberation slot or becomes a decision record. After a lapse, a fresh-start review replaces a backlog of failures | R2 | No daily or weekly message proposes changing, pausing or dropping a goal; a goal taken to deliberation appears in the next deliberation review; a lapse of N weeks yields one fresh-start review |
| GOL-11 | **Outside view:** when the owner drafts a goal or plan, the planned vs. actual hours and dates from their own history are shown next to it | R2 | The shown figures link to the past items they come from |
| GOL-12 | **The module measures itself:** after each session the owner rates ownership and commitment from 1 to 5, and a falling trend is a defect; usage signals: sessions completed, share of active goals with attainment levels and an if-then plan, review completion; a check the owner marks useless across its last runs switches itself off; if the weekly review goes unopened for N weeks in a row, its generation pauses and the owner is asked once whether to keep it. There is no composite alignment score | R2 | Signals are available through an MCP read tool and on the status page; a planted useless check switches itself off; N unopened reviews pause generation |

### 5.18 Timeline (TML)

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| TML-1 | One timeline over every layer — conversations, messages, recordings, meetings, calendar, tasks and status changes, decisions, commitments, notes, money: "what happened on <day>", "around <event>", "between <dates>", filtered by person, direction or channel, with coverage per layer. Journal entries are never stored in the timeline; they appear only in the owner's local timeline view (the local command through the admin API, merged at read time), never through the bot, MCP, search, briefs or the status page | R1 | A day query lists items of every layer with sources; a layer without data for the period is named, not hidden; the MCP timeline tool returns no journal item (canary) |
| TML-2 | The whole personal archive in the timeline: old recordings, chat and mail exports, documents and media as dated items; device clocks corrected (original time kept); deduplicated by content; a cost estimate before any model processing (SIG-11) | R2 | Re-import changes nothing |
| TML-3 | Change over time (research): how the owner's position on a topic evolved (quotes per period), how communication with a person or in general changed (REL-1 measures per period), recurring chains of thought; every finding cites its evidence; the journal only under PRV-9 | Later | — |

### 5.19 Inconsistency findings and alignment research (ALN)

Inconsistency findings are a stage-8 module right after the goals module (owner's decision, 4 October
2026): they compare what the owner thinks (journal, under PRV-9), says (conversations) and does (tasks,
time, commitments, money) with the versioned centre (GOL-1). v1 built engines for this and they
died: a judge that never returned "violation", inputs that went stale, a reference partly seeded by code
(LESSONS_FROM_V1 §7). The findings below therefore rest on evidence, "can't judge" and a planted
evaluation set. Alignment formulas and scores stay research on top of well-built core data (D-029); the
deterministic part of self-control lives in the goals module (GOL-8, LRN-6).

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| ALN-2 | Inconsistency findings: "the centre says … — the stream shows …", with a quote or a fact and its source on both sides; verdicts: consistent, inconsistent, can't judge; scope by period, direction, person or topic | R2 | No finding without evidence on both sides; "can't judge" when evidence is missing |
| ALN-3 | Against the echo: each check searches for disconfirming evidence on purpose and sees its whole input; it is evaluated on a synthetic set with planted inconsistencies before any finding is shown; the owner marks findings useful or not, and a check with fewer than 30 % useful findings over its last 20 switches itself off | R2 | Recall on the planted set is measured and published with the check |
| ALN-4 | The journal in alignment analysis: read only by analysis modules enabled under PRV-9, for a period the owner chooses; sealed entries are excluded; findings derived from the journal are journal class and shown only in the owner's own channel | R2 | The PRV-9 canaries pass for this module |
| ALN-5 | The owner's communication against the centre: their own moves in conversations — promises made and kept, frames held or dropped, pressure, avoidance — with quotes | R2 | Every finding quotes the conversation segment it rests on (SIG-14) |

ALN-1 (the centre) became GOL-1.

### 5.20 Relationships and conductivity research (REL)

The author's model of interaction, the *conductivity integral*: **∫G = V × E** — a system of human
interaction is the people (V) times what happens between them (E). In time:
**G(t) = (V, E(t), X(t), C(t))** — who takes part, the relations between them now, the state of each
participant, the context. (Reading of the symbols drafted from the author's notes; to be confirmed by the
author before REL-4 is specified.) The research question is **how G(t) becomes G(t+1)**: what happened between
people, why the state changed, and whether the next state can be predicted. Everything in this section
except REL-6 is research (Later), built on data the core already stores and pre-registered when started.
REL-6 is in R1 so that this research never needs a re-import.

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| REL-1 | Interaction graph over time, computed by algorithms from stored signals: for each pair (the owner and a person; two other people when they meet in a conversation the owner took part in) — messages, calls, meetings, who initiates, response times, silences, commitments given, kept and broken by each side, topics — per period (E(t)); context C(t) from calendar, goals and channel | Later | The same data gives the same series; every value links to its events |
| REL-2 | Communication balance: important relationships (people linked to active goals and decisions) whose balance shifts — one-sided initiative, growing silence, commitments unkept on either side — appear in the weekly review with evidence | Later | Each alert lists the events behind it |
| REL-3 | Participant state X(t): for other people, only their stated positions over time (PPL-1 facts with quotes: wants, fears, constraints, stance); no psychological diagnoses or emotion scores are inferred or stored; for the owner, also a self-reported state (energy, clarity) when the owner chooses | Later | — |
| REL-4 | Conductivity research module: a pre-registered protocol — a prediction recorded and locked before the outcome, blind annotation of conversations with a fixed codebook, machine-computed features, an outcome checked from CoFlow data (for example, whether a meaningful contact followed within a set number of days), a corpus view; protocol versions are kept. Specified after a planned experiment gate (November 2026) | Later | A case without a locked prediction never enters the corpus |
| REL-5 | Predicting G(t+1): any model that predicts the next state is evaluated against simple baselines on pre-registered cases before it is shown as a result | Later | — |
| REL-6 | **Research-ready signals in the core**, kept without destructive aggregation: for every message its direction (from or to the owner), sender and timestamp to the second; the initiator of every session, meeting and commitment; both sides of commitments with a timestamped status history; device-corrected times with the originals; the centre version used by every analysis | R1 | From a synthetic export, the REL-1 measures (initiative, response times, silences, commitments kept per side) are computed from stored rows alone |

### 5.21 Deployment and delivery (DEP)

Details, recipes and drills: [DEPLOYMENT.md](DEPLOYMENT.md).

| ID | Requirement | Pri | Acceptance |
|---|---|---|---|
| DEP-1 | Two install paths from one codebase and one lockfile: Docker Compose on a Linux host (the reference production install; the same image on any Docker host or rented server) and native Python on Windows or Linux (development, contributors, device agents). Docker is never the only way | R1 | The same release passes the native suite on Windows and Linux and the suite inside the image |
| DEP-2 | Instance identity and role: an instance id, a role (production, staging, dev, drill), a random volume id written at init and a random host-id file in the host's configuration directory. A mismatch refuses start. Only the production role executes outbox actions, polls the owner's bot, runs collectors and uses production tokens; the role shows on the status page and in every non-production answer | R1 | A staging instance restored from a production snapshot executes no external action and polls no production bot |
| DEP-3 | One production writer: a copy or restore starts as non-production; `coflow promote` requires `coflow retire` of the previous production or `--previous-lost` with a confirmation phrase; promote increments an epoch and requires re-issuing runtime credentials (bot token, calendar tokens, device and MCP tokens), which is the fence that stops a returning old host from acting. A Telegram 409, a revoked bot token or a heartbeat with an older epoch puts an instance into fenced mode (outbox, collectors and writers stop) | R1 | A copied database refuses to write as production on a new host; a retired instance refuses to start its writers; after promote the old host returns and cannot act; recreating containers or restarting the host keeps production |
| DEP-4 | Environments: development uses fakes and synthetic data only; until the switch-over the production host runs one instance in the staging role, deployed through the production path; afterwards there is no permanent staging stack — pre-release checks run in CI plus an on-demand `coflow drill` (a restore into a throwaway project on an internal network, with fakes and no bot, destroyed afterwards). One shared set of test credentials is used by one instance at a time | R1 | `doctor` on a drill instance finds no production secret, volume or token |
| DEP-5 | Container image: stateless; non-root fixed UID; read-only root filesystem; no secrets; no models (downloaded at init into a volume); base images pinned by digest; dependencies installed from a hashed lockfile; a licence gate that fails on AGPL or GPL components in the core image, and on LGPL components outside plugins unless listed under the D-001 audio-decoding exception; version, commit and digest stamped into the image | R1 | CI lints the image (user, read-only root, no secrets, no models, pinned base); the licence gate fails on a planted AGPL dependency |
| DEP-6 | Reference Compose stack: `core` (the only database writer: supervisor, bot, scheduler, outbox, MCP, status page) and `stt` (stateless speech-to-text worker without database access, without any network shared with the core's API, with a read-only inbox mount and its own limits); optional profiles `backup` and `llm`; named volumes for data, models and secrets; health checks, restart policies, stop grace periods, log rotation and resource limits on every service; never a Docker socket mount | R1 | A Compose lint in CI enforces these rules; the stack with fakes turns healthy in CI |
| DEP-7 | Public CI runs only on GitHub-hosted runners — never a self-hosted runner on the public repository: native suites on Windows and Linux, the image build, the suite inside the image, a Compose smoke test with fakes and egress blocked, the exposure test (PRV-5), an upgrade test from the previous release, a restore into a fresh volume, the literal gate, secret scanning, DCO and the MCP catalogue check. Actions pinned by commit; the default workflow token read-only; dependency updates merged by a human; repository rules allow `v*` tags only from the release workflow on protected main, never moved or deleted | R1 | Repository settings show no self-hosted runner; a tag pushed by any other principal is rejected |
| DEP-8 | Releases only from the release pipeline: Conventional Commits, a release PR with the changelog, a `vX.Y.Z` tag (pre-releases `v2.0.0-alpha.N`); each tag builds one image, pushed to the registry by digest with a keyless signature that the host verifies against one pinned identity (repository, release workflow, tag reference); the changelog flags migrations and names irreversible ones | R1 | An image signed by another workflow or built from a branch fails verification on the host |
| DEP-9 | Host-side updater: a small component installed by `coflow init --role production`, run by a timer, the only thing allowed to call Docker, updated only with a separate owner approval and never from a pulled application image. Approval over SSH until the bot card exists (stage 5), then a bot card whose preview hash covers the image digest, signer identity, target instance and role, migration ids with an irreversible flag and an expiry; approvals are accepted only from the core of the instance the updater manages (the production core; before the switch-over, the single staging instance), never from a drill. Sequence: pull by digest → verify → check free space → hold writes (bot polling, outbox, collectors and scheduler held; inbox registration paused, the ingestion API answers 503 from stage 6; MCP read-only) → snapshot → stop → migrate in a one-off container → start → health gate and smoke check without external writes → release the holds. No inbound connection from CI | R1 | A tagged pre-release reaches the host with no manual step other than the approval; an unsigned or wrongly signed image is refused; an approval for one digest cannot deploy another |
| DEP-10 | Rollback: automatic only while the holds are on — restore the pre-deploy snapshot, start the previous digest, alert. After the holds are released, fix forward with a new release; a manual rollback to the snapshot warns that later writes will be lost. One previous digest and one snapshot are kept. Rollback cannot undo executed outbox actions, data already sent to the model provider or confirmed bot updates. If the rollback itself fails, everything stays stopped and the off-host monitor alerts | R1 | A deliberately broken release rolls back automatically with no lost bot message and no external write (drill, stage 5) |
| DEP-11 | Remote administration is a precondition for a production host: key-only SSH over a private network, with separate keys per purpose and forced commands (an MCP bridge key whose user is not in the docker group, a journal-append key, a passphrase-protected admin key never loaded into an agent that AI coding tools can use); every operation is a `coflow` command runnable over that channel; a documented fallback when the channel is down | R1 | The install drill ends with status, logs and a restore run from the dev machine without physical access; the MCP bridge key cannot run anything but the bridge |
| DEP-12 | Access recipes, each with a runnable check (`coflow doctor --access`) and a `DATA_FLOWS.md` row stating who sees plaintext and which data classes may pass: the default is an overlay VPN (WireGuard-based) with SSH; LAN access is SSH-only or TLS terminated on the host; an edge tunnel that terminates TLS is an opt-in that routes only to the MCP listener of MCP-5 and carries a warning about regional blocking of shared edge addresses. A second remote path that does not depend on the VPN coordinator is recommended | R1 | `doctor --access`, run from another device, reports which recipes work and which listener each one reaches |
| DEP-13 | Disk space: warn at 80 %; at 90 % pause archive transcription and new uploads while the bot and database writes continue; refuse to deploy unless free space ≥ 2 × database size + image size + 5 GB; the updater prunes old images and snapshots | R1 | A fake filesystem reporting low space triggers each threshold once |
| DEP-14 | Production host baseline, checked by `doctor --host`. Required: key-only SSH, NTP, no sleep, power-on after power loss, the database on internal disk, an off-host backup present. Recommended with warnings: full-disk encryption (a tested recipe with its trade-off), a UPS with clean shutdown. Not a laptop. Automatic reboots only in a configured window, never during a deploy. Minimum and reference hardware are published (NFR-4) | R1 | `doctor --host` passes on the author's home host (staging role in R1); a power cut followed by power restore brings the instance back healthy without action |
| DEP-15 | Outage behaviour: devices buffer; the off-host monitor alerts; after more than 20 h without polling the bot says on recovery that messages before a given time may be lost; the calendar copy reports `stale` until its first sync; outbox items with a stale preflight are re-checked, never executed blindly; a runbook for "host unreachable while travelling" | R1 | R1: a simulated 48-hour outage on the staging host (fake clock, polling held) reports the gap, imports nothing twice and executes no stale outbox item; the full 48-hour drill repeats before the switch-over |
| DEP-16 | Ingestion API on the core listener: authenticated, resumable chunked uploads for media and normalized inbox JSON, per-device tokens (listed, revocable, scoped to ingest and to declared source types), idempotency keys, content-hash checks, size limits and rate limits; items register only after complete arrival; device-pushed text carries device provenance and never counts as the owner's instruction | R2 | A 400 MB upload interrupted twice completes and registers once; a duplicate push imports once; a revoked token gets 401 |
| DEP-17 | Desktop uploader (Windows device agent): watches configured folders (recorder, exports), uploads stable files through DEP-16, keeps the source by default, buffers while the host is unreachable and starts at logon | R2 | A synthetic recorder folder reaches search on the host exactly once, also after a network cut mid-upload |
| DEP-18 | Moving an instance (new hardware, a rented server, failover): retire → final backup → restore on the target → compare counters and last public ids → promote with credential rotation; media moves with a hash manifest; devices and agents are re-pointed. Before the author's switch-over, the instance is rebuilt on a different machine from the off-host backup alone | R2 | The rebuild drill ends with equal counters within a measured time (target ≤ 2 h excluding the OS install) and one production heartbeat |
| DEP-19 | Disaster recovery targets: data loss ≤ 24 h, recovery ≤ 4 h onto another Linux machine or a rented server (a rented server holds the journal at rest with a provider — an explicit owner switch in `DATA_FLOWS.md`) | R2 | A yearly drill meets both targets with one production writer throughout |
| DEP-20 | Supply-chain extras: published SBOM and provenance attestations, arm64 and GPU image variants, automated repository-policy checks | R2 | — |
| DEP-21 | Optional push deploy from CI over the private network with workload identity and an environment approval, calling the same updater | Later | The CI node can reach nothing but the update command |
| DEP-22 | **Toolchain and reproducible installs:** dependencies are declared in `pyproject.toml` and locked in `uv.lock`, which is committed; `uv sync --frozen` is the one install path for development, CI and the image, so the three environments resolve to the same versions; a lock that does not match `pyproject.toml` fails CI. `ruff check` and `ruff format --check` are required checks on Windows and Linux, configured in `pyproject.toml`, and the same versions are pinned for local runs through the lock | R1 | A clean machine reaches a working dev environment with two commands; CI fails on an out-of-date lock, a lint finding or unformatted code; the image installs from the lock, not from a resolver |

## 6. Non-functional requirements (NFR)

| ID | Requirement | Pri |
|---|---|---|
| NFR-1 | Platforms: production reference is Linux x86-64 with Docker Engine; development reference is native Windows 11 and Linux (both in CI); Docker Desktop is for evaluation only, with named volumes; macOS best effort by the community; desktop-only features are device agents or plugins | R1 |
| NFR-2 | Install time per path, following the docs: Docker production install on a prepared Linux host ≤ 60 minutes including bot, model key, calendar login and the default access recipe (timed by someone other than the author); native dev install with fakes ≤ 30 minutes; a device agent ≤ 10 minutes | R1 |
| NFR-3 | Typical cost with defaults: ≤ $1 per active day; cost visible per bot answer | R1 |
| NFR-4 | Responsiveness on the documented minimum hardware (4 x86-64 cores, 16 GB RAM, SSD; reference: 8 cores, 32 GB, 1–2 TB NVMe): bot answer median ≤ 15 s; no write transaction > 1 s in normal operation; background work yields to interactive work | R1 |
| NFR-5 | Tests: offline, temp data, no real tokens, synthetic fixtures, standard runner, full suite ≤ 15 min; container jobs (suite in the image, Compose smoke, exposure, upgrade, restore) are required checks on main | R1 |
| NFR-6 | Privacy canaries for the journal across every channel, table, file area (inbox, work, media), container log and restored backup, run under both journal-switch settings (PRV-9), including outputs derived from journal input | R1 |
| NFR-7 | Code and docs in English; user-facing texts localized (EN, RU) | R1 |
| NFR-8 | No data loss on a crash at any pipeline step; every step is idempotent | R1 |
| NFR-9 | Every feature has a user doc, a `DATA_FLOWS` entry and a usage signal | R1 |
| NFR-10 | Every module ships a module card (P-14, [MODULES.md](MODULES.md)) with quality parameters and an acceptance suite that runs in isolation with fakes; contracts between modules have contract tests; a module is accepted only when its own suite and the cross-module canaries pass, and the weekly episode of the week its stage closes publishes the results | R1 |
| NFR-11 | Speech-to-text throughput is measured, not assumed: `coflow bench stt` reports the real-time factor and peak memory on the host. Targets on reference hardware: a 1-minute voice note in ≤ 20 s, a 1-hour recording in ≤ 30 min | R1 |
| NFR-12 | Time to outcome is measured, not assumed: from the end of a meeting to the outcome message, per meeting and as a monthly median; while the recording has not arrived the owner is told exactly that. Target: <= 30 minutes after the recording arrives | R1 |

## 7. Out of scope and dropped from v1

| Item | Why |
|---|---|
| Multi-user, tenants, SaaS, billing, paid pilot packaging, hardware kits | One installation = one owner; the project is open source, not a product |
| 20-page Streamlit UI | ≈ 1 hour of use in 30 days; work moved to the bot and MCP |
| Leads, outreach templates, segments | 0 activity in 30 days; a team tool, not personal |
| v1's compliance, convergence and corridor engines, LIWC, the knowledge graph, the glossary — as built | Dead in v1: a judge that never returned "violation", inputs stale since May, an empty graph. The ideas return as research with evidence rules (ALN, REL) |
| Voice prints, emotion from voice | Rejected: biometric data of third parties |
| Cloud transcription or diarization by default | Audio stays on the CoFlow host; a cloud option may exist only as a disclosed plugin |
| WhatsApp bridges, automatic email sending, two-way calendar sync | Risk of bans, wrong recipients and silent changes |
| Background suggestion queues as designed in v1 | 10 of 1,785 decided; replaced by inline, capped and measured proposals (CMT-2) |
| A universal link graph | Typed links only; the generic graph stayed empty |
| Tracking links and click attribution of third parties | Tracks other people's behaviour; not part of a personal decision system |
| Autonomous coding agent fixing itself | Incidents become packages and issues (LRN-5); humans review code |
| Issuing invoices, invoice numbering, e-invoice generation, filing tax returns, statutory company accounting; plugins that issue, modify or transmit invoices | Likely obligations and sanctions for software producers under Spain's invoicing-software rules (to be confirmed by a legal opinion); a certified invoicing program and an advisor own these (D-026) |
| Bank connections and aggregators | Credentials and data go to third parties; statement files suffice (proposed, D-018) |
| A built-in local-model-only mode for the journal | Not needed by the author; the provider interface (EXT-2) lets others add it |
| Composite alignment scores, goals written by a model without the owner adopting them, cascading OKRs, goal dashboards | Unfalsifiable numbers; goals must be the owner's own (GOL-5); one owner, chat-first (D-028) |
| Network microservices | They would break one writer and one numbering tap; modules are logical boundaries (D-030) |
| Self-hosted CI runners attached to the public repository | Code from fork pull requests would run next to private data (D-021) |

## 8. Open questions

1. **Google OAuth for personal accounts.** Workspace users can use an internal app; personal Gmail users
   must create their own OAuth client. Which mode works without weekly re-login and without app
   verification for one personal user (calendar is a sensitive scope, Gmail read a restricted one)? To be
   verified in stage 0 and documented.
2. **Telegram Business channel** (MTG-8): does it require Telegram Premium, what happens after 24 hours of
   silence, how replies look to the counterpart — a spike before the plugin is built.
3. **Project name.** "CoFlow" is the working name; check for conflicts before the public announcement.
4. **Default model provider and budget defaults** for new users.
5. **Language packs:** Spanish as the third locale?
6. **Approved email sending** (draft → approval → send through the outbox): ever, or never? v1 never
   sends mail, and a test checks it.
7. **Production host:** the author's existing desktop (a gaming PC, currently on Windows) becomes the
   host and moves to Linux (D-020); still open: Debian or Ubuntu, and whether its hardware needs changes; full-disk encryption yes or no; which overlay
   VPN provider; which object storage for backups ([DEPLOYMENT.md](DEPLOYMENT.md) §14).
8. **Money fixtures** — resolved on 4 October 2026: the first synthetic fixture covers one taxpayer with
   two books (household and a sole-trader practice), accounts in EUR, USD and a spare third currency that exercises multi-currency handling; the
   advisor export defaults to spreadsheet registers plus a ZIP of PDFs (FIN-15). A company stays an
   optional fixture. Still open: which invoicing-program export formats come first (FIN-16).
9. **Statement import timing:** pull Norma 43 and one CSV profile into the first money module so that the
   ledger reconciles from day one (recommended), or keep all importers in their own later module?
10. **Spain pack and legal opinion:** ship the Spain pack as a separate package per tax year
    (recommended), and get a short legal opinion before publishing the money module on: (a) whether a
    ledger used for a sole trader's book is software supporting "accounting or management processes"
    under LGT art. 29.2.j and art. 201 bis.1 a)–e), and whether the append-only design (FIN-2) is enough;
    (b) whether any FIN output turns a non-compliant invoicing tool plus CoFlow into an invoicing system
    under RD 1007/2023; (c) whether art. 201 bis applies to free open-source distribution; (d) the wording
    of the "not tax advice" disclaimer.
11. **Goals module position** — resolved on 4 October 2026: stage-8 module 2, before "send material"
    (D-031).
12. **Conductivity protocol (REL-4):** after a planned experiment gate (November 2026), should the
    author's protocol move into CoFlow as an open research plugin, and may its codebook be published?
13. **Invoices** — resolved on 4 October 2026: invoices are issued in a certified invoicing program and
    CoFlow registers them (D-026).
14. **Inconsistency findings** — resolved on 4 October 2026: a stage-8 module right after the goals
    module (ALN-2…5, D-029).
15. **External systems' MCP access** — resolved on 4 October 2026: no need before stage 8;
    internet-facing MCP stays a stage-8 module (MCP-5, D-023).
16. **Draft wording in goal formation** — resolved on 4 October 2026: the assistant may offer wording
    clearly marked as a suggestion; adopted sentences are recorded as such (GOL-5, D-028).

Resolved on 4 October 2026: the journal in analysis (D-025; the switch design is proposed), the
research status of alignment and conductivity formulas (D-029), invoices registered from a certified
program with no invoicing or filing in CoFlow (D-026), the modular monolith (D-030) and the position of
the goals module (D-031), inconsistency findings as the module after goals (D-029), suggested wording in
goal formation (D-028), no internet-facing MCP before stage 8 (D-023) and the author's existing desktop
moving to Linux as the production host (D-020). Proposed and awaiting the owner: money from files and entries only, never from
bank connections (D-018); books, taxpayers and country packs (D-027).

## 9. Glossary

| Term | Meaning |
|---|---|
| Owner | The one person an installation belongs to |
| Signal | Anything that informs a decision: a conversation, a message, a calendar event, a note |
| Session | One conversation as a stored record (a call, a chat thread, a recording) |
| Meeting | An intent to meet: participants, plan, link to work; may have sessions attached |
| Commitment | Who owes what to whom by when, with the quote it came from |
| Decision record | A decision with grounds, alternatives and assumptions to monitor |
| Approval card | A proposed change the owner confirms with one action; executed once |
| Outbox | The single path for actions that change the outside world |
| Journal | The owner's private notes: a separate data class, never indexed or exposed through tools, search or work answers; sent to a model only by analysis modules the owner enables (PRV-9) |
| Provenance | Model, prompt version, input hash and input data classes stored with every computed output |
| Centre | What the owner declares about themselves: typed, versioned documents written by the owner (GOL-1) |
| Attainment levels | Five outcome levels (−2…+2) written for a goal before its period starts |
| Book | A money boundary (household, own practice, company); nothing is summed across books by default |
| Taxpayer | A tax id with its own calendar and records; one or more books belong to it |
| Country pack | Versioned tax rules as data, with effective dates and an official source per row |
| Timeline | One chronological view over every layer of stored data |
| Interaction graph G(t) | People (V), the relations between them (E(t)), the state of each (X(t)) and the context (C(t)) at a moment in time |
| Module card | A module's purpose, tables, contracts, events, data flows, quality parameters and acceptance suite |
| Host | The machine that runs the production instance |
| Instance and role | One running CoFlow with its data root; its role is production, staging, dev or drill |
| Device agent | A small program on an owner device that sends data to the host through the ingestion API |
| Access recipe | A documented way for owner devices to reach the host, with who can see the traffic |
| Release image | The signed container image built from one release tag |
