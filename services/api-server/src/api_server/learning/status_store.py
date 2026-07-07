"""自己学習ループ(SFT/DPO/評価ゲート)の状況記録ストア(E8-8関連)。

`trainer`(SFT/DPO)・`eval-runner`(評価ゲート・昇格判定)は別uvワークスペース
パッケージのため、api-serverを直接importできない。そのため両サービス側には
本モジュールと同一スキーマ(timestamp/job_type/status/metrics/decision)で
JSON1行を`LEARNING_STATUS_PATH`へ追記する、それぞれ独立した小さな書き出し
関数を持たせている(`trainer.sft._write_learning_status`,
`trainer.dpo._write_learning_status`, `eval_runner.cli._write_learning_status`)。
api-server側は本モジュールでそれを読み取り専用として解釈する
(costsの`usage_store.py`と同じ追記専用JSONLパターン)。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

JobType = Literal["sft", "dpo", "eval"]
JobStatus = Literal["started", "completed", "failed"]
Decision = Literal["promote", "reject"]


class LearningStatusRecord(BaseModel):
    """1件の学習ジョブ状況レコード。"""

    timestamp: datetime
    job_type: JobType
    status: JobStatus
    metrics: dict = Field(default_factory=dict)
    decision: Decision | None = None


def append_status(record: LearningStatusRecord, path: Path) -> None:
    """`record`をJSONL形式で`path`へ追記する(追記専用)。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(record.model_dump_json() + "\n")


def read_status_records(path: Path) -> list[LearningStatusRecord]:
    """`path`から全学習状況レコードを順番に読み込む。ファイルが無ければ空リスト。"""
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(LearningStatusRecord.model_validate(json.loads(line)))
    return records


@dataclass
class LearningStatusSummary:
    """`GET /learning/status`向けの集計結果。"""

    latest_job: LearningStatusRecord | None = None
    gate_history: list[LearningStatusRecord] = field(default_factory=list)


def summarize_learning_status(path: Path) -> LearningStatusSummary:
    """直近ジョブと評価ゲート(promote/reject)履歴を返す。学習実績が無ければ空。"""
    records = read_status_records(path)
    if not records:
        return LearningStatusSummary()
    gate_history = [r for r in records if r.job_type == "eval" and r.decision is not None]
    return LearningStatusSummary(latest_job=records[-1], gate_history=gate_history)


__all__ = [
    "LearningStatusRecord",
    "LearningStatusSummary",
    "append_status",
    "read_status_records",
    "summarize_learning_status",
]
