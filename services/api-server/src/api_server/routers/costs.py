"""コスト計測API(E4-3, AR-04)。

`POST /costs/usage`(admin/editor): agent-core・学習ジョブ等がLLM呼び出し1件
毎のトークン数・レイテンシ・概算コストを報告する。
`GET /costs/summary`(admin/editor/viewer): モデル別・論理名別・日別の
集計値と、月次予算に対する消化率・閾値ステータスを返す(AR-04:
「全呼び出しのトークン数・レイテンシ・概算コストを記録し、月次予算に対する
消化率を可視化する」)。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from api_server.auth.dependencies import require_role
from api_server.auth.models import User
from api_server.config import Settings, get_settings
from api_server.costs.budget import check_budget_threshold, compute_consumption_ratio
from api_server.costs.usage_store import (
    AggregatedUsage,
    UsageRecord,
    append_usage,
    summarize_by_day,
    summarize_by_logical_name,
    summarize_by_model,
    total_spend,
)

router = APIRouter(prefix="/costs", tags=["costs"])


class UsageRequest(BaseModel):
    """`POST /costs/usage`のリクエストボディ。"""

    logical_name: str
    model: str
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    latency_ms: float = Field(default=0.0, ge=0)
    cost_jpy: float = Field(default=0.0, ge=0)
    actor: str = ""
    detail: dict = Field(default_factory=dict)


class UsageResponse(BaseModel):
    recorded: bool = True


class AggregatedUsageResponseEntry(BaseModel):
    key: str
    call_count: int
    total_tokens: int
    total_cost_jpy: float
    total_latency_ms: float


class CostSummaryResponse(BaseModel):
    period: str
    budget_monthly_jpy: float
    total_spend_jpy: float
    consumption_ratio: float
    budget_status: str
    by_model: list[AggregatedUsageResponseEntry]
    by_logical_name: list[AggregatedUsageResponseEntry]
    by_day: list[AggregatedUsageResponseEntry]


def _to_entries(summary: dict[str, AggregatedUsage]) -> list[AggregatedUsageResponseEntry]:
    return [
        AggregatedUsageResponseEntry(
            key=key,
            call_count=agg.call_count,
            total_tokens=agg.total_tokens,
            total_cost_jpy=agg.total_cost_jpy,
            total_latency_ms=agg.total_latency_ms,
        )
        for key, agg in sorted(summary.items())
    ]


@router.post("/usage", response_model=UsageResponse, status_code=status.HTTP_201_CREATED)
def record_usage(
    request: UsageRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[User, Depends(require_role("admin", "editor"))],
) -> UsageResponse:
    """LLM呼び出し1件分のusageを記録する(admin/editorのみ、AR-04)。"""
    record = UsageRecord(
        timestamp=datetime.now(UTC),
        logical_name=request.logical_name,
        model=request.model,
        prompt_tokens=request.prompt_tokens,
        completion_tokens=request.completion_tokens,
        latency_ms=request.latency_ms,
        cost_jpy=request.cost_jpy,
        actor=request.actor,
        detail=request.detail,
    )
    append_usage(record, settings.cost_usage_log_path)
    return UsageResponse(recorded=True)


@router.get("/summary", response_model=CostSummaryResponse)
def get_cost_summary(
    settings: Annotated[Settings, Depends(get_settings)],
    _user: Annotated[User, Depends(require_role("admin", "editor", "viewer"))],
    period: str = "monthly",
) -> CostSummaryResponse:
    """月次予算に対する消化率と、モデル別・論理名別・日別の集計を返す(閲覧はviewer以上)。"""
    now = datetime.now(UTC)
    log_path = settings.cost_usage_log_path

    monthly_spend = total_spend(read_records_path=log_path, year=now.year, month=now.month)
    ratio = compute_consumption_ratio(spend=monthly_spend, budget=settings.budget_monthly_jpy)
    budget_status = check_budget_threshold(ratio)

    return CostSummaryResponse(
        period=period,
        budget_monthly_jpy=settings.budget_monthly_jpy,
        total_spend_jpy=monthly_spend,
        consumption_ratio=ratio,
        budget_status=budget_status.value,
        by_model=_to_entries(summarize_by_model(log_path)),
        by_logical_name=_to_entries(summarize_by_logical_name(log_path)),
        by_day=_to_entries(summarize_by_day(log_path)),
    )


__all__ = ["router"]
