"""他社共有向けの「共有プロファイル」によるPMDFデータのサニタイズ(FR-EX-03)。

マスキング定義はYAMLで表現する(`packages/pmdf/config/sanitize_profiles/
default.yaml`)。指定フィールド(内部コスト、個人名、非公開指標値等)を
マスクしたコピーを返し、元データは変更しない。
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict

#: マスク済みフィールドの固定置換値。
REDACTED_VALUE = "***MASKED***"

MaskStrategy = Literal["redact"]


class MaskRule(BaseModel):
    """1つの`kind`に対するマスク対象フィールドの定義。"""

    model_config = ConfigDict(extra="forbid")

    kind: str
    fields: list[str]
    strategy: MaskStrategy = "redact"


class SanitizeProfile(BaseModel):
    """共有プロファイル(マスキング定義一式)。"""

    model_config = ConfigDict(extra="forbid")

    profile: str
    mask_fields: list[MaskRule] = []

    def rules_for_kind(self, kind: str | None) -> list[MaskRule]:
        """指定`kind`に適用されるマスクルールを返す。"""
        return [rule for rule in self.mask_fields if rule.kind == kind]


def load_sanitize_profile(path: Path) -> SanitizeProfile:
    """YAMLファイルから`SanitizeProfile`をロードする。"""
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return SanitizeProfile.model_validate(data)


def _mask_by_path(data: dict[str, Any], field_path: str, replacement: Any) -> None:
    """`field_path`(ドット区切り)が指すフィールドを`replacement`で置換する。

    途中のパスが存在しない場合は何もしない(対象フィールドが無いだけであり、
    エラーにはしない)。
    """
    parts = field_path.split(".")
    current: Any = data
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return
        current = current[part]
    last = parts[-1]
    if isinstance(current, dict) and last in current:
        current[last] = replacement


def sanitize_entity(entity: dict[str, Any], profile: SanitizeProfile) -> dict[str, Any]:
    """`profile`に基づき指定フィールドをマスクしたコピーを返す(元データは変更しない)。"""
    result = copy.deepcopy(entity)
    kind = result.get("kind") if isinstance(result, dict) else None
    for rule in profile.rules_for_kind(kind):
        if rule.strategy != "redact":
            continue
        for field_path in rule.fields:
            _mask_by_path(result, field_path, REDACTED_VALUE)
    return result


__all__ = [
    "REDACTED_VALUE",
    "MaskRule",
    "SanitizeProfile",
    "load_sanitize_profile",
    "sanitize_entity",
]
