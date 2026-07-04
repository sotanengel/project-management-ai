"""`objective` エンティティのPydanticモデル。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from pmdf.models.common import ID_PATTERN, PmdfBase


class KeyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    target_value: float
    current_value: float | None = None


class Objective(PmdfBase):
    kind: Literal["objective"]
    objective: str
    key_results: list[KeyResult] = Field(min_length=1)
    period: str = Field(pattern=r"^\d{4}-Q[1-4]$")
    parent_objective: str | None = Field(
        default=None, pattern=ID_PATTERN, json_schema_extra={"ref_kind": "objective"}
    )


__all__ = ["KeyResult", "Objective"]
