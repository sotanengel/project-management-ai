"""`stakeholder` エンティティのPydanticモデル。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from pmdf.models.common import PmdfBase

Influence = Literal["low", "medium", "high", "critical"]


class ContactPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    personal_name: str | None = None
    channel: str | None = None
    frequency: str | None = None


class Stakeholder(PmdfBase):
    kind: Literal["stakeholder"]
    name: str
    role: str
    organization: str | None = None
    interests: list[str] = []
    influence: Influence
    contact_policy: ContactPolicy | None = None


__all__ = ["ContactPolicy", "Stakeholder"]
