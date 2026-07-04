"""`risk` エンティティのPydanticモデル。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from pmdf.models.common import ID_PATTERN, PmdfBase

ResponseStrategy = Literal["avoid", "transfer", "mitigate", "accept"]


class Risk(PmdfBase):
    kind: Literal["risk"]
    product: str | None = Field(default=None, pattern=ID_PATTERN)
    event: str
    probability_score: int = Field(ge=1, le=5)
    impact_score: int = Field(ge=1, le=5)
    response_strategy: ResponseStrategy
    owner: str = Field(pattern=ID_PATTERN)


__all__ = ["Risk"]
