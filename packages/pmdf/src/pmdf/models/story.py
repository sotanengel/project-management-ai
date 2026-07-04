"""`story` エンティティのPydanticモデル。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from pmdf.models.common import ID_PATTERN, PmdfBase

PriorityMethod = Literal["RICE", "WSJF", "MoSCoW"]
StoryStatus = Literal["draft", "ready", "in_progress", "done", "dropped"]


class Priority(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: PriorityMethod
    reach: float | None = None
    impact: float | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    effort: float | None = None
    score: float | None = None


class StoryLinks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: str | None = Field(default=None, pattern=ID_PATTERN)
    decisions: list[str] = []


class Story(PmdfBase):
    kind: Literal["story"]
    product: str | None = Field(default=None, pattern=ID_PATTERN)
    title: str
    as_a: str
    i_want: str
    so_that: str
    acceptance_criteria: list[str]
    priority: Priority
    status: StoryStatus
    links: StoryLinks | None = None


__all__ = ["Priority", "Story", "StoryLinks"]
