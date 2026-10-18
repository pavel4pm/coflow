# CoFlow 2.0 — Architecture

Version 0.2 · 18 October 2026 · **draft — stage 0A (the kernel and the decision core) is being built
since 17 October 2026; everything else is not implemented yet**

How CoFlow 2.0 is cut into modules, how the modules talk, which rules keep them apart and how each one is
accepted. Requirement IDs refer to [REQUIREMENTS.md](REQUIREMENTS.md) (v0.7), decisions to
[DECISIONS.md](DECISIONS.md), the process view to [DEPLOYMENT.md](DEPLOYMENT.md). One card per module is in
[MODULES.md](MODULES.md); the decision core in detail is in [SPEC_DECISION_CORE.md](SPEC_DECISION_CORE.md).
The decision behind this document is D-030; the principles are P-14 and P-15.

In one paragraph: one owner per installation, one SQLite database, one writing process (`core`). Inside
`core` run about thirty bounded modules; each owns its tables, exposes an `api` of commands and queries,
and emits events. The decision module (DEC) is the hub of the chain: every record of evidence or
execution says which decision it serves, or says "none" on purpose, and each link is stored by the module
whose workflow forces it, so the hub never imports its spokes (§5.1). Outside `core` run only satellites
without a database path: the speech-to-text worker, the MCP stdio bridge and the local stdio shim, device
agents, out-of-process plugins, the host-side updater and, from stage-8 module 0, the internet-facing
`edge` container. CI enforces the boundaries (§5), and each module is accepted against its own card (§9).

---

## 1. Why not microservices

The owner asked whether CoFlow should be built as microservices. Everything they asked for is kept:
modules designed up front, explicit relations and explicit data exchanged between them, quality criteria
and acceptance per module, growth one module at a time. What is left out is the deployment model of one
networked service with its own database per module. CoFlow takes the microservice organisation and leaves
out the microservice deployment (D-030, accepted by the owner on 4 October 2026). The reasons, in order of weight:

1. **One SQLite writer.** A SQLite transaction is atomic inside one file on one host. The guarantees that
   matter most are "true once the transaction commits": blanking a message as journal (BOT-3), deleting a
   source with everything derived from it (PRV-7), forgetting a person (PPL-6), a consistent snapshot
   (OPS-5). With a database per service each becomes a saga that is only "eventually true", with a window
   in which a journal canary can still be found. Several services writing one shared file instead is v1's
   setup of nine writing processes, which ended in lock timeouts ([LESSONS_FROM_V1.md](LESSONS_FROM_V1.md)).
2. **One numbering tap.** Every public id comes from one sequence inside the caller's transaction (IDN-1).
   Across services that needs a network call per id or a distributed allocator.
3. **One maintainer.** Microservices repay their cost through independent teams, independent deployments
   and measured scaling; none applies here. The cost would arrive every week: N images, health checks and
   release lines, inter-service tokens (more secrets, PRV-4), more listeners (against PRV-5), versioned
   network APIs between modules that change together.
4. **Failure modes.** A network boundary adds partial failure: a call that timed out may or may not have
   happened, so every cross-module write would need the idempotency keys and read-back that only external
   actions need today (P-8). Inside one process a failed unit of work rolls back and leaves nothing.

The part worth showing stays: a container stack (`core` + `stt`) built by public CI, signed, pulled and
approved on the host (D-021, D-024), plus boundary gates, per-module scorecards and drills for the episodes.

**When a module may leave the process (AP-14):** it must run on another host; it needs crash or memory
isolation; it needs licence or trust isolation; it needs another runtime or release cadence; or a scaling
need has been measured. "Cleaner" and "a separate domain" are not reasons. Because a module talks only
through its `api` and its events, extraction swaps the transport (an in-process call becomes HTTP, event
dispatch becomes the ingestion endpoint) and leaves the domain code alone. An extracted module becomes a
client of the job and integration contracts and keeps writing through `core`; a second database writer is
never introduced. Satellites that already meet the criteria: the STT worker (memory isolation; v1's long
audio ran out of memory), device agents and the updater (another machine, or outside the stack),
out-of-process plugins (licence and trust isolation) and the stdio bridge (a transport for stdio clients).

## 2. Architecture principles

