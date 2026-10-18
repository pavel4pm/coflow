"""The owner profile minimum (CFG-1, spec §2.3 ``cfg_profile``): ``decider = self`` resolves here.

Owned by track K; increment I1, spec §12.2. ``OwnerProfile`` and ``load_profile`` are fixed by the
skeleton because tracks D and X need the owner's zone for every "today"; the track implements them.
The owner is never found by a name lookup; the display name is shown, never matched.

``init`` writes the one profile row; ``validate_profile`` is the check it runs first (an IANA zone,
a locale of the R1 packs, an ISO 4217 code, a non-empty display name).

Spec note: the slice stores only the minimum of CFG-1 (display name, zone, locale, currency);
aliases, languages, contacts and ritual times arrive with the modules that use them.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from coflow.kernel.errors import ContractViolation, NotFound

__all__ = ["LOCALES", "OwnerProfile", "load_profile", "profile_row", "validate_profile"]

LOCALES: tuple[str, ...] = ("en", "ru")
"""The R1 locale packs (CFG-3)."""

_CURRENCY = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True, slots=True, kw_only=True)
class OwnerProfile:
    display_name: str  # "Owner" in every fixture
    timezone: str  # IANA zone, e.g. "Europe/Berlin"
    locale: str
    currency: str  # ISO 4217


def validate_profile(profile: OwnerProfile) -> list[str]:
    """What is wrong with a profile before it is stored (empty when it is valid)."""
    problems: list[str] = []
    if not profile.display_name.strip():
        problems.append("the display name is empty")
    try:
        ZoneInfo(profile.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        problems.append(f"{profile.timezone!r} is not an IANA time zone")
    if profile.locale not in LOCALES:
        problems.append(f"locale {profile.locale!r} is not one of {', '.join(LOCALES)}")
    if not _CURRENCY.match(profile.currency):
        problems.append(f"currency {profile.currency!r} is not an ISO 4217 code")
    return problems


def profile_row(profile: OwnerProfile) -> dict[str, str | int]:
    """The ``cfg_profile`` row for ``profile`` (``id`` is always 1)."""
    problems = validate_profile(profile)
    if problems:
        raise ContractViolation("; ".join(problems))
    return {
        "id": 1,
        "display_name": profile.display_name,
        "timezone": profile.timezone,
        "locale": profile.locale,
        "currency": profile.currency,
    }


def load_profile(conn: sqlite3.Connection) -> OwnerProfile:
    row = conn.execute(
        "SELECT display_name, timezone, locale, currency FROM cfg_profile WHERE id = 1"
    ).fetchone()
    if row is None:
        raise NotFound("cfg_profile", "this instance has no owner profile (coflow init)")
    return OwnerProfile(
        display_name=str(row[0]), timezone=str(row[1]), locale=str(row[2]), currency=str(row[3])
    )
