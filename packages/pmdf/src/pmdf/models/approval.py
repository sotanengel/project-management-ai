"""`approval` エンティティのPydanticモデル。

監査用の承認記録。運用上は追記専用(E3-7で強制)とする前提。
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from pmdf.models.common import ID_PATTERN, PmdfBase

ApprovalDecision = Literal["approved", "rejected"]


class Approval(PmdfBase):
    kind: Literal["approval"]
    target: str = Field(pattern=ID_PATTERN)
    proposer: str = Field(pattern=ID_PATTERN)
    approver: str = Field(pattern=ID_PATTERN)
    decision: ApprovalDecision
    reason: str


__all__ = ["Approval"]
