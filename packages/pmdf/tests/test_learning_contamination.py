"""E8-1: 学習データ contamination 検出の検証テスト。"""

from __future__ import annotations

from dataclasses import dataclass

from pmdf.learning.contamination import (
    detect_contamination,
    normalize_scenario_text,
    scenario_hash,
)


@dataclass
class _Record:
    scenario_text: str
    id: str
    scenario_hash: str | None = None


def test_normalize_scenario_text_collapses_whitespace() -> None:
    assert normalize_scenario_text("  hello   world  ") == "hello world"


def test_scenario_hash_is_sha256_hex() -> None:
    h1 = scenario_hash("hello world")
    h2 = scenario_hash("  hello   world  ")
    assert h1 == h2
    assert len(h1) == 64


def test_detect_contamination_finds_overlap() -> None:
    train = [_Record(id="t1", scenario_text="Build auth module")]
    gate = [_Record(id="g1", scenario_text="Build auth module")]
    hits = detect_contamination(train, gate)
    assert len(hits) == 1
    assert hits[0].train_record_id == "t1"
    assert hits[0].gate_record_id == "g1"


def test_detect_contamination_returns_empty_for_clean_sets() -> None:
    train = [_Record(id="t1", scenario_text="Build auth module")]
    gate = [_Record(id="g1", scenario_text="Build billing module")]
    assert detect_contamination(train, gate) == []
