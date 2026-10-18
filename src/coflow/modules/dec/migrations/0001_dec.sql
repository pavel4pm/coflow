-- DEC: every table of spec §2.4 and the import, shadow and case bookkeeping of §2.6.
-- Owned by track S (store, import, shadow); increment I1, spec §12.2.
--
-- The file contract is in coflow/kernel/store/api.py: STRICT tables with the dec_ prefix, created
-- in dependency order (decisions, forks, options, assumptions, readings, checks, facts, then the
-- rest), and one sys_table_registry row per table. K's runner generates the BEFORE UPDATE / BEFORE
-- DELETE triggers from those rows after this file runs: no table accepts DELETE; append-only tables
-- accept only set-once columns (NULL to a value, once) and erasure of erasable columns; mutable
-- tables accept changes of their mutable columns only. tx and recorded_at are stamped by the store.
--
-- Columns common to every table (spec §2.4): tx, recorded_at; [O] importable tables add
-- origin_recorded_at and origin_ref; [E] tables with erasable columns add erased_tx.
--
-- Spec notes (track S):
-- * dec_decisions lists origin_ref twice in §2.4 (the [O] column and the "decided in" reference);
--   it is one column, holding the "decided in" ref (model.py says the same).
-- * dec_readings declares voided_reason as set-once next to voided_at, as dec_checks does.
-- * dec_import_runs gains source_computed_json: the snapshot's v1_computed block, its declared
--   counts and the decision ids it held. §6.5 requires that `coflow dec shadow --run N` recomputes
--   a report that was never stored, which needs what v1 said; the file itself is not kept.
-- * dec_foreign_context, dec_mirror_state, dec_shadow_items and dec_cases carry tx and recorded_at
--   like every domain table (api.py); §2.6 leaves them implicit.
-- * Sequence counters (a_seq, ck_seq, ...) and current_edition are bookkeeping: they are mutable
--   and never versioned; the edition rows are the history of current_edition.
-- * The heads dec_decisions and dec_forks declare their free-text columns both mutable and
--   erasable: DEC's commands and the importer change them (with version rows), and POL's erasure
--   unit blanks them with a new erased_tx (the store's authorizer allows the owner an erasable
--   column only when it is also mutable). title stays out: it is the naming layer (renames add
--   aliases) and NOT NULL. The erasure command itself arrives with PRV-7 (0B or stage 1).

-- 1. The decision head. Mutable through commands only; every content change versioned. [O][E]
CREATE TABLE dec_decisions (
  id                   INTEGER PRIMARY KEY,
  public_id            TEXT NOT NULL UNIQUE,
  number               INTEGER NOT NULL UNIQUE,
  title                TEXT NOT NULL,
  question             TEXT,
  statement            TEXT,
  kind                 TEXT NOT NULL DEFAULT 'choice' CHECK (kind IN
                         ('choice','test','pursue','attendance','advisee','forecast_container')),
  decider              TEXT NOT NULL DEFAULT 'self' CHECK (decider IN ('self','joint','other')),
  decider_basis        TEXT NOT NULL DEFAULT 'stated' CHECK (decider_basis IN ('stated','mapped','assumed')),
  decider_ref          TEXT,
  depth                TEXT NOT NULL DEFAULT 'light' CHECK (depth IN ('light','full')),
  depth_basis          TEXT NOT NULL DEFAULT 'computed' CHECK (depth_basis IN ('computed','owner','import')),
  reversibility        TEXT NOT NULL DEFAULT 'unknown' CHECK (reversibility IN
                         ('cheap','costly','irreversible','unknown')),
  status               TEXT NOT NULL DEFAULT 'draft' CHECK (status IN
                         ('draft','active','closed','cancelled','superseded','withdrawn')),
  manual_flag          TEXT CHECK (manual_flag IN ('ZOMBIE','OFF_TRACK')),
  manual_flag_reason   TEXT,
  context              TEXT,
  known                TEXT,
  would_help           TEXT,
  unknowns_json        TEXT NOT NULL DEFAULT '[]',
  success_criterion    TEXT,
  expected_metric      TEXT,
  expected_target      TEXT,
  expected_unit        TEXT,
  expected_by          TEXT,
  expected_text        TEXT,
  confidence           INTEGER CHECK (confidence BETWEEN 0 AND 100),
  not_doing            TEXT,
  review_due           TEXT,
  review_due_initial   TEXT,
  decided_at           TEXT,
  decided_precision    TEXT NOT NULL DEFAULT 'unknown' CHECK (decided_precision IN
                         ('instant','day','month','unknown')),
  decided_basis        TEXT NOT NULL DEFAULT 'unknown' CHECK (decided_basis IN
                         ('live','stated','source_time','conversation_date','record_date','import','unknown')),
  activated_at         TEXT,
  closed_at            TEXT,
  current_edition      INTEGER NOT NULL DEFAULT 0,
  completion_pending   INTEGER NOT NULL DEFAULT 0 CHECK (completion_pending IN (0,1)),
  origin_kind          TEXT NOT NULL DEFAULT 'not_recorded' CHECK (origin_kind IN
                         ('owner_note','cli','bot','meeting','session','chat','agent_session','occasion',
                          'app','proposal','fork','import','not_recorded')),
  origin_ref           TEXT,
  origin_quote         TEXT,
  publishability       TEXT NOT NULL DEFAULT 'private' CHECK (publishability IN
                         ('private','publishable_abstracted','public')),
  third_party_sensitive INTEGER NOT NULL DEFAULT 0 CHECK (third_party_sensitive IN (0,1)),
  reconstructed        INTEGER NOT NULL DEFAULT 0 CHECK (reconstructed IN (0,1)),
  mirror_of            TEXT,
  mirror_scope         TEXT CHECK (mirror_scope IN ('full','basis_only')),
  notes                TEXT,
  legacy_json          TEXT,
  a_seq                INTEGER NOT NULL DEFAULT 0,
  o_seq                INTEGER NOT NULL DEFAULT 0,
  r_seq                INTEGER NOT NULL DEFAULT 0,
  l_seq                INTEGER NOT NULL DEFAULT 0,
  ft_seq               INTEGER NOT NULL DEFAULT 0,
  version              INTEGER NOT NULL DEFAULT 1,
  tx                   INTEGER NOT NULL,
  recorded_at          TEXT NOT NULL,
  origin_recorded_at   TEXT,
  erased_tx            INTEGER,
  CHECK (status <> 'active' OR review_due IS NOT NULL OR mirror_of IS NOT NULL OR reconstructed = 1),
  CHECK (third_party_sensitive = 0 OR publishability = 'private'),
  CHECK (decider = 'self' OR decider_ref IS NOT NULL OR mirror_of IS NOT NULL),
  CHECK (decider <> 'other' OR kind IN ('advisee','forecast_container')),
  CHECK ((mirror_of IS NULL) = (mirror_scope IS NULL))
) STRICT;

