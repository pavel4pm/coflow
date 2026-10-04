# CoFlow 2.0 — Architecture

Version 0.1 · 4 October 2026 · **draft — nothing here is implemented yet**

How CoFlow 2.0 is cut into modules, how the modules talk, which rules keep them apart and how each one is
accepted. Requirement IDs refer to [REQUIREMENTS.md](REQUIREMENTS.md) (v0.4), decisions to
[DECISIONS.md](DECISIONS.md), the process view to [DEPLOYMENT.md](DEPLOYMENT.md). One card per module is in
[MODULES.md](MODULES.md). The decision behind this document is D-030; the principle is P-14.

In one paragraph: one owner per installation, one SQLite database, one writing process (`core`). Inside
`core` run about thirty bounded modules; each owns its tables, exposes an `api` of commands and queries,
and emits events. Outside `core` run only satellites without a database path: the speech-to-text worker,
the MCP stdio bridge, device agents, out-of-process plugins and the host-side updater. CI enforces the
boundaries (§5), and each module is accepted against its own card (§9).

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
| AP-3 | **No cross-module writes, foreign keys or copies** | References are public ids or `coflow:` refs, checked nightly. Data owned elsewhere is resolved at read time (a task stores `goal_ref`, never the goal's direction) |
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

## 3. Context

```
 OWNER DEVICES                                      EXTERNAL SERVICES (outbound from core only)
 +-------------------------------------+            +-------------------------------------------+
 | phone: messenger app                |            | messenger bot API (long polling)          |
 | desktop: AI clients (stdio over SSH)|            | model provider (as DATA_FLOWS.md allows)  |
 | terminal: coflow CLI (SSH)          |            | calendar provider (read / write tokens)   |
 | folder sync: recordings, exports    |            | invoicing tool: read-only API adapters    |
 | device agents (R2): uploader,       |            |   (plugin); its exports arrive as files   |
 |   activity agent -> INT             |            | image registry (pull by digest)           |
 +------------------+------------------+            | off-host backup storage, dead-man switch  |
                    | SSH over the overlay VPN,     +---------------------^---------------------+
                    | encrypted folder sync                               |
 +------------------v-----------------------------------------------------+---------------------+
 | HOST: Linux, Docker Engine                                                                   |
 |  coflow-updater (systemd timer; pulls, verifies, deploys after the owner approves)           |
 |  coflow-bridge  (SSH forced command; stdio <-> core's MCP on 127.0.0.1 with a client token)  |
 |  +----------------------------------------------------------+  job files  +----------------+ |
 |  | core: one supervisor process, the only database writer   |<----------->| stt: no network| |
 |  |  interfaces  BOT  MCP  STS  INT  ADM   (host 127.0.0.1)  |  work/ dir  | no database    | |
 |  |  domain      PPL SIG JRN WRK DEC CMT CAL MTG RHY LRN     |             +----------------+ |
 |  |              SRC TML FIN TAX GOL                         |             +----------------+ |
 |  |  kernel      STO IDS EVT POL MDL ACT CFG OBS OPS         |------------>| llm (profile)  | |
 |  |  plugin host: in-process plugins (px_<id>_ tables)       |             +----------------+ |
 |  |  child processes: out-of-process plugins (JSON-RPC)      |             | backup (prof.) | |
 |  |  SQLite (WAL) on the data volume                         |             +----------------+ |
 |  +----------------------------------------------------------+                                |
 +----------------------------------------------------------------------------------------------+
```

The owner's channels are the private bot chat and the local CLI on the host. MCP is not an owner channel:
a tool argument may have been written by the client's model, so MCP can create drafts and execute logged,
undoable internal writes, but it never approves anything (P-4, MCP-4).

## 4. Module map

Stage numbers follow the roadmap; "8.1a" is stage 8, module 1a. Kernel tables use `sys_*` and are
registered per kernel module; ACT and CFG use their own prefixes; domain modules use their code as prefix;
plugins use `px_<id>_*`. The authorizer checks the table registry, not the prefix.

| Group | Code | Module | Owns | Release · stage | Runs in |
|---|---|---|---|---|---|
| Kernel | STO | Storage and migrations | `sys_meta`, `sys_migrations`, `sys_table_registry` | R1 · 0 | `core` (writer thread) |
| Kernel | IDS | Identity and numbering | `sys_id_*`, `sys_content_ids` | R1 · 0 | `core` |
| Kernel | EVT | Events, outbox, jobs, scheduler | `sys_events`, `sys_event_deliveries`, `sys_jobs`, `sys_schedules` | R1 · 0 (outbox, scheduler), 2 (jobs) | `core` |
| Kernel | POL | Privacy and data flows | `sys_dataflow_switches`, `sys_derivations`, `sys_tombstones`, `sys_deletion_log`, `sys_retention_runs`, `sys_secrets_inventory` | R1 · 0, 1 (erasure) | `core` |
| Kernel | MDL | Model gateway | `sys_model_calls`, `sys_prompts`, `sys_budget`, `sys_eval_runs` | R1 · 0 | `core`; optional `llm` |
| Kernel | ACT | Approvals, external-action outbox, undo | `act_*` | R1 · 2 (cards), 5 (outbox) | `core` |
| Kernel | CFG | Owner profile and locale | `cfg_*` | R1 · 0 | `core` |
| Kernel | OBS | Traces, health, scorecards | `sys_traces`, `sys_trace_steps`, `sys_health`, `sys_sli_samples`, `sys_usage_signals`, `sys_scorecards` | R1 · 0 (trace skeleton), 1 (traces), 4 | `core` |
| Kernel | OPS | Instance, backups, export, deploy state | `sys_instance`, `sys_backups`, `sys_deploys`, `sys_holds`, `sys_exports` | R1 · 0, 2, 5; R2 · 6 | `core`; CLI through ADM |
| Domain | PPL | People and companies | `ppl_*` | R1 · 1; R2 · 6, 8.8 | `core` |
| Domain | SIG | Signals: sessions, messages, recordings | `sig_*` | R1 · 1, 4 | `core`; audio in `stt` |
| Domain | JRN | Journal | `jrn_entries` | R1 · 1 | `core` |
| Domain | WRK | Work: tasks; directions and goals until 8.2 | `wrk_*` | R1 · 1, 2 | `core` |
| Domain | DEC | Decisions | `dec_*` | R1 · 3; R2 · 7 | `core` |
| Domain | CMT | Commitments | `cmt_*` | R1 · 3; R2 · 8.3 | `core` |
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
| Interfaces | MCP | MCP server | `mcp_*` | R1 · 1; R2 · 8.6 (remote) | `core` |
| Interfaces | STS | Status page | — | R1 · 4 | `core` |
| Interfaces | INT | Integration and ingestion API | `int_*` | R2 · 6 | `core` |
| Interfaces | ADM | Admin API and CLI | `adm_tokens` | R1 · 0 | `core` listener; CLI client |
| Satellites | STT | Speech-to-text and extraction worker | files in `work/` only | R1 · 2; R2 · 8.1a (extract) | `stt` container |
| Satellites | BRG | MCP stdio bridge | — | R1 · 1 | host, SSH forced command |
| Satellites | AGT | Device agents | a buffer on the device | R2 · 6 | owner's desktop |
| Satellites | UPD | Updater | host files | R1 · 0 (manual), 2, 5 | host, outside the stack |
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
 coflow.modules        tier 7  gol
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
| `GoalDirectory`: exists, direction of, active goals, likely goals (WRK-8) | WRK until 8.2, then GOL | WRK, DEC, CMT, FIN, MTG, RHY, SIG |
| `ReviewContributor`: a section of the weekly review | WRK (control view), GOL (control list, reflection) | RHY |
| `Eraser`: purge what a source left in my tables | every module that stores derived data | POL |
| `UndoHandler`: the inverse of an MCP write | every module with MCP write tools | ACT |
| `OperationHandler`: one kind of external effect | CAL, CMT (material send), NEG, OPS (deploy approval) | ACT |
| `HealthProbe`, `Projector` | modules with health checks or read models | OBS, EVT |

Cycles found in review are removed this way: the interaction context lives in the leaf `kernel.context`,
so EVT never imports OBS (OBS subscribes to events); contact proposals are extracted and stored in SIG, so
PPL never reads SIG; PPL takes script variants from CFG's locale pack, never from SRC; RHY takes GOL's
review sections through a port, so RHY never imports GOL.

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
layers = gol
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
forbidden_modules = coflow.adapters   # plus every provider SDK and HTTP client, listed in stage 0
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
| `source`, `subject` | `coflow://<instance_id>/<mod>`; the public id or `coflow:` ref of the entity |
| `time`, `dataversion` | UTC; an integer |
| `correlationid`, `causationid` | The interaction id (OPS-10); the triggering event or command |
| `actor`, `dataclass` | As in §6.1; `journal`, `financial`, `work` or `system` |
| `sourceref` | The originating message, segment, recording or file, as a `coflow:` ref |
| `data` | `entity` (type) and `changed` (field names). **Never field values** |

- Consumers read current state through the owner's `api`: a status change says `changed: ["status"]`.
- Delivery runs after commit, once per declared handler, tracked in `sys_event_deliveries`; handlers are
  idempotent by (event id, handler); retries back off, then dead-letter to the status page.
- A handler receives only the classes it declared. Journal-class events (id only) go to POL and, for
  counting, to OBS; no other handler declares the journal class.
- Delivered events are **pruned after 30 days**; both event tables are in every erasure and in the canary
  scope. No upcasters: a breaking change bumps `dataversion`, and handlers accept the current and the
  previous version for one release.

### 6.3 The two outboxes

The **event outbox** (EVT) is §6.2: a state change commits if and only if its event row exists. In the
**external-action outbox** (ACT) every action that changes the outside world is an `act_operations` row
with a deterministic operation key (kind, target, normalised payload) and external id; states proposed →
approved → executing → applied → verified, plus partial, unknown, failed and needs_refresh. Approval is an
owner action in an owner channel bound to a server-issued preview hash with a 24-hour expiry (P-4); MCP
tools for external writes return the preview and hash only. Handlers are registered per kind, declare
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
  outcome creates proposals, never commitments. Consumer contract tests run in CoFlow's CI against a
  reference consumer; a major change is a new endpoint.
- **CLI:** every CLI write and every bulk import is a call to `core`'s loopback admin API (`/admin`) with
  a scoped token: `admin`, `import`, `journal-write` (append only, cannot read) or `journal-read` (the
  owner's own terminal, never a forced-command key). Only `migrate`, `restore` and `drill` run without a
  live `core` in their target instance, under the OS-held instance lock that `core` also takes. A fitness
  test asserts that the CLI holds no database path while `core` runs.

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
| `system` | Ids, counters, costs, health, events | `sys_*` | Status page, logs | — |
| secrets | Tokens, keys, certificates | Secrets store, never the database | The adapter that needs them | Database, logs, backups, model calls |

`DATA_FLOWS.md` is generated from code declarations: class × destination × purpose × retention × switch
(PRV-2). Destinations: `provider`, `local_llm`, `mcp:<client>`, `messenger`, `app:<client>`, `device:<id>`,
`status_page`, `export`, `calendar`, `edge`, `backup`. `coflow init` asks for the journal switch per
analysis module with no preselected answer and records the answer; the project's advice for new
installations is "off" (proposed, D-025), and the owner of each installation decides.

| Enforcement point | What it checks |
|---|---|
| Table registry and authorizer (STO) | Every table has an owner and a class; no output stored in a table of a less restrictive class |
| Event dispatcher (EVT) | Handlers receive only declared classes; payloads hold no values |
| Model gateway (MDL) | Input classes per function, purpose and switch; masking; tax placeholders; output taint |
| MCP response layer | Each result's classes against `mcp:<client>`; never the journal; withheld parts named in the coverage note |
| Bot renderer | Each answer's classes against `messenger`; tax figures only inside rendered, labelled blocks |
| Search and timeline projectors | No journal class; financial rows in a partition filtered by the requester's destination |
| Exports, INT, status page | `export`, `app:<client>`, `status_page` rows; the status page shows system data and aggregates only |
| Logs and traces (OBS); work directory (STT) | Ids, hashes and error codes only; deletion on completion, watchdog purge, no backup |

## 8. Process view

Consistent with [DEPLOYMENT.md](DEPLOYMENT.md) §5 (D-019, D-020, D-023, D-024); production is the Compose
project `coflow` on an always-on Linux host.

- **`core`**: one container, one supervisor process, the only database writer. Its threads: the writer
  thread (the only write connection, running units of work from a queue); a pool of WAL read connections;
  the bot poller (long polling, no inbound port); the scheduler, event dispatcher, job dispatcher and ACT
  executor; in-process workers (summaries, calendar sync, projections, reviews) that prepare outside
  transactions; one HTTP listener, reachable only on loopback or the container network (published on the
  host's 127.0.0.1 only), for MCP, the status page, INT, the admin API, `/healthz` and `/readyz`;
  in-process plugins; out-of-process plugins as supervised child processes.
- **`stt`**: the stateless worker of §6.5. **Profiles:** `backup` (outbound to the backup target only) and
  `llm` (a local model on an internal network, reached only by MDL's local adapter).
- **Outside the stack:** `coflow-updater`, the only thing that calls Docker (DEPLOYMENT §7);
  `coflow-bridge`, started per MCP client by an SSH forced command; the folder-sync tool filling the inbox.
- **Deploy holds** (DEPLOYMENT §7.4) pause bot polling, the ACT outbox, ingestion, MCP writes, collectors
  and the scheduler; deliveries and jobs survive restarts because their state is in the database.
- **Development** runs natively on Windows (and Linux in CI): `coflow run --role dev` starts the same
  supervisor with fakes and synthetic data and spawns the STT worker as a subprocess pool.

**Writer rule:** satellites never write. They return files (STT), forward calls (bridge), send events and
uploads (agents, apps) or return JSON-RPC results (plugins); `core` validates and applies each one in its
own short unit of work.

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
   POL) or external writes (ACT, CAL, NEG), and for GOL; the money modules (FIN, TAX) and the modules that
   write to the outside world (ACT, CAL, NEG, in the stage where they first write) also get two
   independent review rounds.
   Every other card is accepted through an all-green scorecard.
5. **Deploy** through the release path: tag → signed image by digest → owner approval of the release (CLI
   in stages 0–4, a bot card from stage 5) → staging before the switch-over, production after.
6. **Accept**: first on synthetic data against the card; after the switch-over, a 28-day window on real
   data with SLIs from the module's own events on the status page and hard invariants at zero tolerance.
   An SLO missed two weeks in a row makes the next weekly stage on that module reliability-only; a usage
   signal below its floor leads to redesign, switch-off or removal (P-13).
7. **Episode**: what was built, the scorecard including failures, what was learned, what comes next —
   protocols, synthetic data and aggregate signals only, never the owner's centre, journal, money or
   third-party data.

Card states: drafted → approved (owner or CI) → built → accepted on synthetic data → in production (28-day
window passed) → kept or retired.

## 10. Build order

R1 is stages 0–5, R2 stages 6–8. Deployment items follow DEPLOYMENT.md.

| Stage | Modules and contracts | Deployment |
|---|---|---|
| 0 Minimal kernel | STO, IDS, EVT (outbox, in-process dispatch, scheduler for kernel jobs), POL (data classes, flow switches with the journal switch, canary framework, literal gate), MDL (fake provider, cost ledger, budget, taint), CFG, OBS (trace skeleton), `kernel.context`, OPS and ADM (`init`, `doctor`, backup, restore), import contracts, module map, card template, CI scorecard generator | Dockerfile, Compose, CI image build, suite in the image, Compose smoke test, tag → image by digest, a manual `coflow update <digest>` over SSH to any Linux Docker host (a VM is fine) |
| 1 Memory core | PPL; SIG sessions, messages, segments, quick log, connector contract, messenger export; WRK tasks, directions and goals (WRK-1…3, WRK-8); JRN storage and local entry; SRC; TML-1; POL derivation graph and erasers; OBS traces; MCP over HTTP and BRG with scoped tokens; real provider adapter behind the live flag | Deployed to the same Linux Docker host |
| 2 Bot and rhythm | BOT; ACT approval cards; RHY-1…3; WRK-6; EVT job leases; STT worker for voice | Physical home host in the staging role; off-host heartbeat; overlay-VPN recipe; signature verification |
| 3 Decisions, commitments | DEC-1…4; CMT-1, CMT-2 | — |
| 4 Sources | SIG recorder pipeline (folder sync) and contact proposals; CAL copy; PLG in process with TGC and MLR; STS; OBS health, SLIs and runtime scorecards | Disk-space policy (DEP-13); outage behaviour (DEP-15) |
| 5 Meetings, execution | MTG; ACT outbox executor; CAL writes. **R1 complete** | Automatic rollback with write holds; bot approval card bound to the image digest |
| 6 Switch-over | OPS export and import; INT; AGT uploader and activity agent; RHY activity spans and rules; PPL merge, undo, forget | Import, switch-over and promote on the home host; rebuild drill |
| 7 Learning loop | LRN-1…5; RHY-4; DEC-5; BOT-6 | SBOM and provenance attestations, arm64 image, repository-policy checks (DEP-20) |
| 8.1a Money core | FIN: books, taxpayers, transfers, ledger, invoice register (file adapter), archive, targets (migrated from WRK), reports; `extract` jobs. Proposed: IMP's Norma 43 parser and one CSV profile pulled in, so the ledger reconciles | Legal opinion before public release (covers 8.1a and 8.1b) |
| 8.1b Country pack | TAX: pack interface, taxpayer-scoped calendar, reserve estimates, advisor export, warnings, rules-watch; ESP | Legal opinion before public release |
| 8.2 Centre and goals | GOL, with directions and goals transferred from WRK; LRN-6 reflection, the first consumer of the journal switch (position 2 confirmed, D-031) | — |
| 8.2b Inconsistency findings | ALN: think / say / do against the centre with evidence on both sides, "can't judge", planted evaluation set; the journal under PRV-9 | — |
| 8.3–8.6 | Send material (CMT-3); negotiation (NEG, after a spike); whole archive (TML-2); remote MCP (MCP-5) | Edge recipe with 8.6 |
| 8.7 Statement import | IMP: camt.053, OFX, further CSV profiles; out-of-process plugin host | — |
| 8.8 Week plan and the rest | WPL; PPL-5, PPL-7; WRK-4 hypotheses (in GOL). INV adapters ship per tool at any time after 8.1a | — |
| Research | REL, CND (after a planned experiment gate, November 2026), EVO in `coflow_research`, on core data (REL-6), each with a pre-registered protocol | — |

## 11. What stays open

1. **Resolved on 4 October 2026:** the modular monolith (D-030) and the position of Centre and goals
   at stage-8 module 2 (D-031) are confirmed by the owner.
2. **Money split** into a core module (8.1a) and a country-pack module (8.1b): proposed.
3. **Statement import in 8.1a** (Norma 43 and one CSV profile, so FIN reconciles at its own stage): proposed.
4. **Directions and goals** stay in WRK in R1 and move to GOL in 8.2 by one ownership-transfer migration
   with unchanged public ids; the alternative is a minimal GOL registry from stage 1.
5. **Switch defaults:** the journal switch is asked at `coflow init`; the financial defaults per destination
   and purpose are proposed in the FIN card and confirmed with module 1a.
6. **Money packaging and law:** a separate Spain data package per tax year (recommended); a short legal
   opinion before the money modules are published.
7. **Smaller items:** where `extract` jobs run (the `stt` container or a separate service, with 8.1a);
   whether the authorizer also runs in production (its overhead is measured in stage 0); the reference
   CPU class for STT (`coflow bench stt`, DEPLOYMENT §14). The default thresholds in the cards are
   recalibrated once, after the first 28-day production window, through a recorded decision.
