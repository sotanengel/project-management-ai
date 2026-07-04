"""全PMDFエンティティが共有する共通モデル(PmdfBase/Provenance/Attachment)。

`schemas/pmdf/v1/common.schema.json` に対応するPydantic v2モデル。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

ID_PATTERN = r"^[a-z]+-[0-9A-HJKMNP-TV-Z]{26}$"
PMDF_VERSION_PATTERN = r"^\d+\.\d+\.\d+$"
CREATED_BY_PATTERN = r"^(agent:[^@]+@v.+|user:.+)$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"


class Attachment(BaseModel):
    """添付ファイル参照(相対パス+SHA-256ハッシュ)。バイナリ本体は含まない。"""

    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str = Field(pattern=SHA256_PATTERN)


class Provenance(BaseModel):
    """作成者・承認者・更新日時の来歴情報。"""

    model_config = ConfigDict(extra="forbid")

    created_by: str = Field(pattern=CREATED_BY_PATTERN)
    approved_by: str | None = None
    updated_at: datetime


class PmdfBase(BaseModel):
    """全PMDFエンティティ共通の基底モデル。

    `extra="allow"` としつつ、`model_validator(mode="after")` で
    `x_` 接頭辞以外の未知フィールドを拒否する(JSON Schemaの
    `patternProperties: {"^x_": {}}` + `additionalProperties: false` と
    等価な挙動をPydantic側で再現するため)。
    """

    model_config = ConfigDict(extra="allow")

    pmdf_version: str = Field(pattern=PMDF_VERSION_PATTERN)
    kind: str
    id: str = Field(pattern=ID_PATTERN)
    provenance: Provenance
    attachments: list[Attachment] = Field(default_factory=list)

    @model_validator(mode="after")
    def _reject_non_x_prefixed_extra_fields(self) -> PmdfBase:
        extra: dict[str, Any] = self.model_extra or {}
        unknown = [key for key in extra if not key.startswith("x_")]
        if unknown:
            raise ValueError(
                f"未知のプロパティです(x_接頭辞以外は許可されません): {sorted(unknown)}"
            )
        return self


__all__ = [
    "CREATED_BY_PATTERN",
    "ID_PATTERN",
    "PMDF_VERSION_PATTERN",
    "SHA256_PATTERN",
    "Attachment",
    "PmdfBase",
    "Provenance",
]
