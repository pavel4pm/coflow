-- Kernel tables of spec §2.3 (sys_meta, sys_migrations, sys_table_registry, sys_tx_log,
-- sys_id_*, sys_events, sys_event_deliveries, sys_command_keys, sys_instance, cfg_*,
-- sys_usage_signals, mcp_clients, mcp_call_log, adm_tokens).
-- Owned by track K; increment I1, spec §12.2.
-- The file contract (naming, order, registry rows, generated triggers) is in
-- coflow/kernel/store/api.py. Instants are UTC text with milliseconds and Z; booleans 0/1.
-- Spec notes: sys_tx_log also records owner_module and source_ref; cfg_settings is an append-only
-- history (the latest row per key wins), so every setting change keeps its tx; sys_instance and
-- cfg_profile hold exactly one row.

-- STO --------------------------------------------------------------------------------------------

CREATE TABLE sys_meta (
  key   TEXT PRIMARY KEY,                 -- schema_revision, code_version
  value TEXT NOT NULL
) STRICT;

CREATE TABLE sys_migrations (
  file       TEXT PRIMARY KEY,            -- kernel/0001_kernel.sql, dec/0001_dec.sql
  module     TEXT NOT NULL,
  checksum   TEXT NOT NULL,               -- sha256 of the file with LF line endings
  applied_at TEXT NOT NULL
) STRICT;

CREATE TABLE sys_table_registry (
  table_name    TEXT PRIMARY KEY,
  module        TEXT NOT NULL,
  data_class    TEXT NOT NULL CHECK (data_class IN ('journal','financial','work','system')),
  append_only   INTEGER NOT NULL CHECK (append_only IN (0,1)),
  set_once_cols TEXT NOT NULL DEFAULT '[]',   -- JSON array of column names
  erasable_cols TEXT NOT NULL DEFAULT '[]',
  mutable_cols  TEXT NOT NULL DEFAULT '[]'
) STRICT;

CREATE TABLE sys_tx_log (
  tx             INTEGER PRIMARY KEY,
  committed_at   TEXT NOT NULL,
  actor          TEXT NOT NULL,
  channel        TEXT NOT NULL CHECK (channel IN ('cli','mcp','bot','app','import','system')),
  owner_channel  INTEGER NOT NULL CHECK (owner_channel IN (0,1)),
  interaction_id TEXT NOT NULL,
  source_ref     TEXT,
  approval_ref   TEXT,
  instance_role  TEXT NOT NULL,
  code_version   TEXT NOT NULL,
  owner_module   TEXT NOT NULL,
  command        TEXT,
  CHECK (owner_channel = 0 OR channel IN ('cli','bot'))
) STRICT;

-- IDS --------------------------------------------------------------------------------------------

CREATE TABLE sys_id_prefixes (
  prefix       TEXT PRIMARY KEY,
  entity       TEXT NOT NULL,
  width        INTEGER NOT NULL CHECK (width BETWEEN 1 AND 9),
  owner_module TEXT NOT NULL,
  block_start  INTEGER CHECK (block_start IS NULL OR block_start >= 1),
  scoped_under TEXT,                      -- JSON array of parent prefixes; NULL when top-level
  description  TEXT NOT NULL DEFAULT '',
  tx           INTEGER NOT NULL
) STRICT;

CREATE TABLE sys_id_sequence (
  prefix TEXT PRIMARY KEY REFERENCES sys_id_prefixes(prefix),
  next_n INTEGER NOT NULL CHECK (next_n >= 1),
  tx     INTEGER NOT NULL
) STRICT;

CREATE TABLE sys_id_burned (
  prefix TEXT NOT NULL REFERENCES sys_id_prefixes(prefix),
  n      INTEGER NOT NULL CHECK (n >= 1),
  reason TEXT NOT NULL CHECK (reason IN ('rollback','undo','deleted_in_source','numbering_gap')),
  issuer TEXT,
  tx     INTEGER NOT NULL,
  PRIMARY KEY (prefix, n)
) STRICT;

