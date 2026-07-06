"""E9-1: スケジューラ設定(環境変数から読込)。"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SchedulerConfig:
    api_base_url: str
    model_gateway_url: str
    auth_token: str
    product_id: str
    metric_id: str
    proposer: str
    kpi_cron: str
    weekly_review_cron: str
    learning_loop_cron: str
    weekly_review_period: str


def load_scheduler_config() -> SchedulerConfig:
    """環境変数からスケジュール設定を読み込む(コード変更なしで頻度調整可能)。"""
    return SchedulerConfig(
        api_base_url=os.environ.get("API_BASE_URL", "http://api-server:8000"),
        model_gateway_url=os.environ.get("MODEL_GATEWAY_URL", "http://model-gateway:4000"),
        auth_token=os.environ.get("SCHEDULER_AUTH_TOKEN", ""),
        product_id=os.environ.get("SCHEDULER_PRODUCT_ID", "product-sample"),
        metric_id=os.environ.get("SCHEDULER_METRIC_ID", "metric-sample"),
        proposer=os.environ.get("SCHEDULER_PROPOSER", "scheduler@system"),
        kpi_cron=os.environ.get("SCHEDULER_KPI_CRON", "0 * * * *"),
        weekly_review_cron=os.environ.get("SCHEDULER_WEEKLY_REVIEW_CRON", "0 9 * * 1"),
        learning_loop_cron=os.environ.get("SCHEDULER_LEARNING_LOOP_CRON", "0 2 * * 0"),
        weekly_review_period=os.environ.get("SCHEDULER_WEEKLY_REVIEW_PERIOD", "2026-W01"),
    )


__all__ = ["SchedulerConfig", "load_scheduler_config"]