| ID | Principle | Consequence |
|---|---|---|
| AP-1 | **One store, one writer** | One SQLite file on a host-local volume; only `core`'s writer thread holds a write connection. No other process — worker, bridge, plugin, CLI while `core` runs — can resolve the database path (P-1, D-010, D-022) |
| AP-2 | **Modules are contracts** | A module owns its tables and exposes `coflow.modules.<mod>.api` (commands, queries) and `.events`. In R1 cross-module reads go only through `api`; versioned `pub_<mod>_<name>_vN` views appear in stage 8, when a plugin or research consumer needs them |
| AP-3 | **No cross-module writes, foreign keys or copies** | References are public ids, or `<ISSUER>_<id>` refs for ids issued elsewhere, checked nightly. Data owned elsewhere is resolved at read time (a task stores `goal_ref`, never the goal's direction) |
| AP-4 | **Prepare outside, apply inside** | Reads, model and network calls first; then one short, pure-database unit of work writes the change, its events and its derivation edges. No model or network call inside a write transaction (OPS-3) |
| AP-5 | **Events in the same transaction, ids only** | The event row commits with the change. Payloads carry ids, the entity type and the names of changed fields, never values; delivered events are pruned after 30 days |
| AP-6 | **One gate per risk** | Model calls through MDL, external effects through ACT, deletion through POL's erasure path; every exit (model, MCP response, bot message, export) asks POL whether the data class may go there |
| AP-7 | **Data classes are policy, and they propagate** | Journal and financial flows are switches in `DATA_FLOWS.md` (PRV-2, PRV-9, FIN-5); model outputs inherit the most restrictive input class. The hard bans on the journal hold whatever the switches say |
| AP-8 | **Evidence over inference** | Rankings, control lists, balances and tax figures are computed by code; a model phrases, or produces findings with evidence and a possible "can't judge" (P-6). Tax figures never pass through a model |
| AP-9 | **Ports with fakes** | Model provider, messenger, calendar, clock, file store, STT, statement parser and invoice reader are ports with a fake and a shared contract suite; real adapters only behind the live flag and a budget (OPS-8) |
| AP-10 | **Read models are disposable** | Search, timeline and plans write only their own tables and rebuild from scratch to the same result |
| AP-11 | **Plugins and research are removable** | No core package imports a plugin or `coflow_research`; removing one needs no core migration |
| AP-12 | **Plan and record money, never issue or file** | Books per contour, an append-only ledger, a read-only invoice register, estimates from versioned country packs; no invoices, series, returns or statutory books (D-026; books and packs proposed, D-027) |
| AP-13 | **Every module earns its place** | A card with quality parameters, invariants as fitness functions and a usage signal; a module without use is fixed or removed (P-13, NFR-10) |
| AP-14 | **Extraction only by criterion** | See §1 |
| AP-15 | **A link is stored by the module whose workflow forces it** (proposed, D-042) | A closed registry of link kinds, each with its owner and its enforcement point. DEC stores decision-to-decision links, `serves`, `tests`, `about`, `informed_by`, the origin and the evidence; a spoke (CMT, WRK, MTG, FIN, RHY) stores its own `decision_ref` and the entry-time link answer in its own unit of work. No workflow needs two units of work to link what it creates, and no generic link graph exists (P-15, DEC-11) |
| AP-16 | **Evidence is append-only and bitemporal** (proposed, D-049) | Every unit of work writes one transaction-log row (actor, channel, approval, instance role, code version) stamped by the store layer; append-only, set-once and erasable columns are declared per table and enforced by generated triggers; every row that describes an event carries its event time with precision and basis; `as_of(T)` is a core query (NFR-13, DEC-13) |

## 3. Context

```
 OWNER DEVICES                                      EXTERNAL SERVICES (outbound from core only)
 +-------------------------------------+            +-------------------------------------------+
 | phone: messenger app                |            | messenger bot API (long polling)          |
 | desktop: AI clients (stdio over SSH,|            | model provider (as DATA_FLOWS.md allows)  |
 |   or the local shim on one machine) |            | calendar provider (read / write tokens)   |
 | terminal: coflow CLI (SSH)          |            | invoicing tool: read-only API adapters    |
 | folder sync: recordings, exports    |            |   (plugin); its exports arrive as files   |
 | device agents (R2): uploader,       |            | hosted apps: pulled read-only (D-051)     |
 |   activity agent -> INT             |            | image registry (pull by digest)           |
 +------------------+------------------+            | off-host backup storage, dead-man switch  |
                    | SSH over the overlay VPN,     +---------------------^---------------------+
                    | encrypted folder sync                               |
                    |   INTERNET ENTRY (R2, stage-8 module 0)             |
                    |   cloud AI clients --HTTPS--> owner relay (rented, outside the home):
                    |   TLS passthrough by server name, no keys, no data; DNS of a separate
                    |   domain with DNSSEC and CAA                        |
                    |                   ^ WireGuard tunnel opened by the host (outbound)
 +------------------v-------------------+---------------------------------+---------------------+
 | HOST: Linux, Docker Engine (the author's: a dedicated home laptop with a GPU, D-050)         |
 |  coflow-updater (systemd timer; pulls, verifies, deploys after the owner approves)           |
 |  coflow-bridge  (SSH forced command; stdio <-> core's MCP on 127.0.0.1 with a client token)  |
 |  +---------------------------+ cloud view +-------------------------+                        |
 |  | edge (R2): TLS, OAuth and |----------->| core: one supervisor     |  job files  +--------+ |
 |  | consent pages, MCP parsing| (internal  | process, the only        |<----------->| stt:   | |
 |  | no database; TLS key only | network)   | database writer          |  work/ dir  | no net,| |
 |  +---------------------------+            |  interfaces BOT MCP STS  |             | no DB, | |
 |                                           |   INT ADM (127.0.0.1)    |             | GPU    | |
 |                                           |  domain PPL SIG JRN WRK  |             +--------+ |
 |                                           |   DEC CMT CAL MTG RHY    |             +--------+ |
 |                                           |   LRN SRC TML FIN TAX    |------------>| llm    | |
 |                                           |   GOL ALN                |             +--------+ |
 |                                           |  kernel STO IDS EVT POL  |             | backup | |
 |                                           |   MDL ACT CFG OBS OPS    |             +--------+ |
 |                                           |  plugin host; child      |                        |
 |                                           |   processes (JSON-RPC)   |                        |
 |                                           |  SQLite (WAL), data vol. |                        |
 |                                           +--------------------------+                        |
 +----------------------------------------------------------------------------------------------+
```

The owner's channels are the private bot chat and the local CLI on the host. MCP is not an owner channel:
a tool argument may have been written by the client's model, so MCP can create drafts and execute logged,
undoable internal writes, but it never approves anything (P-4, MCP-4). The `core` listener is never
internet-facing (PRV-13): cloud AI clients reach only the `edge` container, through the owner's relay,
which forwards encrypted traffic and holds no data and no keys (D-053, DEP-12). Hosted apps never push
into the home network; `core` pulls from them outbound with a read-only token (D-051, EXT-4).

## 4. Module map

Stage numbers follow the roadmap; "0A" and "0B" are the two parts of stage 0; "8.1a" is stage 8, module
1a; "8.0" is the module moved to the front of stage 8. Kernel tables use `sys_*` and are registered per
kernel module; ACT and CFG use their own prefixes; domain modules use their code as prefix; plugins use
`px_<id>_*`. The authorizer checks the table registry, not the prefix.

| Group | Code | Module | Owns | Release · stage | Runs in |
|---|---|---|---|---|---|
| Kernel | STO | Storage, migrations and the transaction log | `sys_meta`, `sys_migrations`, `sys_table_registry` (with append-only, set-once and erasable columns), `sys_tx_log` | R1 · 0A | `core` (writer thread) |
| Kernel | IDS | Identity and numbering | `sys_id_*` (sequence, prefixes, burned, foreign, aliases), `sys_content_ids` | R1 · 0A | `core` |
| Kernel | EVT | Events, outbox, jobs, scheduler | `sys_events`, `sys_event_deliveries`, `sys_jobs`, `sys_schedules` | R1 · 0A (events in the unit of work, in-process dispatch), 0B (outbox delivery, scheduler), 2 (jobs) | `core` |
| Kernel | POL | Privacy and data flows | `sys_dataflow_switches`, `sys_derivations`, `sys_tombstones`, `sys_deletion_log`, `sys_retention_runs`, `sys_secrets_inventory` | R1 · 0A (classes, canary fixture), 0B, 1 (erasure, `untrusted_external`), 2 (egress allow-list) | `core` |
| Kernel | MDL | Model gateway | `sys_model_calls`, `sys_prompts`, `sys_budget`, `sys_eval_runs` | R1 · 0B | `core`; optional `llm` |
| Kernel | ACT | Approvals, external-action outbox, undo | `act_*` | R1 · 2 (cards), 5 (outbox) | `core` |
| Kernel | CFG | Owner profile and locale | `cfg_*` | R1 · 0A (minimum), 0B | `core` |
| Kernel | OBS | Traces, health, scorecards | `sys_traces`, `sys_trace_steps`, `sys_health`, `sys_sli_samples`, `sys_usage_signals`, `sys_scorecards` | R1 · 0A (usage signals), 0B (trace skeleton), 1 (traces), 2 (heartbeat, alerts), 4 | `core` |
| Kernel | OPS | Instance, backups, export, deploy state | `sys_instance`, `sys_backups`, `sys_deploys`, `sys_holds`, `sys_exports`, `sys_host_gate` | R1 · 0A (roles dev and validation), 0B, 2, 5; R2 · 6 | `core`; CLI through ADM |
| Domain | PPL | People and companies | `ppl_*` | R1 · 1; R2 · 6, 8.8 | `core` |
| Domain | SIG | Signals: sessions, messages, recordings | `sig_*` | R1 · 1, 4 | `core`; audio in `stt` |
| Domain | JRN | Journal | `jrn_entries` | R1 · 1 | `core` |
| Domain | WRK | Work: tasks; directions and goals until 8.2 | `wrk_*` | R1 · 1, 2 | `core` |
| Domain | DEC | Decisions: the hub of the chain | `dec_*` | R1 · 0A; 2 (chat loop); 3 (capture, occasions); R2 · 6 (external references); Later (DEC-8, DEC-10) | `core` |
| Domain | CMT | Commitments | `cmt_*` | R1 · 0A (minimum); 3 (proposals); R2 · 6, 8.3 | `core` |
| Domain | CAL | Calendar | `cal_*` | R1 · 4 (copy), 5 (writes) | `core` |
| Domain | MTG | Meetings | `mtg_*` | R1 · 5 | `core` |
| Domain | RHY | Rhythm and activity time | `rhy_*` | R1 · 2; R2 · 6, 7 | `core` |
| Domain | LRN | Learning from corrections | `lrn_*` | R2 · 7 | `core` |
| Domain | SRC | Search (read model) | `src_*` | R1 · 1 | `core` |
| Domain | TML | Timeline (read model) | `tml_*` | R1 · 1; R2 · 8.5 | `core` |
| Domain | FIN | Money core | `fin_*` | R2 · 8.1a | `core`; extraction in a worker |
| Domain | TAX | Country packs and tax planning | `tax_*` | R2 · 8.1b | `core` |
| Domain | GOL | Centre and goals | `gol_*` | R2 · 8.2 | `core` |
| Domain | ALN | Inconsistency findings (think / say / do against the centre) | `aln_*` | R2 · 8.2b | `core` |
| Interfaces | BOT | Messenger bot | `bot_*` | R1 · 2 | `core` |
| Interfaces | MCP | MCP server | `mcp_*` | R1 · 0A (loopback, local shim), 1; R2 · 8.0 (remote) | `core` |
| Interfaces | STS | Status page | — | R1 · 4 | `core` |
| Interfaces | INT | Integration and ingestion API | `int_*` | R1 · 3 (decision-anchor schemas, EXT-5); R2 · 6 | `core` |
| Interfaces | ADM | Admin API and CLI | `adm_tokens` | R1 · 0A | `core` listener; CLI client |
| Satellites | STT | Speech-to-text and extraction worker | files in `work/` only | R1 · 2 (CPU and GPU, DEP-25); R2 · 8.1a (extract) | `stt` container |
| Satellites | BRG | MCP stdio bridge and local stdio shim | — | R1 · 0A (local shim), 1 (SSH bridge) | host, SSH forced command; the shim on the client's machine |
| Satellites | AGT | Device agents | a buffer on the device | R2 · 6 | owner's desktop |
| Satellites | UPD | Updater | host files | R1 · 0B (manual), 2, 5 | host, outside the stack |
| Satellites | EDG | Internet edge: TLS, OAuth and consent pages, MCP parsing for cloud clients (proposed, D-053, PRV-13) | — (no database; only its TLS key) | R2 · 8.0 | `edge` container |
| Plugins | PLG | Plugin host | `sys_plugins` | R1 · 4; R2 · 8.7 (out of process) | `core` |
| Plugins | TGC | Messenger user-session collector | `px_tgc_*` | Plugin · 4 | `core`, in process |
| Plugins | MLR | Mail read | `px_mlr_*` | Plugin · 4 | `core`, in process |
| Plugins | IMP | Statement import | `px_imp_*` | Plugin · 8.7 (one format proposed for 8.1a) | in process; GPL parsers out of process |
| Plugins | INV | Invoice API adapters, read-only | `px_inv_*` | Plugin · after 8.1a | `core`, in process |
| Plugins | ESP | Spain reference pack | pack data loaded by TAX | Plugin · 8.1b | data only |
| Plugins | NEG | Negotiation through the owner's messenger | `px_neg_*` | Plugin · 8.4 | `core`, in process |
| Plugins | WPL | Week plan | `px_wpl_*` | Plugin · 8.8 | `core`, in process |
| Research | REL, CND, EVO | Relationship measures, conductivity, evolution | `px_rel_*`, `px_cnd_*`, `px_evo_*` | Research, after stage 8 | `coflow_research` plugin |

## 5. Dependencies

### 5.1 Layers, tiers and ports

```
 coflow.app            composition root: wires adapters into ports, registers handlers
 coflow.interfaces     bot | mcp | status | int | admin          coflow.plugin_host
 coflow.modules        tier 8  aln
                       tier 7  gol
                       tier 6  rhy | src | tml | lrn
                       tier 5  mtg
                       tier 4  wrk | tax
                       tier 3  cmt | fin
                       tier 2  sig | dec
                       tier 1  ppl | jrn | cal
 coflow.kernel         ops > obs > models | actions > policy > events > ids | config > store > context | ports
 coflow.contracts      JSON Schemas and models: jobs, inbox, INT, plugin RPC (imports nothing)
 coflow.adapters       provider, messenger, calendar, file and invoice readers (wired only by app)
 coflow.workers, coflow.bridge, coflow.agents    import only coflow.contracts
```

A module imports only the `api` of modules in lower tiers; modules in one tier are independent; the edges
actually used are declared in each card. Where a lower module needs something a higher one owns, it uses
a **port** in `coflow.kernel.ports`, and the owner registers the implementation in `coflow.app`:

| Port | Implemented by | Used by |
|---|---|---|
| `GoalDirectory`: exists, direction of, active goals, likely goals (WRK-8); a goal's state as of a time | WRK until 8.2, then GOL; in stage 0A a shadow adapter over mirrored goal context | WRK, DEC, CMT, FIN, MTG, RHY, SIG |
| `DecisionDirectory`: resolve a decision from text or a ref (aliases included), info, state as of a time, whether it accepts an attachment, open decisions for subjects, the likely decisions for a new entry (at most three, deterministic), the waiting list, a projection per audience, assumptions to probe (DEC-11, DEC-19) | DEC | SIG, PPL, CAL, CMT, WRK, MTG, RHY, GOL, FIN, INT |
| `DecisionAttachmentProbe`: per decision, the summary and timeline of what is attached (ids, counts and change names only), and the unlinked counts per period in four buckets (DEC-11, DEC-19) | CMT, WRK, MTG, FIN, RHY (each spoke that stores a `decision_ref`) | DEC |
| `EvidenceResolver`: resolve an evidence ref (kind, event time, data class, text for the quote check) and check that a quote is an exact substring of its source; refuses journal-class refs (DEC-2, DEC-13) | SIG, MTG, GOL, FIN; built-ins in DEC for owner statements, AI working sessions and foreign refs | DEC |
| `ReviewContributor`: a section of the weekly review | WRK (control view), GOL (control list, reflection) | RHY |
| `Eraser`: purge what a source left in my tables | every module that stores derived data | POL |
| `UndoHandler`: the inverse of an MCP write | every module with MCP write tools | ACT |
| `OperationHandler`: one kind of external effect | CAL, CMT (material send), NEG, OPS (deploy approval) | ACT |
| `HealthProbe`, `Projector` | modules with health checks or read models | OBS, EVT |

Cycles found in review are removed this way: the interaction context lives in the leaf `kernel.context`,
so EVT never imports OBS (OBS subscribes to events); contact proposals are extracted and stored in SIG, so
PPL never reads SIG; PPL takes script variants from CFG's locale pack, never from SRC; RHY takes GOL's
review sections through a port, so RHY never imports GOL.

**The decision is the hub without a cycle** (P-15; proposed, D-042). DEC stays in tier 2: it cannot move
to tier 1, because modules in one tier are independent and tier 1 holds PPL, which a decision refers to.
Three edges changed in the 18 October 2026 revision:

- **DEC no longer depends on WRK.** That edge was a cycle (WRK already depends on DEC) and an upward
  import. A card that spans modules — a fact, an adjustment and a next task on one approval (DEC-9) — is
  orchestrated by the interface, each item written in its owner's own unit of work.
- **DEC reads its spokes only through `DecisionAttachmentProbe`.** The composition root registers the probe
  of every installed spoke; a missing module simply has no probe and is absent from the hub view (EXT-6).
  DEC keeps another module's data only as frozen counts in a review's execution summary. Spokes and
  same-tier modules reach DEC through `DecisionDirectory`, so their suites run with a fake.
- **ALN is tier 8** in the `domain` import contract: it depends on GOL (tier 7) and was missing.

An import-contract test asserts that DEC imports nothing above tier 2.

**Link ownership** (AP-15). Each link kind has one owner and one enforcement point:

| Link kind | Stored by | Enforcement point | Stage |
|---|---|---|---|
| Decision to decision (`follows`, `supersedes`, `depends_on`, `part_of`, `contradicts`); `tests`, `serves`, `about`, `informed_by`; the origin ("decided in"); ground, monitoring, check and reading evidence | DEC | `create_decision`, `activate_decision`, `link`, the review actions, `add_fact`, `record_check`, `record_reading` | 0A |
| Commitment `executes` decision; the entry-time link answer | CMT (`decision_ref`, `link_answer`) | `create_commitment`, `link_commitment` | 0A |
| Task `executes` decision; the entry-time link answer | WRK (`decision_ref`, `link_answer`) | `create_task` (WRK-8) | 1 |
| Goal `pursued_by` a decision of kind `pursue` | WRK, then GOL | goal activation | 1, 8.2 |
| Meeting `prepares` or `reviews` a decision | MTG (`mtg_meeting_decisions`) | `plan_meeting` (a decision is a valid link to work) | 5 |
| Decision `cites` a centre item | DEC | `link` (GOL-13) | 3 |
| Ledger entry `stake_actual`; time span `hours` | FIN, RHY (`decision_ref`) | `post_entry`; the span rule or the owner | 8.1a, 6 |
| External decision reference; delegated commitment | DEC; CMT (`external_ref`) | the owner's `link`, or the team-tool pull | 6 |

A commitment, a task or another execution item cannot attach to an ended decision, or to one whose
system of record is still another system (a mirror); the refusal names the successor where there is one.

### 5.2 Import contracts (`.importlinter`, excerpt)

```ini
[importlinter:contract:top]
type = layers
layers = coflow.app
         coflow.interfaces | coflow.plugin_host
         coflow.modules
         coflow.kernel
         coflow.contracts
[importlinter:contract:kernel]
type = layers
containers = coflow.kernel
layers = ops
         obs
         models | actions
         policy
         events
         ids | config
         store
         context | ports
[importlinter:contract:domain]
type = layers
containers = coflow.modules
layers = aln
         gol
         rhy | src | tml | lrn
         mtg
         wrk | tax
         cmt | fin
         sig | dec
         ppl | jrn | cal
[importlinter:contract:satellites]
type = forbidden
source_modules = coflow.workers coflow.bridge coflow.agents
forbidden_modules = coflow.kernel coflow.modules coflow.interfaces coflow.app coflow.adapters
[importlinter:contract:removable]
type = forbidden
source_modules = coflow
forbidden_modules = coflow_research coflow_plugins
[importlinter:contract:adapters]
type = forbidden
source_modules = coflow.kernel coflow.modules coflow.interfaces
forbidden_modules = coflow.adapters   # plus every provider SDK and HTTP client, listed in stage 0A
```

A custom contract type (`api-only`) adds the rest: from outside a module only its `api` and `events`
submodules may be imported, and tests of module A import only A's internals and other modules' `api`.

### 5.3 Other fitness functions (every pull request, Windows and Linux)

- **Ownership:** a SQLite authorizer lets a unit of work write only its owner's registered tables; every
  migration runs on a temp database under the authorizer of its module tag. A table without an owner, a
  data class or a canary case fails CI.
- **No database path outside `core`:** worker, bridge, agent, plugin and CLI entry points cannot resolve
  it while `core` runs (a test: the standard library is outside the import graph). The Compose lint
  asserts that `core` is never scaled and no other service mounts the database read-write.
- **No I/O in transactions:** fake ports assert that the writer is not in a transaction when called;
  transactions over 1 s fail the load suite, whose p99 must stay under 100 ms.
- **Registration:** a model function, outbound host, MCP tool or table missing from `DATA_FLOWS.md` or the
  registry fails CI; a new MCP tool is a write tool by default and needs an undo handler or a "not
  undoable" mark.
- **Schemas:** event and DTO schemas are snapshot-diffed; a breaking change needs a version bump; an event
  field other than ids, entity type and changed-field names fails.
- **Read models** rebuilt from scratch equal the incremental result. **Money:** no sum across books
  without the explicit flag (taxpayer aggregation excepted, §6.9), no jurisdiction branch in code, no
  command that allocates an invoice number. **Literal gate and secret scan** on repository, image, logs.

## 6. Contracts

### 6.1 Module `api`

- **Commands** are imperative verbs (`create_task`, `post_entry`) with a context — `actor` (`owner`,
  `bot`, `mcp:<client>`, `worker`, `plugin:<id>`, `device:<id>`, `app:<client>`, `cli`),
  `interaction_id`, `channel`, `source_ref` — and an `idempotency_key` wherever a retry is possible. Each
  runs as one unit of work on the writer thread and returns its result and the ids of its events. Errors
  are typed: `NotFound`, `Ambiguous` (with candidates), `Refused` (with a reason), `Conflict`.
- Inside a unit of work a command calls only kernel services (`IDS.issue_id`, `EVT.publish`,
  `POL.record_derivation`), never another module's command. Cross-module workflows run as events after
  commit or as orchestration by an interface, each step its own idempotent unit.
- **Queries** have no side effects, use WAL read connections, carry `as_of`, `coverage` and `stale` where
  data has a freshness (P-9) and declare the data classes of their result (§7).
- **Projectors:** SRC's synchronous projectors run inside the unit of work, read the changed rows through
  the owner's projection query on the unit's connection and write only `src_*` (p99 < 50 ms). TML and RHY
  use after-commit handlers. No projector accepts the journal class.
- **Undo:** every write reachable over MCP has an `UndoHandler` in its owning module, run as that module's
  own unit of work, or is marked "not undoable" in the catalogue (MCP-4).

### 6.2 Events

The envelope is CloudEvents-compatible and stored in `sys_events` in the same unit of work as the change.

| Field | Content |
|---|---|
| `id`, `type` | UUIDv7; `coflow.<mod>.<entity>.<verb_past>`, e.g. `coflow.wrk.task.status_changed` |
| `source`, `subject` | `coflow://<instance_id>/<mod>` (a URI, the only place the `coflow:` form remains); the plain public id of the entity (`D-0042`, `F-10001`), or an `<ISSUER>_<id>` ref (`V1_D907`) for an id issued elsewhere |
| `time`, `dataversion` | UTC; an integer |
| `correlationid`, `causationid` | The interaction id (OPS-10); the triggering event or command |
| `actor`, `dataclass` | As in §6.1; `journal`, `financial`, `work` or `system` |
| `sourceref` | The originating message, segment, recording or file, as a plain public id or an `<ISSUER>_<id>` ref |
| `data` | `entity` (type) and `changed` (field names). **Never field values** |

- Consumers read current state through the owner's `api`: a status change says `changed: ["status"]`.
- Delivery runs after commit, once per declared handler, tracked in `sys_event_deliveries`; handlers are
  idempotent by (event id, handler); retries back off, then dead-letter to the status page.
- A handler receives only the classes it declared. Journal-class events (id only) go to POL and, for
  counting, to OBS; no other handler declares the journal class.
- Delivered events are **pruned after 30 days**; both event tables are in every erasure and in the canary
  scope. No upcasters: a breaking change bumps `dataversion`, and handlers accept the current and the
  previous version for one release.
- A time-driven change (a review that becomes overdue at midnight) emits nothing by itself; it is visible
  through the owner's queries (pull). From stage 0B the scheduler emits one `check_due` event per
  assumption and due date.

**Events of the decision core** (stage 0A unless marked; `dataversion = 1`; proposed with the design,
D-042 to D-049):

| Type | Emitted by | Declared consumers |
|---|---|---|
| `coflow.dec.decision.created` / `updated` / `activated` | `create_decision` (also proposal approval and fork decide), `update_decision`, `set_manual_flag`, `set_publishability`, `activate_decision` | OBS; SRC, TML (1); BOT (2) |
| `coflow.dec.decision.reviewed` / `closed` / `cancelled` / `superseded` / `withdrawn` | `review_decision`, undo | WRK (1), RHY (2), BOT (2), MTG brief refresh (5), GOL (8.2) |
| `coflow.dec.decision.imported` / `adopted`, `coflow.dec.import.completed` | the snapshot importer, `adopt_mirrors` | OBS |
| `coflow.dec.edition.sealed` | `seal` (at activation, revise, import, completion) | — |
| `coflow.dec.assumption.added` / `superseded` / `dropped` / `checked` / `state_changed` / `postponed` | assumption commands, `record_check`, `postpone_check` | BOT: "violated" asks at once (2); RHY (2) |
| `coflow.dec.assumption.check_due` | the daily scheduler, once per assumption and due date (0B) | BOT (2) |
| `coflow.dec.reading.recorded` | `record_reading` | BOT (2) |
| `coflow.dec.fact.added` / `voided` | `add_fact`, `correct_fact`, undo | TML (1) |
| `coflow.dec.link.added` / `removed` | `link`, `unlink` | — |
| `coflow.dec.fork.opened` / `decided` / `dissolved` / `delegated` | fork commands | — |
| `coflow.dec.proposal.proposed` / `approved` / `rejected` | proposal commands | BOT: an inline card (2) |
| `coflow.dec.integrity.mismatch` | `integrity()` on read, once per edition and day | OBS |
| `coflow.cmt.commitment.created` / `status_changed` / `due_shifted` / `linked` | CMT commands | SRC (1), BOT (2) |

The event schema snapshot test fails on any payload field other than ids, entity type and changed-field
names, and a canary value written into a decision never appears in `sys_events`.

### 6.3 The two outboxes

The **event outbox** (EVT) is §6.2: a state change commits if and only if its event row exists. In the
**external-action outbox** (ACT) every action that changes the outside world is an `act_operations` row
with a deterministic operation key (kind, target, normalised payload) and external id; states proposed →
approved → executing → applied → verified, plus partial, unknown, failed and needs_refresh. Approval is an
owner action in an owner channel bound to a server-issued preview hash with a 24-hour expiry (P-4); the
owner's answer is stored in `act_cards.verdict` (renamed from `decision`, so it does not collide with the
entity name); high-risk cards need a second factor (BOT-11); MCP tools for external writes return the
preview and hash only. Handlers are registered per kind, declare
scopes and safety rules, read back before any retry after a timeout or 409, and mark "verified" only after
a successful read-back (P-8). Each kind is a `DATA_FLOWS.md` destination that ACT checks before executing.

