"""Snapshot import (spec §6.2-§6.5): ``snapshot.py`` validates and plans, ``apply.py`` writes one
unit of work per snapshot (chunked only above ``dec.import_unit_max_rows``),
``rebuild_checks.py`` rebuilds the check log from version rows and snapshot diffs.

Owned by track S (store, import, shadow); increment I1, spec §12.2. ``adopt.py`` (I3, track S) and
``project_log.py`` (I2, track K) are still stubs.
"""
