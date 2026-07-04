"""業務種別×プロダクト単位の自律レベル(L0〜L3)設定(FR-AU-01)。

永続化はPMDFストア(Gitリポジトリ)とは別に、api-server内のシンプルな
JSON設定ファイルとして行う(Gitコミットは不要だが、変更自体は監査ログ
(E3-7)に記録する運用とする)。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, cast, get_args

from pydantic import BaseModel

AutonomyLevel = Literal["L0", "L1", "L2", "L3"]

#: FR-PD-01〜11に対応する業務種別。
BusinessFunction = Literal[
    "vision",
    "roadmap",
    "discovery",
    "backlog",
    "kpi_monitoring",
    "experiment",
    "release",
    "decision_record",
    "stakeholder",
    "initiative",
    "periodic_review",
]

_VALID_BUSINESS_FUNCTIONS = frozenset(get_args(BusinessFunction))

#: 業務種別が未設定の場合の既定レベル(最も保守的なL0: 全て人間が実施)。
DEFAULT_LEVEL: AutonomyLevel = "L0"


class AutonomyConfig(BaseModel):
    """1つの(product_id, business_function)組に対する自律レベル設定。"""

    product_id: str
    business_function: BusinessFunction
    level: AutonomyLevel


def _validate_business_function(business_function: str) -> None:
    if business_function not in _VALID_BUSINESS_FUNCTIONS:
        raise ValueError(f"未知の業務種別です: {business_function!r}")


def _load(config_path: Path) -> list[AutonomyConfig]:
    if not config_path.exists():
        return []
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    return [AutonomyConfig.model_validate(item) for item in raw]


def _save(config_path: Path, entries: list[AutonomyConfig]) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [entry.model_dump(mode="json") for entry in entries]
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get_level(config_path: Path, *, product_id: str, business_function: str) -> AutonomyLevel:
    """`product_id`×`business_function`の自律レベルを返す。未設定時は`DEFAULT_LEVEL`(L0)。"""
    _validate_business_function(business_function)
    for entry in _load(config_path):
        if entry.product_id == product_id and entry.business_function == business_function:
            return entry.level
    return DEFAULT_LEVEL


def set_level(
    config_path: Path, *, product_id: str, business_function: str, level: AutonomyLevel
) -> AutonomyConfig:
    """`product_id`×`business_function`の自律レベルを設定(新規作成または更新)する。

    Raises:
        ValueError: `business_function`が未知の値の場合。
    """
    _validate_business_function(business_function)
    entries = _load(config_path)
    updated = AutonomyConfig(
        product_id=product_id,
        business_function=cast(BusinessFunction, business_function),
        level=level,
    )
    for index, entry in enumerate(entries):
        if entry.product_id == product_id and entry.business_function == business_function:
            entries[index] = updated
            _save(config_path, entries)
            return updated
    entries.append(updated)
    _save(config_path, entries)
    return updated


def list_all(config_path: Path) -> list[AutonomyConfig]:
    """設定済みの全エントリを返す。"""
    return _load(config_path)


__all__ = [
    "DEFAULT_LEVEL",
    "AutonomyConfig",
    "AutonomyLevel",
    "BusinessFunction",
    "get_level",
    "list_all",
    "set_level",
]