### 6.4 Model gateway and taint propagation

Every call is `MDL.call(function, fragments[], purpose)`; each fragment carries its `dataclass` and
`sourceref`. The destination is the configured provider or, with the `llm` profile, the local endpoint.

1. **Registration.** A function is listed in `DATA_FLOWS.md` with the classes it may receive and its
   purpose; an unregistered function or an undeclared class fails CI and is refused at run time.
2. **Input check** with `POL.flow_allowed(class, destination, purpose)` per fragment. Journal fragments
   pass only for an analysis module whose journal switch is on (PRV-9), sealed entries never. Financial
   fragments pass per purpose (FIN-5); third-party tax ids, IBANs and invoice numbers are masked at every
   setting; secrets never pass. Tax figures are never fragments: the model phrases a template with
   placeholders, and TAX's renderer inserts each figure with its "estimate, not tax advice" label and pack
   version after the call.
3. **Record.** `sys_model_calls` keeps model, function, prompt version, input hash, classes sent, tokens,
   cost and duration. For journal input it keeps the module, entry ids and a content hash; such prompts
   are not retained and traces hold hashes only. Other prompts are kept ≤ 30 days (PRV-3).
4. **Taint.** The output takes the most restrictive input class (journal > financial > work > system);
   `sys_derivations` links it to every input. STO refuses a unit of work that stores an output in a table
   of a less restrictive class. A journal-class output lives only in journal-class tables and is shown
   only in owner channels — never indexed, never in MCP, the timeline, plans, dossiers or the status page —
   until the owner writes a work record about it themselves in an owner channel.