-- 4. Forks (open questions). Mutable head, versioned. Created before options, which reference it.
CREATE TABLE dec_forks (
  id                INTEGER PRIMARY KEY,
  public_id         TEXT NOT NULL UNIQUE,
  question          TEXT NOT NULL,
  trigger_text      TEXT,
  trigger_ref       TEXT,
  opened_at         TEXT,
  opened_precision  TEXT NOT NULL CHECK (opened_precision IN ('instant','day','month','unknown')),
  opened_basis      TEXT NOT NULL CHECK (opened_basis IN
                      ('live','stated','source_time','conversation_date','record_date','import','unknown')),
  decider           TEXT NOT NULL DEFAULT 'self' CHECK (decider IN ('self','joint','other')),
  decider_ref       TEXT,
  deadline          TEXT,
  status            TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','decided','dissolved','delegated')),
  outcome_not_heard INTEGER NOT NULL DEFAULT 0 CHECK (outcome_not_heard IN (0,1)),
  decision_id       INTEGER REFERENCES dec_decisions(id),
  closed_at         TEXT,
  close_reason      TEXT,
  delegated_to_ref  TEXT,
  o_seq             INTEGER NOT NULL DEFAULT 0,
  version           INTEGER NOT NULL DEFAULT 1,
  tx                INTEGER NOT NULL,
  recorded_at       TEXT NOT NULL,
  erased_tx         INTEGER
) STRICT;

-- 3. Options of a decision or of a fork. AO; SO(chosen, why_rejected, recorded_before_choice,
--    added_in_edition). [O][E]
CREATE TABLE dec_options (
  id                     INTEGER PRIMARY KEY,
  decision_id            INTEGER REFERENCES dec_decisions(id),
  fork_id                INTEGER REFERENCES dec_forks(id),
  code_n                 INTEGER NOT NULL,
  text                   TEXT NOT NULL,
  chosen                 INTEGER CHECK (chosen IN (0,1)),
  why_rejected           TEXT,
  recorded_before_choice TEXT CHECK (recorded_before_choice IN ('yes','no','unknown')),
  added_in_edition       INTEGER,
  origin                 TEXT NOT NULL DEFAULT 'owner' CHECK (origin IN ('owner','agent','import','app')),
  salt                   TEXT NOT NULL,
  tx                     INTEGER NOT NULL,
  recorded_at            TEXT NOT NULL,
  origin_recorded_at     TEXT,
  origin_ref             TEXT,
  erased_tx              INTEGER,
  CHECK ((decision_id IS NULL) <> (fork_id IS NULL))
) STRICT;
CREATE UNIQUE INDEX dec_options_one_chosen ON dec_options(decision_id) WHERE chosen = 1;
CREATE UNIQUE INDEX dec_options_decision_code ON dec_options(decision_id, code_n) WHERE decision_id IS NOT NULL;
CREATE UNIQUE INDEX dec_options_fork_code ON dec_options(fork_id, code_n) WHERE fork_id IS NOT NULL;

