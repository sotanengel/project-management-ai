"""`roadmap_item` エンティティのPydanticモデル。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from pmdf.models.common import ID_PATTERN, PmdfBase

RoadmapStatus = Literal["planned", "in_progress", "done", "cancelled"]


class RoadmapItem(PmdfBase):
    kind: Literal["roadmap_item"]
    product: str | None = Field(default=None, pattern=ID_PATTERN)
    theme: str
    period: str = Field(pattern=r"^\d{4}-Q[1-4]$")
    status: RoadmapStatus
    dependencies: list[str] = []
    objective: str = Field(pattern=ID_PATTERN)


__all__ = ["RoadmapItem"]
