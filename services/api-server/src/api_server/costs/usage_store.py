"""LLM呼び出しのusage(トークン数・レイテンシ・概算コスト)記録ストア(E4-3, AR-04)。

LiteLLMのspend tracking(DB)を用いない軽量構成向けに、agent-core・学習
ジョブ等の呼び出し元が`POST /costs/usage`経由で1呼び出し毎のusageを
報告し、JSONL追記専用ファイルへ蓄積する。集計は読み取り時に行う
(監査ログ`api_server.audit.log`と同様の追記専用パターン)。
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class UsageRecord(BaseModel):
    """1回のLLM/埋め込み呼び出し分のusageレコード。"""

    timestamp: datetime
    #: 論理名(pdm-main/pdm-teacher/pdm-judge/pdm-embed等)。
    logical_name: str
    #: 実モデル名(集計・可視化用。論理名→実モデルの対応はゲートウェイ設定が正)。
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    #: 概算コスト(日本円)。
    cost_jpy: float = 0.0
    #: 呼び出し元(agent-core、学習ジョブ等の識別子)。
    actor: str = ""
    detail: dict = Field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def append_usage(record: UsageRecord, log_path: Path) -> None:
    """`record`をJSONL形式で`log_path`へ追記する(追記専用)。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(record.model_dump_json() + "\n")


def read_usage_records(log_path: Path) -> list[UsageRecord]:
    """`log_path`から全usageレコードを順番に読み込む。ファイルが無ければ空リスト。"""
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(UsageRecord.model_validate(json.loads(line)))
    return records


def _filter_by_month(
    records: list[UsageRecord], *, year: int | None, month: int | None
) -> list[UsageRecord]:
    if year is None or month is None:
        return records
    return [r for r in records if r.timestamp.year == year and r.timestamp.month == month]


def total_spend(
    *,
    read_records_path: Path,
    year: int | None = None,
    month: int | None = None,
) -> float:
    """`log_path`の全usageレコードから概算コスト合計(円)を算出する。

    `year`/`month`を指定すると、その月に絞り込んだ合計を返す(月次予算消化率算出用)。
    """
    records = read_usage_records(read_records_path)
    records = _filter_by_month(records, year=year, month=month)
    return sum(r.cost_jpy for r in records)


@dataclass
class AggregatedUsage:
    """集計単位(モデル別・論理名別・日別)ごとのusage合計。"""

    call_count: int = 0
    total_tokens: int = 0
    total_cost_jpy: float = 0.0
    total_latency_ms: float = 0.0

    def add(self, record: UsageRecord) -> None:
        self.call_count += 1
        self.total_tokens += record.total_tokens
        self.total_cost_jpy += record.cost_jpy
        self.total_latency_ms += record.latency_ms


def _summarize_by_key(
    log_path: Path, key_fn: Callable[[UsageRecord], str]
) -> dict[str, AggregatedUsage]:
    summary: dict[str, AggregatedUsage] = defaultdict(AggregatedUsage)
    for record in read_usage_records(log_path):
        summary[key_fn(record)].add(record)
    return dict(summary)


def summarize_by_model(log_path: Path) -> dict[str, AggregatedUsage]:
    """実モデル名別の集計を返す。"""
    return _summarize_by_key(log_path, lambda r: r.model)


def summarize_by_logical_name(log_path: Path) -> dict[str, AggregatedUsage]:
    """論理名別の集計を返す。"""
    return _summarize_by_key(log_path, lambda r: r.logical_name)


def summarize_by_day(log_path: Path) -> dict[str, AggregatedUsage]:
    """日別(`YYYY-MM-DD`、UTC基準)の集計を返す。"""
    return _summarize_by_key(log_path, lambda r: r.timestamp.date().isoformat())


__all__ = [
    "AggregatedUsage",
    "UsageRecord",
    "append_usage",
    "read_usage_records",
    "summarize_by_day",
    "summarize_by_logical_name",
    "summarize_by_model",
    "total_spend",
]
