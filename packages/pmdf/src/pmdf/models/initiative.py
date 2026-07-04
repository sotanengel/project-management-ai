"""`initiative` エンティティのPydanticモデル。"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from pmdf.models.common import ID_PATTERN, PmdfBase

Approach = Literal["predictive", "adaptive", "hybrid"]


class WbsNode(BaseModel):
    """WBS(階層構造)のノード。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    children: list[WbsNode] = []


class Schedule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date | None = None
    end_date: date | None = None


class Evm(BaseModel):
    """EVM値(PV/EV/AC/SPI/CPI相当)。"""

    model_config = ConfigDict(extra="forbid")

    planned_value: float | None = None
    earned_value: float | None = None
    actual_cost: float | None = None
    spi: float | None = None
    cpi: float | None = None


class Initiative(PmdfBase):
    kind: Literal["initiative"]
    product: str | None = Field(
        default=None, pattern=ID_PATTERN, json_schema_extra={"ref_kind": "product"}
    )
    charter: str
    approach: Approach
    wbs: list[WbsNode] = []
    schedule: Schedule | None = None
    evm: Evm | None = None


__all__ = ["Evm", "Initiative", "Schedule", "WbsNode"]