5. **Budget and compute-once.** An unchanged input with an unchanged prompt version is never sent again
   (P-7); the daily budget defers background work, with at most one call past it.

The canary suite plants a journal canary, runs every enabled analysis with the switch on and asserts that
neither the canary nor any output of those calls reaches search, MCP, the timeline, plans, the status page
or a work table; with the switch off, no model call contains the canary.

### 6.5 Worker job contract (STT and extraction)

Workers have no database and no network; they meet `core` through `sys_jobs` and the work directory.

1. `core` writes `work/jobs/<job_id>.json` by atomic rename: schema version, kind (`transcribe`; from 8.1a
   `extract`, local PDF text and OCR for financial documents), input path, parameters, limits. Bot audio
   is written to `work/audio/` by `core`.
2. The worker keeps a lease through a heartbeat file and writes `work/results/<job_id>.json` (and any
   artefacts) by atomic rename.
3. `core` validates the result against a JSON Schema with size limits, as untrusted data (P-10), and
   records completion in one unit of work. In the same step, right after the commit, it deletes the job
   file, the result file and the job's audio files. An out-of-memory kill is transient; the job is
   re-queued (SIG-3).
4. A watchdog purges any file in `work/` older than 10 minutes that belongs to no live lease, including
   leftovers of a crash between commit and deletion. `work/` is excluded from backups and is in the
   journal canary and erasure scope: a test kills the worker during a voice journal entry and finds no
   residue afterwards.

