"""Per-instance settings (``cfg_settings``, spec §2.1 configuration keys).

Owned by track K; increment I1, spec §12.2. ``load_settings`` and ``set_setting`` are fixed by the
skeleton because DEC builds its ``DecConfig`` from them; the track implements them. Defaults live
with their consumer (``modules/dec/domain/model.py`` ``DecConfig``), so a key absent here means the
default applies.

``cfg_settings`` is an append-only history: ``set_setting`` adds a row, and the latest row of a key
is its value, so every change keeps the unit (``tx``) that made it. ``init`` writes the keys it
knows: ``owner.timezone``, ``owner.locale``, ``owner.currency``, ``ids.issuer`` and
``ids.foreign_issuers`` (``V1,CF2LOG``; lists are comma-separated, as ``DecConfig`` reads them).

Spec note: ``ids.issuer`` never changes after ``init`` (§2.2), so ``set_setting`` refuses it.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Mapping

from coflow.kernel.errors import ContractViolation
from coflow.kernel.store.api import current_unit

__all__ = [
    "DEFAULT_FOREIGN_ISSUERS",
    "FIXED_KEYS",
    "initial_settings",
    "load_settings",
    "set_setting",
]

DEFAULT_FOREIGN_ISSUERS = "V1,CF2LOG"
FIXED_KEYS: frozenset[str] = frozenset({"ids.issuer"})
_KEY = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")


def initial_settings(
    *, timezone: str, locale: str, currency: str, issuer: str
) -> Mapping[str, str]:
    """The settings ``init`` writes (the rest keep their consumers' defaults)."""
    return {
        "owner.timezone": timezone,
        "owner.locale": locale,
        "owner.currency": currency,
        "ids.issuer": issuer,
        "ids.foreign_issuers": DEFAULT_FOREIGN_ISSUERS,
    }


def load_settings(conn: sqlite3.Connection) -> dict[str, str]:
    """Every stored key (``dec.drift_margin``, ``ids.issuer``, ...) with its text value."""
    rows = conn.execute(
        "SELECT key, value FROM cfg_settings WHERE id IN"
        " (SELECT MAX(id) FROM cfg_settings GROUP BY key) ORDER BY key"
    ).fetchall()
    return {str(k): str(v) for k, v in rows}


def set_setting(key: str, value: str) -> None:
    """Set ``key`` inside the current unit of work (owner module ``cfg``)."""
    if not _KEY.match(key):
        raise ContractViolation(f"{key!r} is not a setting key (dotted lower-case names)")
    if not isinstance(value, str):
        raise ContractViolation(f"{key}: settings are text, not {type(value).__name__}")
    unit = current_unit()
    if unit.owner_module != "cfg":
        raise ContractViolation(f"settings are written in a cfg unit, not {unit.owner_module!r}")
    latest = unit.fetch_one(
        "SELECT value FROM cfg_settings WHERE key = ? ORDER BY id DESC LIMIT 1", (key,)
    )
    if latest is not None:
        if str(latest["value"]) == value:
            return
        if key in FIXED_KEYS:
            raise ContractViolation(f"{key} is fixed at init and never changes")
    unit.insert("cfg_settings", {"key": key, "value": value})
