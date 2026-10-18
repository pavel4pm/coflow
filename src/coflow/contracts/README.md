# Contracts

Versioned data formats that other systems write and CoFlow reads. Each format has a JSON Schema in
this folder and a synthetic example in [`examples/`](examples/). The package `coflow.contracts`
imports nothing from CoFlow, so an exporter in another repository can use the schema without the
rest of the code.

| Schema | Format | Version | Written by | Read by |
|---|---|---|---|---|
| [`import_decisions_v1.schema.json`](import_decisions_v1.schema.json) | `coflow.import.decisions` | 1 | an exporter of the predecessor system (it lives with that system, not here) | the snapshot importer, `coflow dec import v1 FILE` |

## `coflow.import.decisions`, version 1

A one-way snapshot of a predecessor system's decisions, taken daily during the shadow period. The
importer turns each decision into a read-only mirror that keeps its number (`D907` becomes
`D-0907`), seals it as an imported edition, and computes health, due dates and the waiting list
itself. The `v1_computed` block carries what the source system computed at export time, so the
shadow report compares v2 against what the source really said, and v2 never runs the source's code.
The decision-core design describes the format in §6.2, the field mapping in §6.3, the re-import in
§6.5 and the comparison in §6.6.

### Rules

- **JSON, UTF-8, one file per run.** Every object is closed: an unknown field is an error, so a
  change in the source shows up as a refused import, not as silently dropped data. Every key is
  present; an empty value is `null`.
- **Integers only.** No number has a fraction or an exponent. The canonical form (CFJ-1) refuses
  floats, so a file with `70.0` passes a generic JSON Schema check and is still refused by the
  importer.
- **Times.** Instants (`exported_at`, `as_of`, every `created_at`, `changed_at`) are UTC with `Z`.
  Dates (`decided_at`, `review_due`, `next_check_at`, `last_checked_at`, `occurred_at`,
  `reviewed_at`, `next_review_due`, `status_changed_at`) are as the source stored them, in the zone
  named by `source.timezone`. Text is verbatim; the date parser unescapes HTML as the source did.
- **Per-row recording times.** `created_at` on decisions, assumptions, facts, reviews and links, and
  `changed_at` on versions, are when the source first recorded the row. They become the rows'
  knowledge time, so "as known on day 5" means what the source knew on day 5.
- **The `synthetic` flag is mandatory.** A `dev` instance accepts only `"synthetic": true`. Real
  snapshots go only to a `validation` instance whose data root lies outside any repository working
  tree.
- **`id_space.decision.highest_issued`** must stay below the native block start (`1001`), so the
  source's numbers and CoFlow's own never collide. `deleted_without_trace` lists numbers the source
  issued and deleted; they are never issued again.
- **`kind` and `decider_mapping`** come from an explicit mapping file kept with the exporter. They are
  never inferred from names. `null` for `decider_mapping` means "self, assumed".
- **What never goes in:** the journal, diary tables, private session kinds and chat summaries. The
  exporter reads the source read-only and changes nothing in it.

### Order of checks in the importer

1. The file's sha256: the same file twice is a no-op.
2. This schema: an unknown field, a missing key or a wrong type refuses the file
   (`IMPORT_FORMAT_UNSUPPORTED`), and so does any float.
3. `content_hash` (`IMPORT_HASH_MISMATCH`).
4. The instance role and the `synthetic` flag (`IMPORT_NOT_SYNTHETIC`, `IMPORT_ROLE`).
5. The id space (`IMPORT_SOURCE_CONFLICT`) and adopted records (`IMPORT_ADOPTED`).

### `content_hash`

`"sha256:" + sha256(CFJ-1(document without the content_hash key))`, where CFJ-1 is
`json.dumps(normalise(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":"),
allow_nan=False).encode("utf-8")` and `normalise` turns every string into Unicode NFC and refuses
floats. In Python:

```python
import hashlib, json, unicodedata


def normalise(x):
    if isinstance(x, str):
        return unicodedata.normalize("NFC", x)
    if isinstance(x, float):
        raise TypeError("CFJ-1 refuses floats")
    if isinstance(x, list):
        return [normalise(v) for v in x]
    if isinstance(x, dict):
        return {str(k): normalise(v) for k, v in x.items()}
    return x  # bool, None, int


def content_hash(document: dict) -> str:
    body = {k: v for k, v in document.items() if k != "content_hash"}
    canonical = json.dumps(
        normalise(body), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()
```

### Fields the target has and the source does not

`question`, `success_criterion` and structured thresholds have no source field. They stay empty, and
the card lists them as missing; filling them after adoption is a completion, not a revision.

### Changing the format

A new field, a removed field or a changed meaning is a new format version with its own schema file,
`import_decisions_v2.schema.json`; version 1 stays readable. The exporter and the importer move
together, and the synthetic fixtures gain a file of the new version.