CREATE TABLE sys_id_foreign (
  prefix    TEXT NOT NULL REFERENCES sys_id_prefixes(prefix),
  n         INTEGER NOT NULL CHECK (n >= 1),
  issuer    TEXT NOT NULL,
  source_id TEXT NOT NULL,
  tx        INTEGER NOT NULL,
  PRIMARY KEY (prefix, n)
) STRICT;

CREATE TABLE sys_id_aliases (
  alias_norm TEXT PRIMARY KEY,
  canonical  TEXT NOT NULL,
  issuer     TEXT NOT NULL,
  kind       TEXT NOT NULL CHECK (kind IN ('legacy','rename','merge','foreign')),
  tx         INTEGER NOT NULL
) STRICT;
CREATE INDEX sys_id_aliases_canonical ON sys_id_aliases (canonical);

-- EVT --------------------------------------------------------------------------------------------

CREATE TABLE sys_events (
  id            TEXT PRIMARY KEY,         -- UUIDv7
  type          TEXT NOT NULL,            -- coflow.<mod>.<entity>.<verb_past>
  source        TEXT NOT NULL,            -- coflow://<instance_id>/<mod>
  subject       TEXT NOT NULL,            -- a plain public id or <ISSUER>_<id>
  time          TEXT NOT NULL,
  dataversion   INTEGER NOT NULL,
  correlationid TEXT NOT NULL,            -- the interaction id
  causationid   TEXT,
  actor         TEXT NOT NULL,
  dataclass     TEXT NOT NULL CHECK (dataclass IN ('journal','financial','work','system')),
  sourceref     TEXT,
  data          TEXT NOT NULL,            -- CFJ-1: {"changed": [field names], "entity": type}
  tx            INTEGER NOT NULL
) STRICT;
CREATE INDEX sys_events_tx ON sys_events (tx);

CREATE TABLE sys_event_deliveries (
  event_id     TEXT NOT NULL REFERENCES sys_events(id),
  handler      TEXT NOT NULL,
  status       TEXT NOT NULL CHECK (status IN ('delivered','failed','dead')),
  attempts     INTEGER NOT NULL CHECK (attempts >= 1),
  last_error   TEXT,                      -- an error type name, never a value
  delivered_at TEXT,
  tx           INTEGER NOT NULL,
  PRIMARY KEY (event_id, handler)
) STRICT;

CREATE TABLE sys_command_keys (
  key         TEXT PRIMARY KEY,
  command     TEXT NOT NULL,
  result_json TEXT NOT NULL,
  tx          INTEGER NOT NULL
) STRICT;

-- OPS --------------------------------------------------------------------------------------------

CREATE TABLE sys_instance (
  instance_id TEXT PRIMARY KEY,
  role        TEXT NOT NULL CHECK (role IN ('dev','validation','drill','staging','production')),
  volume_id   TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  singleton   INTEGER NOT NULL DEFAULT 1 UNIQUE CHECK (singleton = 1),
  tx          INTEGER NOT NULL
) STRICT;

-- CFG --------------------------------------------------------------------------------------------

CREATE TABLE cfg_profile (
  id           INTEGER PRIMARY KEY CHECK (id = 1),
  display_name TEXT NOT NULL,             -- shown, never matched (decider = self resolves here)
  timezone     TEXT NOT NULL,             -- IANA zone
  locale       TEXT NOT NULL,
  currency     TEXT NOT NULL,             -- ISO 4217
  tx           INTEGER NOT NULL
) STRICT;

CREATE TABLE cfg_settings (
  id    INTEGER PRIMARY KEY,
  key   TEXT NOT NULL,
  value TEXT NOT NULL,
  tx    INTEGER NOT NULL
) STRICT;
CREATE INDEX cfg_settings_key ON cfg_settings (key, id);

