# Decision log

Newest first. Each entry: context, decision, alternatives, consequences.
Status: **accepted** (the author decided) or **proposed** (waiting for the author's review).

The private v1 is referred to as "v1". Its numbers are aggregates; no personal data is published.

---

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
  approves every publication, and publishes. A main episode every Monday (video and posts) and a short
  lesson post on Thursdays — at most two touches a week — with the episode calendar and the review gate
  on 9 November 2026 as recorded in [BUILD_IN_PUBLIC.md](BUILD_IN_PUBLIC.md). Episode 0.1 publishes on
  6 October 2026; the canonical text of every episode goes into [DEVLOG.md](../DEVLOG.md).
- **Proposed:** the rubric's working name ("Decision system at work"); merging code automatically once CI
  and the independent review pass, so the author is never the bottleneck of the build.
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

## D-005 · The core is a personal decision system — accepted (4 Oct 2026)

- **Context:** earlier plans described v1's successor as a SaaS product with tenants, a paid pilot and a
  hardware kit; other plans described a CRM. The author does not see a product in it.
- **Decision:** CoFlow 2.0 is a personal decision system:
  `Signal → Decision → Commitment → Action → Outcome → Learning`. One installation = one owner. No
  tenants, no billing, no team features.
- **Consequences:** the out-of-scope list in REQUIREMENTS §7.

## D-004 · Requirements first, code after the v1 acceptance period — accepted (4 Oct 2026)

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
