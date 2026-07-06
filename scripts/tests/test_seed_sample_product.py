"""E10-1: seed_sample_product のテスト。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

from seed_sample_product.seed import (  # noqa: E402
    iter_seed_entities,
    materialize_data_dir,
    seed_store,
)


def test_materialize_includes_story_example_and_both_approvals(tmp_path: Path) -> None:
    import seed_sample_product.seed as seed_mod

    seed_mod.DATA_DIR = tmp_path / "data"
    materialize_data_dir()
    entities = iter_seed_entities()
    kinds = {e.kind for e in entities}
    assert "product" in kinds
    assert "story" in kinds
    stories = [e for e in entities if e.kind == "story"]
    assert any("ゲスト購入" in e.title for e in stories)
    approvals = [e for e in entities if e.kind == "approval"]
    decisions = {a.decision for a in approvals}
    assert "approved" in decisions
    assert "rejected" in decisions
    decisions_with_att = [e for e in entities if e.kind == "decision" and e.attachments]
    assert len(decisions_with_att) >= 1


def test_seed_store_is_idempotent(tmp_path: Path) -> None:
    import seed_sample_product.seed as seed_mod

    seed_mod.DATA_DIR = tmp_path / "data"
    store_path = tmp_path / "pmdf-store"
    first = seed_store(store_path)
    second = seed_store(store_path)
    assert first > 0
    assert second == 0


def test_pmdf_validate_cli_passes_on_materialized_data(tmp_path: Path) -> None:
    import seed_sample_product.seed as seed_mod

    seed_mod.DATA_DIR = tmp_path / "data"
    materialize_data_dir()
    for path in (tmp_path / "data").rglob("*.yaml"):
        result = subprocess.run(
            ["uv", "run", "pmdf", "validate", str(path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
