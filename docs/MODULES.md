# CoFlow 2.0 — Modules

Version 0.1 · 4 October 2026 · **draft — nothing here is implemented yet**

One card per module: what it owns, what it offers, what it needs, and the numbers it must meet to be
accepted (P-14, NFR-10). How the modules fit together — layers, contracts, data classes, process view,
the quality gate and the build order — is in [ARCHITECTURE.md](ARCHITECTURE.md). Requirement IDs refer to
[REQUIREMENTS.md](REQUIREMENTS.md) v0.4 and [DEPLOYMENT.md](DEPLOYMENT.md).

---

## How to read a card

| Field | Meaning |
|---|---|
| Release · stage | R1, R2, Plugin or Research, and the roadmap stage; "8.1a" is stage 8, module 1a |
| Runs in | `core` (the writing process), a satellite process, or the owner's device |
| Owns | The tables this module alone writes. Kernel tables are `sys_*`, registered per module; domain modules use their code as prefix; plugins use `px_<id>_*` |
| Commands · Queries | The module's `api`: commands write (one unit of work each), queries read (with `as_of` and coverage). Names only; signatures live in code |
| Emits · consumes | Event types `coflow.<mod>.<entity>.<verb>`; payloads carry ids and changed-field names only |
| Depends on | The `api` of modules in lower tiers, and kernel ports (ARCHITECTURE §5) |
| Requirements | IDs this module delivers, wholly or in part |
| Data classes · DATA_FLOWS | The class of the owned tables and the `DATA_FLOWS.md` rows the module declares |
| Quality parameters | 2–7 attributes (ISO/IEC 25010 names), each with a metric and a threshold that a test, an evaluation set or a drill checks. Where a requirement said "measured", the card states a default number |
| Acceptance suite | What runs in isolation: a temp database, fakes for every port, synthetic fixtures, other modules only through their `api` |
| Usage signal | What shows the module is used, and the floor below which it is redesigned or removed (P-13) |
| Approval | **Owner** for modules that hold money, the journal or external writes, and for GOL; otherwise **CI scorecard** |

A card's thresholds become binding when the card is merged, before the build starts; changing one later
needs a recorded decision. Cards move through: drafted → approved → built → accepted on synthetic data →
in production (28-day window passed) → kept or retired.

**Applies to every card and is not repeated:** the fitness functions of ARCHITECTURE §5.3; the journal
canary under both switch settings; every table registered with an owner and a data class; no model or
network call inside a write transaction; idempotency keys on every retried command; an undo handler or a
"not undoable" mark on every command reachable over MCP.

### Template

```markdown
### <CODE> — <Module name>

<Purpose in two or three sentences.>

| Field | Value |
|---|---|
| Release · stage | |
| Runs in | |
| Owns | |
| Commands | |
| Queries | |
| Emits · consumes | |
| Depends on | |
| Requirements | |
| Data classes · DATA_FLOWS | |
| Acceptance suite | |
| Usage signal | |
| Approval | |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| | | |
```

### Approval at a glance

| Approval | Modules |
|---|---|
| Owner (card and scorecard, before the first deploy that enables the module) | FIN, TAX (with ESP), IMP, INV — money; JRN, POL — journal; ACT, CAL, NEG — external writes; GOL |
| CI scorecard (all green) | Every other module |

## Ported from v1

The new repository ports proven v1 capabilities one module at a time, with tests and synthetic fixtures;
v1's code history is not published (D-003). The table names the v1 capability each module carries over,
or "new", and the lessons from v1 it must honour ([LESSONS_FROM_V1.md](LESSONS_FROM_V1.md), by section).
What v1 built but nobody used is not ported (REQUIREMENTS §7).