In production this is the `stt` container (inbox and models read-only, `work/` read-write, no network); in
native development the supervisor spawns the same worker as a subprocess pool.

### 6.6 Plugin contract

A plugin's manifest declares: id, version, hookspec range, licence, in or out of process, requested ports,
the `api` commands and queries it calls, its data flows (class × destination × purpose), its warning
text, and its `px_<id>_*` tables with their own migration ledger.

- **Plugins never open database connections.** In process, a plugin reads through the host's facade on a
  read connection whose authorizer allows only its own tables and declared queries (declared `pub_` views
  from stage 8). It writes by submitting units of work to the writer queue with the authorizer's owner set
  to `px_<id>`, or by calling a declared `api` command, which runs as the owning module's unit of work.
- **Out of process**, a plugin is a child process speaking versioned JSON-RPC over stdio: it gets its
  inputs in the request and returns data that `core` validates as untrusted and applies. It has no
  database path and no network unless a declared port provides one.
- Permissive licences in process, LGPL only unmodified, GPL only out of process (a conservative project
  rule, not a legal opinion on GPL boundaries). Off by default; enabling
  needs the warning acknowledged; undeclared flows are refused; a fitness test asserts that no plugin entry
  point can resolve the database path. R1 ships only the in-process host; the out-of-process host arrives
  with the GPL-isolated statement parsers (stage 8.7).