-- 5. Assumptions. Basis columns are immutable after insert (generated trigger); a change is a
--    successor row. Mutable: next_check_at, status, superseded_by, drop_reason, ck_seq, rd_seq,
--    version. SO(added_in_edition, probability_recorded_at). [O][E]
--    There is no stored state column: the effective state is computed (§3.4).
CREATE TABLE dec_assumptions (
  id                      INTEGER PRIMARY KEY,
  decision_id             INTEGER NOT NULL REFERENCES dec_decisions(id),
  code_n                  INTEGER NOT NULL,
  position                INTEGER NOT NULL,
  statement               TEXT NOT NULL,
  metric                  TEXT,
  comparator              TEXT CHECK (comparator IN ('>=','<=','>','<','=','!=','between')),
  threshold_value         TEXT,
  threshold_value2        TEXT,
  unit                    TEXT,
  threshold_text          TEXT,
  by_date                 TEXT,
  judge_from              TEXT,
  drift_margin            TEXT,
  data_source_kind        TEXT NOT NULL CHECK (data_source_kind IN
                            ('manual','internal_query','external_system','none')),
  data_source_text        TEXT,
  data_source_ref         TEXT,
  check_frequency         TEXT CHECK (check_frequency IN ('weekly','monthly','quarterly','ad_hoc')),
  next_check_at           TEXT,
  is_critical             INTEGER NOT NULL DEFAULT 1 CHECK (is_critical IN (0,1)),
  scope                   TEXT,
  check_cost              TEXT CHECK (check_cost IN ('minutes','hours','day_plus','unknown')),
  class_tag               TEXT,
  probability             INTEGER CHECK (probability BETWEEN 0 AND 100),
  probability_by          TEXT CHECK (probability_by IN ('owner','import')),
  probability_recorded_at TEXT,
  shareable               INTEGER NOT NULL DEFAULT 0 CHECK (shareable IN (0,1)),
  status                  TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','superseded','dropped')),
  superseded_by           INTEGER REFERENCES dec_assumptions(id),
  drop_reason             TEXT,
  added_in_edition        INTEGER,
  ck_seq                  INTEGER NOT NULL DEFAULT 0,
  rd_seq                  INTEGER NOT NULL DEFAULT 0,
  salt                    TEXT NOT NULL,
  version                 INTEGER NOT NULL DEFAULT 1,
  tx                      INTEGER NOT NULL,
  recorded_at             TEXT NOT NULL,
  origin_recorded_at      TEXT,
  origin_ref              TEXT,
  erased_tx               INTEGER,
  UNIQUE (decision_id, code_n),
  CHECK (probability IS NULL OR probability_by IS NOT NULL),
  CHECK (comparator IS NULL OR threshold_value IS NOT NULL),
  CHECK (comparator <> 'between' OR threshold_value2 IS NOT NULL)
) STRICT;

-- 7. Readings: measured values that propose a state. AO; SO(accepted_by_check_id, voided_at,
--    voided_reason). [O]
CREATE TABLE dec_readings (
  id                   INTEGER PRIMARY KEY,
  assumption_id        INTEGER NOT NULL REFERENCES dec_assumptions(id),
  decision_id          INTEGER NOT NULL REFERENCES dec_decisions(id),
  code_n               INTEGER NOT NULL,
  value                TEXT,
  unit                 TEXT,
  value_text           TEXT,
  observed_at          TEXT,
  observed_precision   TEXT NOT NULL CHECK (observed_precision IN ('instant','day','month','unknown')),
  observed_basis       TEXT NOT NULL CHECK (observed_basis IN
                         ('live','stated','source_time','conversation_date','record_date','import','unknown')),
  source_kind          TEXT NOT NULL CHECK (source_kind IN
                         ('owner_statement','internal_query','app','document','import')),
  source_ref           TEXT,
  quote                TEXT,
  proposed_state       TEXT CHECK (proposed_state IN ('HOLDING','DRIFTING','VIOLATED')),
  no_proposal_reason   TEXT CHECK (no_proposal_reason IN
                         ('text_threshold','before_judge_from','unit_mismatch','no_value')),
  proposed_by          TEXT NOT NULL CHECK (proposed_by IN ('owner','rule','app','import')),
  accepted_by_check_id INTEGER,
  voided_at            TEXT,
  voided_reason        TEXT,
  tx                   INTEGER NOT NULL,
  recorded_at          TEXT NOT NULL,
  origin_recorded_at   TEXT,
  origin_ref           TEXT,
  UNIQUE (assumption_id, code_n)
) STRICT;

