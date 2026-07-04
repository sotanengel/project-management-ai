"""`metric` エンティティのPydanticモデル。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from pmdf.models.common import PmdfBase


class TimeSeriesPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    value: float


class Metric(PmdfBase):
    kind: Literal["metric"]
    name: str
    definition: str
    calculation_method: str
    target_value: float | None = None
    threshold_value: float | None = None
    current_value: float | None = None
    time_series: list[TimeSeriesPoint] = []
    external_source_url: str | None = None


__all__ = ["Metric", "TimeSeriesPoint"]
