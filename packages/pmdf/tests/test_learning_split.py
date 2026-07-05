"""E8-1: 学習データ split 割当の検証テスト。"""

from __future__ import annotations

from dataclasses import dataclass

from pmdf.learning.split import assign_split


@dataclass
class _Record:
    scenario_text: str
    scenario_hash: str | None = None
    id: str = ""


def test_assign_split_respects_ratios() -> None:
    records = [
        _Record(scenario_text=f"scenario-{i}", scenario_hash=f"hash-{i}", id=f"r{i}")
        for i in range(10)
    ]
    result = assign_split(records, ratios={"train": 0.8, "val": 0.1, "gate": 0.1})
    assert sum(len(v) for v in result.values()) == 10
    assert len(result["train"]) == 8
    assert len(result["val"]) == 1
    assert len(result["gate"]) == 1


def test_same_scenario_hash_never_spans_splits() -> None:
    records = [
        _Record(scenario_text="same scenario", scenario_hash="shared-hash", id="a"),
        _Record(scenario_text="same scenario", scenario_hash="shared-hash", id="b"),
        _Record(scenario_text="other", scenario_hash="other-hash", id="c"),
    ]
    result = assign_split(records, ratios={"train": 0.5, "val": 0.25, "gate": 0.25})
    train_hashes = {r.scenario_hash for r in result["train"]}
    val_hashes = {r.scenario_hash for r in result["val"]}
    gate_hashes = {r.scenario_hash for r in result["gate"]}
    all_hashes = (train_hashes, val_hashes, gate_hashes)
    assert any("shared-hash" in s for s in all_hashes)
    assert sum(1 for s in all_hashes if "shared-hash" in s) == 1


def test_assign_split_derives_hash_from_scenario_text() -> None:
    records = [
        _Record(scenario_text="  hello   world  ", id="r1"),
        _Record(scenario_text="hello world", id="r2"),
    ]
    result = assign_split(records, ratios={"train": 1.0, "val": 0.0, "gate": 0.0})
    assert len(result["train"]) == 2
    assert len(result["val"]) == 0
    assert len(result["gate"]) == 0
