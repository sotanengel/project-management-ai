"""E8-1: 自己学習ループ用 Pydantic スキーマ(DR-02 来歴管理)。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class RecordProvenance(BaseModel):
    """学習レコードの生成来歴(DR-02)。

    既存 `pmdf.models.common.Provenance`(PMDFエンティティ来歴)と
    名前衝突を避けるため `RecordProvenance` とする。
    """

    model_config = ConfigDict(extra="forbid")

    model: str
    prompt_template_version: str
    kb_version: str
    generated_at: datetime


class TrajectoryRecord(BaseModel):
    """エージェント実行軌跡レコード。"""

    model_config = ConfigDict(extra="forbid")

    scenario_text: str
    steps: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    pmdf_diffs: list[dict[str, Any]]
    model: str
    provenance: RecordProvenance
    scenario_hash: str


class SftRecord(BaseModel):
    """SFT 用 prompt/completion ペア。"""

    model_config = ConfigDict(extra="forbid")

    prompt: str
    completion: str
    trajectory_id: str
    provenance: RecordProvenance


class DpoRecord(BaseModel):
    """DPO 用 chosen/rejected ペア。"""

    model_config = ConfigDict(extra="forbid")

    prompt: str
    chosen: str
    rejected: str
    origin: Literal["human_feedback", "rule_rejection"]
    provenance: RecordProvenance


class ContaminationHit(BaseModel):
    """train/gate 間の重複検出結果。"""

    model_config = ConfigDict(extra="forbid")

    scenario_hash: str
    train_record_id: str
    gate_record_id: str
