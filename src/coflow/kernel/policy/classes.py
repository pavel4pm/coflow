"""Data classes (PRV-1, spec §2.11, ARCHITECTURE §7).

Owned by track K; increment I1, spec §12.2. ``DataClass`` and ``CLASS_ORDER`` are fixed by the
skeleton because every module's migration declares its tables' classes; the track adds the
enforcement: ``declare_inputs`` marks a unit's inputs, and the unit of work refuses a journal-class
input (``JOURNAL_CLASS_INPUT``) and any row stored in a table less restrictive than its inputs.

Spec note: kernel-service rows written for such a unit (its ``sys_tx_log`` row, its events, its
numbers) carry ids only, so they are exempt from the class check.

The order is journal > financial > work > system: a derived output takes the most restrictive class
of its inputs. No DEC or CMT table accepts journal-class input.
"""

from __future__ import annotations

from typing import Literal

from coflow.kernel.errors import ContractViolation
from coflow.kernel.store.api import current_unit
from coflow.kernel.store.unit import Unit

__all__ = [
    "CLASS_ORDER",
    "PROTECTED_CLASSES",
    "DataClass",
    "class_rank",
    "declare_inputs",
    "may_store",
    "most_restrictive",
]

DataClass = Literal["journal", "financial", "work", "system"]

CLASS_ORDER: tuple[DataClass, ...] = ("journal", "financial", "work", "system")


def class_rank(data_class: str) -> int:
    """0 for journal (the most restrictive) to 3 for system; unknown classes are refused."""
    if data_class not in CLASS_ORDER:
        raise ContractViolation(f"unknown data class {data_class!r}")
    return CLASS_ORDER.index(data_class)


def most_restrictive(*classes: DataClass) -> DataClass:
    """The most restrictive of ``classes`` (journal first)."""
    if not classes:
        raise ContractViolation("most_restrictive needs at least one class")
    return min(classes, key=class_rank)


PROTECTED_CLASSES: tuple[DataClass, ...] = ("journal", "financial")
"""The classes that taint what is derived from them (the unit of work applies the same rule)."""


def may_store(table_class: str, input_class: str) -> bool:
    """Whether output derived from ``input_class`` may be stored in a ``table_class`` table.

    Journal and financial input never goes into a less restrictive table (ARCHITECTURE §7, "Table
    registry and authorizer"); work input may feed system bookkeeping (counts, hashes, reports).
    """
    class_rank(table_class)
    if class_rank(input_class) > class_rank("financial"):
        return True
    return class_rank(input_class) >= class_rank(table_class)


def declare_inputs(*classes: DataClass) -> None:
    """Declare the data classes of the current unit's inputs.

    STO then refuses to store them in a less restrictive table; a journal-class input in a module
    without journal tables is ``Refused(JOURNAL_CLASS_INPUT)`` at once (P-2, spec §2.11). DEC and
    CMT call this in the apply phase with the classes ``EvidenceResolver`` reported.
    """
    unit = current_unit()
    if not isinstance(unit, Unit):
        raise ContractViolation("inputs are declared inside a kernel unit of work")
    for data_class in classes:
        class_rank(data_class)
        unit.declare_input_class(data_class)