| Module | Ports from v1 | Lessons it carries |
|---|---|---|
| STO | The SQLite layer: WAL mode, initialisation once per code and schema revision, the long-transaction watchdog; hand-written migrations become numbered ones | §2 |
| IDS | The single numbering tap and its concurrency tests; content-hash identity of files; machine-readable labels in event titles and file names | §3, §5 |
| EVT | New; its scheduler replaces v1's operating-system scheduler jobs | §8 |
| POL | Rule-based routing between work and journal, "this was journal" blanking, the deletion log, the privacy canaries of the bot evaluation | §4 |
| MDL | The model layer: model choice by role, prompt caching, the cost log with prompt version and input hash; the offline bot evaluation | §7 |
| ACT | Approval cards executed once; calendar writes with deterministic ids and read-back, as in the week plan | §5 |
| CFG | New (v1 kept owner settings in code and prompts) | — |
| OBS | The model-call and change logs; usage pulses of screens; health and the off-host heartbeat are new | §1, §6, §9 |
| OPS | Daily snapshots and the worker's command-line operations; instance roles, restore drills and fencing are new | §8, §9 |
| PPL | The people registry with `resolve_or_create_person`, temporal facts with quotes, deterministic dossiers, contact proposals, companies | §3 |
| SIG | The recorder pipeline (inbox to session, chunking, retries, the night archive queue), chats as sessions, voice notes as text, one-sentence logs of calls | §6 |
| JRN | The private journal: entries by explicit marker, no index, no tools | §4 |
| WRK | Directions, goals and tasks with a status log and a ball holder; goal moves without copies | §1 |
| DEC | Decision records with grounds, monitored assumptions and computed health | — |
| CMT | Commitments with a due date and a quote; v1's unreviewed proposal queue is not ported | §1 |
| CAL | The read-only calendar copy, free slots and approved calendar writes | §5 |
| MTG | Meetings as intents linked to work, briefs, recording-to-meeting linking, outcomes | §5 |
| RHY | The morning plan with a deterministic ranking, evening plan vs. fact, close the day; activity spans | §7 |
| LRN | New (a preference memory was planned in v1) | — |
| SRC | Full-text search with deterministic row ids, cross-script matching, rule-based entities | §2, §7 |
| TML | New (v1's timeline page was barely used) | — |
| FIN, TAX | New (v1 had no ledger) | — |
| GOL | The versioned manifest, principles and strategy documents — the documents, not v1's compliance engines | §7 |
| BOT | The Telegram bot: owner only, work by default and journal by marker, compact answers with dossiers, approval cards, notifications, local transcription of voice | §4, §7 |
| MCP | The context-oriented MCP server, the explicit read-only tool list, the catalogue generated from code | §4, §8, §9 |
| STS | The recorder status page, one of the two web pages in use | §1 |
| INT | v1's MCP bridge for external apps (a brief in; a session, highlights and an outcome out); the ingestion API is new | §9 |
| ADM | New (v1 could be administered only physically) | §9 |
| STT | Local CPU transcription with chunking at silences and a memory check | §6 |
| BRG | New; it replaces v1's local stdio mode for a remote host | §9 |
| AGT | The Windows activity agent (spans, no screenshots, titles purged after 90 days); the uploader is new | §7, §9 |
| UPD | New (v1 deployed by a manual pull plus a script) | §8, §9 |
| PLG | New | — |
| TGC | The read-only Telegram user-session collector for marked chats, with voice and video notes | — |
| MLR | Mail read: threads the owner wrote or with registry counterparts, read-only scope | — |
| IMP, INV, ESP | New | — |
| NEG | New (planned in v1) | — |
| WPL | The week plan applied to the calendar with one approval | §5 |
| ALN | Not ported: v1's compliance, convergence and corridor engines; the idea returns as module 2b with evidence rules | §7 |
| REL, CND, EVO | New; v1's knowledge graph is not ported | §1 |

---

## Kernel

### STO — Storage and migrations

The single writer and the schema: runs units of work on the writer thread, hands out read connections,
applies migrations, keeps the table registry and runs the writer watchdog.

| Field | Value |
|---|---|
| Release · stage | R1 · 0 |
| Runs in | `core`, writer thread |
| Owns | `sys_meta` (schema version, code revision), `sys_migrations` (file, module tag, checksum), `sys_table_registry` (table, owner, data class) |
| Commands | `submit_unit_of_work` (kernel only), `apply_migrations` (admin, `core` stopped, snapshot first), `checkpoint` |
| Queries | `schema_version`, `table_registry`, `writer_stats` (queue depth, longest transaction) |
| Emits · consumes | `coflow.sto.migration.applied` · none |
| Depends on | `kernel.context` |
| Requirements | P-1, P-14, OPS-3, OPS-4, NFR-4, NFR-8, DEP-6 |
| Data classes · DATA_FLOWS | system · no outbound flow |
| Acceptance suite | Fault-injection harness (process killed at random points) on a temp database; migration replay from the previous release; authorizer harness |
| Usage signal | Kernel: writer queue depth and transaction times on the status page |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Reliability (crash safety) | Integrity-check failures and partial units over 1,000 fault-injection runs | 0 and 0 |
| Performance efficiency | Write-transaction duration in the load suite | p99 < 100 ms, max < 1 s; every hold > 10 s logged |
| Maintainability (ownership) | Writes outside the unit owner's registered tables, over the full suite and every migration | 0 |
| Compatibility (upgrade) | Previous release's schema upgraded vs. a clean install (`sqldiff`) | Empty diff |
| Security (one writer) | Entry points other than `core` able to resolve the database path while `core` runs | 0 |
| Security (classes) | Units of work that store an output in a table of a less restrictive data class | 0 (refused) |

### IDS — Identity and numbering

One numbering tap for every public id and one prefix registry; content-hash identity for files and
statement lines; machine-readable labels in external artifacts.

| Field | Value |
|---|---|
| Release · stage | R1 · 0 |
| Runs in | `core` |
| Owns | `sys_id_sequence`, `sys_id_prefixes`, `sys_id_burned`, `sys_content_ids` (hash, kind, public ref) |
| Commands | `issue_id(prefix)` (inside the caller's unit of work), `burn_id`, `register_content(hash, kind)` |
| Queries | `prefix_registry`, `render_label`, `parse_label`, `lookup_content(hash)` |
| Emits · consumes | `coflow.ids.id.burned` · none |
| Depends on | STO |
| Requirements | IDN-1, IDN-2, IDN-6, IDN-7 |
| Data classes · DATA_FLOWS | system · no outbound flow |
| Acceptance suite | Concurrency test with 8 threads on a temp database; property tests for labels; content-identity fixtures |
| Usage signal | Kernel: ids issued per prefix per week |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Functional correctness | Duplicate or reused ids after 1,000 concurrent issues from 8 threads, burned ids included | 0 |
| Security (registry) | Issues with an unregistered prefix that are accepted | 0 |
| Functional correctness (labels) | `parse_label(render_label(id)) = id` over 10,000 generated cases, every prefix | 100 % |
| Functional correctness (content) | Source records after the same file is imported twice, renamed or re-sent | Exactly 1 |

### EVT — Events, outbox, jobs and scheduler

The transactional event outbox with per-handler delivery; the job table shared by in-process and
satellite workers; the scheduler that replaces operating-system scheduler entries (OPS-2).

| Field | Value |
|---|---|
| Release · stage | R1 · 0 (outbox, in-process dispatch, scheduler for kernel jobs such as the daily backup and retention); 2 (worker jobs and leases) |
| Runs in | `core` |
| Owns | `sys_events` (envelope, ids only), `sys_event_deliveries`, `sys_jobs` (kind, input ref, state, lease, result ref), `sys_schedules` |
| Commands | `publish` (inside a unit of work), `retry_delivery`, `prune_delivered`, `enqueue_job`, `claim_job` / `complete_job` / `fail_job` (core-side dispatcher), `register_schedule` |
| Queries | `delivery_lag`, `dead_letters`, `job_status` (with the "why it waits" reason), `schedule_next` |
| Emits · consumes | `coflow.evt.delivery.dead_lettered`, `coflow.evt.job.failed` · every event, dispatched to declared handlers by declared class |
| Depends on | STO, `kernel.context` |
| Requirements | P-7, P-14, NFR-8, OPS-2, SIG-3 (retry schedule) |
| Data classes · DATA_FLOWS | system (each envelope carries the class of its subject) · no outbound flow |
| Acceptance suite | Fault injection (crash after commit before handling, handler exceptions, restarts); property test of atomicity; schema scan of every event type |
| Usage signal | Kernel: delivery lag and dead letters on the status page |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Reliability (delivery) | Lost events and double effects over 500 fault-injection runs | 0 and 0 |
| Functional correctness (atomicity) | Property test: a state change committed without its event row, or the reverse | 0 |
| Security (payloads) | Event schemas with a field other than ids, entity type and changed-field names; canary values found in `sys_events` | 0 and 0 |
| Reliability (retention) | Delivered events older than 30 days at the nightly check | 0 |
| Performance efficiency | Delivery lag from commit to handler completion | p95 ≤ 5 s; dead letters on the status page within 5 min (from stage 4) |

### POL — Privacy and data flows

Data classes and the `DATA_FLOWS.md` switches, including the journal switch; the derivation graph;
erasure (delete a source, "this was journal", forget a person); retention; the secrets inventory; the
literal gate and the canary framework.

| Field | Value |
|---|---|
| Release · stage | R1 · 0 (classes, switches, canary, literal gate); 1 (derivations, erasure); R2 · 6 (forget a person) |
| Runs in | `core` |
| Owns | `sys_dataflow_switches` (class × destination × purpose → off / on), `sys_derivations` (output ref → input refs), `sys_tombstones`, `sys_deletion_log` (ids and hashes, no content), `sys_retention_runs`, `sys_secrets_inventory` (names only) |
| Commands | `set_flow_switch` (owner channel only), `record_derivation` (inside a unit of work), `erase_source`, `blank_as_journal`, `forget_person`, `run_retention` |
| Queries | `flow_allowed(class, destination, purpose)`, `data_flows_report` (generates `DATA_FLOWS.md`), `derivations_of`, `deletion_log`, `retention_state` |
| Emits · consumes | `coflow.pol.erasure.completed`, `coflow.pol.flow.changed` · journal-class events (bookkeeping only) |
| Depends on | STO, EVT; `Eraser` implementations registered by every module that stores derived data |
| Requirements | P-2, P-10, P-11, P-12, PRV-1, PRV-2, PRV-4, PRV-7, PRV-9, BOT-3 (mechanism), PPL-6 (mechanism), NFR-6, NFR-9 |
| Data classes · DATA_FLOWS | system · generates the whole document from code declarations; every switch change is logged |
| Acceptance suite | The canary suite, run twice (journal switch off and on) over every channel, table, index, plan, event table, log, trace and the worker directory; erasure fixtures over every registered eraser |
| Usage signal | Erasures and switch changes per month (counts only) |
| Approval | **Owner** |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Security (journal switch) | Canary entries (one normal, one sealed) in model calls | Off: 0 calls contain either. On: only calls of enabled modules contain the normal one; none contains the sealed one |
| Security (hard bans and taint) | Journal canary, or any output of a call with journal input, in search, MCP, the timeline, plans, dossiers, the status page, event payloads, logs or work tables | 0 under both settings |
| Safety (erasure) | Canary residue after `erase_source`, `blank_as_journal`, `forget_person` over every table, the index, plan snapshots, event tables and `work/` | 0 after the purge; tombstoned rows hidden from reads in the same transaction |
| Safety (retention) | Financial documents deleted before their retention date through any erasure path | 0 (refused with reason and date) |
| Functional completeness | Model functions, tables, outbound hosts and MCP tools not registered in `DATA_FLOWS.md` or the registry | 0 (CI fails) |
| Security (literals, secrets) | Literal-gate and secret-scan hits in the repository, the image and the logs | 0 |
| Reliability (retention) | Prompts and traces older than 30 days; retained prompts that contained journal text | 0 and 0 |

### MDL — Model gateway

The single path to any language model: provider port and fake provider, the data-class check on every
input fragment, taint propagation to outputs, prompt templates and versions, provenance and compute-once,
the cost ledger and daily budget, and the offline evaluation harness.

| Field | Value |
|---|---|
| Release · stage | R1 · 0 (fake provider, ledger, budget, policy check, taint); 1 (real adapter behind the live flag) |
| Runs in | `core`; the local adapter calls the optional `llm` service |
| Owns | `sys_model_calls` (model, function, prompt version, input hash, classes sent, tokens, cost, duration, error), `sys_prompts`, `sys_budget`, `sys_eval_runs` |
| Commands | `call(function, fragments, purpose)` (never inside a transaction), `set_budget`, `record_eval_run` |
| Queries | `cost_by_day`, `cost_by_month`, `budget_state`, `provenance(output_ref)`, `eval_report(set)` |
| Emits · consumes | `coflow.mdl.call.completed` (no content), `coflow.mdl.budget.exhausted` · `coflow.pol.flow.changed` |
| Depends on | STO, POL, CFG (templates, locale); provider port |
| Requirements | P-6, P-7, EXT-2, OPS-7, OPS-8, OPS-11, OPS-12, PRV-2, PRV-3, PRV-9, FIN-5 (mechanism), NFR-3 |
| Data classes · DATA_FLOWS | system rows; prompts kept ≤ 30 days, never when they held journal text · one row per model function: classes it may receive, destination (`provider` or `local_llm`), purpose |
| Acceptance suite | Every suite runs on the fake provider, which asserts the policy and the transaction rule; the shared port contract suite runs on the fake and, behind the live flag, on the real adapter |
| Usage signal | Calls and cost per function per day; functions without a call in 90 days are reviewed |
| Approval | CI scorecard (its policy canaries are part of POL's owner-approved suite) |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Security (policy) | Calls carrying a fragment whose class or purpose the switch does not allow | 0 |
| Security (taint) | Outputs recorded with a class less restrictive than their most restrictive input; outputs without derivation edges | 0 and 0 |
| Safety (tax figures) | Tax-figure values in any model call (placeholder canary) | 0 |
| Functional correctness | Provider calls made while the writer is in a transaction | 0 |
| Performance efficiency (cost) | Cost per active day with default settings over 28 days; calls past the budget | ≤ $1; never more than 1 |
| Maintainability (provenance) | Outputs without model, prompt version and input hash; repeated calls on unchanged input | 0 and 0 |
| Compatibility | Shared port contract suite on the fake and the real adapter | Both pass |
| Functional correctness (truncation) | Structured calls stored as complete although the provider reported a truncated answer (OPS-12) | 0 |
| Transparency (cost forecast) | Deviation of the monthly forecast of the chosen tier from the actual cost after a month (OPS-11) | ≤ 20 % |

### ACT — Approvals, external-action outbox and undo

Approval cards bound to a server-issued preview hash; the single outbox for every action that changes the
outside world; the undo log for internal writes made over MCP, executed by each module's undo handler.

| Field | Value |
|---|---|
| Release · stage | R1 · 2 (cards); 5 (outbox executor, verification, deploy-approval card) |
| Runs in | `core` |
| Owns | `act_cards` (preview hash, expiry, channel, decision), `act_operations` (operation key, external id, state), `act_attempts`, `act_undo_log` |
| Commands | `propose_card`, `approve_card(card, preview_hash)` (owner channel only), `reject_card`, `execute_operation`, `undo_write(entry)` |
| Queries | `pending_cards`, `operation_state(key)`, `undo_log(channel, period)` |
| Emits · consumes | `coflow.act.card.proposed` / `approved` / `rejected` / `expired`, `coflow.act.operation.applied` / `verified` / `failed` · none |
| Depends on | STO, EVT, IDS, POL; `OperationHandler` (CAL, CMT, NEG, OPS) and `UndoHandler` (every module with MCP writes) |
| Requirements | P-3, P-4, P-8, MCP-4, BOT-4, MTG-5 (mechanism), DEP-9 (deploy approval card) |
| Data classes · DATA_FLOWS | work (previews), system · one destination row per operation kind (`calendar`, `messenger`, …) |
| Acceptance suite | Recording fakes for every operation kind; fault injection (lost response, double approval, crash between steps); the generated MCP catalogue checked against registered undo handlers |
| Usage signal | Cards approved, rejected and expired per week; an expiry share above 50 % over 4 weeks opens a redesign issue |
| Approval | **Owner** |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Safety (exactly once) | External effects under a lost response, a double approval and a crash between steps | Exactly 1 in 100 % of fault cases |
| Security (unforgeable approval) | Executions without a valid preview hash and an owner-channel action, including approvals asserted in text | 0 |
| Reliability (verification) | Operations marked "verified" without a successful read-back | 0 |
| Functional correctness | Cards executed twice or after their 24-hour expiry | 0 |
| Maintainability (undo) | MCP write tools without an undo handler or a "not undoable" mark; undoable tools whose undo does not restore the prior state (table test) | 0 and 0 |

### CFG — Owner profile and locale

The single answer to "who is the owner": profile, languages, time zone, currency, booking hours, ritual
times, life domains and direction roles; locale packs (EN and RU in R1) with script-variant tables; the
rendering of prompt and bot templates.

| Field | Value |
|---|---|
| Release · stage | R1 · 0 |
| Runs in | `core` |
| Owns | `cfg_profile`, `cfg_locale_overrides`, `cfg_life_domains`, `cfg_direction_roles` |
| Commands | `update_profile`, `set_locale`, `set_life_domains`, `set_direction_role` |
| Queries | `profile`, `render(template_key, locale)`, `variants(text)` (from the locale pack) |
| Emits · consumes | `coflow.cfg.profile.changed` · none |
| Depends on | STO |
| Requirements | CFG-1…CFG-5, NFR-7, P-12 |
| Data classes · DATA_FLOWS | work · none of its own (profile fields reach the provider only inside other modules' registered prompts) |
| Acceptance suite | Literal gate on code, prompts and stored defaults; the scenario suite in both locales; fresh-install content scan |
| Usage signal | Kernel: profile changes (counts) |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Flexibility (no literals) | Owner literals in code, prompts and stored defaults; personal content in a fresh install | 0 and 0 |
| Interaction capability (locales) | User-facing strings present in both locales; scenario suite in EN and RU | 100 %; both pass |
| Maintainability | Templates using profile fields that do not change after a profile change without a rebuild | 0 |

### OBS — Traces, health and scorecards

Interaction traces and behaviour versions, health probes, SLIs computed from events, usage signals per
feature and the runtime module scorecards shown on the status page.

| Field | Value |
|---|---|
| Release · stage | R1 · 0 (trace skeleton); 1 (traces); 4 (health, SLIs, runtime scorecards) |
| Runs in | `core` |
| Owns | `sys_traces`, `sys_trace_steps`, `sys_health`, `sys_sli_samples`, `sys_usage_signals`, `sys_scorecards` |
| Commands | `record_step` (interfaces), `record_health` (from `HealthProbe`s), `compute_scorecard(module, window)` |
| Queries | `trace(interaction_id)`, `health`, `scorecard(module, window)`, `usage(feature)` |
| Emits · consumes | `coflow.obs.health.degraded`, `coflow.obs.slo.missed`, `coflow.obs.trace.closed` · every event (counts and SLIs; journal events counted only) |
| Depends on | STO, EVT, `kernel.context`; never imported by EVT |
| Requirements | OPS-6, OPS-10, P-13, NFR-9, PRV-3 (traces), DEP-15 |
| Data classes · DATA_FLOWS | system; ids and hashes only · `status_page` row (aggregates) |
| Acceptance suite | Traced evaluation runs on the fake provider; a failure-injection drill (stopped worker, stale source, old backup) |
| Usage signal | Kernel: scorecards viewed (through STS) |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Maintainability (traceability) | Bot answers and MCP calls in evaluation runs traceable to their steps and versions | 100 % |
| Reliability (detection) | Time from a stopped worker, a stale source or an old backup to a red status | ≤ 5 min in the drill |
| Functional completeness | Features without a usage signal; hand-entered numbers in scorecards | 0 and 0 |
| Security | Trace steps holding message, transcript or journal text instead of ids and hashes | 0 |

### OPS — Instance, backups, export and deploy state

The supervisor and OS-held single-instance locks; instance identity, roles, epoch and fencing; `init`,
`doctor`, `promote`, `retire`, `drill`; backup and restore; full export and import. The CLI reaches it
through ADM; the updater (UPD) runs outside the stack.

| Field | Value |
|---|---|
| Release · stage | R1 · 0 (init, doctor, backup, restore, image, Compose); 2 (staging host, promote, retire, fencing); 5 (holds, rollback support); R2 · 6 (export, import, move and rebuild drill) |
| Runs in | `core` (supervisor); CLI through ADM; `migrate`, `restore`, `drill` without a live `core` in their target instance |
| Owns | `sys_instance` (instance id, role, epoch, host id, volume id), `sys_backups`, `sys_deploys`, `sys_holds`, `sys_exports` |
| Commands | `init`, `doctor`, `backup`, `restore`, `drill`, `migrate`, `promote`, `retire`, `hold` / `release`, `export`, `import` |
| Queries | `instance_state`, `backup_age`, `doctor_report`, `deploy_history` |
| Emits · consumes | `coflow.ops.backup.completed`, `coflow.ops.instance.fenced`, `coflow.ops.role.changed` · `coflow.obs.health.degraded` |
| Depends on | STO, EVT, POL, OBS, ACT (implements the deploy-approval `OperationHandler`) |
| Requirements | OPS-1, OPS-2, OPS-5, PRV-4 (inventory check), PRV-5, PRV-8, NFR-1, NFR-2, NFR-5, DEP-1…DEP-7, DEP-12…DEP-15, DEP-18…DEP-20 |
| Data classes · DATA_FLOWS | system · `backup` (ciphertext, off-host), `export` (owner's files) |
| Acceptance suite | CI restore test; Compose smoke with egress blocked; exposure test; upgrade test; fencing drill with a copied database; DEPLOYMENT §10.3 drills |
| Usage signal | Kernel: backup age and drill results on the status page |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Interaction capability (install) | Time to a green `doctor` following the docs: Docker production install on a prepared Linux host, by a non-author (NFR-2); native dev install with fakes; a device agent | ≤ 60 min; ≤ 30 min; ≤ 10 min (at R1) |
| Reliability (recovery) | Restore drill counters and deletion-log re-application; backup age at every check | Equal counters, log re-applied; ≤ 26 h |
| Safety (one writer) | A second production instance or a copied database left able to write or poll | 0; fenced or refused in 100 % of drills |
| Security (exposure) | Listeners on a non-loopback address with default configuration | 0 |
| Maintainability (CI) | Full offline suite time on Windows and Linux runners | ≤ 15 min |
| Reliability (rebuild) | Rebuild on another machine from the off-host backup (stage 6); RTO in R2 | ≤ 2 h excluding the OS install; ≤ 4 h |

---

## Domain

### PPL — People and companies

The registry of people and companies: `resolve_or_create_person`, temporal facts with source and quote,
deterministic dossiers, merge and undo, forgetting a person, birthdays and the client view.

| Field | Value |
|---|---|
| Release · stage | R1 · 1; R2 · 6 (merge, undo, forget), 8.8 (birthdays, client view) |
| Runs in | `core` |
| Owns | `ppl_persons`, `ppl_companies`, `ppl_aliases`, `ppl_strong_keys`, `ppl_facts` (temporal, sourced, stated positions only), `ppl_merges` |
| Commands | `resolve_or_create_person`, `update_person`, `add_strong_key`, `add_fact`, `merge` / `undo_merge`, `forget` (through POL) |
| Queries | `person_profile`, `dossier(person, size budget)`, `search_persons` (script variants from CFG), `company_context`, `client_view`, `birthdays_due` |
| Emits · consumes | `coflow.ppl.person.created` / `updated` / `merged` / `forgotten`, `coflow.ppl.fact.added` · `coflow.pol.erasure.completed` |
| Depends on | Kernel only (IDS, CFG, POL) |
| Requirements | IDN-3, IDN-4, IDN-5, IDN-8, PPL-1…PPL-7 (PPL-3 acceptance writes), REL-3 (stated positions only) |
| Data classes · DATA_FLOWS | work · dossiers to `provider` (answers, briefs), `mcp:<client>`, `messenger` |
| Acceptance suite | Synthetic identity set (namesakes, strong keys, transliterations); dossier golden files; merge and undo round trips |
| Usage signal | Resolutions and dossiers served per week |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Functional correctness (no silent duplicates) | Duplicates on the synthetic identity set; rows written on an ambiguous match | 0; 0 (candidates returned) |
| Functional correctness (read-only lookup) | Bytes changed in any table by a lookup, including fields filled in on a person it found (IDN-8) | 0 |
| Functional correctness (name is not a key) | Contact keys written to a person matched on name or alias alone; duplicates created when the same person was added between a card and its approval (IDN-8) | 0 and 0 |
| Safety (pipelines) | People created by background pipelines on unknown senders | 0 |
| Functional correctness (dossier) | Byte equality for the same input; budget overruns; journal content | Identical; 0; 0 |
| Functional correctness (cross-script) | Recall of cross-script name matching on the labelled set | ≥ 95 % |
| Safety (no profiling) | Schema fields for inferred emotions or diagnoses of other people | 0 |
| Functional correctness (merge) | State after merge followed by undo vs. the original | Identical |

### SIG — Signals

Conversations as sessions and messages: transcript segments, quick logs and notes, the connector contract
and its adapters (messenger export, recorder), the recorder pipeline, summaries computed once, and contact
proposals extracted from conversations.

| Field | Value |
|---|---|
| Release · stage | R1 · 1 (sessions, messages, segments, quick log, connector contract, messenger export); 4 (recorder pipeline, contact proposals) |
| Runs in | `core`; transcription in `stt` through jobs |
| Owns | `sig_sources` (content hash, consent), `sig_sessions` (initiator), `sig_messages` (direction, sender, timestamp to the second), `sig_participants`, `sig_segments` (offset, absolute and original time), `sig_summaries`, `sig_connector_cursors`, `sig_recorder_profiles`, `sig_notes`, `sig_contact_proposals`, `sig_rejected_values` |
| Commands | `register_file`, `import_connector_batch`, `log_quick`, `set_participant`, `request_summary`, `retry_recording`, `decide_contact_proposal`, `delete_source` (through POL) |
| Queries | `session`, `messages(session)`, `segment(ref)` with a playable offset, `recording_queue` (why it waits), `recent_sessions`, `contact_proposals`, projection queries for SRC and TML |
| Emits · consumes | `coflow.sig.source.registered`, `coflow.sig.transcript.ready`, `coflow.sig.session.created` / `updated`, `coflow.sig.message.added`, `coflow.sig.summary.computed`, `coflow.sig.contact.proposed` · job completions, `coflow.pol.erasure.completed` |
| Depends on | PPL (resolve only; never creates people from pipelines); `GoalDirectory`; MDL, POL |
| Requirements | SIG-1…SIG-6, SIG-11, SIG-14, SIG-15, PPL-3 (extraction, rejected values), PRV-6, REL-6 (direction, initiators, timestamps, original times); SIG-12, SIG-13 Later |
| Data classes · DATA_FLOWS | work · transcripts and messages to `provider` (summaries); audio never leaves the host |
| Acceptance suite | Synthetic exports and audio fixtures; fake STT worker; out-of-memory and transient-error injection; inbox JSON contract tests |
| Usage signal | Sessions per source per week; contact-proposal decision rate (a type below 20 % over its last 30 switches itself off) |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Functional correctness (idempotency) | Changes after re-importing the same export or re-summarising unchanged input | 0 |
| Reliability (freshness SLO) | Fresh recording to registered; to searchable, over 28 days | ≤ 2 min; ≤ 30 min for ≥ 95 % of files |
| Reliability (resilience) | Simulated out-of-memory and transient errors recovered without a human | 100 % |
| Functional correctness (quotes) | Quotes that resolve to a segment and a playable offset | 100 % |
| Compatibility (connector) | Inbox schema drift silently dropped | 0 (a visible error) |
| Interaction capability (proposals) | Rejected values proposed again; proposals over the cap (default 5 per type per day) | 0 and 0 |

### JRN — Journal

The owner's private notes as their own data class: written through the bot (by explicit marker) or the
local CLI, never indexed, never in MCP, search, dossiers, plans or work answers; analysed only by modules
the owner enables with the journal switch (PRV-9).

| Field | Value |
|---|---|
| Release · stage | R1 · 1 (storage, local entry path); 2 (bot routing through BOT); first analysis consumer in 8.2 (LRN-6 in GOL) |
| Runs in | `core` |
| Owns | `jrn_entries` (journal class; `sealed` flag) |
| Commands | `add_entry` (bot route; CLI through ADM with a journal-write token), `move_to_journal(message_ref)` (through `POL.blank_as_journal`), `seal_entry` |
| Queries | `list_entries` (ADM with a journal-read token, the owner's terminal only), `entries_for_analysis(module, period)` (only to MDL-gated functions of enabled modules; sealed entries excluded) |
| Emits · consumes | `coflow.jrn.entry.added` (id only, journal class) · none |
| Depends on | Kernel only (STO, POL, MDL) |
| Requirements | P-2, PRV-1, PRV-9, BOT-3, BOT-7 (voice entries), TML-1 (local view), ALN-4 (consumer rule), NFR-6; D-025 |
| Data classes · DATA_FLOWS | journal · `messenger` (entries written in the bot pass the messenger's servers; journal outputs shown there are switchable); `provider` and `local_llm` per analysis module, asked at `coflow init` with no preselected answer; `index`, `mcp`, `status_page`, `edge`, logs: never |
| Acceptance suite | The PRV-9 canaries (a normal and a sealed entry) under both settings; the local entry path on Windows and Linux; voice-entry canaries with the fake STT worker |
| Usage signal | Entries per week (count only, no ids on the status page) |
| Approval | **Owner** |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Security (isolation) | Journal rows reachable through search, MCP, the status page or event payloads (canary) | 0 |
| Security (switch) | Journal text in a model call with the switch off; in a call of a module not enabled; sealed text in any call | 0; 0; 0 |
| Security (logging) | Prompt logs or traces holding journal text instead of hashes | 0 |
| Security (voice) | Voice journal entry in any model call (switch off); in any routing or work call (switch on) | 0; 0 |
| Interaction capability | Local entry without any messenger | Passes on Windows and Linux |

### WRK — Work

Execution: tasks with status, ball holder, next step with a date, comments and links; the deterministic
control view. In R1 it also holds directions and goals (with an optional money target until 8.1a); from
8.2 those move to GOL and WRK keeps tasks.

| Field | Value |
|---|---|
| Release · stage | R1 · 1 (tasks, directions, goals, WRK-8); 2 (control view); 8.2 (directions and goals transferred to GOL) |
| Runs in | `core` |
| Owns | `wrk_tasks` (`goal_ref` only, never a direction copy), `wrk_status_log`, `wrk_comments`, `wrk_links` (decisions, sessions); until 8.2: `wrk_directions`, `wrk_goals` |
| Commands | `create_task`, `update_task`, `change_status` (one operation, logged), `set_ball`, `comment`, `link_task`, `take_to_deliberation(goal)`; until 8.2: `create_direction`, `create_goal`, `update_goal` |
| Queries | `task_context`, `open_tasks`, `search_tasks`, `control_view` (overdue, waiting for me, waiting for them, no movement for N days, goals without a next step), `unlinked_share(week)` |
| Emits · consumes | `coflow.wrk.task.created` / `status_changed` / `ball_changed` / `linked` (and `coflow.wrk.goal.*` until 8.2) · `coflow.act.card.approved` (approved task proposals) |
| Depends on | DEC, SIG, FIN (money target, from 8.1a); `GoalDirectory` (implements it until 8.2); implements `ReviewContributor` (control view) |
| Requirements | WRK-1…WRK-3, WRK-6, WRK-8, CFG-5; WRK-5 Later |
| Data classes · DATA_FLOWS | work · to `provider` (answers, phrasing), `mcp:<client>`, `messenger` |
| Acceptance suite | Property tests for status and ball; control-view golden files; resolution tests after a goal moves |
| Usage signal | Tasks created and status changes per week; share of unlinked items per week (WRK-8) |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Functional correctness (status) | Status changes without a log row; tasks without an explicit ball holder | 0 and 0 |
| Maintainability (no copies) | Direction values stored on tasks (schema check) | 0 |
| Functional correctness (resolution) | Property test: after a goal moves, every task of the goal reports the new direction at read time | 100 % |
| Functional correctness (control view) | Same data → same list and order; items that do not say why they are listed | Identical; 0 |
| Safety (execution mode) | Daily or weekly items offering pause or drop (exits are a dated next step or "take to the next deliberation slot"; before 8.2 the slot is the goal's review date) | 0 |
| Performance efficiency | MCP `create_task` and `change_status` latency | p95 ≤ 300 ms |
| Interaction capability (WRK-8) | Background link-proposal queues | 0 (offers are inline only) |

### DEC — Decisions

Decision records: statement, context, alternatives, stake; grounds and monitored assumptions; health
computed from assumption states; explicit closing with an outcome; morning surfacing.

| Field | Value |
|---|---|
| Release · stage | R1 · 3; R2 · 7 (DEC-5 surfacing) |
| Runs in | `core` |
| Owns | `dec_decisions`, `dec_facts` (grounds, monitoring), `dec_assumptions` (metric, threshold, source, frequency), `dec_checks`, `dec_outcomes` |
| Commands | `create_decision`, `add_fact`, `add_assumption`, `set_assumption_state`, `close_decision` (needs an outcome), `cancel`, `supersede` |
| Queries | `decision_context`, `decisions_due`, `health(decision)`, `list_decisions` |
| Emits · consumes | `coflow.dec.decision.created` / `closed` / `health_changed`, `coflow.dec.assumption.state_changed` · none |
| Depends on | PPL; `GoalDirectory`; ACT (cards for model-proposed decisions) |
| Requirements | DEC-1…DEC-5 |
| Data classes · DATA_FLOWS | work · to `provider` (phrasing), `mcp:<client>`, `messenger` |
| Acceptance suite | Table test of every assumption-state combination; a synthetic month of assumption checks |
| Usage signal | Decisions opened and closed per month; assumption checks answered on their due day |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Functional correctness (health) | Table test over every assumption-state combination | 100 % match |
| Functional correctness (closing) | Closings accepted without an outcome | 0 |
| Functional correctness (evidence) | Grounds or assumptions without a source | 0 |
| Reliability (surfacing) | Assumption checks due that appear in the morning plan on their due day, synthetic month | 100 % |

### CMT — Commitments

Who owes what to whom by when, with the quote it came from; inline, capped proposals with the decision
rate measured per type; "send material" as the first commitment carried through to a result.

| Field | Value |
|---|---|
| Release · stage | R1 · 3; R2 · 8.3 (send material); CMT-4 Later |
| Runs in | `core` |
| Owns | `cmt_commitments` (both sides, initiator), `cmt_history` (timestamped status), `cmt_proposals`, `cmt_proposal_stats`, `cmt_material_sends` |
| Commands | `create_commitment`, `close_commitment` (needs a reason), `propose_inline`, `decide_proposal`, `prepare_material_send`, `confirm_sent` |
| Queries | `open_commitments`, `due(period)`, `proposal_decision_rate(type)`, `material_send_state` |
| Emits · consumes | `coflow.cmt.commitment.created` / `closed` / `due`, `coflow.cmt.proposal.type_switched_off` · `coflow.sig.summary.computed`, `coflow.sig.message.added` (finding an outgoing message for "sent") |
| Depends on | PPL, SIG, DEC; `GoalDirectory`; ACT (implements `OperationHandler` for material send), MDL |
| Requirements | CMT-1…CMT-3, REL-6 (both sides, history); CMT-4 Later |
| Data classes · DATA_FLOWS | work · to `provider` (proposal extraction, drafts), `mcp:<client>`, `messenger` |
| Acceptance suite | Synthetic conversations and outcomes with planted agreements; proposal-cap and switch-off rule tests; recording fake for material sends |
| Usage signal | Decision rate per proposal type: below 20 % over the last 30 proposals the type switches itself off and says so |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Functional correctness (evidence) | Commitments whose quote does not resolve to a segment or message | 0 |
| Interaction capability (hygiene) | Proposals over the cap (default 5 per type per day); a type below 20 % over its last 30 that stays on | 0; 0 |
| Safety (send material) | Automatic sends; "sent" without an owner confirmation or a found outgoing message | 0; 0 |
| Functional correctness (history) | Status changes without a timestamped history row | 0 |

### CAL — Calendar

A read-only calendar copy with freshness flags and a mass-disappearance guard; free slots, fresh
preflight and the time model; the calendar-write handler for the outbox, with write safety.

| Field | Value |
|---|---|
| Release · stage | R1 · 4 (copy); 5 (writes through ACT) |
| Runs in | `core` |
| Owns | `cal_events` (no descriptions, conference links or guest names), `cal_sync_state`, `cal_owned_events` (events CoFlow created, with their computed ids) |
| Commands | `sync` (every 15 min), `plan_write(create / move / cancel)` (becomes an ACT operation), `answer_invitation` |
| Queries | `day`, `free_slots`, `preflight(slot)`, `freshness` |
| Emits · consumes | `coflow.cal.event.synced` / `changed` / `disappeared`, `coflow.cal.write.verified` · none (writes arrive through its `OperationHandler`) |
| Depends on | Kernel (ACT, CFG, IDS); calendar port (one reference adapter, separate read and write tokens, and a recording fake) |
| Requirements | SIG-9, EXT-3, MTG-5 (handler), MTG-6, MTG-7, MTG-11 |
| Data classes · DATA_FLOWS | work · `calendar` (read; write through ACT); event titles to `provider` (briefs), `mcp:<client>`, `messenger` |
| Acceptance suite | Recording fake calendar; DST table tests; scope test on token requests; mass-disappearance fixture |
| Usage signal | Answers that used the copy per week; writes per week |
| Approval | **Owner** |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Safety (write) | Changes to foreign or recurring events; owner-moved events moved back (recording fake) | 0 and 0 |
| Security (scopes) | Token requests with a forbidden scope; a shared read-write token | Test fails on either |
| Reliability (freshness) | Answers without `synced_at` and `stale`; a mass disappearance that gets applied | 0; 0 (refused) |
| Functional correctness (time) | DST gaps and overlaps accepted silently (table test); writes using a preflight older than 60 s | 0; 0 |

### MTG — Meetings

A meeting is an intent linked to work: plan, participants, briefs with sources, recording-to-meeting
linking, and outcomes that become commitment and task proposals through the outcome card.

| Field | Value |
|---|---|
| Release · stage | R1 · 5; MTG-9 Later |
| Runs in | `core` |
| Owns | `mtg_meetings` (initiator; `goal_ref` and task refs, no direction copy), `mtg_participants`, `mtg_briefs`, `mtg_outcomes`, `mtg_recording_links`, `mtg_link_proposals` |
| Commands | `plan_meeting` (link to work required unless "no link"), `update_meeting`, `complete_meeting`, `record_outcome`, `decide_link` |
| Queries | `meeting_brief`, `upcoming`, `meeting_chain`, `link_options` |
| Emits · consumes | `coflow.mtg.meeting.planned` / `changed` / `held`, `coflow.mtg.brief.ready`, `coflow.mtg.outcome.recorded`, `coflow.mtg.recording.linked` · `coflow.sig.transcript.ready`, `coflow.sig.session.created`, `coflow.cal.event.synced`, `coflow.cal.write.verified` |
| Depends on | PPL, SIG, CAL, DEC, CMT, WRK; `GoalDirectory`; ACT, MDL, IDS (labels) |
| Requirements | MTG-1…MTG-4, MTG-12…MTG-16, OPS-11 (the tier for the analysis mode), OPS-13, NFR-12, REL-6 (initiator); MTG-9 Later |
| Data classes · DATA_FLOWS | work · briefs to `provider` (phrasing), `mcp:<client>`, `messenger` |
| Acceptance suite | 30 consecutive synthetic meetings with recordings; outcome fixtures with planted agreements; fake clock for brief times |
| Usage signal | Meetings planned and held per week; briefs opened |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Functional correctness (linking) | Meetings linked to their recording without manual work over 30 consecutive synthetic meetings; duplicates after reprocessing | ≥ 90 %; 0 |
| Functional correctness (evidence) | Outcome quotes that are exact substrings of a segment; brief facts with sources | 100 %; 100 %, gaps named |
| Reliability (brief SLO) | Briefs delivered at the configured time over 28 days | ≥ 26 of 28 days |
| Functional correctness (link to work) | Meetings accepted without a link to work and without "no link" | 0 |
| Functional correctness (outcome recall) | Planted agreements reaching the outcome card on the fixture set; recall on the owner's private set for the chosen tier (OPS-13) | 100 %; ≥ 80 % |
| Transparency (honest outcomes) | "Nothing found" messages produced by a run that was truncated or dropped items (MTG-13) | 0 |
| Timeliness (time to outcome) | Median time from the arrival of the recording to the outcome message (NFR-12) | ≤ 30 min |
| Functional correctness (online meetings) | Approval cards for a meeting write without the "with video link / in person" line; events left without the requested conference and without a message saying so (MTG-16) | 0 and 0 |

### RHY — Rhythm and activity time

The daily and weekly rhythm — morning plan with a deterministic ranking, snapshots, evening plan vs.
fact, the weekly review as a structured debrief — and, from stage 6, activity time: spans and the
classification rules with their labelled-day accuracy gate.

| Field | Value |
|---|---|
| Release · stage | R1 · 2 (RHY-1…3); R2 · 6 (activity spans and rules), 7 (RHY-4 weekly review) |
| Runs in | `core` |
| Owns | `rhy_plans` (snapshots), `rhy_day_reviews`, `rhy_week_reviews` (journal-class sections referenced by id only), `rhy_activity_spans` (start, end, goal or direction ref, device, rule version), `rhy_classification_rules` (versioned, gate state), `rhy_labelled_days` |
| Commands | `build_morning_plan` (scheduled), `refine_plan`, `close_day`, `run_weekly_review`, `record_spans` (from INT), `propose_rules`, `record_labelled_day`, `activate_rules` (only after the gate) |
| Queries | `today_plan`, `plan_vs_fact(period)`, `week_review(period)`, `time_by_direction(period)` with coverage, `agent_config` (served to agents by INT) |
| Emits · consumes | `coflow.rhy.plan.delivered`, `coflow.rhy.day.closed`, `coflow.rhy.week.reviewed`, `coflow.rhy.spans.recorded` · `coflow.obs.health.degraded` (health line) |
| Depends on | WRK, CMT, DEC, CAL, MTG, TAX (reminders); `GoalDirectory`; `ReviewContributor` (WRK, GOL); MDL (phrasing of top lines only) |
| Requirements | RHY-1…RHY-5, WRK-8 (spans), DEC-5 (surfacing), FIN-12 (reminders in the plan), GOL-12 (weekly-review pause rule) |
| Data classes · DATA_FLOWS | work · plans to `provider` (phrasing), `messenger`, `mcp:<client>`; window titles never reach `core` |
| Acceptance suite | Golden morning plans; an adversarial fake model; fake clock over 28 days; a labelled synthetic day for rule accuracy |
| Usage signal | Plans opened per week; weekly review unopened 3 weeks in a row → generation pauses and asks once (GOL-12 default); completion below 50 % over 4 weeks opens a redesign issue |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Functional correctness (ranking) | Same data → same order; ranking changed by the model (adversarial fake) | Identical; 0 |
| Reliability (SLO) | Morning plan within 5 min of the configured time over 28 days | ≥ 26 of 28 days |
| Functional correctness (activity gate) | Classification accuracy on the labelled day before spans count; spans counted from rules below the gate | ≥ 90 %; 0 |
| Security | Journal content in plans or stored reviews | 0 |
| Interaction capability (usage rules) | The redesign issue opened when weekly review completion is below 50 % over 4 weeks; weekly generation that continues after 3 unopened weekly reviews without asking once (rule tests) | Opened in 100 % of test cases; 0 |

### LRN — Learning

Owner corrections become typed, versioned rules through approval cards: `/remember`, `/problem`,
one-off exceptions with an expiry, "why this time" answered from rules and sources, incident packages
ready to become public issues. The weekly reflection (LRN-6) is delivered by GOL.

| Field | Value |
|---|---|
| Release · stage | R2 · 7 |
| Runs in | `core` |
| Owns | `lrn_corrections`, `lrn_rules`, `lrn_rule_versions`, `lrn_exceptions` (expiry), `lrn_incidents` |
| Commands | `remember`, `report_problem`, `propose_rule`, `approve_rule` (ACT card), `revoke_rule`, `package_incident` |
| Queries | `rules(active)`, `rule_history`, `why(answer_ref)` |
| Emits · consumes | `coflow.lrn.rule.approved` / `revoked`, `coflow.lrn.incident.packaged` · `coflow.obs.trace.closed` (errors) |
| Depends on | Kernel only (ACT, MDL, OBS, POL) |
| Requirements | LRN-1…LRN-5 |
| Data classes · DATA_FLOWS | work · corrections to `provider` (rule candidates, owner's own words only) |
| Acceptance suite | Rule evaluation set run in a new conversation and after a restart; forwarded-text injection set; incident-package scrubbing fixtures |
| Usage signal | Rules approved and applied per week |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Functional correctness (persistence) | A rule explained once applies in a new conversation and after a restart (rule evaluation set) | 100 % |
| Security (injection) | Rules created from forwarded or third-party text | 0 |
| Security (incident hygiene) | Journal text or real third-party data in incident packages | 0 |
| Functional correctness (exceptions) | One-off exceptions without an expiry | 0 |

### SRC — Search

A full-text read model over transcripts, summaries, messages, facts, decisions, tasks, meetings and (from
8.1a) money, with rule-based entities, script variants, a source for every hit and stated coverage.

| Field | Value |
|---|---|
| Release · stage | R1 · 1; financial partition from R2 · 8.1a; SRC-5, SRC-6 Later |
| Runs in | `core` |
| Owns | `src_fts` (row id = kind code × 10¹² + id), `src_entities`, `src_fin_fts` (financial partition) |
| Commands | `rebuild_index` (admin, batched) |
| Queries | `search(query, filters, destination)` with coverage and freshness; `entities_of(ref)` |
| Emits · consumes | `coflow.src.index.rebuilt` · synchronous projectors on SIG, PPL, WRK, DEC, CMT, MTG and FIN changes; `coflow.pol.erasure.completed` |
| Depends on | PPL, SIG, DEC, CMT, FIN, WRK, MTG (projection queries); CFG (variants) |
| Requirements | SRC-1…SRC-4, P-9; SRC-5, SRC-6 Later |
| Data classes · DATA_FLOWS | work, financial (separate partition) · results to `mcp:<client>`, `messenger`, `provider` per the requester's flow |
| Acceptance suite | Load test of projector cost; labelled Latin ↔ Cyrillic query set; rebuild-equals-incremental test; canaries |
| Usage signal | Searches per week and zero-hit share |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Performance efficiency | Projector cost per message update under load | p99 < 50 ms |
| Functional correctness (cross-script) | Recall of Latin ↔ Cyrillic queries on the labelled set | ≥ 95 % |
| Maintainability (rebuildable) | Index rebuilt from scratch vs. the incremental index | Identical |
| Security | Journal rows or journal-derived outputs in the index; hits without a source link | 0; 0 |
| Security (financial) | Financial hits returned to a destination whose financial flow is off | 0 |

### TML — Timeline

One chronological read model over every layer, with coverage per layer; from 8.5 the whole personal
archive as dated items with clock corrections. Journal items are never stored here: the owner's local
view merges them at read time through ADM.

| Field | Value |
|---|---|
| Release · stage | R1 · 1 (TML-1); R2 · 8.5 (TML-2) |
| Runs in | `core` |
| Owns | `tml_items` (time, layer, ref, original and corrected time), `tml_coverage`, `tml_archive_imports`, `tml_clock_corrections` |
| Commands | `import_archive` (through SIG connectors, after a sample-based cost estimate), `set_clock_correction` |
| Queries | `day(date)`, `around(ref)`, `between(dates, filters)`, `coverage(period)` |
| Emits · consumes | `coflow.tml.archive.imported` · creation, change and deletion events of dated entities |
| Depends on | SIG, MTG, CAL, WRK, DEC, CMT, FIN; MDL (estimates only) |
| Requirements | TML-1, TML-2, SIG-11, REL-6 (original times kept) |
| Data classes · DATA_FLOWS | work, financial items per flow · day views to `mcp:<client>`, `messenger` |
| Acceptance suite | A synthetic year across every layer; archive re-import fixtures with skewed device clocks |
| Usage signal | Day and range queries per week |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Functional completeness | Day queries over a synthetic year that list every layer with sources and name the empty ones | 100 % |
| Functional correctness (idempotency) | Changes on archive re-import; corrected items that lose their original time | 0; 0 |
| Performance efficiency | Day-query latency on a synthetic year | p95 ≤ 2 s |
| Performance efficiency (cost) | Bulk model runs started without a sample-based estimate | 0 |
| Security | Journal items returned by the MCP timeline tool (canary) | 0 |

### FIN — Money core (stage 8, module 1a)

The planning and evidence layer for money, for one owner with several books that never mix: taxpayers
and books, accounts (mixed-use only within one taxpayer), an append-only multi-currency ledger, transfers
and related-party flows, a read-only invoice register, the document archive with retention, financial
targets keyed by goal, and reports. It never issues invoices, keeps statutory books or files returns
(D-026); invoices come from a certified invoicing program.

| Field | Value |
|---|---|
| Release · stage | R2 · 8.1a; FIN-19, FIN-20 Later |
| Runs in | `core` (structured files first: CSV, XLSX, structured XML); PDF text and OCR as `extract` jobs in a worker |
| Owns | `fin_taxpayers`, `fin_books` (taxpayer, contour, regime), `fin_accounts` (mixed-use flag), `fin_entries` (append-only; one book, or a split with a reason), `fin_transfers` (same-taxpayer pairs), `fin_related_flows` (related-party flag, "market value documented?"), `fin_fx_rates`, `fin_categories`, `fin_invoices` (EN 16931 names; source: compliant system id, QR or hash, structured e-invoice, or "manual, outside register"), `fin_payment_matches`, `fin_documents` (hash, `retention_until`), `fin_targets` (`goal_ref`; migrated from WRK's optional goal money target), `fin_import_identities` |
| Commands | `post_entry`, `reverse_entry`, `split_entry`, `record_transfer` (same taxpayer), `record_related_flow` (income in one book, expense in the other), `import_invoice_files`, `attach_document`, `set_target`, `close_period`, `post_imported_entries` (for IMP) |
| Queries | `balance(book, account, as_of)`, `report(book, period, currency)`, `consolidated_report` (explicit flag, stated FX), `taxpayer_entries(taxpayer, period)` (for TAX only), `runway(book)`, `target_progress(goal_ref)`, `money_by_client`, `money_by_direction`, `decision_money` |
| Emits · consumes | `coflow.fin.entry.posted` / `reversed`, `coflow.fin.invoice.registered` / `paid`, `coflow.fin.period.closed`, `coflow.fin.target.set` · `coflow.pol.erasure.completed` (refusals inside retention) |
| Depends on | PPL (counterparties), DEC; `GoalDirectory`; MDL (one-line parsing and phrasing under the financial switch); invoice-file port |
| Requirements | FIN-1, FIN-2, FIN-4…FIN-9, FIN-14, FIN-16 (file adapter), PRV-7 and PPL-6 (retention refusals); FIN-19, FIN-20 Later; D-026, D-027 |
| Data classes · DATA_FLOWS | financial · `provider` per purpose (proposed defaults: owner questions on; weekly review, goal control and reminders off, amounts as placeholders); `mcp:<client>` off until allowed per client; `messenger` on; raw documents to `provider` a separate row, off, only after redaction; third-party identifiers masked; credentials never |
| Acceptance suite | A three-book fixture (household and own practice under one taxpayer, a company as a second); invoice export fixtures (CSV, XLSX, structured XML, PDFs); canary documents with a synthetic tax id and IBAN |
| Usage signal | Entries posted per week; reports opened per month |
| Approval | **Owner**, with two review rounds; a legal opinion before public release |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Functional correctness (balance) | Balance vs. opening + entries for every account and period; per-book balances of a mixed account vs. the account balance | Equal in 100 %; equal |
| Safety (audit trail) | UPDATE or DELETE on posted entries (authorizer); corrections that are not reversals | 0; 0 |
| Security (book isolation) | Sums across books without the flag (taxpayer aggregation for TAX excepted); sums across taxpayers or currencies without a stated rate; an account shared across taxpayers; reports for a period with an unassigned mixed-account entry | 0; 0; 0 (refused); blocked |
| Functional correctness (flows) | Same-taxpayer transfers that change income or expense totals; a practice → own company invoice raising practice income, VAT output and company expense; dividends booked as a company expense; transfers between taxpayers accepted unless a capital contribution or a loan with interest terms | 0; 100 %; 0; 0 |
| Safety (never billing) | Commands that allocate invoice series or render a document titled as an invoice; manual issued invoices placed in an official issued-register layout, a per-form figure or a box mapping (they feed only plain lists with totals) | 0; 0 |
| Safety (retention) | Documents deleted before `retention_until` through any path | 0 (refused with reason and date) |
| Security (financial flows) | Amounts in model calls for a purpose that is off; unmasked third-party tax ids or IBANs, or raw document text with its switch off | 0; 0 |

If the Norma 43 parser and one CSV profile move into 8.1a (proposed), the reconciliation parameter of IMP
moves into this card with them.

### TAX — Country packs and tax planning (stage 8, module 1b)

The jurisdiction-neutral country-pack interface and the Spain reference pack (ESP, a data package):
taxpayer-scoped filing calendar, labelled reserve and quarterly estimates, the advisor export pack,
threshold warnings and the rules-watch. Every figure, calendar entry, reminder, applicability decision and
warning is an estimate for planning, not tax advice, and carries that label with the pack version.

| Field | Value |
|---|---|
| Release · stage | R2 · 8.1b (interface); ESP as a plugin data package per tax year |
| Runs in | `core` |
| Owns | `tax_packs` (country, tax year, version, verified), `tax_rules` (effective dates, official source, rule version), `tax_obligations` (per taxpayer; status; receipt document ref), `tax_estimates` (formula, inputs, pack version), `tax_filed_amounts`, `tax_warnings`, `tax_exports`, `tax_rules_watch` |
| Commands | `load_pack`, `mark_pack_year_verified`, `generate_calendar(taxpayer, year)`, `compute_estimates(taxpayer, period)`, `record_filed(obligation, amount)`, `run_threshold_checks`, `generate_export_pack(taxpayer, period)` |
| Queries | `tax_view(taxpayer, period)`, `filing_calendar(taxpayer)`, `reserve(book)` (set-aside per book from taxpayer-level figures), `warnings`, `rules_watch`, `render_figure(id, locale)` (labelled block) |
| Emits · consumes | `coflow.tax.obligation.due`, `coflow.tax.estimate.computed`, `coflow.tax.warning.raised`, `coflow.tax.pack.loaded` · `coflow.fin.entry.posted`, `coflow.fin.invoice.registered`, `coflow.fin.period.closed` |
| Depends on | FIN (`taxpayer_entries`, invoices with a compliant source); CFG (residence, regime, registration in the intra-EU operator register (ROI), individual or joint filing). Never MDL with figures |
| Requirements | FIN-10…FIN-13, FIN-15, FIN-17, FIN-18; D-026, D-027 |
| Data classes · DATA_FLOWS | financial · tax figures to a model: never (placeholders only); to `messenger` and `mcp:<client>` only as rendered blocks, per the financial switch; advisor export to `export` |
| Acceptance suite | Golden files per tax year; fixtures for one person with two books and for a person plus their company; one fixture per threshold; a fixture with only intra-EU purchases; a fixture of manual issued invoices; the core suite with no pack installed |
| Usage signal | Obligations tracked and estimates viewed per quarter |
| Approval | **Owner**, with two review rounds and the advisor's review of the pack |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Functional correctness (tax matrix) | Golden matrix per tax year: Spanish B2B, EU B2B, EU B2C, non-EU B2B, non-EU B2C, EU purchase, non-EU purchase | 100 % |
| Functional correctness (calendar) | Calendar vs. the official one for the tax year, including moves off non-working days; a year without a pack; 349 on a fixture with only intra-EU purchases; obligations judged not to apply (130 by the 70 % rule, 202 without the pack's condition) | Equal; "no calendar for <year>", never a guess; listed; listed as "considered not applicable" with rule and source, never left out |
| Security (labels) | Tax figures in any output outside a rendered block with the label and pack version; tax figures in model calls; calendar entries, reminders, applicability decisions or warnings without the label and pack version | 0; 0; 0 |
| Functional correctness (taxpayer scope) | Income-tax estimate on the fixture with practice income and household savings interest; sums across taxpayers; a joint return or an attribution-of-income entity the pack does not support | Includes both, names both books; 0; marked "incomplete" |
| Functional correctness (warnings) | Fixtures crossing each threshold (720 per category, including the re-filing increase; 721 for crypto held abroad; monthly 349; cash payments toward one operation of EUR 1,000 or more, split payments added up, in any book where either party acts as a business; foreign tax withheld; related-party flows; EU B2B while ROI is "not registered" or unknown; EU B2B without a VAT-number check dated on or before accrual) | Exactly 1 warning each, with its rows, the label and the pack version |
| Functional correctness (estimates) | Quarterly estimate vs. the filed amount after two quarters; figures from an unverified pack year; VAT figures that depend on "manual, outside register" records | Within 10 % of the filed amount until the owner sets a tolerance; 100 % marked "unverified"; 100 % marked "incomplete: invoices outside a compliant invoicing system" |
| Functional correctness (export) | Export pack content for the same data (timestamps aside); manual issued invoices in the official issued-register layout, a per-form figure or a box mapping | Byte-identical; 0 |

### GOL — Centre and goals (stage 8, module 2)

Helps the owner form their centre (values, manifest, life vision, directions, period goals) and checks
whether time, money, commitments and decisions follow it. The owner writes or adopts every sentence; the
system asks, structures, gives feedback against fixed criteria, offers wording only as marked suggestions
and versions what the owner approves. Control is computed by code; a model only phrases. No composite
score.

| Field | Value |
|---|---|
| Release · stage | R2 · 8.2; WRK-4 hypotheses in 8.8 |
| Runs in | `core` |
| Owns | `gol_centre_documents`, `gol_centre_versions` (immutable, with diffs), `gol_spans`, `gol_rules` (typed fields; free text only as a span reference), `gol_directions` and `gol_goals` (transferred from WRK, ids unchanged), `gol_goal_versions`, `gol_hypotheses`, `gol_if_then_plans`, `gol_sessions` and `gol_drafts` (journal class; origin owner or MCP client), `gol_reviews`, `gol_verdicts` (output, outcome, path), `gol_check_marks`, `gol_reflections` (journal class when journal input was used) |
| Commands | `import_centre_documents`, `classify_section`, `start_session(protocol)`, `submit_draft`, `propose_version` (approval card with diff), `approve_version` (bot or local CLI only), `set_rule_field`, `create_direction`, `create_goal`, `activate_goal`, `set_goal_state` (pause, drop, supersede only in a deliberation review or by a DEC record), `park_for_deliberation`, `record_verdict`, `set_cap`, `mark_check` |
| Queries | `centre(version)`, `directions`, `goals(filter)`, `goal_context` (money targets through FIN), `control_list(period)`, `review_pack(period)`, `session_state` (owner channels only), `self_measures` |
| Emits · consumes | `coflow.gol.centre.version_approved`, `coflow.gol.direction.created` / `changed`, `coflow.gol.goal.created` / `state_changed` / `moved`, `coflow.gol.review.completed`, `coflow.gol.check.switched_off` · none (reads through `api` at review time) |
| Depends on | WRK, FIN, CMT, CAL, DEC, MTG, RHY; ACT; MDL (dialogue, pointing to spans, phrasing); CFG. Implements `GoalDirectory` and `ReviewContributor` |
| Requirements | GOL-1…GOL-12, LRN-6, RHY-4 (link), WRK-1 (directions and goals, from 8.2), WRK-4, CFG-4, CFG-5, REL-6 (centre version per analysis); D-028 |
| Data classes · DATA_FLOWS | work (approved centre, rules, goals), journal (sessions, drafts, journal-derived reflections) · session turns to `provider` (formation; journal class, so model feedback in sessions needs the journal switch on for GOL, or the local model); approved centre to `mcp:<client>` read; drafts from MCP write-only (a client cannot read sessions or drafts back) |
| Acceptance suite | A synthetic year with planted problems (top direction at 5 % of hours, a goal without a next step for 30 days, a cap exceeded, a domain with zero time) and planted non-problems; a provenance set with pasted-back model sentences and MCP-origin drafts; byte-identical import fixtures |
| Usage signal | Sessions completed; share of active goals with attainment levels and an if-then plan; review completion; median session duration. The pause rule for the weekly review is enforced by RHY |
| Approval | **Owner** |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Safety (authorship) | Approved sentences not traced to owner-typed text; sentences with normalised 5-gram overlap ≥ 0.6 with a model output of the session, not recorded by an owner action as "adopted from suggestion" or "adopted from reflection"; versions approved outside the bot or local CLI | 0; 0; 0 |
| Safety (rule objects) | Free text in a confirmed rule not byte-equal to a centre span; planted model paraphrases that can be confirmed | 0; 0 |
| Functional correctness (import) | Imported text vs. source; centre content in a fresh install | Byte-identical; 0 |
| Functional correctness (control) | Same data → same list; recall on the synthetic year; false alarms among raised items; items raised where layer coverage < 70 % instead of "can't judge"; time checks without a time source | Identical; ≥ 90 %; ≤ 10 %; 0; 100 % "can't judge (no time source)" |
| Safety (modes) | Daily or weekly messages offering pause, drop or supersede; parked goals missing from the next deliberation review | 0; 0 |
| Interaction capability | Owner-rated ownership and commitment after each session (1–5); cost per session | Median ≥ 4, a falling trend over 3 sessions is a defect; ≤ $0.50 by default |
| Functional suitability (self-measurement) | A planted check marked useless over its last 5 runs that stays on (the weekly-review pause is tested in RHY) | 0 |

GOL's control list cites WRK's control-view items and adds only declaration-level checks: caps, the share
of time and money per direction, period goals and neglect. Envelopes are shares and caps; money amounts
tied to a goal are FIN targets. Time comes from CAL and RHY's activity spans; where no spans exist (before
stage 6, or without the activity agent) the time checks answer "can't judge (no time source)".

---

### ALN — Inconsistency findings (stage 8, module 2b)

Compares what the owner thinks (journal, under PRV-9), says (conversations) and does (tasks, time,
commitments, money) with the versioned centre from GOL. Every finding is a pair of evidence — "the centre
says … — the stream shows …" — with the verdict consistent, inconsistent or can't judge. Built right after
the goals module by the owner's decision of 4 October 2026; alignment formulas and scores stay research.

| Field | Value |
|---|---|
| Release · stage | R2 · 8.2b |
| Runs in | `core` |
| Owns | `aln_checks` (versioned check definitions), `aln_runs` (period, scope, centre version, coverage per layer), `aln_findings` (work class; evidence references on both sides), `aln_findings_j` (journal class, when journal input was used), `aln_marks` (useful / not useful), `aln_eval_runs` (results on the planted sets) |
| Commands | `run_check(scope, period)`, `mark_finding`, `enable_check`, `disable_check` |
| Queries | `findings(period, scope)` (journal-class findings only in owner channels), `check_status`, `eval_results` |
| Emits · consumes | `coflow.aln.run.completed`, `coflow.aln.check.switched_off` · none (reads through `api` at run time) |
| Depends on | GOL (centre versions, rule objects), WRK, CMT, FIN, CAL, RHY, SIG, JRN (through MDL under PRV-9); MDL; CFG |
| Requirements | ALN-2…ALN-5, PRV-9, LRN-6 (adds findings to the weekly reflection when enabled), SIG-14, REL-6; D-017, D-029 |
| Data classes · DATA_FLOWS | work (findings from work data), journal (findings that used journal input) · centre spans and stream excerpts to `provider` per check; journal input only with the switch on for ALN; journal-class findings never to `mcp:<client>`, search, the timeline or the status page |
| Acceptance suite | A synthetic quarter with planted inconsistencies and planted consistent cases across think, say and do; journal canaries under both switch settings; evidence-integrity fixtures (every quote equals a stored segment or record) |
| Usage signal | Findings marked useful per month; checks switched off; weekly-reflection lines that cite a finding |
| Approval | **Owner** |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Functional correctness (evidence) | Findings without evidence on both sides; quotes not equal to a stored segment or record | 0; 0 |
| Functional correctness (detection) | Recall on the planted set before a check is shown; findings raised on planted consistent cases | ≥ 70 %; ≤ 15 % |
| Honesty | Findings raised where evidence coverage is below 70 % instead of "can't judge" | 0 |
| Safety (journal) | Journal-derived findings reaching MCP, search, the timeline or the status page; journal text in any call with the switch off | 0; 0 |
| Usefulness | Checks with fewer than 30 % of their last 20 findings marked useful that stay on | 0 |
| Cost | Cost of a weekly run on the synthetic quarter | ≤ $0.50 by default |

---

## Interfaces

### BOT — Messenger bot

The private daily interface: long polling, owner only, rule-based routing (work by default, journal by
marker), local transcription of voice before routing, answers through `api` queries, approval cards,
notifications with caps and quiet hours, sources and a "wrong" button.

| Field | Value |
|---|---|
| Release · stage | R1 · 2; BOT-6 in R2 · 7 |
| Runs in | `core` |
| Owns | `bot_offsets`, `bot_routes` (message ref → route), `bot_notifications` (sent, caps) |
| Commands | `handle_update` (internal), `route`, `send_notification`, `render` (data-flow check for `messenger`) |
| Queries | None public (state on the status page) |
| Emits · consumes | `coflow.bot.message.routed` (journal routes carry no text) · `coflow.act.card.proposed`, `coflow.rhy.plan.delivered`, `coflow.mtg.brief.ready`, `coflow.sig.transcript.ready`, `coflow.cmt.commitment.due`, `coflow.tax.obligation.due`, `coflow.obs.health.degraded` |
| Depends on | Module `api`s; ACT, JRN, LRN, POL, MDL, CFG; STT through jobs; messenger port (one reference adapter and a fake) |
| Requirements | BOT-1…BOT-7, BOT-8…BOT-10, LRN-7 (gap to scenario change), OPS-14 (provider errors), P-5, P-10; threads follow BOT-2 routing |
| Data classes · DATA_FLOWS | all classes pass its renderer · `messenger` rows per class; journal outputs only when the journal × messenger row is on (otherwise the local CLI) |
| Acceptance suite | Fake messenger with text, voice, captions, replies, commands and forwards; double taps and restarts; quiet-hour clock tests |
| Usage signal | Owner messages per active day; cards decided per week |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Security (owner only) | Messages from other senders that are acted on | 0 |
| Security (routing canary) | Journal canary in a model call before the owner's choice, over every message kind, under both switch settings | 0 |
| Security (financial) | Financial canary in bot answers with the financial × messenger row off | 0 |
| Safety | Card executions under double taps and restarts | Exactly 1 |
| Performance efficiency | Answer latency; answers without the cost shown | Median ≤ 15 s; 0 |
| Interaction capability | Notifications breaking the daily cap or quiet hours | 0 |
| Interaction capability (asking) | Turns asking more than one question, or asking again about something already resolved in the same command (BOT-10) | 0 and 0 |
| Functional correctness (scenarios) | Scenarios without a covering test; prompts or tool descriptions drifted from their scenario (BOT-9) | 0 and 0 |
| Interaction capability (gaps) | Refusals that end without a named gap and a proposed scenario change (LRN-7) | 0 |
| Transparency (provider errors) | Raw provider payloads reaching the owner; balance alerts beyond one a day (OPS-14) | 0 and 0 |

### MCP — MCP server

Context-oriented tools over module `api`s: Streamable HTTP inside `core` on loopback with scoped tokens
and host and Origin checks; stdio through BRG; a generated catalogue; remote MCP for cloud clients in 8.6.

| Field | Value |
|---|---|
| Release · stage | R1 · 1; R2 · 8.6 (MCP-5) |
| Runs in | `core` |
| Owns | `mcp_clients` (token hash, scope, tool allow-list, allowed flows), `mcp_call_log` |
| Commands | Tool calls mapped to `api` commands: internal writes execute, are logged in `act_undo_log` and are undoable; external writes return a preview only. `issue_client`, `revoke_client` (through ADM) |
| Queries | Tool calls mapped to `api` queries; `catalogue` |
| Emits · consumes | none · none |
| Depends on | Module `api`s; ACT, OBS, POL |
| Requirements | MCP-1…MCP-5, DEP-11, DEP-12, GOL-5 (drafts only, origin "MCP client") |
| Data classes · DATA_FLOWS | work, financial per client · one `mcp:<client>` row per client; journal never |
| Acceptance suite | HTTP tests with valid, missing and read-only tokens; response-layer canaries (journal, financial); generated catalogue diff; read-tool latency on the synthetic dataset |
| Usage signal | Calls per tool per week; tools without a call in 90 days are reviewed for removal |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Security (auth) | Requests without a valid token; write tools reachable with a read-only token | 401 in 100 %; 0 |
| Security (journal) | Journal tools in the catalogue; journal canary or journal-derived output in responses | 0; 0 |
| Security (financial) | Financial canary in responses to a client without the financial flow | 0 |
| Maintainability | Generated catalogue vs. code; write tools without an undo handler or a "not undoable" mark | Equal; 0 |
| Performance efficiency | Read-tool latency on the synthetic dataset | p95 ≤ 2 s |
| Interaction capability | Responses without the instance role and id | 0 |

### STS — Status page

The only R1 web screen: health, queues, freshness, costs, switch states and module scorecards, on loopback
with the same token and host check as MCP. More screens only when their use is measured.

| Field | Value |
|---|---|
| Release · stage | R1 · 4; UI-2 Later |
| Runs in | `core` |
| Owns | None (reads OBS, EVT, MDL, OPS, POL through `api`) |
| Commands · Queries | none · `status`, `scorecards`, `queue_details` |
| Emits · consumes | none · none |
| Depends on | OBS, EVT, MDL, OPS, POL |
| Requirements | UI-1, PRV-9 (switch state shown); UI-2 Later |
| Data classes · DATA_FLOWS | system and aggregates · `status_page` |
| Acceptance suite | HTTP tests without a token and from a non-loopback address; injected failures; content canaries |
| Usage signal | Visits per week per screen: fewer than 1 a week for 4 consecutive weeks removes the screen |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Security | Reachable without a token or from a non-loopback address; journal or financial content shown | 0; 0 |
| Reliability | Time for an injected failure to appear | ≤ 5 min |
| Interaction capability (usage rule) | Screen removal triggered by < 1 visit a week over 4 weeks (rule test) | Triggered in 100 % of test cases |

### INT — Integration and ingestion API

The public versioned contract for external apps (read a brief; write a session, highlights and an
outcome, idempotently) and the ingestion API for device agents (resumable uploads, CloudEvents batches,
agent configuration).

| Field | Value |
|---|---|
| Release · stage | R2 · 6 |
| Runs in | `core` (HTTP on the `core` listener) |
| Owns | `int_clients` (scoped, revocable tokens; per-device source types), `int_idempotency` (key → result), `int_uploads` (resumable chunks) |
| Commands | `write_session`, `write_highlights`, `write_outcome`, `upload_chunk` / `complete_upload`, `ingest_events` |
| Queries | `read_brief`, `agent_config` (direction list and active rules from RHY) |
| Emits · consumes | `coflow.int.upload.completed`, `coflow.int.events.ingested` · none |
| Depends on | SIG, MTG, PPL, RHY; EVT, POL |
| Requirements | EXT-4, DEP-16, RHY-5 (rule distribution) |
| Data classes · DATA_FLOWS | work · `app:<client>` and `device:<id>` rows |
| Acceptance suite | JSON Schema contract suite against the reference consumer; replay tests; deploy-hold tests |
| Usage signal | Calls per client per week |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Functional correctness (idempotency) | Duplicate sessions, outcomes or events after replaying with the same key or event id | 0 |
| Compatibility | Contract suite on provider and reference consumer | Passes; a breaking change needs a new version |
| Security | Writes outside a device token's source types; device text treated as an instruction; outcomes that create commitments without approval | 0; 0; 0 |
| Reliability | Behaviour during deploy holds | 503 with `Retry-After`; 0 lost uploads |

### ADM — Admin API and CLI

The loopback admin API on the `core` listener and the `coflow` CLI that calls it. Every CLI write and bulk
import goes through it with a scoped token; only `migrate`, `restore` and `drill` run without a live
`core` in their target instance, under the OS-held instance lock.

| Field | Value |
|---|---|
| Release · stage | R1 · 0 |
| Runs in | `core` listener (`/admin`, 127.0.0.1); CLI on the host or through `docker compose exec` |
| Owns | `adm_tokens` (hash, scope: `admin`, `import`, `journal-write`, `journal-read`) |
| Commands | Every write the CLI offers (`journal add`, `import`, `export`, `backup`, `promote`, `retire`, `set-flow`, `issue-mcp-client`, approvals before stage 5) |
| Queries | `status`, `logs` (ids only), `doctor`, journal reading (journal-read token, owner's terminal only) |
| Emits · consumes | none · none |
| Depends on | OPS, POL, ACT and module `api`s |
| Requirements | DEP-11, OPS-1, PRV-1 (local entry path) |
| Data classes · DATA_FLOWS | all classes, owner channel · none outbound |
| Acceptance suite | CLI against a running `core` on a temp data root; token-scope matrix; fitness test on the CLI entry point |
| Usage signal | Kernel: admin calls per week |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Security (one writer) | CLI entry point able to resolve the database path while `core` runs; writes that bypass the admin API | 0; 0 |
| Security (scopes) | A journal-write token that can read; journal reads available to forced-command keys | 0; 0 |
| Functional correctness | Changes after re-running the same bulk import | 0 |

---

## Satellites

### STT — Speech-to-text and extraction worker

A stateless local worker: transcription of voice notes and recordings, and from 8.1a local text and OCR
extraction of financial documents. It takes jobs from files, returns schema-validated results and has no
database and no network (ARCHITECTURE §6.5).

| Field | Value |
|---|---|
| Release · stage | R1 · 2 (voice), 4 (recordings); R2 · 8.1a (`extract`); embeddings Later (SRC-5) |
| Runs in | `stt` container; a supervised subprocess pool in native development |
| Owns | No tables; job, result and audio files in `work/`, deleted on completion |
| Commands · Queries | `transcribe(job)`, `extract(job)` · `bench` (`coflow bench stt`) |
| Emits · consumes | none (`core` records completion in `sys_jobs`) · none |
| Depends on | `coflow.contracts` only; the models volume |
| Requirements | BOT-7, SIG-2, SIG-3, SIG-14, NFR-11, FIN-14 (local extraction); SRC-5 Later |
| Data classes · DATA_FLOWS | transient work, journal or financial content in `work/` · none outbound (no network) |
| Acceptance suite | Synthetic EN and RU audio benchmark; OOM kill mid-job; malformed-result fixtures; residue scan of `work/` |
| Usage signal | Jobs per day and backlog on the status page |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Performance efficiency | Real-time factor on the reference CPU class recorded by `coflow bench stt` (default: 8 x86-64 cores) | 1-min voice note ≤ 20 s; 1-h recording ≤ 30 min |
| Reliability | Out-of-memory kills recovered as transient errors without a human | 100 % |
| Security (isolation) | Database or network access (Compose lint, import contract, fitness test); malformed results accepted by `core` | 0; 0 |
| Security (residue) | Files left in `work/` after completion, and after a kill mid-job plus recovery | 0 |
| Functional correctness | Word error rate on the synthetic benchmark vs. the recorded baseline | No regression > 2 points |

### BRG — MCP stdio bridge

`coflow-bridge mcp` forwards a stdio MCP client to `core`'s loopback MCP endpoint with that client's
scoped token. It is started by an SSH forced command and holds no database path.

| Field | Value |
|---|---|
| Release · stage | R1 · 1 |
| Runs in | The host, one process per MCP client, started by an SSH forced command |
| Owns | Nothing |
| Commands · Queries | None of its own; forwards MCP requests and responses |
| Emits · consumes | none · none |
| Depends on | `coflow.contracts`; `core`'s loopback MCP endpoint |
| Requirements | MCP-1, DEP-11 |
| Data classes · DATA_FLOWS | Whatever MCP returns to that client, checked in MCP's response layer · covered by the client's `mcp:<client>` row |
| Acceptance suite | MCP conformance suite through the bridge and directly over HTTP; forced-command tests |
| Usage signal | Bridge sessions per client per week (from the MCP call log) |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Security | Database path resolvable; requests forwarded without the client's token | 0; 0 |
| Compatibility | MCP conformance suite through the bridge vs. direct HTTP | Same results |

### AGT — Device agents

Agents on other machines: the Windows uploader for recorder and export folders, and the activity agent
(aggregated spans only). They store and forward to INT, idempotent by event id and content hash.

| Field | Value |
|---|---|
| Release · stage | R2 · 6 |
| Runs in | The owner's desktop |
| Owns | A local buffer on the device (never the core database) |
| Commands · Queries | `watch_folders`, `push_events`, `upload_file` · local status |
| Emits · consumes | `coflow.agt.activity.span_recorded`, `coflow.agt.file.offered` (through INT) · rules and directions from INT |
| Depends on | INT over HTTP; `coflow.contracts` |
| Requirements | RHY-5, DEP-17, NFR-1 |
| Data classes · DATA_FLOWS | work · `device:<id>` row; window titles never leave the device |
| Acceptance suite | 72-hour offline simulation; canary window titles; rule-version tests |
| Usage signal | Spans and uploads per day |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Reliability (store and forward) | Lost or duplicated events after 72 h offline and reconnecting | 0 and 0 |
| Security (minimal intake) | Window titles or screenshots leaving the device (canary); titles kept past 90 days | 0; 0 |
| Functional correctness | Spans classified with rules that have not passed the labelled-day gate | 0 |

### UPD — Updater

`coflow-updater` on the host, outside the stack: pulls by digest, verifies the signature, waits for the
owner's approval, holds writes, snapshots, migrates, health-gates and rolls back (DEPLOYMENT §7).

| Field | Value |
|---|---|
| Release · stage | R1 · 0 (manual `coflow update <digest>` over SSH), 2 (signature verification), 5 (approval card bound to the digest, holds, automatic rollback); DEP-21 Later |
| Runs in | The host (systemd timer); the only component that calls Docker |
| Owns | Host files: handled tags, the deploy lock, approvals read from `control/` |
| Commands · Queries | `approve <version>` (CLI, stages 0–4), `deploy`, `rollback --to-snapshot` · `status`, deploy history (recorded through OPS) |
| Emits · consumes | Deploy records in `control/`, picked up by OPS into `sys_deploys` · approvals written to `control/` by `core` (from stage 5) |
| Depends on | Docker Engine, the image registry, signature verification; never the database |
| Requirements | DEP-8, DEP-9, DEP-10; DEP-21 Later |
| Data classes · DATA_FLOWS | system · the image-registry row (host address, pull times) |
| Acceptance suite | Signature tests with wrong identities; approval-hash mismatch and expiry; the rollback and failed-rollback drills |
| Usage signal | Deploys and rollbacks per month |
| Approval | CI scorecard plus the drills of DEPLOYMENT §10.3 |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Security | Images deployed with a missing or foreign signature; approvals accepted that mismatch, expired or came from another instance | 0; 0 |
| Reliability (rollback drill) | A deliberately broken release | Rolled back automatically; no lost bot message; no external write |
| Reliability (failed rollback) | A rollback that fails | Everything stopped; off-host alert received |

---

## Plugins

### PLG — Plugin host

The versioned plugin contract (ARCHITECTURE §6.6). Plugins never open database connections: in process
they read through the host's facade and write through the writer queue as `px_<id>`; out of process they
exchange JSON-RPC over stdio. Plugins declare flows, ports and warnings and are off by default.

| Field | Value |
|---|---|
| Release · stage | R1 · 4 (in-process host); R2 · 8.7 (out-of-process host) |
| Runs in | `core`; out-of-process plugins as supervised child processes |
| Owns | `sys_plugins` (manifest, version, hookspec range, enabled, warning acknowledged); each plugin's `px_<id>_*` tables are registered to it |
| Commands · Queries | `install`, `enable` (warning acknowledged), `disable`, `uninstall` · `plugins`, `declared_flows(plugin)` |
| Emits · consumes | `coflow.plg.plugin.enabled` / `disabled` · as declared per plugin |
| Depends on | STO (writer queue, authorizer), EVT, POL, MDL; declared module `api`s |
| Requirements | EXT-1, P-14 |
| Acceptance suite | A test plugin that tries to write outside its tables, to resolve the database path and to call undeclared ports; the core suite with every plugin uninstalled |
| Usage signal | Plugins enabled |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Security (ownership) | Plugin writes outside `px_<id>_*`; plugin entry points that resolve the database path | 0; 0 |
| Security (declarations) | Plugins loaded with undeclared flows or ports; enabled without the warning acknowledged | 0 (refused); 0 |
| Compatibility | Plugins with a hookspec mismatch | Refused with a clear message |
| Maintainability (removable) | Core suite with all plugins uninstalled | Passes |

### TGC — Messenger user-session collector

Read-only collection of marked chats through the owner's user session (encrypted), with local
transcription of voice and video notes. Off by default, with an explicit warning about account access
and the messenger's terms.

| Field | Value |
|---|---|
| Release · stage | Plugin · 4 |
| Runs in | `core`, in process; off by default |
| Owns | `px_tgc_cursors`, `px_tgc_chats` (marked chats) |
| Commands · Queries | `mark_chat`, `unmark_chat`, `collect` (scheduled) · `collection_state` |
| Emits · consumes | none (batches go to `SIG.import_connector_batch`, which emits the events) · none |
| Depends on | SIG (inbox contract); STT through jobs; a read-only user-session port |
| Requirements | SIG-7, SIG-8 |
| Data classes · DATA_FLOWS | work · the messenger account as an inbound source; the encrypted session in the secrets store |
| Acceptance suite | Fake account with marked and unmarked chats; send-capability test; re-collection fixtures |
| Usage signal | Messages collected per day from marked chats |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Safety | Send capability in the plugin (test); collection from unmarked chats | Cannot send; 0 |
| Functional correctness | Changes after re-collecting the same window | 0 |

### MLR — Mail read

Mail threads where the owner wrote or the counterpart is in the registry; newsletters and promotions
dropped, quotes stripped, no attachments, never sends.

| Field | Value |
|---|---|
| Release · stage | Plugin · 4 |
| Runs in | `core`, in process; off by default |
| Owns | `px_mlr_cursors` |
| Commands · Queries | `collect` (scheduled) · `collection_state` |
| Emits · consumes | none (batches go to `SIG.import_connector_batch`) · none |
| Depends on | SIG (inbox contract), PPL (registry lookups); a read-only mail port |
| Requirements | SIG-10 |
| Data classes · DATA_FLOWS | work · the mailbox as an inbound source, read-only scope |
| Acceptance suite | Labelled mailbox fixture (owner-written, registry counterparts, promotions); scope test |
| Usage signal | Threads imported per week |
| Approval | CI scorecard |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Security | Token requests with a forbidden scope; send capability | Test fails; cannot send |
| Functional correctness | Promotional threads imported from the labelled fixture | ≤ 5 % |

### IMP — Statement import

Bank statement files in, normalised rows out, posted through FIN's `api`. Identity: the format's own id,
then a content fingerprint, then an occurrence index; raw lines and file hashes are kept; never bank
credentials. Proposed: Norma 43 and one CSV profile ship with 8.1a; camt.053, OFX and further CSV profiles
in 8.7 (MT940, QIF optional).

| Field | Value |
|---|---|
| Release · stage | Plugin · 8.7 (one format and one CSV profile proposed for 8.1a) |
| Runs in | In process for permissively licensed parsers; GPL-only parsers out of process |
| Owns | `px_imp_files` (hash), `px_imp_rows` (raw line, identity key), `px_imp_mappings` (CSV profiles) |
| Commands · Queries | `import_statement(file, book, account)` → `FIN.post_imported_entries` · `import_report(file)` |
| Emits · consumes | `coflow.imp.statement.parsed` · none |
| Depends on | FIN |
| Requirements | FIN-3 |
| Data classes · DATA_FLOWS | financial · none outbound |
| Acceptance suite | Golden fixtures per format; the five failure-mode fixtures; reconciliation fixtures |
| Usage signal | Statements imported per month |
| Approval | **Owner** |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Functional correctness (failure modes) | Changes after: the same file twice; an overlapping statement; a re-export with different formatting; duplicates inside one file. Genuine identical same-day payments dropped | 0 in each; 0 (both kept) |
| Functional correctness (reconciliation) | Opening + movements vs. the statement's closing balance | Equal; a mismatch is shown, never forced |
| Security | Schema fields that can hold a bank credential | 0 |
| Compatibility | Golden fixtures per format | 100 % pass |

### INV — Invoice API adapters

Read-only adapters per invoicing tool, mirroring issued and received invoices, status and payments into
FIN's register. The file adapter in FIN comes first; an API adapter is an optional extra. Records from a
tool that is not a compliant invoicing system are marked "manual, outside register" and feed only plain
lists with totals (FIN-8, FIN-9).

| Field | Value |
|---|---|
| Release · stage | Plugin · any time after 8.1a |
| Runs in | `core`, in process |
| Owns | `px_inv_cursors` |
| Commands · Queries | `sync_invoices(book)` (scheduled; into FIN's register with the same identity rules as file imports) · `sync_state` |
| Emits · consumes | none (FIN emits `coflow.fin.invoice.registered`) · none |
| Depends on | FIN; an invoice-reader port with read-only scopes |
| Requirements | FIN-16 (API adapters) |
| Data classes · DATA_FLOWS | financial · the invoicing tool, inbound only; API keys in the secrets store, never in a model call or log |
| Acceptance suite | Contract test against a recording fake API that fails on any write call; period-total fixtures; re-import fixtures |
| Usage signal | Invoices mirrored per period |
| Approval | **Owner** |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Safety (read-only) | Non-GET or write calls in the contract test; scopes not listed in the manifest | 0 (the test fails on any); 0 |
| Functional correctness | Invoice count and totals per period vs. the source tool; changes on re-import | Equal; 0 |
| Security | API key in any model call or log (canary) | 0 |

### NEG — Negotiation through the owner's messenger

On the owner's explicit instruction for one contact, proposes 2–3 slots through the owner's messenger
account, through the outbox, treating counterpart text as untrusted; a final card to the owner, then a
calendar write. Starts with a spike.

| Field | Value |
|---|---|
| Release · stage | Plugin · 8.4 (after a spike) |
| Runs in | `core`, in process; off by default |
| Owns | `px_neg_threads`, `px_neg_messages` |
| Commands · Queries | `start_negotiation(contact, meeting intent)`, `propose_slots`, `finalize` · `negotiation_state` |
| Emits · consumes | `coflow.neg.agreement.reached` · `coflow.act.operation.verified` |
| Depends on | CAL (free slots), MTG; ACT (implements `OperationHandler` for messenger sends); messenger port |
| Requirements | MTG-8 |
| Data classes · DATA_FLOWS | work · `messenger` to the counterpart through ACT: slot times only, never busy-event titles |
| Acceptance suite | Injection set of counterpart messages; recording fake messenger and calendar; busy-title canaries |
| Usage signal | Negotiations started and completed per month; none completed in the first 60 days → redesign or removal |
| Approval | **Owner** |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Security (injection) | Tool calls or approvals triggered by counterpart text on the injection set | 0 |
| Security (disclosure) | Busy-event titles revealed to the counterpart (canary) | 0 |
| Safety | Messages sent outside the outbox or without an explicit instruction for that contact | 0 |

### WPL — Week plan

The week plan as calendar windows and slots, applied with one card. Ships only after use is proven.

| Field | Value |
|---|---|
| Release · stage | Plugin · 8.8 |
| Runs in | `core`, in process; off by default |
| Owns | `px_wpl_plans`, `px_wpl_slots` |
| Commands · Queries | `propose_week_plan`, `apply` (ACT card), `update` · `week_plan` |
| Emits · consumes | `coflow.wpl.plan.applied` · `coflow.cal.write.verified` |
| Depends on | CAL, ACT; `GoalDirectory` |
| Requirements | MTG-10 |
| Data classes · DATA_FLOWS | work · calendar writes only through CAL's handler |
| Acceptance suite | Re-apply fixtures on the recording fake calendar |
| Usage signal | Slots applied per week: 0 in the first 30 days after shipping → removed or redesigned |
| Approval | CI scorecard (its writes go through CAL's owner-approved handler) |

| Quality attribute | Metric | Acceptance threshold |
|---|---|---|
| Safety | Duplicate events after re-applying the same plan | 0 |
| Interaction capability (usage rule) | Removal or redesign issue when 0 slots are applied in 30 days (rule test) | Triggered in 100 % of test cases |

---

## Research

Research modules (D-029) — relationship measures, conductivity and evolution — live in the `coflow_research` plugin, after the stage-8 modules, and start only
on core data that R1 already stores (REL-6), each with a pre-registered protocol. They own `px_<code>_*`
tables, read through the host's facade (declared `pub_` views), reach the journal only through MDL under
PRV-9, and store journal-derived findings in journal-class tables shown only in owner channels. No core
module imports them, and removing them needs no core migration. Each gets a full card when it starts.

| Code | Module | Requirements | Reads | Key acceptance thresholds |
|---|---|---|---|---|
| REL | Relationship measures E(t) and balance alerts; stated positions only | REL-1…REL-3 | SIG, MTG, CMT, PPL | Same data → same series; values without links to their events: 0; recall of planted balance shifts in a synthetic quarter ≥ 90 %; schema fields for inferred emotions or diagnoses: 0 |
| CND | Conductivity protocol and prediction of G(t+1), specified after a planned experiment gate (November 2026) | REL-4, REL-5 | REL measures, SIG, MTG | Corpus cases without a prediction locked before the outcome: 0; predictive models shown before beating the pre-registered baselines: 0 |
| EVO | Evolution over time: positions per period, communication change, recurring chains of thought | TML-3 | TML, REL; the journal under PRV-9 | Findings without per-period evidence: 0; same data → identical series |

Common to all three: core changes needed to remove the module — none; any alignment or conductivity
formula stays an experiment inside the plugin and is never a product score.
