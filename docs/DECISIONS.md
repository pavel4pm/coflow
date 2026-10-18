# Decision log

Newest first. Each entry: context, decision, alternatives, consequences.
Status: **accepted** (the author decided) or **proposed** (waiting for the author's review).

The private v1 is referred to as "v1". Its numbers are aggregates; no personal data is published.

---

## D-054 · Decisions are sliced by direction everywhere they are listed — accepted (17 October 2026); placement proposed

- **Context:** after a first look at v1's new decisions screen the author found it fine as it is ("nothing to
  redo for now") and expects something similar in 2.0 — with one gap: all decisions sat in one list. In the
  author's words, decisions must be linked to directions and it must be possible to filter and sort by them,
  for the screen and for the forecasting research alike. In v1 most decisions already reach a direction through
  their goal, a few are linked directly, and a few have no link at all.
- **Decision:** a decision's direction is resolved, not stored a second time: its own `serves` link to a
  direction first (DEC-11), else the direction of the goal it serves or tests, else of its task, and the source
  is shown; one direct link per decision. Every list of decisions — the waiting list, the view, the bot's list
  and MCP — can be filtered and grouped by it; decisions without one are listed as such and counted in the
  unlinked report (DEC-19); forecasting scores are reported per direction (DEC-10, DEC-24).
- **Alternatives:** a direction field stored on each decision (it duplicates the goal's direction and drifts when
  a goal moves); free tags (no hierarchy, nothing to check against GOL-14); several direct directions per
  decision (a decision then hides in every grouping but one).
- **Consequences:** DEC-24 joins stage 2 with the decision loop in the chat (proposed: R1). The author's verdict
  on the v1 screen is recorded here; its use is measured for one to two weeks before DEC-8's priority is
  revisited. v1 has the same slicing since 17 October 2026. Written on 17 October as D-038 and renumbered when
  the decision-core package took D-038…D-053 the next day.

## D-053 · The public entry is an owner relay that never decrypts, on a separate domain outside the edge platform's DNS — accepted (18 October 2026); the relay recipe details and the opt-in edge-tunnel recipe are proposed

- **Context:**
  - An edge tunnel that terminates TLS lets a third party read every response and token; its account can
    route to local services; and shared edge address ranges are blocked by some regional internet
    providers during sports broadcasts by court order.
  - On a zone served by an edge platform with universal certificates, CAA account and validation-method
    binding (RFC 8657) may not be enforced, so the instance's names need a zone whose DNS provider serves
    its records as configured.
  - A pass-through relay must not terminate TLS for other services, expose SSH to the internet, or be
    managed with a provider token stored on a development machine.
- **Owner's decision (18 October 2026):** the public entry is the owner's own relay on a separate small
  virtual machine in the EU, used for nothing else. It passes TLS through by server name, without
  decrypting, into a WireGuard tunnel that the laptop opens; TLS, OAuth and every check terminate on the
  laptop. The host names live on a separate domain whose DNS is not served by the edge platform, because
  CAA is not enforced there, with DNSSEC on. The domain is bought now and kept closed, with CAA forbidding
  all issuance, until the entry opens.
- **Proposed:**
  - the relay forwards TCP 443 for two neutral host names (MCP and authorization) only; it has no
    TLS-terminating proxy, no port 80 and no SSH from the internet, and a provider-level firewall; its
    provider credential is never stored on a development machine; its configuration has one source and
    is provider-neutral (DEP-12);
  - the domain's DNS provider is neither an edge platform that rewrites CAA nor the relay's provider; the
    registrar lock is set; when MCP-5 opens, CAA pins one certificate authority, the host's ACME account
    and `tls-alpn-01`, with wildcard issuance forbidden; certificate-transparency monitoring covers the
    whole domain;
  - TLS terminates in the separate `edge` container on the host (PRV-13);
  - from stage 2 the relay tunnel is the second remote administration path (DEP-11): WireGuard inside
    WireGuard, the relay forwarding the packets of an owner-device tunnel whose keys it does not hold;
    the relay's own peer reaches only the edge port; no public name exists before stage 8;
  - the client address from the PROXY protocol is used for logs and rate limits, never for authorization;
  - the edge-tunnel recipe (for example Cloudflare Tunnel with Cloudflare Access) stays a documented
    opt-in and is never the default; a mesh-VPN funnel that terminates TLS on the node is an accepted
    fallback if the relay fails.
- **Alternatives:**
  - an edge tunnel by default: a third party decrypts, plus regional blocking; its one gain is a managed
    OAuth server;
  - a relay that terminates TLS: it holds keys, so its compromise is a full interception;
  - host names in a zone at an edge platform that rewrites CAA and is shared with public apps: CAA is not
    enforced, and cookies and the WebAuthn relying party share a site with public apps;
  - a delegated sub-zone at another DNS provider: cheaper, but the parent zone's account can re-delegate
    it, and the site is still shared;
  - a hosted mesh-VPN funnel as the default: beta, provider-owned names only, capped bandwidth, one vendor
    for both paths;
  - a port forward on the home router: exposes the home address and network and fails behind CGNAT.
- **Consequences:** DEP-11, DEP-12, MCP-5 and PRV-4 change; the relay and the DNS provider get
  `DATA_FLOWS.md` rows; DEPLOYMENT §8 gains the owner-relay recipe; D-023 is revisited.

## D-052 · Internet access in two steps: the bot and the VPN now, cloud AI clients later as the first stage-8 module — accepted (18 October 2026); the module's security baseline is proposed

- **Context:** internet access means three different things. The bot needs no inbound port (long
  polling). The owner's devices reach the host over the overlay VPN. Cloud AI clients connect to remote
  MCP servers from their operator's cloud on every client, mobile included, so they need a public
  endpoint. A hosted multi-tenant OAuth client identifier does not identify the owner's account at the AI
  provider, so consent can be phished into another account; text written by third parties, returned into
  a chat that also has send-capable connectors, is an exfiltration path that "read-only" does not close;
  and the client's operator receives every result and holds a refresh token for as long as the grant
  lives.
- **Owner's decision (18 October 2026):** the first step is the bot and the VPN: the phone, a travelling
  laptop and desktop AI clients reach v2 from anywhere, without a public entry. Cloud AI clients in the
  browser and on the phone come later, as a separate module with its own security baseline, first in the
  stage-8 queue: read-only first, with other people's raw text withheld.
- **Proposed:**
  - the module's baseline is MCP-5: a separate `edge` container (PRV-13), OAuth as the MCP authorization
    specification defines it, a pairing window opened from an owner channel, one grant per client
    confirmed in the bot, an absolute grant lifetime of 14 days, quotas and quiet-hour alerts, and
    `untrusted_external` text withheld by default (PRV-14);
  - writes for cloud clients are a separate resource with a separate audience, off by default;
  - before the module opens, interoperability and pairing (including an attempt from a foreign account at
    the AI provider) are tested on a throwaway machine with synthetic data and a throwaway name, never on
    the production host or the production domain;
  - high-risk approvals need a second factor (BOT-11) and security alerts go to two channels (OPS-17), so
    a hijacked messenger session alone cannot pair a client.
- **Alternatives:** read-only cloud access at stage 6 (the whole baseline lands on the switch-over, the
  riskiest moment of the year); keeping the module at its old place in stage 8 (the same security, months
  later); a static token in the connector header (a beta open only to some organisations at the time of
  writing).
- **Consequences:** D-031's stage-8 order changes: internet-facing MCP moves to the front as module 0;
  D-023 is revisited; MCP-5 grows from M to L; PRV-13, PRV-14, BOT-11 and OPS-17 are added.

## D-051 · Trust zones: the core on the home host, hosted apps stay where they run and are pulled read-only, no shared server — accepted (18 October 2026); the connector rules are proposed

- **Context:** the owner also runs apps with external users on a serverless platform (an event-memory
  app and a tasks-from-correspondence app) and a live conversation assistant that must run on the
  machine where the meeting happens (system audio loopback, a USB controller). The owner had considered
  one own server for the whole organisation. One server for the core and all of these would put
  customers' data next to the journal and would mean rewriting the hosted apps away from their platform
  bindings.
- **Owner's decision (18 October 2026):** hosting follows trust zones. CoFlow 2.0 runs on the home GPU
  laptop, with its data and processing at home (D-050); the two hosted apps stay on their platform, and
  the core takes data from them read-only; the live conversation assistant runs on the work desktop.
  There is no single server for the whole organisation.
- **Proposed:**
  - the instance's host runs the instance and nothing else;
  - hosted apps never push into the home network and never hold a credential of the instance;
  - `core` pulls from them outbound with a read-only export token that the app issues for one workspace
    the owner owns (never an operator or service-wide scope); acknowledgement is a separate right with its
    own token; tokens are revocable in the app and rate-limited; the pull is served by cursor; every pull
    has size limits and a schema check;
  - pulls never go through a fallback host name whose TLS terminates on a third machine;
  - pulled items are `untrusted_external` (PRV-14) and become proposals (P-3), never records;
  - apps on the owner's devices use EXT-4 over the private network with per-app tokens; a local app that
    holds an instance token enforces a Host allow-list, a per-launch token and Origin checks, and its
    token covers only what it needs (for a live conversation assistant: briefs of meetings within the
    next 12 hours, no person search);
  - data that the owner processes on behalf of an app's customers is not pulled unless the customer
    agreed to that purpose; backups of hosted apps never restore onto the instance's host; a processing
    agent that serves an app's customers does not run on the instance's host and holds no instance
    credential;
  - every app uses its own model API key, and the instance's key carries a provider-side spend limit
    (PRV-4).
- **Alternatives:** one server for the core and all apps (customer data next to the journal; a rewrite
  of the apps); moving the hosted apps to a rented machine (weeks of rewriting, for a gain that other
  measures already give); push from hosted apps into the home network (an inbound path and a credential
  of the instance stored on a third-party platform).
- **Consequences:** EXT-4 gains the pull-connector clause; PRV-14 is added; `DATA_FLOWS.md` gains one
  `app:<client>` row per connector, naming the controller of every pulled data class; the blocks of D-041
  get their hosting.

## D-050 · Production runs on a dedicated home laptop with a GPU, reachable over the internet, after a 30-day gate — accepted (17 October 2026); the gate accepted (18 October 2026); the laptop profile is proposed

- **Context:** the owner wants the instance reachable over the internet, while all work happens on a
  separate home machine whose GPU is dedicated to this data (local speech-to-text, optionally a local
  model). The machine is a laptop; DEP-14 said "not a laptop", and D-020's owner decision named a desktop.
  v1's home server failed because it was run like a desktop application (start at logon, sleep on lid
  close, no remote administration), not because it was a laptop. A laptop differs in four ways that
  matter: its firmware rarely powers on when AC returns; its battery keeps the host running but not the
  network equipment; firmware and boot-chain updates can stop an unattended disk unlock; and it is
  tempting to take it on a trip. The alternative the owner weighed is an own server on the internet
  holding everything (D-051). The host decision had changed several times since July; a measured gate is
  meant to stop that.
