"""`persona` エンティティのPydanticモデル。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from pmdf.models.common import PmdfBase


class Job(BaseModel):
    """JTBD(Jobs To Be Done)形式のジョブ。"""

    model_config = ConfigDict(extra="forbid")

    situation: str
    motivation: str
    outcome: str


class Persona(PmdfBase):
    kind: Literal["persona"]
    name: str
    attributes: dict[str, str] = {}
    pain_points: list[str] = []
    jobs: list[Job] = Field(min_length=1)


__all__ = ["Job", "Persona"]
