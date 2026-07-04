"""`report` エンティティのPydanticモデル。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from pmdf.models.common import ID_PATTERN, PmdfBase

HealthAssessment = Literal["green", "yellow", "red"]


class Report(PmdfBase):
    kind: Literal["report"]
    product: str | None = Field(
        default=None, pattern=ID_PATTERN, json_schema_extra={"ref_kind": "product"}
    )
    period: str
    health_assessment: HealthAssessment
    decisions_needed: list[str]
    summary: str | None = None


__all__ = ["Report"]
