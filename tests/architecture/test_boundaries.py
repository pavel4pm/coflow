"""The ``api-only`` contract and other import fitness functions (ARCHITECTURE §5.2, §5.3).

- From outside a domain module only its ``api`` and ``events`` submodules may be imported (the
  package itself too, which holds only a docstring).
- Tests of module A import only A's internals and other modules' ``api`` / ``events``.
- The health oracle stays independent: it never imports DEC's domain functions (spec §12.5).
- Only ``kernel.store`` opens database connections.
- No private name of a module's ``api`` (``_queries``, ``dec_api._repo``) is used from outside
  that module, and only kernel code calls a unit's raw writers (``kernel_insert``, ...).
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path

import grimp

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src" / "coflow"
TESTS = REPO / "tests"
PUBLIC_SUBMODULES = {"api", "events"}


def _domain_modules(graph: grimp.ImportGraph) -> list[str]:
    return sorted(graph.find_children("coflow.modules"))


def _is_inside(module: str, package: str) -> bool:
    return module == package or module.startswith(package + ".")


def _allowed_from_outside(imported: str, package: str) -> bool:
    if imported == package:
        return True
    head = imported[len(package) + 1 :].split(".")[0]
    return head in PUBLIC_SUBMODULES


def test_api_only_between_source_modules() -> None:
    graph = grimp.build_graph("coflow")
    violations = []
    for package in _domain_modules(graph):
        for imported in sorted(graph.find_descendants(package) | {package}):
            if _allowed_from_outside(imported, package):
                continue
            for importer in sorted(graph.find_modules_that_directly_import(imported)):
                if not _is_inside(importer, package):
                    violations.append(f"{importer} imports {imported}")
    assert not violations, "only api and events may be imported from outside:\n" + "\n".join(
        violations
    )


def _imports(path: Path) -> Iterator[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.lineno, node.module
            for alias in node.names:
                yield node.lineno, f"{node.module}.{alias.name}"


def _test_scope(path: Path) -> str | None:
    """The domain module whose internals a test file may import, or None for api-only."""
    rel = path.relative_to(TESTS).parts
    if rel[0] == "modules" and len(rel) > 2:
        return rel[1]
    if rel[0] == "oracle":
        return "dec"
    return None


def _module_internal(name: str) -> tuple[str, str] | None:
    """('dec', 'domain') for 'coflow.modules.dec.domain.model'; None for api/events/non-modules."""
    parts = name.split(".")
    if len(parts) < 4 or parts[:2] != ["coflow", "modules"]:
        return None
    if parts[3] in PUBLIC_SUBMODULES:
        return None
    if (
        not (SRC / "modules" / parts[2] / parts[3]).exists()
        and not (SRC / "modules" / parts[2] / f"{parts[3]}.py").exists()
    ):
        return None  # an attribute imported from the package itself
    return parts[2], parts[3]


def test_tests_import_only_their_module_internals() -> None:
    violations = []
    for path in sorted(TESTS.rglob("*.py")):
        scope = _test_scope(path)
        for lineno, name in _imports(path):
            internal = _module_internal(name)
            if internal and internal[0] != scope:
                rel = path.relative_to(REPO)
                violations.append(f"{rel}:{lineno}: imports {name}")
    assert not violations, "\n".join(violations)


def test_health_oracle_is_independent() -> None:
    violations = []
    for path in sorted((TESTS / "oracle").rglob("*.py")):
        for lineno, name in _imports(path):
            if name.startswith("coflow.modules.dec.domain.") and not name.startswith(
                "coflow.modules.dec.domain.model"
            ):
                violations.append(f"{path.relative_to(REPO)}:{lineno}: imports {name}")
            if name.startswith("coflow.modules.dec.queries"):
                violations.append(f"{path.relative_to(REPO)}:{lineno}: imports {name}")
    assert not violations, "the oracle is written from §3.7 only:\n" + "\n".join(violations)


def test_only_the_store_opens_database_connections() -> None:
    violations = []
    for path in sorted(SRC.rglob("*.py")):
        if path.is_relative_to(SRC / "kernel" / "store"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "connect"
                and isinstance(node.value, ast.Name)
                and node.value.id == "sqlite3"
            ):
                violations.append(f"{path.relative_to(REPO)}:{node.lineno}: sqlite3.connect")
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "sqlite3"
                and any(a.name == "connect" for a in node.names)
            ):
                violations.append(f"{path.relative_to(REPO)}:{node.lineno}: sqlite3.connect")
    assert not violations, "\n".join(violations)


# Review findings: grimp records ``from coflow.modules.dec.api import _queries`` as an import of
# ``api`` only, so the api-only rule above does not see a private name reached through the facade;
# and the kernel's raw writers are public methods on every unit of work.

_API = re.compile(r"^coflow\.modules\.(\w+)\.api$")
_PACKAGE = re.compile(r"^coflow\.modules\.(\w+)$")
KERNEL_ONLY_ATTRS = frozenset({"kernel_insert", "kernel_update", "erase", "_exec", "_writer"})
"""Unit-of-work internals only kernel code may call (``events.publish``, ``ids``, ``ops.init``)."""


def _own_module(path: Path) -> str | None:
    """The domain module a file belongs to (its own api may be used privately), if any."""
    if path.is_relative_to(SRC):
        rel = path.relative_to(SRC).parts
        return rel[1] if rel[0] == "modules" and len(rel) > 2 else None
    return _test_scope(path)


def _private_through_api(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rel = path.relative_to(REPO)
    return [f"{rel}:{line}" for line in _private_names(tree, _own_module(path))]


def _private_names(tree: ast.AST, own: str | None) -> list[str]:
    """``line: what`` for every private name of another module's api that ``tree`` reaches."""
    aliases: set[str] = set()
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            m = _API.match(node.module)
            if m and m.group(1) != own:
                out += [
                    f"{node.lineno}: from {node.module} import {a.name}"
                    for a in node.names
                    if a.name.startswith("_")
                ]
            p = _PACKAGE.match(node.module)
            if p and p.group(1) != own:
                aliases |= {a.asname or a.name for a in node.names if a.name == "api"}
        elif isinstance(node, ast.Import):
            for a in node.names:
                m = _API.match(a.name)
                if m and m.group(1) != own and a.asname:
                    aliases.add(a.asname)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in aliases
            and node.attr.startswith("_")
        ):
            out.append(f"{node.lineno}: {node.value.id}.{node.attr}")
    return out