### 6.7 Device-agent contract

Agents (AGT, stage 6) hold a per-device token: listed, revocable, ingest-only, scoped to declared source
types. They buffer locally and send CloudEvents batches and resumable chunked uploads to INT over the
configured access recipe, idempotent by event id and content hash. The activity agent fetches the
direction list and the active classification rules from INT (served by RHY), classifies on the device and
sends aggregated spans with the rule version; window titles never leave the device and are purged there
after 90 days. `core` tags pushed text with device provenance, never treats it as an instruction, and
answers 503 with `Retry-After` during deploy holds.

### 6.8 Integration contract and admin API

- **External apps** (EXT-4): versioned HTTP + JSON on the `core` listener, with equivalent MCP tools —
  `read_brief(meeting_ref)`, `write_session`, `write_highlights`, `write_outcome`, each write with an
  idempotency key. Per-client scoped tokens; every call logged; responses checked for `app:<client>`; an
  outcome creates proposals, never commitments. The brief and the session carry the decision anchors of
  EXT-5: the decisions in play with up to five assumptions to probe, and decision, assumption and occasion
  references on what an app sends; everything an app sends about decisions is a proposal or a reading,
  never a state. Consumer contract tests run in CoFlow's CI against a reference consumer; a major change is
  a new endpoint.
- **Hosted apps** on a third-party platform never push into the host and never hold a credential of the
  instance (D-051): `core` pulls from them outbound with a read-only export token for one workspace the
  owner owns, acknowledgement being a separate right with its own token; pulls go by cursor, with size
  limits and a schema check, and never through a fallback host name whose TLS terminates on a third
  machine; pulled items are `untrusted_external` (PRV-14) and become proposals.
