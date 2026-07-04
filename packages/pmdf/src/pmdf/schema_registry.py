"""PMDF JSON Schema(schemas/pmdf/v1/*.schema.json)のロードと検証。

`schemas/pmdf/v1/*.schema.json` がPMDFフォーマットの正である。本モジュールは
そのJSON Schema群をロードし、`$ref` によるスキーマ間参照(例:
`common.schema.json#/$defs/id`)を解決した上で、`kind` ごとのエンティティ
データを検証するユーティリティを提供する。
"""

from __future__ import annotations

import json
from functools import cache, lru_cache
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.validators import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

# packages/pmdf/src/pmdf/schema_registry.py -> packages/pmdf
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = _PACKAGE_ROOT / "schemas" / "pmdf" / "v1"

#: JSON Schema上の `kind` enum値とスキーマファイル名の対応。
KIND_TO_SCHEMA_FILE: dict[str, str] = {
    "product": "product.schema.json",
    "stakeholder": "stakeholder.schema.json",
    "persona": "persona.schema.json",
    "objective": "objective.schema.json",
    "metric": "metric.schema.json",
    "roadmap_item": "roadmap_item.schema.json",
    "story": "story.schema.json",
    "experiment": "experiment.schema.json",
    "decision": "decision.schema.json",
    "release": "release.schema.json",
    "risk": "risk.schema.json",
    "initiative": "initiative.schema.json",
    "report": "report.schema.json",
    "approval": "approval.schema.json",
}


class SchemaNotFoundError(Exception):
    """指定された `kind` に対応するスキーマファイルが存在しない場合に送出。"""


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _build_registry() -> Registry:
    """`schemas/pmdf/v1/` 配下の全スキーマを読み込みRegistryを構築する。"""
    registry: Registry = Registry()
    for schema_path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        contents = _load_json(schema_path)
        resource = Resource.from_contents(contents, default_specification=DRAFT202012)
        # ファイル名でも解決できるよう、$idと相対ファイル名の両方で登録する。
        registry = registry.with_resource(schema_path.name, resource)
        if "$id" in contents:
            registry = registry.with_resource(contents["$id"], resource)
    return registry


@cache
def get_validator(kind: str) -> Draft202012Validator:
    """`kind` に対応するJSON Schemaの `jsonschema` バリデータを返す。"""
    if kind not in KIND_TO_SCHEMA_FILE:
        raise SchemaNotFoundError(f"未知のkindです: {kind!r}")
    schema_path = SCHEMA_DIR / KIND_TO_SCHEMA_FILE[kind]
    if not schema_path.exists():
        raise SchemaNotFoundError(f"スキーマファイルが見つかりません: {schema_path}")
    schema = _load_json(schema_path)
    registry = _build_registry()
    return Draft202012Validator(schema, registry=registry)  # type: ignore[call-arg]


def validate_entity(data: dict[str, Any], kind: str | None = None) -> None:
    """PMDFエンティティ(dict)をJSON Schemaで検証する。

    Args:
        data: 検証対象のエンティティデータ。
        kind: 検証に用いるスキーマのkind。省略時は `data["kind"]` を用いる。

    Raises:
        SchemaNotFoundError: kindに対応するスキーマが存在しない場合。
        jsonschema.exceptions.ValidationError: 検証に失敗した場合。
    """
    resolved_kind = kind if kind is not None else data.get("kind")
    if not isinstance(resolved_kind, str):
        raise SchemaNotFoundError("dataに文字列型の'kind'がありません。")
    validator = get_validator(resolved_kind)
    validator.validate(data)


def iter_validation_errors(data: dict[str, Any], kind: str | None = None):
    """検証エラーをすべて列挙するイテレータを返す(存在チェック等に利用)。"""
    resolved_kind = kind if kind is not None else data.get("kind")
    if not isinstance(resolved_kind, str):
        raise SchemaNotFoundError("dataに文字列型の'kind'がありません。")
    validator = get_validator(resolved_kind)
    return validator.iter_errors(data)


__all__ = [
    "KIND_TO_SCHEMA_FILE",
    "SCHEMA_DIR",
    "SchemaNotFoundError",
    "get_validator",
    "iter_validation_errors",
    "validate_entity",
    "jsonschema",
]