-- 6. The check log: owner assessments and postponements. AO; SO(voided_at, voided_reason). [O][E]
--    A non-owner, non-import proposed_by requires an approval_ref from an owner channel on the
--    unit's tx (a command rule); in the slice only 'owner' and 'import' occur.
CREATE TABLE dec_checks (
  id                  INTEGER PRIMARY KEY,
  assumption_id       INTEGER NOT NULL REFERENCES dec_assumptions(id),
  decision_id         INTEGER NOT NULL REFERENCES dec_decisions(id),
  code_n              INTEGER NOT NULL,
  kind                TEXT NOT NULL CHECK (kind IN ('assessment','postponement')),
  state               TEXT CHECK (state IN ('HOLDING','DRIFTING','VIOLATED','UNVERIFIABLE','UNKNOWN')),
  reading_id          INTEGER REFERENCES dec_readings(id),
  observed_value      TEXT,
  observed_text       TEXT,
  observed_at         TEXT,
  observed_precision  TEXT NOT NULL CHECK (observed_precision IN ('instant','day','month','unknown')),
  observed_basis      TEXT NOT NULL CHECK (observed_basis IN
                        ('live','stated','source_time','conversation_date','record_date','import','unknown')),
  due_answered        TEXT,
  due_source_answered TEXT CHECK (due_source_answered IN ('explicit','by_date','text','review')),
  next_check_set      TEXT,
  next_check_rule     TEXT NOT NULL CHECK (next_check_rule IN
                        ('explicit','frequency','ad_hoc_clear','kept','dropped','none','postpone','import')),
  evidence_kind       TEXT,
  evidence_ref        TEXT,
  evidence_quote      TEXT,
  quote_verified      INTEGER CHECK (quote_verified IN (0,1)),
  note                TEXT,
  proposed_by         TEXT NOT NULL DEFAULT 'owner' CHECK (proposed_by IN ('owner','model','rule','app','import')),
  reconstructed       INTEGER NOT NULL DEFAULT 0 CHECK (reconstructed IN (0,1)),
  voided_at           TEXT,
  voided_reason       TEXT,
  tx                  INTEGER NOT NULL,
  recorded_at         TEXT NOT NULL,
  origin_recorded_at  TEXT,
  origin_ref          TEXT,
  erased_tx           INTEGER,
  UNIQUE (assumption_id, code_n),
  CHECK ((kind = 'assessment') = (state IS NOT NULL)),
  CHECK (kind <> 'postponement' OR next_check_set IS NOT NULL)
) STRICT;

-- 8. Facts: grounds and monitoring, including outcome reports. AO; SO(added_in_edition, voided_at,
--    voided_reason). [O][E]
CREATE TABLE dec_facts (
  id                 INTEGER PRIMARY KEY,
  decision_id        INTEGER NOT NULL REFERENCES dec_decisions(id),
  code_n             INTEGER NOT NULL,
  phase              TEXT NOT NULL CHECK (phase IN ('ground','monitoring')),
  kind               TEXT NOT NULL DEFAULT 'observation' CHECK (kind IN
                       ('observation','action','statement','context_change','outcome_report','external_decision')),
  claimed_outcome    TEXT CHECK (claimed_outcome IN ('success','failure','mixed','done','not_done')),
  text               TEXT NOT NULL,
  occurred_at        TEXT,
  occurred_precision TEXT NOT NULL CHECK (occurred_precision IN ('instant','day','month','unknown')),
  occurred_basis     TEXT NOT NULL CHECK (occurred_basis IN
                       ('live','stated','source_time','conversation_date','record_date','import','unknown')),
  evidence_kind      TEXT NOT NULL CHECK (evidence_kind IN ('segment','message','session','document',
                       'owner_statement','agent_session','app_envelope','foreign','none')),
  evidence_ref       TEXT,
  evidence_quote     TEXT,
  quote_verified     INTEGER CHECK (quote_verified IN (0,1)),
  source_text        TEXT,
  reported_by        TEXT NOT NULL DEFAULT 'owner' CHECK (reported_by IN
                       ('owner','counterpart','app','agent','import')),
  added_in_edition   INTEGER,
  corrects_fact_id   INTEGER REFERENCES dec_facts(id),
  salt               TEXT NOT NULL,
  reconstructed      INTEGER NOT NULL DEFAULT 0 CHECK (reconstructed IN (0,1)),
  voided_at          TEXT,
  voided_reason      TEXT,
  tx                 INTEGER NOT NULL,
  recorded_at        TEXT NOT NULL,
  origin_recorded_at TEXT,
  origin_ref         TEXT,
  erased_tx          INTEGER,
  UNIQUE (decision_id, code_n),
  CHECK ((kind = 'outcome_report') = (claimed_outcome IS NOT NULL))
) STRICT;

