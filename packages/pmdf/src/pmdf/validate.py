"""エンティティ間参照整合チェック。

各Pydanticモデルのフィールドメタデータ(`Field(json_schema_extra={"ref_kind":
...})`)から参照フィールドを動的に収集し、エンティティ集合内で参照が実在
するID・期待されるkindを指しているかを検証する。ハードコードした参照
フィールドのリストを持たないため、モデル側にref_kindを追加するだけで
新しい参照フィールドを検証対象に加えられる。
"""

from __future__ import annotations

import types
from dataclasses import dataclass
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel

from pmdf.models.common import PmdfBase

_UNION_TYPES = (Union, types.UnionType)


@dataclass(frozen=True)
class RefFieldSpec:
    """モデル定義から収集した1つの参照フィールドの仕様。"""

    path: tuple[str, ...]
    ref_kind: str | None
    many: bool


@dataclass(frozen=True)
class ReferenceError:
    """参照整合エラー1件。"""

    entity_kind: str
    entity_id: str
    field_path: str
    referenced_id: str
    reason: str  # "missing" | "kind_mismatch"
    expected_kind: str | None = None
    actual_kind: str | None = None

    def __str__(self) -> str:
        if self.reason == "missing":
            return (
                f"{self.entity_kind}:{self.entity_id} の {self.field_path} が参照する "
                f"{self.referenced_id!r} は存在しません"
            )
        return (
            f"{self.entity_kind}:{self.entity_id} の {self.field_path} が参照する "
            f"{self.referenced_id!r} は kind={self.actual_kind!r} ですが "
            f"期待されるkindは {self.expected_kind!r} です"
        )


def _extract_basemodel(annotation: Any) -> type[BaseModel] | None:
    """アノテーションから(Optionalでラップされていても)BaseModelサブクラスを取り出す。"""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    origin = get_origin(annotation)
    if origin in _UNION_TYPES:
        for arg in get_args(annotation):
            if isinstance(arg, type) and issubclass(arg, BaseModel):
                return arg
    return None


def _iter_ref_field_specs(
    model_cls: type[BaseModel], prefix: tuple[str, ...] = ()
) -> list[RefFieldSpec]:
    """モデルクラス(ネストしたサブモデルを含む)から参照フィールド仕様を収集する。"""
    specs: list[RefFieldSpec] = []
    for name, field in model_cls.model_fields.items():
        extra = field.json_schema_extra
        if isinstance(extra, dict) and "ref_kind" in extra:
            ref_kind = extra["ref_kind"]
            assert ref_kind is None or isinstance(ref_kind, str)
            is_list = get_origin(field.annotation) is list
            specs.append(RefFieldSpec(path=(*prefix, name), ref_kind=ref_kind, many=is_list))
            continue
        nested_cls = _extract_basemodel(field.annotation)
        if nested_cls is not None:
            specs.extend(_iter_ref_field_specs(nested_cls, (*prefix, name)))
    return specs


def _get_by_path(obj: Any, path: tuple[str, ...]) -> Any:
    value = obj
    for part in path:
        if value is None:
            return None
        value = getattr(value, part, None)
    return value


def validate_references(entities: list[PmdfBase]) -> list[ReferenceError]:
    """エンティティ集合内で、参照フィールドが実在かつ期待kindのIDを指すか検証する。"""
    id_to_kind: dict[str, str] = {entity.id: entity.kind for entity in entities}
    errors: list[ReferenceError] = []

    for entity in entities:
        specs = _iter_ref_field_specs(type(entity))
        for spec in specs:
            value = _get_by_path(entity, spec.path)
            if value is None:
                continue
            ref_ids: list[str] = value if spec.many else [value]
            field_path = ".".join(spec.path)
            for ref_id in ref_ids:
                if not ref_id:
                    continue
                if ref_id not in id_to_kind:
                    errors.append(
                        ReferenceError(
                            entity_kind=entity.kind,
                            entity_id=entity.id,
                            field_path=field_path,
                            referenced_id=ref_id,
                            reason="missing",
                        )
                    )
                    continue
                actual_kind = id_to_kind[ref_id]
                if spec.ref_kind is not None and actual_kind != spec.ref_kind:
                    errors.append(
                        ReferenceError(
                            entity_kind=entity.kind,
                            entity_id=entity.id,
                            field_path=field_path,
                            referenced_id=ref_id,
                            reason="kind_mismatch",
                            expected_kind=spec.ref_kind,
                            actual_kind=actual_kind,
                        )
                    )
    return errors


__all__ = ["ReferenceError", "RefFieldSpec", "validate_references"]