- **CLI:** every CLI write and every bulk import is a call to `core`'s loopback admin API (`/admin`) with
  a scoped token: `admin`, `import` (snapshot imports of the owner's existing system and bulk imports),
  `journal-write` (append only, cannot read) or `journal-read` (the owner's own terminal, never a
  forced-command key). If `core` is not running, the CLI starts an ephemeral `core` in process for the
  command, under the same instance lock, so there is never a second writer. Only `migrate`, `restore` and
  `drill` run without a live `core` in their target instance, under the OS-held instance lock that `core`
  also takes. A fitness test asserts that the CLI holds no database path while `core` runs.
- **Local AI clients** on the instance's own machine use `coflow mcp-stdio`, a shim that forwards stdio to
  the loopback MCP endpoint and never resolves the database path, so two clients on one machine share one
  `core`; clients on other machines use the SSH bridge (MCP-1, DEP-11).

### 6.9 Connector inbox and country packs

- **Connector inbox** (SIG-5): adapters produce normalised inbox JSON — format version, account, external
  refs, participants with external ids, messages, media refs, raw meta. SIG keeps the cursor; adapters
  never create people; schema drift is a visible error.
- **Country packs** (FIN-10) are data, immutable once released: rule rows with effective dates, an
  official source per row and a rule version. TAX computes only from pack rows and stores the pack version
  with every figure. Tax views are taxpayer-scoped: TAX reads one taxpayer's books through
  `FIN.taxpayer_entries`, the only default cross-book aggregation; sums across taxpayers are refused.

## 7. Data classes and where they are enforced

| Class | What | Stored in | May go to (switch) | Never |
|---|---|---|---|---|
| `journal` | Journal entries; voice journal transcripts; GOL formation transcripts and unapproved drafts; every model output derived from journal input | Journal-class tables only (`jrn_entries`, `gol_sessions`, `gol_drafts`, `gol_reflections`) | Provider or local model per analysis module (PRV-9); the bot as owner channel (its own row, since the messenger's servers see it); the local CLI | Index, MCP, timeline outside the owner's local view, dossiers, briefs, plans, work answers, event payloads, logs and traces (hashes only), status page, edge listener, incident packages |
| `financial` | Amounts, ledger, invoices, documents, tax figures | `fin_*`, `tax_*`, `px_imp_*`, `px_inv_*` | Provider per purpose — owner questions, weekly review, goal control, reminders (FIN-5); `mcp:<client>` per client; the bot; advisor export | A model: tax figures, unmasked third-party identifiers, raw documents (unless their own switch is on, after redaction), credentials |
| `work` | Everything else the owner works with | Domain tables | Provider, MCP clients, the bot, as listed | — |
| `untrusted_external` (a sub-class of work) | Text not written by the owner: satellite payloads, pulled app items, inbound messages, transcripts of other people's speech (PRV-14) | Every stored text field declares whether it may hold it | MCP clients on the owner's devices; cloud AI clients only if the owner enables it per client, then in a typed field with its provenance | An instruction to any tool, rule or approval; a record created from a satellite item without a proposal (P-3) |
| `system` | Ids, counters, costs, health, events | `sys_*` | Status page, logs | — |
| secrets | Tokens, keys, certificates | Secrets store, never the database | The adapter that needs them | Database, logs, backups, model calls |

`DATA_FLOWS.md` is generated from code declarations: class × destination × purpose × retention × switch
(PRV-2). Destinations: `provider`, `local_llm`, `mcp:<client>`, `messenger`, `app:<client>`, `device:<id>`,
`status_page`, `export`, `calendar`, `edge` (only the cloud view; never the journal; `untrusted_external`
withheld by default), `backup`. `coflow init` asks for the journal switch per analysis module with no
preselected answer and records the answer; the project's advice for new installations is "off"
(proposed, D-025), and the owner of each installation decides.

| Enforcement point | What it checks |
|---|---|
| Table registry and authorizer (STO) | Every table has an owner and a class; no output stored in a table of a less restrictive class |
| Event dispatcher (EVT) | Handlers receive only declared classes; payloads hold no values |
| Model gateway (MDL) | Input classes per function, purpose and switch; masking; tax placeholders; output taint |
| MCP response layer | Each result's classes against `mcp:<client>`; never the journal; withheld parts named in the coverage note |
| Bot renderer | Each answer's classes against `messenger`; tax figures only inside rendered, labelled blocks |
| Search and timeline projectors | No journal class; financial rows in a partition filtered by the requester's destination |
| Exports, INT, status page | `export`, `app:<client>`, `status_page` rows; the status page shows system data and aggregates only |
| Public projections (build-in-public material) | Only decisions marked public, or the owner's abstracted text for decisions marked publishable abstracted; a decision touching a third party's personal situation stays private; making a decision public is an owner-channel action (PRV-10) |
| `edge` cloud view (R2, stage-8 module 0) | `core` re-checks every class before the cloud view answers; `untrusted_external` text withheld and counted; the coverage note never reveals withheld journal items (MCP-5, PRV-13, PRV-14) |
| Logs and traces (OBS); work directory (STT) | Ids, hashes and error codes only; deletion on completion, watchdog purge, no backup |

## 8. Process view

Consistent with [DEPLOYMENT.md](DEPLOYMENT.md) §5 (D-019, D-020, D-023, D-024, D-050 to D-053); production
is the Compose project `coflow` on an always-on Linux host — for the author, a dedicated home laptop with a
GPU, which holds real data only after its 30-day gate (D-050, DEP-27).

- **`core`**: one container, one supervisor process, the only database writer. Its threads: the writer
  thread (the only write connection, running units of work from a queue); a pool of WAL read connections;
  the bot poller (long polling, no inbound port); the scheduler, event dispatcher, job dispatcher and ACT
  executor; in-process workers (summaries, calendar sync, projections, reviews) that prepare outside
  transactions; one HTTP listener, reachable only on loopback or the container network (published on the
  host's 127.0.0.1 only) and never internet-facing, for MCP, the status page, INT, the admin API,
  `/healthz` and `/readyz`; in-process plugins; out-of-process plugins as supervised child processes. It
  takes an OS-level instance lock on the data root. Its egress goes only to declared destinations: the
  messenger API, the model provider, the calendar provider and declared pull sources (PRV-12).
- **`stt`**: the stateless worker of §6.5; it may reserve the GPU, and falls back to CPU with a warning
  (DEP-25). **Profiles:** `backup` (outbound to the backup target only) and `llm` (a local model on an
  internal network, reached only by MDL's local adapter; it may also reserve the GPU, never `core`).
- **`edge`** (R2, stage-8 module 0; proposed, D-053): a separate container with its own route table and
  worker pool, holding no database and no secret except its TLS key, making no outbound requests, and
  calling only the internal cloud-view API of `core` over an `internal` network (PRV-13). TLS and the OAuth
  pages terminate here; the owner relay forwards encrypted traffic to it (DEP-12).
- **Outside the stack:** `coflow-updater`, the only thing that calls Docker (DEPLOYMENT §7);
  `coflow-bridge`, started per MCP client by an SSH forced command; the folder-sync tool filling the inbox.
- **Validation instance** (DEP-23; proposed, D-046): a non-production instance in the `validation` role on
  the owner's machine, run natively from stage 0A. It holds the one-way snapshot of the owner's existing
  system as read-only mirrors, with its data root outside any repository working tree; it never executes
  outward actions, polls no bot and uses no production token, and CI and the live evaluation harness refuse
  it. The owner's named real cases run on throw-away copies of its database (OPS-16). Its data reaches
  production only at the decision adoption gate, by a restore onto a host that passed its gate and a
  promote there (DEP-27); the host's staging instance and the validation instance are then retired, and
  the kinds the owner's existing system still owns are mirrored one way into production until stage 6.
- **Deploy holds** (DEPLOYMENT §7.4) pause bot polling, the ACT outbox, ingestion, MCP writes, collectors
  and the scheduler; deliveries and jobs survive restarts because their state is in the database.
- **Development** runs natively on Windows (and Linux in CI): `coflow init --role dev` once, then
  `coflow run`, starts the same supervisor with fakes and synthetic data and spawns the STT worker as a
  subprocess pool.

**Writer rule:** satellites never write. They return files (STT), forward calls (bridge, shim, `edge`),
send events and uploads (agents, apps) or return JSON-RPC results (plugins); `core` validates and applies
each one in its own short unit of work.

**Remote access** (D-052, D-053; the recipes in DEPLOYMENT §8). Three kinds of access reach the host, and
only one needs a public entry:

| Who | Path | Public entry | Stage |
|---|---|---|---|
| The owner from the phone, anywhere | The bot: `core` long-polls the messenger, outbound | None | 2 |
| The owner's devices (phone, a travelling laptop, desktop AI clients) | The overlay VPN with SSH and the stdio bridge; a second path through the relay tunnel (WireGuard inside WireGuard, keys only on the owner's devices) | None | 2 |
| Cloud AI clients (browser and phone), whose connections come from their operator's cloud | Owner relay → WireGuard tunnel opened by the host → `edge` → the cloud view of `core` | Two neutral host names on a separate domain | 8.0 |

The relay passes TLS through by server name and never decrypts: it holds no data, no TLS keys and no
application secrets, and its peer reaches only the edge port. TLS, OAuth and every check terminate on the
host. The relay is never an administration path of its own: the only administration that crosses it is
the owner's tunnel nested inside the relay tunnel, whose keys the relay does not hold, so the relay cannot
reach the host's SSH (DEP-11). Every
write carries an actor, a channel, an interaction id and an idempotency key from day one, so remote
clients and satellites retry safely.

## 9. Quality gate

1. **Module card**, from the template in [MODULES.md](MODULES.md), merged before the build starts. Its
   thresholds are the acceptance contract; changing one later needs a recorded decision.
2. **Build** with six test layers: property tests for invariants; module tests through `api` only, on a
   temp database with fake ports; contract tests between modules, run in the provider's CI; event and DTO
   schema snapshots; fault injection; privacy canaries under both journal-switch settings. The fitness
   functions of §5.3 run on every pull request on Windows and Linux.
3. **CI scorecard**, generated per module: each quality parameter → measured value → pass or fail, plus
   evaluation results for model-backed parts (code graders first; a regression subset on the fake provider;
   live runs only behind the flag and the budget). No number is entered by hand.
4. **Owner approval for high-risk cards.** The owner approves card and scorecard together before the first
   deploy that enables the module, for modules that hold money (FIN, TAX, IMP, INV), the journal (JRN,
   POL) or external writes (ACT, CAL, NEG), for the internet-facing edge (EDG), and for GOL and DEC (the
   decision core becomes the core data); the money modules (FIN, TAX) and the modules that
   write to the outside world (ACT, CAL, NEG, in the stage where they first write) also get two
   independent review rounds.
   Every other card is accepted through an all-green scorecard.
5. **Deploy** through the release path (from stage 0B): tag → signed image by digest → owner approval of
   the release (CLI in stages 0B–4, a bot card from stage 5) → staging before the switch-over, production
   after. Stage 0A runs natively in the `dev` and `validation` roles.
6. **Accept**: first on synthetic data against the card, and on the stage's named real cases in the
   validation instance (D-046); after the switch-over, a 28-day window on real
   data with SLIs from the module's own events on the status page and hard invariants at zero tolerance.
   An SLO missed two weeks in a row makes the next weekly stage on that module reliability-only; a usage
   signal below its floor leads to redesign, switch-off or removal (P-13).
7. **Episode**: what was built, the scorecard including failures, what was learned, what comes next —
   protocols, synthetic data and aggregate signals only, never the owner's centre, journal, money or
   third-party data.

Card states: drafted → approved (owner or CI) → built → accepted on synthetic data → in production (28-day
window passed) → kept or retired.

## 10. Build order

R1 is stages 0A–5, R2 stages 6–8. Deployment items follow DEPLOYMENT.md.

| Stage | Modules and contracts | Deployment |
|---|---|---|
| 0A Kernel and decision core | STO with the transaction log and the table registry, IDS (tap, prefix registry, foreign and burned numbers, aliases), EVT (events in the unit of work, in-process dispatch), POL (data classes, the canary fixture, the minimal literal gate), CFG minimum, OBS usage signals, `kernel.context` and `kernel.ports` (`DecisionDirectory`, `DecisionAttachmentProbe`, `EvidenceResolver`, `GoalDirectory` with a shadow adapter), OPS (`init` with the `dev` and `validation` roles, basic `doctor`), ADM, MCP on loopback with the local shim; DEC (DEC-1…4, DEC-6, DEC-11…20, the importer, the shadow report, the case runner, the adoption gate), CMT minimum (CMT-1) | None: native on Windows and Linux in CI; the validation instance on the owner's machine (DEP-23) |
| 0B Delivery and operations | EVT outbox delivery and scheduler; POL flow switches with the journal switch and the full literal gate; MDL (fake provider, cost ledger, budget, taint); CFG in full; OBS trace skeleton; OPS backup and restore, the supervisor importing the daily snapshot; import contracts, module map, card template, CI scorecard generator | Dockerfile, Compose, CI image build, suite in the image, Compose smoke test, tag → image by digest, a manual `coflow update <digest>` over SSH to any Linux Docker host (a VM is fine) |
| 1 Memory core with decision anchors | PPL; SIG sessions, messages, segments, quick log, connector contract, messenger export, `EvidenceResolver`; WRK tasks with `decision_ref`, directions and goals (WRK-1…3, WRK-8), `GoalDirectory` and the attachment probe; JRN storage and local entry; SRC; TML-1; POL derivation graph, erasers and the `untrusted_external` sub-class; OBS traces; MCP over the network and BRG with scoped tokens; real provider adapter behind the live flag | Deployed to the same Linux Docker host |
| 2 Telegram bot, daily rhythm, the decision loop in chat and the home laptop | BOT; ACT approval cards with step-up; RHY-1…3; WRK-6; EVT job leases; STT worker for voice; DEC-5, DEC-7, DEC-9 (the decision loop in the chat) | The home laptop in the staging role: the laptop profile, disk encryption, the GPU variant, travel mode, the relay tunnel as the second admin path, the egress allow-list; off-host heartbeat and alerts in two channels; overlay-VPN recipe; signature verification; the 30-day gate starts |
| 3 Capture, commitment proposals and the centre slice | CMT-2, DEC-17 (conversations), DEC-21, DEC-22, EXT-5; GOL-13, GOL-14 | — |
| 4 Sources | SIG recorder pipeline (folder sync) and contact proposals; CAL copy; PLG in process with TGC and MLR; STS; OBS health, SLIs and runtime scorecards | Disk-space policy (DEP-13); outage behaviour (DEP-15) |
| 5 Meetings and reliable execution | MTG; ACT outbox executor; CAL writes. **R1 complete** | Automatic rollback with write holds; bot approval card bound to the image digest |
| 6 Import and the switch-over of everything else to the home laptop | OPS export and import; INT with the decision anchors and pull connectors; AGT uploader and activity agent; RHY activity spans and rules; PPL merge, undo, forget; DEC external references (DEC-23), CMT delegated commitments (CMT-5) | Import of everything else into the production instance on the home laptop; promote only if the decision adoption has not happened, and only after the host gate (DEP-27); rebuild drill |
| 7 Learning loop | LRN-1…5; RHY-4; BOT-6 | SBOM and provenance attestations, arm64 image, repository-policy checks (DEP-20) |
| 8.0 Internet-facing MCP for cloud clients, read-only first | EDG; MCP-5 OAuth, pairing, the cloud view (PRV-13, PRV-14) | The owner relay recipe; the separate domain opened (CAA pinned to the host's ACME account) |
| 8.1a Money core | FIN: books, taxpayers, transfers, ledger, invoice register (file adapter), archive, targets (migrated from WRK), reports; `extract` jobs. Proposed: IMP's Norma 43 parser and one CSV profile pulled in, so the ledger reconciles | Legal opinion before public release (covers 8.1a and 8.1b) |
| 8.1b Country pack | TAX: pack interface, taxpayer-scoped calendar, reserve estimates, advisor export, warnings, rules-watch; ESP | Legal opinion before public release |
| 8.2 Centre and goals | GOL, with directions and goals transferred from WRK; LRN-6 reflection, the first consumer of the journal switch (position 2 confirmed, D-031) | — |
| 8.2b Inconsistency findings | ALN: think / say / do against the centre with evidence on both sides, "can't judge", planted evaluation set; the journal under PRV-9 | — |
| 8.3–8.5 | Send material (CMT-3); negotiation (NEG, after a spike); whole archive (TML-2) | — |
| 8.7 Statement import | IMP: camt.053, OFX, further CSV profiles; out-of-process plugin host | — |
| 8.8 Week plan and the rest | WPL; PPL-5, PPL-7; WRK-4 hypotheses (in GOL). INV adapters ship per tool at any time after 8.1a | — |
| Research | REL, CND (after a planned experiment gate, November 2026), EVO in `coflow_research`, on core data (REL-6), each with a pre-registered protocol | — |

## 11. What stays open

1. **Resolved on 4 October 2026:** the modular monolith (D-030) and the position of Centre and goals
   at stage-8 module 2 (D-031) are confirmed by the owner; on 18 October 2026 internet-facing MCP moved
   to the front of stage 8 (D-052).
2. **Money split** into a core module (8.1a) and a country-pack module (8.1b): proposed.
3. **Statement import in 8.1a** (Norma 43 and one CSV profile, so FIN reconciles at its own stage): proposed.
4. **Directions and goals** stay in WRK in R1 and move to GOL in 8.2 by one ownership-transfer migration
   with unchanged public ids; the alternative is a minimal GOL registry from stage 1.
5. **Switch defaults:** the journal switch is asked at `coflow init`; the financial defaults per destination
   and purpose are proposed in the FIN card and confirmed with module 1a.
6. **Money packaging and law:** a separate Spain data package per tax year (recommended); a short legal
   opinion before the money modules are published.
7. **Smaller items:** where `extract` jobs run (the `stt` container or a separate service, with 8.1a);
   whether the authorizer also runs in production (its overhead is measured in stage 0A); the reference
   CPU class for STT (`coflow bench stt`, DEPLOYMENT §14). The default thresholds in the cards are
   recalibrated once, after the first 28-day production window, through a recorded decision.
8. **The decision core's shape** (D-042 to D-049): the link ownership rule, the ports and the tier
   placement above are proposed; the sealed basis with editions under one number, the numbering and the
   decision link offered at entry were accepted on 18 October 2026.
9. **Health order** (D-044): the composite order and "the unverifiable share first" are proposed and wait
   for the owner.
10. **Adoption without the chat loop** (D-039): the adoption gate requires the stage-2 chat loop as the
    daily asking channel; a pull-only adoption would need a separate owner decision.
11. **Where adopted decisions live** (DEP-23, DEP-27): proposed — restored onto the production host once
    it has passed its gate; the owner may record an interim host.