- **Owner's decision (17 October 2026):** (1) access to v2 over the internet is required; (2) all work,
  data and processing stay on a separate home laptop whose GPU is dedicated to this data.
- **Owner's decision (18 October 2026):** before the laptop holds real data it passes a measured gate of at
  least 30 days in the staging role: availability of at least 99 %; drills for a power cut, a network loss
  and 48 hours without connectivity; a 4-hour sustained heat run; battery health of at least 70 %; a
  weekly restore from the off-host backup; a rebuild on another machine within 2 hours. While the owner
  travels, up to 7 days of downtime is acceptable. If the gate fails, another home machine with a GPU
  takes the same image.
- **Proposed:**
  - the laptop is dedicated: no other workloads, no second user, and it does not travel;
  - it runs under the laptop profile of DEP-14, with full-disk encryption required (PRV-11);
  - the GPU image variant comes at stage 2 (DEP-25); platform updates are applied only by an owner
    command, and a travel mode exists (DEP-26);
  - the gate's measurements and drills in detail are DEP-27: availability measured by an off-host monitor
    that does not depend on blocked address ranges, with no failure that needed physical intervention
    while the owner was away; a 20-minute power cut with the host and the network reachable; a longer cut
    ending in a clean shutdown and an unattended power-on by a tested method; a network unplug alerting
    within 30 minutes; a forced kernel panic recovered by the watchdog; the 48-hour outage drill; four
    green weekly off-host restore drills; a rebuild of the first two restore tiers within 2 hours; and,
    beyond the owner's list, one platform update applied at home with the unlock-policy prediction, after
    which the disk unlocked without the recovery key; one hour of sustained load with the lid closed,
    without sleep and with at most 20 % slowdown; the bot, the VPN and the relay path checked from a mobile
    network during a regional blocking window, with no false alarm from the off-host monitor; free disk
    for a year of active recordings below the 80 % warning;
  - the fallback host has firmware power-on after AC loss; a rented server remains a disaster-recovery
    target only (DEP-19), with the explicit "journal at rest with a provider" switch; the machine for the
    yearly rebuild drill with real data is declared in advance (DEP-19).
- **Alternatives:**
  - a rented GPU server holding everything: the journal and third parties' recordings at rest with a
    provider, and a monthly cost of the order of a few hundred euros for the smallest GPU line at the
    time of writing;
  - a rented CPU server with the home GPU as a remote worker: data at rest with a provider and a
    networked speech-to-text worker, against D-024;
  - a rented CPU server without a GPU: the archive takes weeks;
  - one server for every app of the owner: see D-051;
  - no gate, switching over as soon as the functions are ready: faster, and it repeats v1's path.
- **Consequences:** D-020's owner decision changes to the laptop; DEP-3, DEP-14, DEP-15, DEP-18, DEP-19
  and OPS-5 change; PRV-11, DEP-25, DEP-26 and DEP-27 are added; ROADMAP stages 2 and 6 name the laptop and
  the gate; REQUIREMENTS §8 question 7 is updated; the decision adoption of D-039 waits for the gate
  (proposed).

## D-049 · Evidence is append-only and bitemporal; one transaction log holds provenance; as-of is a core query — proposed

- **Context:** in v1 a repeated "still holding" check left no trace, bot writes were labelled as MCP
  writes, and 75 % of "done" marks fell on clean-up days (aggregates), so status dates measured clean-ups,
  not execution.
- **Decision (proposed):**
  - every unit of work writes one transaction-log row (actor, channel, owner-channel flag, approval,
    instance role, code version), stamped by the store layer, never by callers;
  - append-only, set-once and erasable columns are declared per table and enforced by generated triggers;
  - every row that describes an event carries its event time with precision and basis, and imported rows
    keep their original record time;
  - `as_of(T)` answers on the knowledge, instance and occurrence axes;
  - an event time is never defaulted to a record time;
  - readings only propose states, and an owner assessment decides them.
- **Alternatives:** per-table actor and channel columns (duplication, and the v1 mislabel stays possible);
  versions only (a repeated check leaves no row).
- **Consequences:** DEC-13 and NFR-13; the kernel's table registry and transaction log in stage 0A.

## D-048 · Every new commitment, task and meeting is offered its likely decisions at entry; "no decision" is allowed and counted — accepted (18 October 2026); the offer for ledger entries and time spans, and the attachment refusals, are proposed

- **Context:** in v1 a handful of tasks were formally linked to decisions while dozens named a decision
  only in their title, and background link queues were never reviewed.
- **Owner's decision (18 October 2026):** the link to a decision is offered and counted, not required.
  When a task, a commitment or a meeting is created, up to three likely decisions are offered, and "no
  decision" is a valid answer. A report shows four buckets: linked, deliberately without a decision, not
  answered, not offered. A commitment may exist without a decision.
- **Proposed:**
  - the offers are deterministic, and a named label beats a guess; an explicit "no decision" carries a
    reason;
  - every spoke stores the answer, and the hub reports the buckets;
  - the same offer applies to ledger entries and time spans when those modules exist;
  - a commitment cannot attach to a decision whose system of record is still v1, or to an ended decision.
- **Alternatives:** a mandatory link (friction on routine items, and false links); no offer (the links
  stay in titles).
- **Consequences:** P-15; DEC-19; WRK-8, CMT-1 and GOL-14 edited.

## D-047 · Decision kinds instead of parallel entities: a hypothesis is a decision to test, a goal is framed by a decision to pursue, an event is an attendance decision; others' decisions are referenced — proposed

- **Context:** in v1, goals, hypotheses and decision assumptions stored the same measure up to three times.
  Offline events had no home. Decisions of clients recorded while advising became orphaned reminders when
  the engagement ended.
- **Decision (proposed):**
  - the kinds are `choice`, `test`, `pursue` and `attendance`, plus `advisee` and `forecast_container` for
    imported records only;
  - deciders are `self` (always the owner profile, never a name lookup), `joint`, and `other` for those
    imported kinds only;
  - one measure lives in one assumption and is referenced by goals and gates;
  - other people's decisions are facts or external references;
  - imported advisee records are asked about once, through the goal-changed question, when their
    engagement's goal ends.