def test_no_private_name_is_reached_through_another_module_s_api() -> None:
    files = [*sorted(SRC.rglob("*.py")), *sorted(TESTS.rglob("*.py"))]
    violations = [v for path in files for v in _private_through_api(path)]
    assert not violations, "a module's api exposes its public names only:\n" + "\n".join(violations)


def test_only_the_kernel_calls_the_unit_s_raw_writers() -> None:
    violations = []
    for path in sorted(SRC.rglob("*.py")):
        if path.is_relative_to(SRC / "kernel"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in KERNEL_ONLY_ATTRS:
                violations.append(f"{path.relative_to(REPO)}:{node.lineno}: .{node.attr}")
    assert not violations, "only kernel code writes around publish() and the id tap:\n" + (
        "\n".join(violations)
    )


def test_the_private_api_check_catches_both_forms() -> None:
    """The scan itself: both loopholes the review demonstrated are caught outside DEC, and DEC's
    own code may use its facade's private names."""
    probe = ast.parse(
        "from coflow.modules.dec.api import _queries\n"
        "from coflow.modules.dec import api as dec_api\n"
        "import coflow.modules.dec.api as dec2\n"
        "x = dec_api._repo\n"
        "y = dec2._directory\n"
        "z = dec_api.waiting\n"
    )
    assert [f.split(": ", 1)[1] for f in _private_names(probe, own="cmt")] == [
        "from coflow.modules.dec.api import _queries",
        "dec_api._repo",
        "dec2._directory",
    ]
    assert _private_names(probe, own="dec") == []