-- 9. A fact may bear on several assumptions of the same decision (command rule + test). AO.
CREATE TABLE dec_fact_assumptions (
  fact_id       INTEGER NOT NULL REFERENCES dec_facts(id),
  assumption_id INTEGER NOT NULL REFERENCES dec_assumptions(id),
  bearing       TEXT NOT NULL DEFAULT 'bears_on' CHECK (bearing IN ('bears_on','supports','contradicts')),
  tx            INTEGER NOT NULL,
  recorded_at   TEXT NOT NULL,
  PRIMARY KEY (fact_id, assumption_id)
) STRICT;

-- 10. Reviews. AO; SO(unverifiable_after, edition_after, voided_at, voided_reason). [O][E]
CREATE TABLE dec_reviews (
  id                     INTEGER PRIMARY KEY,
  decision_id            INTEGER NOT NULL REFERENCES dec_decisions(id),
  code_n                 INTEGER NOT NULL,
  action                 TEXT NOT NULL CHECK (action IN ('keep','adjust','revise','close','cancel','supersede')),
  verdict                TEXT,
  notes                  TEXT,
  revise_basis           TEXT CHECK (revise_basis IN ('trigger_fact','change_of_mind','correction')),
  trigger                TEXT NOT NULL DEFAULT 'owner_initiative' CHECK (trigger IN ('scheduled',
                           'violated_assumption','outside_fact','non_occurrence','goal_change','fork',
                           'owner_initiative','import')),
  trigger_ref            TEXT,
  trigger_at             TEXT,
  occurred_at            TEXT,
  occurred_precision     TEXT NOT NULL CHECK (occurred_precision IN ('instant','day','month','unknown')),
  occurred_basis         TEXT NOT NULL CHECK (occurred_basis IN
                           ('live','stated','source_time','conversation_date','record_date','import','unknown')),
  next_review_due        TEXT,
  status_before          TEXT,
  review_due_before      TEXT,
  edition_before         INTEGER,
  edition_after          INTEGER,
  health_before          TEXT,
  ground_before          TEXT,
  timeliness_before      TEXT,
  unverifiable_before    TEXT,
  unverifiable_after     TEXT,
  reasons_answered_json  TEXT,
  execution_summary_json TEXT,
  successor_ref          TEXT,
  is_correction          INTEGER NOT NULL DEFAULT 0 CHECK (is_correction IN (0,1)),
  legacy_health_at_review TEXT,
  reconstructed          INTEGER NOT NULL DEFAULT 0 CHECK (reconstructed IN (0,1)),
  voided_at              TEXT,
  voided_reason          TEXT,
  tx                     INTEGER NOT NULL,
  recorded_at            TEXT NOT NULL,
  origin_recorded_at     TEXT,
  origin_ref             TEXT,
  erased_tx              INTEGER,
  UNIQUE (decision_id, code_n)
) STRICT;

-- 11. Outcome resolutions (reports are facts of kind outcome_report). AO. [O]
CREATE TABLE dec_outcomes (
  id                    INTEGER PRIMARY KEY,
  decision_id           INTEGER NOT NULL REFERENCES dec_decisions(id),
  review_id             INTEGER REFERENCES dec_reviews(id),
  kind                  TEXT NOT NULL CHECK (kind IN ('success','failure','mixed','unknown')),
  basis                 TEXT NOT NULL CHECK (basis IN ('resolved','reported','not_confirmed')),
  evidence_refs_json    TEXT NOT NULL DEFAULT '[]',
  measured_value        TEXT,
  expected_vs_actual    TEXT,
  occurred_at           TEXT,
  occurred_precision    TEXT NOT NULL CHECK (occurred_precision IN ('instant','day','month','unknown')),
  occurred_basis        TEXT NOT NULL CHECK (occurred_basis IN
                          ('live','stated','source_time','conversation_date','record_date','import','unknown')),
  resolved_by           TEXT NOT NULL CHECK (resolved_by IN ('owner','import')),
  supersedes_outcome_id INTEGER REFERENCES dec_outcomes(id),
  reconstructed         INTEGER NOT NULL DEFAULT 0 CHECK (reconstructed IN (0,1)),
  tx                    INTEGER NOT NULL,
  recorded_at           TEXT NOT NULL,
  origin_recorded_at    TEXT,
  origin_ref            TEXT,
  CHECK (kind <> 'unknown' OR basis = 'not_confirmed'),
  CHECK (resolved_by <> 'import' OR reconstructed = 1)
) STRICT;

-- 12. Learnings. AO. [O][E]
CREATE TABLE dec_learnings (
  id                 INTEGER PRIMARY KEY,
  decision_id        INTEGER NOT NULL REFERENCES dec_decisions(id),
  code_n             INTEGER NOT NULL,
  edition            INTEGER NOT NULL,
  review_id          INTEGER REFERENCES dec_reviews(id),
  outcome_id         INTEGER REFERENCES dec_outcomes(id),
  confirmed          TEXT,
  refuted            TEXT,
  limits             TEXT,
  next_step          TEXT,
  same_again         TEXT CHECK (same_again IN ('yes','no','unsure')),
  legacy_text        TEXT,
  salt               TEXT NOT NULL,
  reconstructed      INTEGER NOT NULL DEFAULT 0 CHECK (reconstructed IN (0,1)),
  tx                 INTEGER NOT NULL,
  recorded_at        TEXT NOT NULL,
  origin_recorded_at TEXT,
  origin_ref         TEXT,
  erased_tx          INTEGER,
  UNIQUE (decision_id, code_n),
  CHECK (coalesce(confirmed,'') <> '' OR coalesce(refuted,'') <> '' OR coalesce(legacy_text,'') <> '')
) STRICT;

