"""E8-1: 学習データ contamination 検出。"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Sequence
from typing import Protocol

from pmdf.learning.schemas import ContaminationHit

_WHITESPACE_RE = re.compile(r"\s+")


class HashableScenario(Protocol):
    """scenario_hash 属性または scenario_text からハッシュ導出可能なレコード。"""

    scenario_text: str

    @property
    def scenario_hash(self) -> str | None: ...


class ScenarioRecord(HashableScenario, Protocol):
    id: str


def normalize_scenario_text(text: str) -> str:
    """シナリオ文字列を正規化する(空白の折りたたみ)。"""
    return _WHITESPACE_RE.sub(" ", text.strip())


def scenario_hash(text: str) -> str:
    """正規化済みシナリオ文字列の SHA-256 ハッシュ(hex)。"""
    normalized = normalize_scenario_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def resolve_scenario_hash(record: HashableScenario) -> str:
    explicit = getattr(record, "scenario_hash", None)
    if explicit:
        return explicit
    return scenario_hash(record.scenario_text)


def detect_contamination(
    train: Sequence[ScenarioRecord],
    gate: Sequence[ScenarioRecord],
) -> list[ContaminationHit]:
    """train/gate 間の scenario_hash 重複を検出する。

    n-gram 近似重複検出は将来拡張(TODO)。
    """
    # TODO: n-gram 近似重複検出を追加する
    gate_index: dict[str, list[ScenarioRecord]] = defaultdict(list)
    for record in gate:
        gate_index[resolve_scenario_hash(record)].append(record)

    hits: list[ContaminationHit] = []
    for train_record in train:
        train_hash = resolve_scenario_hash(train_record)
        for gate_record in gate_index.get(train_hash, []):
            hits.append(
                ContaminationHit(
                    scenario_hash=train_hash,
                    train_record_id=train_record.id,
                    gate_record_id=gate_record.id,
                )
            )
    return hits
