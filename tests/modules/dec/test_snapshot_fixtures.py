"""Track S: the synthetic snapshot family is what the builder makes, and it is a valid
``coflow.import.decisions`` v1 document; the format's own example imports too."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from coflow.contracts import load_example
from coflow.kernel.context import CommandContext, FakeClock
from coflow.kernel.store.api import Store
from coflow.modules.dec import api as dec
from coflow.modules.dec.domain import cfj
from coflow.modules.dec.importer import snapshot as snapshot_mod
from tests.modules.dec import snapshot_builder as sb


@pytest.mark.parametrize("name", sorted(sb.FILES))
def test_the_committed_file_is_the_builders_output(name: str) -> None:
    committed = (sb.SNAPSHOT_DIR / name).read_text(encoding="utf-8")
    assert committed == sb.dumps(sb.FILES[name]()), (
        f"{name} is stale: run python -m tests.modules.dec.snapshot_builder"
    )


@pytest.mark.parametrize("name", sorted(sb.FILES))
def test_the_file_is_a_valid_snapshot(name: str) -> None:
    doc = snapshot_mod.parse_snapshot((sb.SNAPSHOT_DIR / name).read_bytes())
    assert doc["synthetic"] is True
    assert doc["source"]["issuer"] == "V1"
    numbers = sorted(d["v1_id"] for d in doc["decisions"])
    assert set(numbers) <= set(range(903, 911))
    assert doc["id_space"]["decision"]["deleted_without_trace"] == [901, 902]


def test_the_documented_hash_equals_cfj() -> None:
    doc = sb.s1()
    body = {k: v for k, v in doc.items() if k != "content_hash"}
    assert sb.content_hash(doc) == "sha256:" + cfj.sha256_hex(cfj.cfj(body))


def test_the_contract_example_imports(
    dev_store: Store, clock: FakeClock, owner_ctx: CommandContext, tmp_path: Path
) -> None:
    path = tmp_path / "example.json"
    path.write_bytes(load_example("import_decisions_v1.example.json"))
    report: Any = dec.import_snapshot(dec.default_env(), path, ctx=owner_ctx).value
    assert report.status == "applied"
    assert report.counts["decisions"].new == 1
    shadow = dec.shadow_report(dec.default_env(), run_id=report.run_id).value
    assert shadow.report_status == "written"
