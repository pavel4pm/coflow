"""Versioned data contracts: JSON Schemas that other systems write against (ARCHITECTURE §5.1).

Skeleton package (spec §12.1, §6.2). The lowest layer of the top-level import contract: it imports
nothing from CoFlow. The schemas ship inside the package, so the importer loads them with
``load_schema`` and an external exporter can read the same file from the repository.

- ``import_decisions_v1.schema.json``: format ``coflow.import.decisions`` version 1, written by a
  predecessor system's exporter (track E, private), read by the snapshot importer (track S).

See ``README.md`` next to this file.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

__all__ = ["SCHEMAS", "load_example", "load_schema"]

SCHEMAS: dict[str, str] = {
    "coflow.import.decisions/1": "import_decisions_v1.schema.json",
}


def load_schema(name: str) -> dict[str, Any]:
    """The JSON Schema of ``name`` (``'coflow.import.decisions/1'``) as a dict."""
    filename = SCHEMAS[name]
    text = resources.files(__package__).joinpath(filename).read_text(encoding="utf-8")
    return json.loads(text)


def load_example(filename: str) -> bytes:
    """The bytes of a synthetic example in ``examples/`` (for exporters and tests)."""
    return resources.files(__package__).joinpath("examples", filename).read_bytes()
