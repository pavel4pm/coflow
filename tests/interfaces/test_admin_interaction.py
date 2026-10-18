"""The admin API keeps only an id-shaped interaction id from the client's header (review finding:
free text in ``x-coflow-interaction`` reached ``sys_events.correlationid``)."""

from __future__ import annotations

from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from coflow.interfaces.admin.api import CLI_INTERACTION, INTERACTION_HEADER, admin_routes


class _Service:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def dispatch(self, op: str, body: Any, *, interaction_id: str, scope: str) -> dict[str, Any]:
        self.seen.append(interaction_id)
        return {"ok": True}


class _Tokens:
    def verify(self, token: str) -> str | None:
        return "admin" if token == "cfa_test" else None


@pytest.mark.parametrize(
    ("header", "kept"),
    [
        ("cli-0123456789abcdef", True),
        ("CANARY the statement says 1200 EUR", False),
        ("cli-http", False),
        ("", False),
        (None, False),
    ],
)
def test_the_interaction_header_is_kept_only_in_the_cli_s_shape(
    header: str | None, kept: bool
) -> None:
    service = _Service()
    app = Starlette(routes=admin_routes(service, _Tokens()))  # type: ignore[arg-type]
    headers = {"authorization": "Bearer cfa_test"}
    if header is not None:
        headers[INTERACTION_HEADER] = header
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.post("/admin/v1/dec.waiting", json={}, headers=headers)
    assert response.status_code == 200
    (seen,) = service.seen
    assert CLI_INTERACTION.fullmatch(seen)
    assert (seen == header) is kept