-- 13. Structured stake. AO; SO(added_in_edition); data class FINANCIAL. [O]
CREATE TABLE dec_stakes (
  id                 INTEGER PRIMARY KEY,
  decision_id        INTEGER NOT NULL REFERENCES dec_decisions(id),
  type               TEXT NOT NULL CHECK (type IN ('money','hours','attention')),
  amount             TEXT,
  currency           TEXT,
  period             TEXT CHECK (period IN ('once','week','month','quarter','year')),
  count_periods      INTEGER,
  direction          TEXT CHECK (direction IN ('cost','income','at_risk')),
  note               TEXT,
  planned            INTEGER NOT NULL DEFAULT 1 CHECK (planned IN (0,1)),
  added_in_edition   INTEGER,
  salt               TEXT NOT NULL,
  tx                 INTEGER NOT NULL,
  recorded_at        TEXT NOT NULL,
  origin_recorded_at TEXT,
  origin_ref         TEXT,
  CHECK (type <> 'money' OR currency IS NOT NULL)
) STRICT;

-- 14. DEC-owned links (§2.10). AO; SO(removed_tx, removed_reason). [O]
CREATE TABLE dec_links (
  id                 INTEGER PRIMARY KEY,
  decision_id        INTEGER NOT NULL REFERENCES dec_decisions(id),
  role               TEXT NOT NULL CHECK (role IN ('follows','supersedes','depends_on','part_of','contradicts',
                       'tests','serves','about','informed_by','foreign_attachment')),
  target_ref         TEXT NOT NULL,
  target_kind        TEXT NOT NULL CHECK (target_kind IN ('decision','learning','goal','direction','person',
                       'company','foreign_task','foreign_goal','foreign_topic','foreign_session')),
  resolution         TEXT NOT NULL CHECK (resolution IN ('resolved','foreign','pending','dangling')),
  note               TEXT,
  removed_tx         INTEGER,
  removed_reason     TEXT,
  tx                 INTEGER NOT NULL,
  recorded_at        TEXT NOT NULL,
  origin_recorded_at TEXT,
  origin_ref         TEXT
) STRICT;
CREATE UNIQUE INDEX dec_links_live ON dec_links(decision_id, role, target_ref) WHERE removed_tx IS NULL;

-- 15. Context of mirrored foreign records (goals, tasks, topics, sessions, people, companies).
--     Mutable, system class. foreign_ref is the source's own ref as written (G901); the issuer
--     column holds V1, so DEC's link target is <issuer>_<foreign_ref> (V1_G901).
CREATE TABLE dec_foreign_context (
  issuer                   TEXT NOT NULL,
  kind                     TEXT NOT NULL,
  foreign_ref              TEXT NOT NULL,
  title                    TEXT,
  status                   TEXT,
  status_changed_at        TEXT,
  status_changed_precision TEXT NOT NULL DEFAULT 'unknown' CHECK (status_changed_precision IN
                             ('instant','day','month','unknown')),
  first_seen_status_run_id INTEGER,
  last_run_id              INTEGER,
  tx                       INTEGER NOT NULL,
  recorded_at              TEXT NOT NULL,
  PRIMARY KEY (issuer, kind, foreign_ref)
) STRICT;

-- 16. Proposals: inferred, not approved. Mutable status; payload immutable.
CREATE TABLE dec_proposals (
  id                    INTEGER PRIMARY KEY,
  type                  TEXT NOT NULL CHECK (type IN ('decision_new','fact')),
  decision_id           INTEGER REFERENCES dec_decisions(id),
  payload_json          TEXT NOT NULL,
  payload_hash          TEXT NOT NULL,
  origin_kind           TEXT NOT NULL,
  origin_ref            TEXT,
  origin_quote          TEXT,
  proposed_by           TEXT NOT NULL,
  match_candidates_json TEXT NOT NULL DEFAULT '[]',
  status                TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN
                          ('proposed','approved','rejected','withdrawn','expired')),
  decided_tx            INTEGER,
  reject_class          TEXT,
  reject_reason         TEXT,
  result_ref            TEXT,
  tx                    INTEGER NOT NULL,
  recorded_at           TEXT NOT NULL,
  erased_tx             INTEGER
) STRICT;
CREATE UNIQUE INDEX dec_proposals_never_again ON dec_proposals(type, coalesce(decision_id,0), payload_hash)
  WHERE status = 'rejected';

