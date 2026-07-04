"""`experiment` エンティティのPydanticモデル。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from pmdf.models.common import ID_PATTERN, PmdfBase

ExperimentStatus = Literal["planned", "running", "completed", "aborted"]


class Experiment(PmdfBase):
    kind: Literal["experiment"]
    product: str | None = Field(
        default=None, pattern=ID_PATTERN, json_schema_extra={"ref_kind": "product"}
    )
    hypothesis: str
    design: str
    success_criteria: list[str]
    status: ExperimentStatus
    results: str | None = None
    learnings: str | None = None


__all__ = ["Experiment"]
