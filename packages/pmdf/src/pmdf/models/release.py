"""`release` エンティティのPydanticモデル。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from pmdf.models.common import ID_PATTERN, PmdfBase

GoNoGo = Literal["go", "no_go", "pending"]


class Release(PmdfBase):
    kind: Literal["release"]
    product: str | None = Field(default=None, pattern=ID_PATTERN)
    name: str
    scope: list[str]
    go_no_go: GoNoGo
    released_at: datetime | None = None
    actuals: dict[str, Any] = {}


__all__ = ["Release"]