-- 17. Field history of mutable heads. AO. [O]
CREATE TABLE dec_versions (
  id                 INTEGER PRIMARY KEY,
  entity             TEXT NOT NULL CHECK (entity IN ('decision','assumption','fork','link','proposal')),
  entity_id          INTEGER NOT NULL,
  field              TEXT NOT NULL,
  old_value          TEXT,
  new_value          TEXT,
  reason             TEXT,
  cause_kind         TEXT NOT NULL CHECK (cause_kind IN ('command','review','check','import','undo','adoption')),
  cause_ref          TEXT,
  reconstructed      INTEGER NOT NULL DEFAULT 0 CHECK (reconstructed IN (0,1)),
  tx                 INTEGER NOT NULL,
  recorded_at        TEXT NOT NULL,
  origin_recorded_at TEXT,
  origin_ref         TEXT
) STRICT;
CREATE INDEX dec_versions_entity ON dec_versions(entity, entity_id);

-- 2. Sealed editions. AO; erasable: fields_json values and field_salts_json entries (per key),
--    recorded in erased_fields_json. [E]
CREATE TABLE dec_editions (
  decision_id          INTEGER NOT NULL REFERENCES dec_decisions(id),
  n                    INTEGER NOT NULL,
  reason               TEXT NOT NULL CHECK (reason IN
                         ('activation','revise','correction','completion','import','source_changed')),
  fields_json          TEXT NOT NULL,
  field_salts_json     TEXT NOT NULL,
  field_hashes_json    TEXT NOT NULL,
  items_json           TEXT NOT NULL,
  seal_hash            TEXT NOT NULL,
  canon_version        INTEGER NOT NULL DEFAULT 1,
  sealed_at            TEXT NOT NULL,
  sealed_by            TEXT NOT NULL,
  review_id            INTEGER REFERENCES dec_reviews(id),
  reason_text          TEXT,
  unverifiable_at_seal TEXT,
  reconstructed        INTEGER NOT NULL DEFAULT 0 CHECK (reconstructed IN (0,1)),
  erased_fields_json   TEXT NOT NULL DEFAULT '[]',
  tx                   INTEGER NOT NULL,
  recorded_at          TEXT NOT NULL,
  erased_tx            INTEGER,
  PRIMARY KEY (decision_id, n)
) STRICT;

-- §2.6 Import, shadow and case bookkeeping (system class).

CREATE TABLE dec_import_runs (
  id                   INTEGER PRIMARY KEY,
  source_issuer        TEXT NOT NULL,
  format               TEXT NOT NULL,
  format_version       INTEGER NOT NULL,
  synthetic            INTEGER NOT NULL CHECK (synthetic IN (0,1)),
  file_hash            TEXT NOT NULL UNIQUE,
  exported_at          TEXT,
  as_of                TEXT,
  as_of_date           TEXT,
  mode                 TEXT NOT NULL CHECK (mode IN ('shadow','final','dry_run')),
  status               TEXT NOT NULL CHECK (status IN ('applied','noop','partial','refused','failed')),
  counts_json          TEXT NOT NULL,
  v2_output_json       TEXT,
  report_status        TEXT NOT NULL DEFAULT 'pending' CHECK (report_status IN ('pending','written','blocked')),
  error                TEXT,
  source_computed_json TEXT,
  tx                   INTEGER NOT NULL,
  recorded_at          TEXT NOT NULL
) STRICT;

CREATE TABLE dec_mirror_state (
  issuer              TEXT NOT NULL,
  source_kind         TEXT NOT NULL,
  source_id           TEXT NOT NULL,
  local_table         TEXT NOT NULL,
  local_id            INTEGER NOT NULL,
  content_hash        TEXT NOT NULL,
  first_run_id        INTEGER NOT NULL,
  last_run_id         INTEGER NOT NULL,
  absent_since_run_id INTEGER,
  adopted_at          TEXT,
  tx                  INTEGER NOT NULL,
  recorded_at         TEXT NOT NULL,
  PRIMARY KEY (issuer, source_kind, source_id)
) STRICT;
CREATE INDEX dec_mirror_state_local ON dec_mirror_state(local_table, local_id);

CREATE TABLE dec_shadow_items (
  id             INTEGER PRIMARY KEY,
  run_id         INTEGER NOT NULL REFERENCES dec_import_runs(id),
  decision_ref   TEXT NOT NULL,
  aspect         TEXT NOT NULL CHECK (aspect IN
                   ('health','waiting_membership','waiting_reasons','due','order','count','basis_drift')),
  subject_ref    TEXT,
  v1_value       TEXT,
  v2_value       TEXT,
  classification TEXT NOT NULL CHECK (classification IN ('same','expected','unexpected','finding')),
  rule_id        TEXT,
  tx             INTEGER NOT NULL,
  recorded_at    TEXT NOT NULL,
  CHECK ((classification = 'expected') = (rule_id IS NOT NULL))
) STRICT;
CREATE INDEX dec_shadow_items_run ON dec_shadow_items(run_id);