-- OBS --------------------------------------------------------------------------------------------

CREATE TABLE sys_usage_signals (
  signal      TEXT NOT NULL,
  day         TEXT NOT NULL,              -- YYYY-MM-DD in the owner's zone
  channel     TEXT NOT NULL,
  value       TEXT NOT NULL,              -- a decimal as text
  detail_json TEXT NOT NULL DEFAULT '{}',
  tx          INTEGER NOT NULL,           -- the unit that created the row
  PRIMARY KEY (signal, day, channel)
) STRICT;

-- MCP and ADM (written by the interfaces through their own units) --------------------------------

CREATE TABLE mcp_clients (
  client     TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE,
  scopes     TEXT NOT NULL,
  financial  INTEGER NOT NULL DEFAULT 0 CHECK (financial IN (0,1)),
  revoked_at TEXT,
  tx         INTEGER NOT NULL
) STRICT;

CREATE TABLE mcp_call_log (
  id             INTEGER PRIMARY KEY,
  at             TEXT NOT NULL,
  client         TEXT NOT NULL,
  tool           TEXT NOT NULL,
  args_hash      TEXT NOT NULL,
  result_kind    TEXT NOT NULL,
  interaction_id TEXT,
  tx             INTEGER NOT NULL
) STRICT;

CREATE TABLE adm_tokens (
  token_hash TEXT PRIMARY KEY,
  scope      TEXT NOT NULL CHECK (scope IN ('admin','import')),
  created_at TEXT NOT NULL,
  revoked_at TEXT,
  tx         INTEGER NOT NULL
) STRICT;

-- The registry rows of the kernel's own tables ---------------------------------------------------

INSERT INTO sys_table_registry
  (table_name, module, data_class, append_only, set_once_cols, erasable_cols, mutable_cols)
VALUES
  ('sys_meta',             'sto', 'system', 0, '[]', '[]', '["value"]'),
  ('sys_migrations',       'sto', 'system', 1, '[]', '[]', '[]'),
  ('sys_table_registry',   'sto', 'system', 0, '[]', '[]',
     '["data_class","append_only","set_once_cols","erasable_cols","mutable_cols"]'),
  ('sys_tx_log',           'sto', 'system', 1, '[]', '[]', '[]'),
  ('sys_id_prefixes',      'ids', 'system', 0, '[]', '[]', '["block_start","description"]'),
  ('sys_id_sequence',      'ids', 'system', 0, '[]', '[]', '["next_n"]'),
  ('sys_id_burned',        'ids', 'system', 1, '[]', '[]', '[]'),
  ('sys_id_foreign',       'ids', 'system', 1, '[]', '[]', '[]'),
  ('sys_id_aliases',       'ids', 'system', 1, '[]', '[]', '[]'),
  ('sys_events',           'evt', 'system', 1, '[]', '[]', '[]'),
  ('sys_event_deliveries', 'evt', 'system', 0, '[]', '[]',
     '["status","attempts","last_error","delivered_at"]'),
  ('sys_command_keys',     'evt', 'system', 1, '[]', '[]', '[]'),
  ('sys_instance',         'ops', 'system', 0, '[]', '[]', '["role"]'),
  ('cfg_profile',          'cfg', 'work',   0, '[]', '[]',
     '["display_name","timezone","locale","currency"]'),
  ('cfg_settings',         'cfg', 'system', 1, '[]', '[]', '[]'),
  ('sys_usage_signals',    'obs', 'system', 0, '[]', '[]', '["value","detail_json"]'),
  ('mcp_clients',          'mcp', 'system', 0, '[]', '[]',
     '["token_hash","scopes","financial","revoked_at"]'),
  ('mcp_call_log',         'mcp', 'system', 1, '[]', '[]', '[]'),
  ('adm_tokens',           'adm', 'system', 1, '["revoked_at"]', '[]', '[]');
