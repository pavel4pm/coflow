"""The MCP catalogue of I1 (MCP-1, MCP-3, MCP-4, spec §5.5). The generated-file check of AT-X3
arrives with the I3 catalogue."""

from __future__ import annotations

import jsonschema
import pytest

from coflow.interfaces.mcp.catalogue import (
    CATALOGUE,
    NEVER_EXPOSED,
    ToolSpec,
    catalogue_document,
    visible_tools,
)
from coflow.interfaces.mcp.tools_dec import HANDLERS
from coflow.modules.dec import api as dec_api

I1_TOOLS = {
    "dec_list": "list_decisions",
    "dec_context": "decision_context",
    "dec_waiting": "waiting",
    "dec_integrity": "integrity",
    "dec_shadow_report": "shadow_report",
}


def test_the_i1_catalogue_is_the_five_read_tools() -> None:
    assert {t.name: t.maps_to for t in CATALOGUE} == I1_TOOLS
    assert all(t.kind == "read" for t in CATALOGUE)
    assert all(hasattr(dec_api, t.maps_to) for t in CATALOGUE)
    assert set(HANDLERS) == set(I1_TOOLS)
    assert not {t.maps_to for t in CATALOGUE} & NEVER_EXPOSED
    for t in CATALOGUE:
        jsonschema.Draft202012Validator.check_schema(dict(t.input_schema))
        assert t.input_schema["additionalProperties"] is False


def test_a_new_tool_is_a_write_tool_by_default() -> None:
    with pytest.raises(ValueError, match="undo handler or not_undoable"):
        ToolSpec(name="dec_new", maps_to="new", description="x", input_schema={"type": "object"})
    marked = ToolSpec(
        name="dec_new",
        maps_to="new",
        description="x",
        input_schema={"type": "object"},
        undo="not_undoable",
    )
    assert marked.kind == "write"
    with pytest.raises(ValueError, match="names its handler"):
        ToolSpec(
            name="dec_new",
            maps_to="new",
            description="x",
            input_schema={"type": "object"},
            undo="undoable",
        )
    with pytest.raises(ValueError, match="namespace"):
        ToolSpec(
            name="review_decision",
            maps_to="review_decision",
            description="x",
            input_schema={"type": "object"},
            kind="read",
        )
    with pytest.raises(ValueError, match="never exposed"):
        ToolSpec(
            name="dec_approve",
            maps_to="approve_proposal",
            description="x",
            input_schema={"type": "object"},
            undo="not_undoable",
        )
    assert visible_tools(frozenset({"read"}), [marked]) == []
    assert visible_tools(frozenset({"read", "write"}), [marked]) == [marked]


def test_the_catalogue_document_is_deterministic() -> None:
    doc = catalogue_document()
    assert [d["name"] for d in doc] == sorted(I1_TOOLS)
    assert doc == catalogue_document(reversed(CATALOGUE))
    waiting = next(d for d in doc if d["name"] == "dec_waiting")
    assert waiting["usage_signal"] == "dec.waiting.pull"