- **Alternatives:** separate hypothesis and event entities (two parallel monitoring mechanisms); storing
  client decisions natively (a second register of other people's choices).
- **Consequences:** DEC-1 and DEC-4 edited; DEC-21 and DEC-23; WRK-4, GOL-7 and GOL-9 edited (R2).

## D-046 · A validation instance holds the real snapshot; real cases run there and on throw-away copies; selected entries of the project's decision log are native data — proposed

- **Context:** DEP-4 allowed no real data before the staging host (stage 2), so the real snapshot had no
  legal home, while the stage gates require real cases (D-036). The owner wants to use v2 now without a
  second writer.
- **Decision (proposed):**
  - a `validation` role on the owner's machine holds the snapshot as read-only mirrors, with its data root
    outside any repository; it never acts outward; its data reaches production only at the adoption gate,
    by a restore onto a host that passed its gate (DEP-27), where the restored instance is promoted to
    production with decisions only and the host's staging instance is retired;
  - `dev` accepts only snapshots marked synthetic, and `validation` accepts only snapshots that are not;
  - the owner's named cases are scripts that run on a throw-away copy of the validation database, so
    write paths are exercised on real decisions before adoption, and their results gate the stage and the
    adoption; the cases themselves stay in the validation data root, never in any repository;
  - entries the owner selects from the public decision log are imported as drafts whose text the log owns
    and whose monitoring v2 owns; no other native decision is recorded in the validation instance before
    adoption, because until then every real record is written in v1 (D-039);
  - after adoption there is no staging instance: pre-releases are checked in CI and by `coflow drill`
    before the owner approves a production deploy; the kinds v1 still owns (people, sessions, commitments,
    tasks, goals) are imported one way into production as read-only mirrors until stage 6; the real cases
    of stages 3 to 5 run on throw-away drill copies of the production database.
- **Alternatives:** bring the staging host forward (hardware work before code); synthetic data only until
  stage 6 (no real use); write paths only after adoption (the cases could not pass before the gate).
- **Consequences:** DEP-23; DEP-2, DEP-4, OPS-8 and OPS-15 edited; OPS-16; ROADMAP "How a stage runs",
  steps 5 and 6, edited; before the first real snapshot enters the validation instance, the AI coding
  agents' account cannot read a validation data root and the development disk is encrypted (PRV-15).

## D-045 · Decision numbers keep v1's in fixed width, new decisions start at D-1001, forks are Q and commitments F from F-10001 — accepted (18 October 2026); scoped codes and aliases are proposed

- **Context:** the owner uses decision and promise numbers as conversation keys. The identity protocol
  wants a fixed width and one source per issuing space, and v1 keeps issuing numbers during the shadow
  period.
- **Owner's decision (18 October 2026):** decisions from v1 keep their numbers, written in four digits
  (`D907` becomes `D-0907`); new 2.0 decisions are numbered from `D-1001`; `Q` numbers forks (open
  questions); `F` numbers commitments, new ones from `F-10001`. Numbers are permanent.
- **Proposed:**
  - every number v1 issued is registered as taken and every one it deleted as burned; after adoption the
    tap continues after the highest number in use, and ids never change;
  - `Q` takes four digits and `F` five;
  - codes scoped inside a decision take the protocol's form (`D-0042_A-03`); foreign forms are
    issuer-scoped aliases (`V1_D907`); input is tolerant and output canonical.
- **Alternatives:** restart numbering (it breaks the conversation keys and the pilot's references); a
  validation-only prefix renumbered at switch-over (ids change); a shared range (two taps for one space).
- **Consequences:** IDN-2 edited; IDN-9 and IDN-10; the prefix registry is fixed before the first number
  is issued.

## D-044 · Health on two axes, one composite label by a fixed table, the unverifiable share first — proposed

- **Context:** three implementations in the ecosystem evaluate health in three different orders. v1
  masked overdue reviews behind missing data, ignored non-critical violations while its waiting list
  included them, and showed "watch" for decisions that had simply not been checked (aggregate: 15 of 23
  active decisions).
- **Decision (proposed; not yet put to the owner):**
  - a ground axis (from the critical assumptions, or all when none is critical) and a timeliness axis
    (review, checks, silence);
  - the composite order is the owner's flag, then review required, stale, insufficient data, watch, on
    track, and awaiting checks;
  - an overdue check or a stale "holding" is never on track, and a non-critical violation is a "watch"
    reason that also waits;
  - the unverifiable share is always the first line;
  - named vectors and an independent oracle are the acceptance test.
- **Alternatives:** insufficient data first (it hides a known violation behind fog); v1's order (it masks
  overdue reviews).
- **Consequences:** DEC-3 edited; the shadow comparison carries the expected-difference rules SR-1 to
  SR-10.

## D-043 · The basis is sealed; revise is a new edition of the same decision; outcomes carry a basis and closing carries a learning — accepted (18 October 2026) for the seal and the editions; outcome bases and the learning at closing are proposed

- **Context:** DEC-7 said "revise: the decision itself is rewritten, the record keeps its history". The
  forecast pilot and the team-tool line showed that what was believed before the result is the one thing
  that cannot be rebuilt later. v1 closed most decisions without a learning, and could not tell a measured
  outcome from a reported one.
- **Owner's decision (18 October 2026):** a revision keeps the decision's number and creates a new sealed
  edition. The basis is sealed by a hash when the decision is activated. A revision needs a reason: a new
  fact, a stated change of mind, or the correction of a mistake. A genuinely different decision gets a new
  number and a link saying that it replaces the old one (supersede).
- **Proposed:**
  - the seal uses salted per-item hashes over a float-free canonical JSON that is byte-identical to the
    pilot's for its records, so an erasure keeps the seal verifiable;
  - adjust (the terms change, the decision stands) cuts no edition;
  - imported records are sealed at import, and a changed source cuts a `source_changed` edition;
  - outcome resolutions are `resolved`, `reported` or `not_confirmed`, and only `resolved` shows green;
    outcome claims from anyone are evidence;
  - closing requires a learning, and later decisions of the same kind, subject or assumption class are
    shown it.
- **Alternatives:** a new record per revision (stable ids are the owner's conversation keys); free-text
  outcome and learning (v1's state); adjust as an edition too (it inflates editions and mixes execution
  with belief).
- **Consequences:** P-16; DEC-12, DEC-13 and DEC-15; DEC-3 and DEC-7 edited.

## D-042 · Links to a decision are stored by the module whose workflow forces them; the hub reads its spokes through ports — proposed

- **Context:** making the decision the base needs links from many modules. It needs them without import
  cycles, without a generic link graph (dropped in REQUIREMENTS §7) and without two units of work per
  entry. The DEC→WRK edge in the module map was a cycle.
- **Decision (proposed):**
  - a closed registry of link kinds, each stored by the module whose workflow fills it, at a named
    enforcement point;
  - DEC stores decision↔decision links, serves, tests, about, informed by, origin and evidence; spokes
    store their own `decision_ref` and entry-time answer;
  - DEC reads spokes only through `DecisionAttachmentProbe` (implemented by every spoke), and spokes and
    same-tier modules reach DEC through `DecisionDirectory`; evidence is checked through
    `EvidenceResolver`;
  - DEC stays in tier 2 and loses its WRK dependency; ALN joins the import contract as tier 8.
- **Alternatives:** every decision link in DEC (two units of work per entry, silent partial failures); a
  kernel link ledger (the generic graph again).
- **Consequences:** DEC-11 and DEC-19; WRK-3, WRK-8 and MTG-1 edited; three ports in ARCHITECTURE §5.1;
  an import-linter test that DEC imports nothing above its tier.

## D-041 · The ecosystem stays as separate blocks — accepted (17 October 2026); independence from every block, remote access and the contracts are proposed

- **Context:** the owner runs a real-time online conversation agent, an offline-event app for events whose
  purpose is known upfront, plain uploads of communications, and a tool for external work with a team.
  Hosting was decided in parallel: internet access is required, and data and processing should live on a
  home GPU laptop.
- **Decision:** the owner decided that these stay separate blocks, as they are. The hosting choice itself
  is recorded in D-050 to D-053.
- **Alternatives:** absorbing the apps into CoFlow (it mixes customer data with the journal and couples
  release cycles); a private network only (cloud clients cannot reach it).
- **Consequences (proposed):**
  - CoFlow works without any of the blocks: this restates the independence rule of the owner's earlier
    product notes (29 September 2026) and waits for the owner to confirm it for v2 (EXT-6);
  - remote access is not precluded: MCP over the internet with OAuth, and satellites calling an ingestion
    API (the owner requires internet access, D-050);
  - apps are sensors around decisions: they read projections and send evidence and proposals, never
    state (EXT-5, EXT-6);
  - all decision behaviour sits behind the module `api`, with thin MCP, CLI and INT adapters;
  - every write carries an actor, a channel and an idempotency key from day one.

## D-040 · Today's build order: a minimal kernel and a vertical slice of the decision core — accepted (17 October 2026); the increments are proposed

- **Context:** the decision core needs only part of stage 0 to run on the owner's machine, and the owner
  wants to use it on real data as early as possible.
- **Decision:** the owner decided to build now a minimal stage-0 kernel (storage with migrations, one
  numbering tap, events, data classes, CI on Windows and Linux, uv and ruff) and a vertical slice of the
  decision core (decision, fork, options, assumptions with check dates, facts, reviews, commitments,
  outcome, learning; CLI and MCP for decisions; import of v1 decisions). Docker, CD and backups come in
  the next part of stage 0.
- **Alternatives:** the full stage 0 first (the decision core waits for the delivery pipeline); the
  decision core without the kernel (no numbering tap, no one-writer guarantee).
- **Consequences (proposed):** events are written in the same unit of work as the change, and the
  kernel includes the configuration minimum (the owner profile and settings). Stage 0 splits into 0A and
  0B. 0A is built in three increments, each a gate:
  a read-only shadow first, then the native loop, then commitments, history and metrics. The slice is
  model-free and offline. DEC-6 moves to stage 0A, and DEC-5, DEC-7 and DEC-9 move to stage 2 with the
  bot; this replaces the stage placement proposed in D-037.

## D-039 · Shadow first, then switch-over; never two writers; v1 stays the decision system of record until the forecast pilot reports — accepted (17 October 2026); reading the shadow during the pilot accepted (18 October 2026); the mechanics are proposed

- **Context:** two writers of the same data broke v1 before. A pilot of weekly sealed forecasts runs on
  v1's decision data until 30 November 2026 and needs v1 to stay the decision system of record until its
  report on 1 December 2026.
- **Decision:** the owner decided that v2 runs in shadow on one-way snapshots of the owner's v1 decisions
  (v1 → v2 only, never back) and computes the waiting list, check dates and health itself, so the owner
  can compare. When the owner's 3–5 real cases pass, decisions move to v2 for good, and v1's decision
  module becomes read-only. There are never two writers for the same data. Because of the forecast pilot,
  the switch-over gate is not before 1 December 2026 unless the owner changes that; until then every real
  record is written in v1.
- **Owner's decision (18 October 2026):** reading the shadow is part of the pilot's record: the pilot's
  change journal records that the v2 shadow started on 18 October 2026, the owner reads the shadow waiting
  list daily, and every intervention it causes is recorded and taken into account in the pilot's analysis.
- **Alternatives:** v2 live with mirroring into v1 (two writers); waiting until the full switch-over at
  stage 6 (no real use for months); a weekly shadow report only until 30 November (less influence on the
  pilot, but no daily use of v2 for six weeks).
- **Consequences (proposed):**
  - imported decisions are read-only mirrors that keep their numbers;
  - a daily idempotent import with a classified shadow report (OPS-16);
  - real cases run on throw-away copies (D-046);
  - an adoption gate enforced in code (date, cases, 14 clean runs, backups, a daily asking channel, the
    target host);
  - the daily asking channel is the stage-2 chat loop; a pull-only adoption (CLI and MCP only) needs a
    separate owner decision;
  - the target host is the production host after its gate (D-050, DEP-27), so adopted decisions never
    land on a machine that has not passed it: at adoption the host's staging instance is retired and the
    restored validation instance becomes production, and the kinds v1 still owns are mirrored into it one
    way until stage 6 (D-046);
  - the v2 MCP tools use their own namespace, so the pilot's v1 tool stays its only write path.

## D-038 · The decision is the base entity of CoFlow 2.0, and development starts on 17 October 2026 — accepted (17 October 2026); the stage placement is proposed

- **Context:** the decision layer is the one the private v1 proved, yet in the plan it was built at stage 3,
  behind the memory core and the bot, and the goal was the only cross-cutting anchor. A study of v1's
  decision records (aggregates: 25 decisions, 91 assumptions, none ever checked, 6 reviews) found the
  record filled at creation and its loop open. D-004 tied the start of code to the end of v1's acceptance
  period, and the acceptance record had no case marked.
- **Decision:** the owner decided that the decision is the base entity of CoFlow 2.0: signals,
  commitments, tasks, meetings, events, goals and learning attach to it, so the owner can test and use v2
  on themselves systematically. Development starts on 17 October 2026. This overrides D-004's "code after
  the v1 acceptance period".
- **Alternatives:** keep the goal as the spine (cheaper now, but the decision stays a leaf and its loop
  stays untested until 2027); wait for the acceptance period to end (it had produced no marks).
- **Consequences (proposed):** the decision core moves to a new stage 0A, built in three gated
  increments; today's stage 0 splits into 0A and 0B; D-042 to D-049 propose the shape of the core, and
  D-050 to D-053 record where it runs and how it is reached; the roadmap's timeline, the README and the
  build-in-public calendar move "stage 0 starts" to 17 October 2026; the v1 acceptance period continues
  in parallel and is no longer a condition for code.

## D-037 · Close the decision loop: check dates, one question in the chat, every write behind approval — accepted (17 October 2026); the priorities of DEC-6…DEC-10 are proposed

- **Context:** a retrospective study on the private v1 (17 October 2026) found the decision record filled
  but its loop open: 0 of 89 assumptions had ever been checked, none of the 6 decisions past their review
  date had been reviewed, and a change agreed in a conversation (an agreement extended by a month on new
  terms) had reached the record only as a stale date. The v1 decision screens were barely opened. The same
  study had a memory-free model guess the author's choice at a recorded fork in 13 of 15 cases, but none of
  the decisions that actually came up: the agenda follows new outside facts, not stated intentions.
- **Decision:** the author decided to build the loop in v1 now, as the one exception to its feature freeze
  (D-006) — check dates and the "waiting" list, a decisions screen, and review questions in the chat whose
  answers are written only after approval — and to carry the same part into these requirements: computed
  check dates and one "waiting" list (DEC-6); a review asked in the chat, one question at a time, with every
  write behind one approval card (DEC-7); a context change recorded as fact, adjustment and next task on one
  card (DEC-9); a decisions view with the reason each decision waits (DEC-8); weekly sealed forecasts as
  research (DEC-10). In v1 the bot may change decisions from the chat, but only through approval — the rule
  of P-4 and BOT-4. The author also started a pilot of weekly sealed forecasts on v1's data, run outside
  v1's code until 30 November 2026.
- **Alternatives:** keep the loop for 2.0 alone (the freeze stays clean, but the core claim stays untested
  until 2027 and the record keeps drifting); let the bot set assumption states straight from a free-text
  answer (faster, but a model would decide what the author meant); a bigger web UI first (v1's usage data
  says the work does not happen in its screens).
- **Consequences (placement proposed):** DEC-6, DEC-7 and DEC-9 join stage 3 next to DEC-5 (proposed: R1,
  stage 3); DEC-8 waits behind UI-2 and the measured use of v1's new screen (proposed: Later); DEC-10 is a
  research module with a pre-registered protocol (proposed: Later, research, D-029). The v1 implementation —
  a scenario file, tests and a process document — is the reference for the 2.0 scenario (BOT-9). The pilot's
  result goes to the author, who decides whether DEC-10 moves up.
- **Placement revised (proposed, 18 October 2026):** DEC-6 moves to stage 0A, and DEC-5, DEC-7 and DEC-9
  move to stage 2 with the bot (D-040); DEC-8 and DEC-10 stay Later.

## D-036 · A thin slice of the centre in R1, real history from stage 1, and real cases as the stage gate — accepted (7 October 2026)

- **Context:** the decision layer is the one v1 proved — 17 decision records with 102 facts and assumptions
  in 30 days — while its strategy and manifest screens were used zero times in the same period. In the plan
  as written, the centre, the goal control and the inconsistency findings all sit at stage 8, in 2027. That
  leaves the project's own claim — that the system makes its owner's decisions more conscious — untested
  for a year, and it leaves every stage before the switch-over tested on synthetic fixtures alone.
- **Decision (three changes, taken together):**
  1. A thin slice of the centre enters R1: the owner's existing documents are imported, kept and versioned,
     and decisions and directions can cite them (GOL-13); one computed check reports what carries no link to
     a goal or a direction (GOL-14); the morning surfacing of decisions that need the owner moves from R2 to
     R1 (DEC-5). The formation protocols, the goal cards and the full control stay at stage 8.
  2. From stage 1, a one-way snapshot of the system the owner runs today is imported into a dev instance,
     read-only toward the source, so every stage is exercised on real history (OPS-15). The documented
     format and the real switch-over stay at stage 6.
  3. Before each stage the owner names 3–5 real cases from their own last 30 days; they become part of that
     stage's exit criteria and must pass on the snapshot.
- **Alternatives:** keep the centre entirely at stage 8 (the core claim stays unmeasured until 2027); build
  the goals module early and in full (expensive, and built on the one part of v1 that proved zero use);
  validate on synthetic fixtures until stage 6 (cheap, but the gap between a fixture and real history is
  exactly where v1's defects lived).
- **Consequences:** GOL-13, GOL-14, OPS-15 and DEC-5 enter stages 1 and 3; the R1 target absorbs a few days
  inside stages 3 and 5 rather than a new stage; GOL-14's usage signal becomes evidence for or against the
  stage-8 goals module — if the owner does not open the list, that is a finding, not a failure, and the
  module is re-scoped before it is built.
- **Extended (proposed, 18 October 2026):** the snapshot and the named cases live in a validation
  instance, and the cases run on throw-away copies of it (D-046, OPS-16).

## D-035 · uv for dependencies and environments, ruff for linting and formatting — accepted (6 October 2026)

- **Context:** v1 had no linter at all and its environment was a `requirements.txt` with no lock, so the
  machine, the server and the tests never resolved to provably the same versions. Stage 0 already called
  for a test runner, a linter and CI on Windows and Linux without naming the tools, and naming them before
  the first line of code is cheaper than migrating later. A contributor's first interaction with the
  project is the setup, so it has to be two commands. The suggestion to adopt both from the first day
  came from outside the project, from a reader of the launch episode.
- **Decision:** `uv` is the package and environment manager — dependencies in `pyproject.toml`, `uv.lock`
  committed, `uv sync --frozen` the single install path for development, CI and the image. `ruff` is the
  linter and formatter, configured in the same `pyproject.toml`, with `ruff check` and
  `ruff format --check` as required CI checks (DEP-22).
- **Alternatives:** pip with `requirements.txt` and pip-tools (what v1 did; slower, and the lock is a
  second tool); Poetry or PDM (another resolver and lock format, slower installs); flake8 with black and
  isort instead of ruff (three tools and their plugins where one does the work).
- **Consequences:** DEP-22 and stage 0; the Dockerfile installs from the lock (DEP-1); CONTRIBUTING gives
  the two setup commands. Both tools come from one young vendor, which is the risk taken knowingly: the
  configuration is portable — ruff maps back to flake8 and black, and uv back to pip with a lock file —
  so the exit stays cheap.

## D-034 · The bot's behaviour lives in scenario files, and a gap becomes a scenario change approved in the chat — proposed (relayed as the author's wish of 5 October 2026)

- **Context:** in v1 the bot's behaviour lived in prompts and tool descriptions. Asked to create a meeting
  from a forwarded conversation, it asked for the link to work twice, asked whose email it was on every
  message, showed a raw provider error about an exhausted balance, and ended with "people can only be
  created in the interface" — no meeting. Each of those is a missing or unwritten scenario, and nothing
  in the system turned the gap into work.
- **Proposed decision (relayed from the author on 5 October 2026; it becomes accepted when the author
  confirms it here):** the rules for handling a request type live in owner-readable scenario files with
  tests (BOT-9); the bot never answers "I can't" — it names the gap and proposes a scenario change the
  owner approves in the chat, which becomes a scenario version plus a development task (LRN-7).
- **Alternatives:** behaviour in prompts only (v1's answer: it drifts and nobody can read it); a
  rules engine the owner edits directly (a second language to learn); collecting gaps silently for the
  maintainer (the owner stays blocked in the moment).
- **Consequences:** BOT-9, BOT-10, LRN-7, MTG-17 and OPS-14; scenario files are part of the repository and
  of each module's acceptance suite (NFR-10); a scenario change proposed by the machine is a proposal
  until the owner approves it (P-3).

## D-033 · The owner picks the model tier per function, with the monthly cost in front of them — accepted (5 October 2026)

- **Context:** v1 ran every model-backed function on one small tier. Its meeting outcomes were weak for
  two reasons at once — a pipeline that summarised the transcript away and hid truncation (OPS-12, MTG-12,
  MTG-13) and a tier too small for the job — while a manual pass on a large tier, with the full transcript
  and context, produced an outcome the author could act on. The other half of the choice is the bill: the
  difference between tiers is the owner's monthly cost, and v1 measured that cost only after the fact.
- **Decision:** the
  tier is the owner's choice per function group, never the machine's, and the choice is offered with the
  expected monthly cost of each tier computed from the owner's own volumes, next to the measured quality of
  that tier on the evaluation set for that function (OPS-11).
- **Alternatives:** one tier everywhere (v1's answer: cheap, and wrong where quality decides); the machine
  choosing per call (an opaque bill and no budget the owner can hold); choosing on quality alone (the bill
  is the owner's, not the machine's).
- **Consequences:** OPS-11; the cost ledger (OPS-7) and the evaluation harness (OPS-8) report per tier;
  the analysis mode of a meeting outcome runs on the tier chosen for it (MTG-15); private evaluation sets
  measure recall per tier before a change ships (OPS-13); NFR-3's "≤ $1 per active day" is a target for
  the default tiers, not a cap on the owner's choice.

## D-032 · Building in public: the machine drives, the author decides — accepted (4 Oct 2026); the rubric name and automatic merges are proposed

- **Context:** with CoFlow 2.0 developed in the open (D-001), the open question was who does what, at what
  pace, and where the author stays in the loop. v1 was built without any public record, and its decisions
  survive only in chat logs.
- **Decision (accepted):** the machine drives and the author decides. Coding agents follow the roadmap
  week by week — they build, test, release and draft the episodes; the author tests the result, says what
  using it was like, answers the decisions marked "proposed", approves deploys that touch real data,
  approves every publication, and publishes. A main episode every Tuesday (a post, and a video in the
  weeks that allow one) and a short lesson post on Thursdays — at most two touches a week — with the episode calendar and the review gate
  on 10 November 2026 as recorded in [BUILD_IN_PUBLIC.md](BUILD_IN_PUBLIC.md). Episode 0.1 published on
  6 October 2026; the canonical text of every episode goes into [DEVLOG.md](../DEVLOG.md).
- **Changed 6 October 2026 (accepted):** the main episode moves from Monday to Tuesday, the day the
  series actually launched, and a video is part of an episode only in the weeks that allow one — episode
  0.1 went out as a post alone. The review gate moves with it, to 10 November 2026.
- **Changed 15 October 2026 (accepted):** the Thursday lesson post becomes a Friday lesson video of
  4–6 minutes on how one thing is made, after the author found the format cheap to produce — with a
  cost guard: a Friday video that would take more than about 45 minutes end to end does not ship that
  week. The series also gets its description: everything the author spent years putting into other
  people's companies, now built for themselves and shown as it goes.
- **Proposed:** the rubric's working name ("Decision system at work"); merging code automatically once CI
  and the independent review pass, so the author is never the bottleneck of the build.
- **Proposed (18 October 2026):** automatic merges never touch security-sensitive paths (edge and
  authorization, the MCP response layer, data-class policy, egress, the updater, secrets handling,
  Compose and CI workflows); those need a review by a human code owner (DEP-8). An agent that reads
  untrusted issue text holds no token with write access.
- **Alternatives:** publishing only finished releases (no evidence of how decisions were made, which is
  the point of the series); the author writing the episodes (the time is not there); no public record at
  all (v1's outcome).
- **Consequences:** [BUILD_IN_PUBLIC.md](BUILD_IN_PUBLIC.md) holds the cycle, the calendar and the
  publication rules; the scheduled weekly driver is set up when stage 0 starts; the dates shift with the
  v1 acceptance period and are targets, not promises.

## D-031 · Stage-8 order and the weekly episode — accepted (4 Oct 2026); the money split is proposed

- **Context:** the author confirmed the order of the modules after the switch-over, at the pace available,
  with a weekly public episode on what was done, tested and worked through. The same day the author moved
  the alignment and conductivity formulas to research (D-029) and asked for a separate goals module
  (D-028).
- **Decision (accepted):** the relative order of the remaining modules — money, send material,
  negotiation, the whole archive, internet-facing MCP, statement import, week plan and the rest; research
  afterwards; one episode per week with per-module acceptance results.
- **Accepted later the same day:** the centre and goals module at position 2, before "send material",
  followed directly by the inconsistency-findings module (2b, D-029).
- **Changed 18 October 2026 (accepted):** internet-facing MCP for cloud clients moves to the front of
  stage 8 as module 0, read-only first (D-052); the relative order of the other modules is unchanged.
- **Proposed:** money split into a core module and a country-pack module.
- **Consequences:** ROADMAP stage 8; REQUIREMENTS §8 questions 11 and 14.

## D-030 · A modular monolith with contracts, not network microservices — accepted (4 Oct 2026)

- **Context:** the author proposed a microservice organisation: architecture, module structure, relations
  and exchanged data designed up front, with quality and acceptance parameters per module. One SQLite
  writer (D-010) and one numbering tap (IDN-1) cannot be split across services, and there is one
  maintainer.
- **Decision:** the microservice organisation without the microservice deployment. Bounded modules own
  their tables, expose `api` queries and commands and emit events that carry ids and the names of changed
  fields, never values; all modules run in the one writing process; separate processes exist only for
  stateless workers without database access; plugins never open the database. Every module has a card
  with quality parameters and an acceptance suite that runs in isolation; import rules and table
  ownership are checked in CI (P-14, NFR-10, [ARCHITECTURE.md](ARCHITECTURE.md),
  [MODULES.md](MODULES.md)).
- **Alternatives:** network microservices with their own databases (distributed transactions and
  numbering, many more moving parts for one person to operate); an unstructured monolith (no per-module
  quality gates).
- **Consequences:** the module map and card template are stage-0 deliverables; a module can be extracted
  along its contract later if a real need appears.

## D-029 · Formulas are research; inconsistency findings are a module after goals — accepted (4 Oct 2026)

- **Context:** the author: the formulas of alignment and conductivity must be treated very carefully; they
  are a research model on top of a well-built data structure, for research and self-control, and not a
  priority.
- **Decision (accepted, 4 Oct 2026):** alignment and conductivity formulas, scores and predictions
  (REL-1…5, any alignment score, TML-3) are research, not a priority: Later, after the stage-8 modules,
  each specified and pre-registered when started. The core keeps the data they need from R1 (REL-6). The
  deterministic, near-term part of self-control lives in the goals module (GOL-8, LRN-6).
- **Decision (accepted later the same day):** the evidence-based inconsistency findings between what the
  owner thinks, says and does (ALN-2…5) are a stage-8 module right after the goals module (module 2b),
  built under D-017's evidence rules; formulas and scores stay research.
- **Consequences:** D-017 stays as the method for this research; the research table in ROADMAP is
  indicative.

## D-028 · A centre and goals module, authored by the owner — accepted (4 Oct 2026) as a module; the method is proposed except where marked

- **Context:** the author wants the system to help a person formulate their goals — manifest, goals,
  directions, quality criteria, a vision of their future life — and to control that they act in line with
  them. Many owners, like the author, may already have such documents.
- **Decision:** a GOL domain (R2): import existing documents unchanged; formation sessions with versioned
  protocols; the owner writes every sentence — approval only through a card with a diff in an
  owner-typed channel, checked by a provenance test; rule objects as typed fields and exact quotes; a
  deterministic weekly control with "can't judge" where coverage is low; three verdicts per goal (output,
  outcome, path); review cadences where the goal choice is reopened only in deliberation slots; the
  module measures its own usefulness. R1 adds only the data hooks (WRK-1, WRK-8).
- **Owner's decision (4 Oct 2026):** the assistant may offer draft wording, clearly marked as a
  suggestion; sentences the owner adopts are recorded as "adopted from suggestion" (GOL-5).
- **Alternatives:** templates only (no help with formation); an assistant that drafts the goals (the goals
  stop being the owner's); an OKR dashboard (weak evidence, conflicts with chat-first).
- **Consequences:** ALN-1 became GOL-1; LRN-6 and the goal part of RHY-4 depend on this module.

## D-027 · Books per contour, taxpayers, and country packs as versioned data — proposed

- **Context:** an owner may run a household, an own practice and a company whose money must never mix. A
  household and a sole-trader practice share one tax id; a company subject to corporate tax is its own
  taxpayer. Entities taxed under attribution of income and joint returns of a family unit are
  pack-defined groupings that the income-tax estimate can span; until the pack supports them, such
  estimates are marked "incomplete". Tax rules, rates and calendars change every year.
- **Decision:** a book key on every money row; nothing summed across books by default, and nothing across
  currencies without a stated rate. Money within one taxpayer moves as paired transfers; money between
  taxpayers (the owner's practice and the owner's company) is income in one book and expense in the
  other, except dividends, which are income for the recipient and a distribution of profit (not an
  expense) for the company; all such flows carry a related-party flag. Mixed-use accounts are shared only between books of the same
  taxpayer. Tax figures are computed per taxpayer from all of that taxpayer's books. A
  jurisdiction-neutral core with country packs as data: effective dates and an official source per row,
  a quarterly rules-watch, "unverified" marking. Spain is the reference pack, shipped per tax year as a
  separate package (FIN-6, FIN-7, FIN-10, FIN-11, FIN-13, FIN-18).
- **Alternatives:** hard-coded Spanish rules (a code release for every rule change; excludes other
  countries); one ledger with tags per contour (mixing becomes untestable).
- **Consequences:** each tax year needs a pack release with golden tests — a natural episode.

## D-026 · Money: CoFlow plans and records; it never issues invoices or files returns — accepted (4 Oct 2026)

- **Context:** the author wants all money flows, taxes, invoices and documents in one system, so that
  reporting and tax periods are in order and can be planned.

  As of 4 October 2026, summarised by a non-lawyer — this is not legal or tax advice: Spain's rules for
  invoicing software (LGT art. 29.2.j and 201 bis, [Ley 58/2003](https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186);
  [RD 1007/2023](https://www.boe.es/eli/es/rd/2023/12/05/1007);
  [Orden HAC/1177/2024](https://www.boe.es/eli/es/o/2024/10/17/hac1177), "VERI*FACTU") bind producers
  and distributors of invoicing systems (adapted products due since 29 July 2025; fines of EUR 150,000
  per year and system type, EUR 1,000 per uncertified copy sold) and their users (EUR 50,000 per year for
  holding a non-compliant system). Users must comply from 1 January 2027 if they pay corporate tax and
  from 1 July 2027 otherwise, unless they are in the SII, domiciled in the Basque Country or Navarra, or
  invoice only by hand (RDL 15/2025, BOE of 3 December 2025, convalidated 11 December 2025
  ([BOE-A-2025-25695](https://www.boe.es/buscar/doc.php?id=BOE-A-2025-25695)) and being processed as a
  bill, so still open to amendment).

  Per the tax agency's FAQ
  ([index](https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/preguntas-frecuentes.html),
  [concepts](https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/preguntas-frecuentes/cuestiones-generales-conceptos-definiciones.html),
  [scope](https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu/preguntas-frecuentes/cuestiones-generales-ambitos-aplicacion.html)),
  an invoicing system is any hardware and software used to issue invoices that takes in, keeps and
  processes invoicing data. The processing counts even when another system does it, if that system has
  access to the data, for example to produce VAT or income-tax register books, accounting, or any other
  result used for tax compliance. Word processors and spreadsheets used only to enter, issue, print and
  keep invoices (plain lists with totals included) are outside the rules; once they generate the register
  books, they are inside. CoFlow's design keeps away from that case; whether it succeeds is the question
  for the legal opinion below.
- **Owner's decision:** invoices are issued in a certified invoicing program; CoFlow registers them.
- **Decision:** CoFlow keeps books, an append-only ledger, an invoice register, a document archive, a tax
  calendar, labelled reserve estimates and exports for the advisor. Invoices come from a compliant
  invoicing tool through read-only adapters, or are recorded after the fact; a record without a compliant
  source feeds only plain working lists with totals — never per-form figures, a register-book layout or a
  box mapping. CoFlow never issues invoices, assigns invoice numbers, files returns, handles tax
  certificates or keeps statutory company accounts (FIN-9). Every tax figure is labelled "estimate, not
  tax advice" with its rule version, and tax figures never go to a model. GPL money tools are reached
  only through files or command-line subprocesses. This is a conservative project rule, not a legal
  opinion on GPL boundaries.
- **Alternatives:** an invoicing module of its own (likely producer obligations and liability for maintainers,
  users and every fork); preparing and submitting returns (certificates, liability, duplicates the advisor's work);
  another open-source ledger as the master (no invoices, VAT or Spanish statement formats).
- **Consequences:** a short legal opinion before the money module is published, which also tests LGT
  art. 29.2.j and 201 bis (REQUIREMENTS §8 question 10). Owners who issue invoices should check with
  their advisor whether their invoicing software has to meet these rules and from which date. Mandatory
  structured business e-invoicing in Spain (Ley 18/2022;
  [Real Decreto 238/2026](https://www.boe.es/buscar/act.php?id=BOE-A-2026-7295)) applies in phases by
  turnover (above or below EUR 8M), counted from its technical ministerial order, and was not yet
  applicable at the time of writing; the pack tracks the dates through the rules-watch (FIN-18). CoFlow
  gives no legal or tax advice.

## D-025 · The journal may reach a model — accepted (4 Oct 2026); the switch design is proposed

- **Context:** v0.3 said the journal never goes to a model and would be read only by a local model. The
  author allows external models: the journal is not secret to them, people discuss personal matters with
  chat assistants anyway, and the purpose is to find their own mistakes and inconsistencies. Anyone who
  wants local-only can extend the system.
- **Decision (accepted):** the journal stays a separate data class, routed only by explicit markers, never
  indexed and never exposed through MCP, search, dossiers, plans or work answers. Journal text may go to
  the configured model provider (or to a local model endpoint if the owner configured one) for analysis;
  anything derived from journal input stays journal class; calls are logged by hash; prompts with journal
  text are not retained. No local-model-only mode is built (PRV-9).
- **Proposed:** the switch is per installation and per analysis module; `coflow init` asks with no
  preselected answer and records the choice; single entries can be sealed; the project's advice for new
  installations is "off", because other installers and the people named in their journals did not choose
  it.
- **Alternatives:** keep the ban with a local model only (the author does not want it); release entry by
  entry (unnecessary friction for the author); switched on for every installation (other installers and
  the people named in their journals did not choose it).
- **Consequences:** P-2, PRV-1, PRV-2, PRV-3, PRV-9, ALN-4, BOT-3, BOT-7, TML-1, LRN-6 and NFR-6 changed;
  canaries run under both settings.

## D-024 · A Compose stack with one writer and a stateless speech-to-text worker; desktop capture through device agents — proposed

- **Context:** v1 ran about nine writing processes on one SQLite file, and an hour-long recording ran out
  of memory; in a shared container, a transcription out-of-memory would take the bot down. Recorders,
  exports and window activity are produced on the desktop.
- **Decision:** `core` is the only database writer; `stt` has no database access, no network shared with
  the core's API and its own limits; optional profiles add backups and a local model. Recordings reach the
  host through an encrypted folder sync in R1; from stage 6 device agents push through an authenticated,
  resumable ingestion API and never open the database (DEP-6, DEP-16, DEP-17).
- **Alternatives:** one all-in-one container (an out-of-memory kill takes the bot down); one container per
  service on a shared volume (many writers again); Kubernetes or Swarm (far too heavy; rolling updates
  conflict with a single writer).
- **Extended (proposed, 18 October 2026):** a separate `edge` container without database access serves the
  internet-facing listener (PRV-13), and `stt` may reserve the GPU (DEP-25).

## D-023 · Private-network access by default; owner-device MCP in R1, internet-facing MCP in R2 — proposed

- **Context:** the owner's AI clients run on the dev machine and the phone, while CoFlow runs on another
  host. Cloud connectors need a public endpoint. An edge tunnel that terminates TLS sees the traffic, and
  shared edge address ranges are periodically blocked by internet providers in some regions.
- **Decision:** the R1 default recipe is an overlay VPN plus SSH; MCP reaches owner devices through an SSH
  bridge with a forced-command key or over the private network, with scoped per-client tokens, Host and
  Origin checks (MCP-1, DEP-11, DEP-12). Internet-facing MCP with OAuth stays R2, on a separate listener
  that exposes only MCP and OAuth paths, with TLS terminating on the owner's host by default (MCP-5).
- **Alternatives:** an edge tunnel as the default (a third party decrypts; regional blocking); all of
  MCP-5 in R1 (OAuth work before any user needs it); loopback only (unusable when CoFlow runs on another
  machine).
- **Owner's confirmation (4 Oct 2026):** external systems need no MCP access before stage 8.
- **Revisited 18 October 2026 (accepted):** internet-facing MCP for cloud clients is the first stage-8
  module, read-only first (D-052), reached through the owner's relay on a separate domain, with TLS
  terminating on the owner's host (D-053). Proposed: an edge tunnel stays an opt-in recipe.

## D-022 · Instance roles and one production writer — proposed

- **Context:** dev, drills and production will exist at the same time on different machines. File locks do
  not cross machines, two pollers on one bot token conflict, and v1's two writing copies collided on 17
  numbers. A lease stored inside each copy of the database cannot fence another host.
- **Decision:** every instance has an id, a role, a volume id and a host id; only production executes
  external actions, polls the owner's bot and uses production tokens; a copy starts as non-production;
  promote requires retiring the previous production (or declaring it lost) and re-issuing runtime
  credentials, so a returning old host cannot act; a Telegram 409, a revoked token or an older epoch puts
  an instance into fenced mode. Data flows one way: production → backup → non-production (DEP-2, DEP-3).
- **Alternatives:** trust the owner to remember which copy is live (failed in v1); two-way sync between
  dev and production (recreates the collision); a shared database over the network (breaks WAL).
- **Extended (proposed, 18 October 2026):** a fifth role, `validation`, on the owner's machine holds the
  real snapshot as read-only mirrors and never acts outward (D-046, DEP-23).

## D-021 · Pull-based, signed releases; no self-hosted runner on the public repository — proposed

- **Context:** the repository is public and the production host is private and holds the journal.
  GitHub advises against self-hosted runners on public repositories, because code from fork pull requests
  can reach them ([GitHub: secure use reference](https://docs.github.com/en/actions/reference/security/secure-use)). Generic auto-updaters know nothing about snapshots, migrations, the outbox or the
  one-poller rule of the bot.
- **Decision:** CI runs on GitHub-hosted runners only and builds one image per release tag, pushed by
  digest with a keyless signature. A small updater on the host pulls, verifies the signature against one
  pinned identity, asks the owner (over SSH until stage 5, then with a bot card bound to the digest),
  holds writes, snapshots, migrates, health-gates and releases — or rolls back while the holds are on.
  Nothing from GitHub reaches into the home network (DEP-7…DEP-10).
- **Alternatives:** a self-hosted runner on the home machine (fork-PR code next to private data); push
  deploy over the private network as the default (CI holds a path into the home network — possible later
  as an option, DEP-21); generic auto-updaters (no approval, no snapshot).

## D-020 · Linux with Docker Engine on the production host — accepted (4 Oct 2026)

- **Context:** in the configurations tried in v1, Docker Desktop on Windows required an interactive user
  session and its WSL VM stopped when idle, and v1's Windows home server had no remote administration
  path.
- **Decision:** Debian or Ubuntu LTS with Docker Engine, key-only SSH over the private network, NTP, no
  sleep, power-on after power loss; full-disk encryption and a UPS are recommended. Hardware guidance:
  minimum 4 x86-64 cores and 16 GB RAM; reference 8 cores and 32 GB with a 1–2 TB NVMe disk; measure
  transcription speed with `coflow bench stt` before buying (DEP-14, NFR-4, NFR-11).
- **Owner's decision:** the author's existing gaming desktop, currently on Windows, becomes the
  production host and moves to Linux for it (at stage 2 at the latest); the machine's old v1 instance is
  retired in the process.
- **Alternatives:** Windows with Docker Desktop or WSL2 (the configuration that failed in v1); a
  hypervisor with a Linux VM (more layers); a low-power mini-PC (fine for daily load, slow for the
  archive).
- **Changed 17 October 2026 (accepted):** the production host is a separate home laptop whose GPU is
  dedicated to this work, not the desktop, and it moves to Linux for it (D-050); it holds real data only
  after its gate (D-050, DEP-27). Proposed: the laptop profile of DEP-14.

## D-019 · Production runs on a separate home computer, delivered by CI/CD — accepted (4 Oct 2026); preconditions and staging plan proposed

- **Context:** the author develops on their own machine and wants production on a separate home computer
  through a proper CI/CD process, with Docker or an external server as the final way to install the
  project — and wants to show this path publicly. v1 ran on a separate home machine for about two months
  and moved back on 30 August 2026: it could be administered only physically, the documented remote
  access was never configured, deploys were manual, and the old instance kept writing.
- **Decision (accepted):** production on a dedicated home computer, reached only through CI/CD; the same
  image installs with Docker on any host or rented server.
- **Proposed:** remote administration, off-host backups, an off-host heartbeat and one enforced writer as
  preconditions, not later improvements; the delivery skeleton in stage 0, the home host in the staging
  role from stage 2, the author's data moving there in stage 6 ([DEPLOYMENT.md](DEPLOYMENT.md)).

## D-018 · Money comes from the owner's entries, invoice records and statement files, never from bank connections — proposed

- **Context:** the owner wants financial goals and real income, expenses and balance next to decisions
  and commitments (FIN). Bank APIs and aggregators need bank credentials and send data to third parties.
  Many Spanish banks offer Norma 43 statement files, and some business channels offer camt.053.
- **Decision:** a ledger fed by one-line entries (bot, MCP), invoice records from a compliant invoicing
  tool and imported statement files (Norma 43 and camt.053 first, then CSV profiles and OFX). CoFlow never
  stores or uses bank logins, bank API credentials or tax certificates; credentials and API keys never
  reach a model, whatever the financial-data switches say (FIN-3, FIN-5, FIN-16).
- **Alternatives:** an open-banking aggregator (convenient, but credentials and data go to another
  company; possible later only as a plugin through a new decision); no money at all (decisions lose their
  most concrete outcome).

## D-017 · Analysis returns as evidence-first research modules, not as v1's scoring engines — proposed

- **Context:** the owner wants their words, thoughts and actions compared with their own centre, and the
  balance of their relationships measured — the author's model `∫G = V × E`,
  `G(t) = (V, E(t), X(t), C(t))`. v1 built engines for this (compliance, convergence, corridor, a
  knowledge graph). They died: the judge never returned "violation", the inputs went stale, part of the
  reference was seeded by code, and the graph stayed empty.
- **Decision:** observable measures first, computed by algorithms (REL-1); findings only with evidence on
  both sides and an allowed "can't judge" (ALN-2); deliberate search for disconfirming evidence, a
  synthetic evaluation set, and usefulness marked by the owner (ALN-3); the journal only under the
  owner's switch (D-025); conductivity research only under a pre-registered protocol (REL-4); no inferred
  psychological profiles of other people (REL-3).
- **Alternatives:** port the v1 engines (proven not to work); scores from a model on many axes (plausible
  numbers that cannot be falsified).
- **Consequences:** all these modules are research (D-029), built on core data (REL-6) and the centre
  from GOL-1; each one must show a usage signal to stay.

## D-016 · A timeline over every layer is part of the core — proposed

- **Context:** the owner wants to find any day or event in their history across all layers and, later,
  to study how their positions and communication changed.
- **Decision:** a timeline query over every stored layer is in R1 (TML-1) and grows with each new layer;
  importing the whole personal archive (TML-2) comes after the switch-over; research on change over time
  (TML-3) comes later and cites evidence.

## D-015 · Contributions under Apache-2.0 with a DCO sign-off — proposed

- **Context:** the project accepts outside contributions later; the licence must stay clean.
- **Decision:** inbound = outbound (Apache-2.0); every commit carries a Developer Certificate of Origin
  sign-off (`git commit -s`). No contributor licence agreement.
- **Alternatives:** a CLA (heavier for contributors, needs a legal entity to hold it); no sign-off (weak
  provenance).
- **Consequences:** a DCO check in CI from stage 0.

## D-014 · Model provider behind an interface; Anthropic is the reference — proposed

- **Context:** v1 calls one provider directly from one module, logging every call with its cost. Open-source
  users may prefer other providers or local models; tests must not call any provider.
- **Decision:** one provider interface; Anthropic is the reference implementation and the default; a fake
  provider runs the test suite.
- **Consequences:** prompts must not depend on provider-specific features without a fallback; cost tables
  live in configuration.

## D-013 · No voice prints, no biometric data of third parties — accepted (September 2026, in the private v1's meeting-recording specification; carried over)

- **Context:** speaker recognition by voice needs biometric templates of people who never agreed to it.
  Diarization in v1 failed on real recordings and is off.
- **Decision:** CoFlow never stores voice prints. "Who said what" comes from the meeting anchor and the
  owner's naming of anonymous speakers.
- **Consequences:** diarization stays "Later" (SIG-12) and only after a measured pass on real recordings.

## D-012 · Rules, not models, decide where text goes — accepted

- **Context:** in v1 the bot first treated unmarked messages as journal entries; an evening review would
  have gone into the private journal. On 30 September 2026 the owner decided to invert the routing; it
  shipped in early October.
- **Decision:** every unmarked message is work; the journal is chosen only by an explicit marker; an
  ambiguous start is resolved by the owner with a button before any model sees the text. "This was journal"
  blanks every record derived from the message.
- **Consequences:** canary tests over every message kind and every channel (BOT-2, BOT-3, NFR-6).

## D-011 · Approval cards and one outbox for external writes — proposed

- **Context:** in v1 a meeting with a calendar event was marked done even when the calendar call failed,
  and a one-off event had no own id, so a retry could duplicate it and resend invitations. The week plan
  fixed this with deterministic ids, conditional writes and read-back.
- **Decision:** model-proposed writes become approval cards; every action that changes the outside world
  goes through one outbox with explicit states, deterministic external ids, read-back before retry and
  read-back verification.
- **Consequences:** stage 5 has two review rounds and a recording fake calendar (MTG-5).

## D-010 · SQLite, one writing instance, strict write discipline — proposed

- **Context:** v1 runs about nine writing processes on one SQLite file. On 30 September 2026 lock timeouts
  took processes down; the cause was search triggers scanning ≈ 233k rows under the write lock, plus
  start-up writes and model calls inside write transactions. Two writing copies of the database once
  produced 17 colliding company numbers.
- **Decision:** SQLite in WAL mode; one writing instance per owner; no network or model call inside a write
  transaction; short idempotent writes retried on "locked"; a watchdog for long writers; numbered
  migrations. Postgres, tenants and row-level security are out (see D-005).
- **Consequences:** OPS-3, OPS-4; a second writing copy is unsupported by design (P-1). The database lives
  on a local disk or volume of the production host, never on a network share; instance roles and
  promote/retire keep one writer across machines (D-022); failover means restore → promote → retire, never
  two production instances; other machines use the API only. *Revised 4 Oct 2026 for the server
  deployment.*

## D-009 · Chat-first: a bot and MCP; one status page — proposed

- **Context:** v1 has 20 web pages; in 30 days the whole web interface, apart from the recorder status
  page, was used for about an hour. Daily work happened in the Telegram bot (138 messages on 13 of 13
  days) and through MCP from AI clients (1,464 calls on 12 days).
- **Decision:** the bot and MCP are the interfaces of R1; the only web screen is a status page. Further
  screens come one by one when use is measured.
- **Consequences:** UI-1, UI-2; requirements are written as bot and MCP scenarios.

## D-008 · Cross-platform Python; native install for development, a container image for production — accepted (4 Oct 2026; revised the same day)

- **Context:** v1 runs only on Windows, with 11 scheduler jobs created by hand. Later the same day the
  author decided that production runs on a separate machine delivered by CI/CD, and that the project must
  be easy to install with Docker or on an external server (D-019).
- **Decision:** Python, cross-platform, with two install paths from one codebase: a container image with
  Docker Compose is the reference production install (on a Linux host — accepted, D-020; the same image
  runs on any Docker host or rented server); native Python on Windows and Linux is the development and contributor install,
  both tested in CI. macOS is best effort by the community. One supervisor process replaces OS scheduler
  jobs. Desktop-bound features (activity tracking, recorder folders, input devices) run as device agents
  or plugins.
- **Alternatives:** native only (no immutable artifact to promote from CI to production; drift on the
  host); Docker only (hurts Windows development and device access); Windows only (excludes most
  self-hosters).
- **Consequences:** DEP-1…DEP-21; NFR-1 assigns platforms their roles. The first version of this decision
  rejected Docker-first; it was revised when production moved to a separate machine.

## D-007 · The Telegram user-session collector is a plugin, off by default — accepted (4 Oct 2026)

- **Context:** reading one's own chats through a user session is the richest signal in v1 (new messages
  every day), but it touches account security and Telegram's terms.
- **Owner's decision:** the Telegram user-session collector is a plugin, off by default. The details below
  are proposed.
- **Decision:** ship it as a plugin, off by default, read-only, only for chats the owner marks, with an
  explicit warning. The core works with Telegram Desktop exports.

## D-006 · v1 feature freeze — accepted (4 Oct 2026)

- **Context:** v1 is under acceptance testing since 1 October 2026; its planned next stages would double
  the work if built twice.
- **Decision:** from 4 October 2026, v1 gets only acceptance fixes and fixes of dangerous bugs. All planned
  stages move to v2.
- **Changed 17 October 2026 (accepted):** one exception — the decision loop is built in v1 now (check dates
  and the "waiting" list, a decisions screen, review questions in the chat written only after approval), and
  the same part is specified for 2.0 (D-037). The forecast pilot of the same day runs outside v1's code.

## D-005 · The core is a personal decision system — accepted (4 Oct 2026)

- **Context:** earlier plans described v1's successor as a SaaS product with tenants, a paid pilot and a
  hardware kit; other plans described a CRM. The author does not see a product in it.
- **Decision:** CoFlow 2.0 is a personal decision system:
  `Signal → Decision → Commitment → Action → Outcome → Learning`. One installation = one owner. No
  tenants, no billing, no team features.
- **Consequences:** the out-of-scope list in REQUIREMENTS §7.

## D-004 · Requirements first, code after the v1 acceptance period — accepted (4 Oct 2026); its timing superseded by D-038 (17 October 2026)

- **Decision:** the requirements, roadmap and lessons are written and published first; development starts
  when the v1 acceptance period ends (planned mid-October 2026).

## D-003 · A new clean repository; v1's history is not published — accepted (4 Oct 2026)

- **Context:** v1's history contains real conversations, contact data and names in files and commit
  messages. Earlier v2 design documents (July 2026) fell behind v1 by about 60 versions; some of their
  decisions were disproved in practice (voice prints, one central review queue, search without
  triggers, and a home server run without remote administration, without CD and with the old instance
  left writing — a home server returns in D-019 with those failures addressed).
- **Decision:** a new repository; proven v1 modules are ported one by one with tests and synthetic
  fixtures; the July design is a reference only. The author's data moves through an import format
  (stage 6).
- **Alternatives:** clean up and publish v1 (history rewrite, high risk of leaking data); implement the July
  design as written (outdated).

## D-002 · English for code and docs; media in Russian and English — accepted (4 Oct 2026)

- **Owner's decision:** code and docs in English; media in Russian and English. The details below (the
  locales in R1, the channel for each language) are proposed.
- **Decision:** code, docs, issues and commit messages in English. User-facing texts are localized
  (English and Russian in R1). Episodes are published in Russian (Telegram) and English (LinkedIn,
  GitHub).

## D-001 · Open source under Apache-2.0 — accepted (4 Oct 2026)

- **Context:** CoFlow is the author's research lab for decision systems. The value is the evidence it
  produces — decision cases, commitments, outcomes — not the code.
- **Owner's decision:** open source under the Apache License 2.0, developed in public. The consequences
  below are proposed.
- **Decision:** publish CoFlow 2.0 under the Apache License 2.0 and develop it in public.
- **Alternatives:** MIT (no explicit patent grant); AGPL-3.0 (discourages integration and embedding; the
  author does not host CoFlow for others); keep it private.
- **Consequences:** no AGPL dependencies in the core; a NOTICE file; models are downloaded at runtime and
  keep their own licences, never baked into images; LGPL libraries only in plugins unless the licence of
  the bundled audio-decoding stack, verified in stage 0, requires amending this rule. Published container
  images are a binary distribution: CI runs a licence gate on every image, and an SBOM with a third-party
  licence inventory follows in R2 (DEP-5, DEP-20).
