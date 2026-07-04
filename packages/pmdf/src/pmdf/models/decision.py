"""`decision` エンティティ(Decision Record)のPydanticモデル。

背景/選択肢/採用案/根拠/却下理由を必須項目として持つ(E5-6のDR自動記録の前提)。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from pmdf.models.common import ID_PATTERN, PmdfBase

AutonomyLevel = Literal["L0", "L1", "L2", "L3"]


class Option(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    pros: list[str] = []
    cons: list[str] = []


class RejectedReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option: str
    reason: str


class Decision(PmdfBase):
    kind: Literal["decision"]
    product: str | None = Field(
        default=None, pattern=ID_PATTERN, json_schema_extra={"ref_kind": "product"}
    )
    background: str
    options: list[Option] = Field(min_length=1)
    chosen_option: str
    rationale: str
    rejected_reasons: list[RejectedReason]
    approver: str | None = Field(
        default=None, pattern=ID_PATTERN, json_schema_extra={"ref_kind": "stakeholder"}
    )
    autonomy_level: AutonomyLevel


__all__ = ["Decision", "Option", "RejectedReason"]
