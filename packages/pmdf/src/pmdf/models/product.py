"""`product` エンティティのPydanticモデル。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from pmdf.models.common import ID_PATTERN, PmdfBase

LifecycleStage = Literal["introduction", "growth", "maturity", "decline"]


class Product(PmdfBase):
    kind: Literal["product"]
    name: str
    vision: str
    target: str | None = None
    positioning: str | None = None
    lifecycle_stage: LifecycleStage
    north_star_metric: str | None = Field(
        default=None, pattern=ID_PATTERN, json_schema_extra={"ref_kind": "metric"}
    )


__all__ = ["Product"]