CREATE TABLE dec_cases (
  case_id       TEXT PRIMARY KEY,
  title         TEXT NOT NULL,
  script_hash   TEXT NOT NULL,
  last_result   TEXT CHECK (last_result IN ('pass','fail')),
  last_run_at   TEXT,
  source_run_id INTEGER,
  report_json   TEXT,
  tx            INTEGER NOT NULL,
  recorded_at   TEXT NOT NULL
) STRICT;

-- The table registry rows (spec §2.3): owner, data class and the append-only, set-once, erasable
-- and mutable declarations the trigger generator and the authorizer read.
INSERT INTO sys_table_registry
  (table_name, module, data_class, append_only, set_once_cols, erasable_cols, mutable_cols)
VALUES
  ('dec_decisions', 'dec', 'work', 0, '[]',
   '["question","statement","context","known","would_help","unknowns_json","success_criterion","expected_text","not_doing","manual_flag_reason","origin_quote","notes","legacy_json"]',
   '["title","question","statement","kind","decider","decider_basis","decider_ref","depth","depth_basis","reversibility","status","manual_flag","manual_flag_reason","context","known","would_help","unknowns_json","success_criterion","expected_metric","expected_target","expected_unit","expected_by","expected_text","confidence","not_doing","review_due","review_due_initial","decided_at","decided_precision","decided_basis","activated_at","closed_at","current_edition","completion_pending","origin_kind","origin_ref","origin_quote","publishability","third_party_sensitive","mirror_of","mirror_scope","notes","legacy_json","a_seq","o_seq","r_seq","l_seq","ft_seq","version"]'),
  ('dec_forks', 'dec', 'work', 0, '[]', '["question","trigger_text","close_reason"]',
   '["question","trigger_text","trigger_ref","opened_at","opened_precision","opened_basis","decider","decider_ref","deadline","status","outcome_not_heard","decision_id","closed_at","close_reason","delegated_to_ref","o_seq","version"]'),
  ('dec_options', 'dec', 'work', 1,
   '["chosen","why_rejected","recorded_before_choice","added_in_edition"]',
   '["text"]', '[]'),
  ('dec_assumptions', 'dec', 'work', 0,
   '["added_in_edition","probability_recorded_at"]',
   '["statement"]',
   '["next_check_at","status","superseded_by","drop_reason","ck_seq","rd_seq","version"]'),
  ('dec_readings', 'dec', 'work', 1,
   '["accepted_by_check_id","voided_at","voided_reason"]', '[]', '[]'),
  ('dec_checks', 'dec', 'work', 1,
   '["voided_at","voided_reason"]', '["evidence_quote","note"]', '[]'),
  ('dec_facts', 'dec', 'work', 1,
   '["added_in_edition","voided_at","voided_reason"]', '["text","evidence_quote"]', '[]'),
  ('dec_fact_assumptions', 'dec', 'work', 1, '[]', '[]', '[]'),
  ('dec_reviews', 'dec', 'work', 1,
   '["unverifiable_after","edition_after","voided_at","voided_reason"]', '["verdict","notes"]', '[]'),
  ('dec_outcomes', 'dec', 'work', 1, '[]', '[]', '[]'),
  ('dec_learnings', 'dec', 'work', 1, '[]',
   '["confirmed","refuted","limits","next_step","legacy_text"]', '[]'),
  ('dec_stakes', 'dec', 'financial', 1, '["added_in_edition"]', '[]', '[]'),
  ('dec_links', 'dec', 'work', 1, '["removed_tx","removed_reason"]', '[]', '[]'),
  ('dec_foreign_context', 'dec', 'system', 0, '[]', '[]',
   '["title","status","status_changed_at","status_changed_precision","first_seen_status_run_id","last_run_id"]'),
  ('dec_proposals', 'dec', 'work', 0, '[]', '["origin_quote"]',
   '["status","decided_tx","reject_class","reject_reason","result_ref"]'),
  ('dec_versions', 'dec', 'work', 1, '[]', '[]', '[]'),
  ('dec_editions', 'dec', 'work', 1, '[]',
   '["fields_json","field_salts_json","erased_fields_json"]', '[]'),
  ('dec_import_runs', 'dec', 'system', 0, '[]', '[]',
   '["status","counts_json","v2_output_json","report_status","error","source_computed_json"]'),
  ('dec_mirror_state', 'dec', 'system', 0, '[]', '[]',
   '["local_table","local_id","content_hash","last_run_id","absent_since_run_id","adopted_at"]'),
  ('dec_shadow_items', 'dec', 'system', 1, '[]', '[]', '[]'),
  ('dec_cases', 'dec', 'system', 0, '[]', '[]',
   '["title","script_hash","last_result","last_run_at","source_run_id","report_json"]');
