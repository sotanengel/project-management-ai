"""PMDF CRUD API(`/pmdf/{kind}`)。

書込前に必ずPMDFスキーマ検証・参照整合チェックを行い、不正データを422で
拒否する(FR-DF-02)。approval/decisionの削除は明示的に405で拒否する
(DR-06、E3-7で本格的に扱うがルーティング自体はここで用意する)。
"""

from __future__ import annotations

from typing import Annotated, Any

import jsonschema
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pmdf.io import entity_to_json_dict
from pmdf.models import KIND_TO_MODEL
from pmdf.models.common import PmdfBase
from pmdf.schema_registry import SchemaNotFoundError, validate_entity
from pmdf.validate import validate_references

from api_server.deps import get_pmdf_store_dependency
from api_server.pmdf_store.store import PmdfStore

router = APIRouter(prefix="/pmdf", tags=["pmdf"])

#: 削除不可のエンティティ種別(DR-06)。
_UNDELETABLE_KINDS = frozenset({"approval", "decision"})

# TODO(E3-4完了後): 認証実装後、認証済みユーザー情報から actor
# (`user:<id>`)を取得するよう差し替える。現時点では暫定的に固定値を使う。
_PLACEHOLDER_ACTOR = "user:placeholder-until-e3-4"


def _get_model_cls(kind: str) -> type[PmdfBase]:
    if kind not in KIND_TO_MODEL:
        raise HTTPException(status_code=404, detail=f"未知のkindです: {kind!r}")
    return KIND_TO_MODEL[kind]


def _validate_schema_and_references(data: dict[str, Any], kind: str, store: PmdfStore) -> None:
    """JSON Schema検証+参照整合チェックを行い、失敗時は422を送出する。"""
    try:
        validate_entity(data, kind=kind)
    except jsonschema.exceptions.ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"スキーマ検証エラー: {exc.message}") from exc
    except SchemaNotFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    model_cls = _get_model_cls(kind)
    candidate = model_cls.model_validate(data)

    # 参照整合チェックは、当該kindだけでなく参照されうる全種別を対象に
    # ストア全体から既存エンティティを集めて行う。
    existing_entities = []
    for other_kind in KIND_TO_MODEL:
        if other_kind == kind:
            continue
        existing_entities.extend(store.list_all(other_kind))
    existing_entities.extend(e for e in store.list_all(kind) if e.id != candidate.id)

    reference_errors = validate_references([*existing_entities, candidate])
    relevant_errors = [e for e in reference_errors if e.entity_id == candidate.id]
    if relevant_errors:
        detail = "; ".join(str(e) for e in relevant_errors)
        raise HTTPException(status_code=422, detail=f"参照整合エラー: {detail}")


@router.post("/{kind}", status_code=status.HTTP_201_CREATED)
def create_entity(
    kind: str,
    payload: dict[str, Any],
    store: Annotated[PmdfStore, Depends(get_pmdf_store_dependency)],
) -> dict[str, Any]:
    payload = {**payload, "kind": kind}
    _validate_schema_and_references(payload, kind, store)

    model_cls = _get_model_cls(kind)
    entity = model_cls.model_validate(payload)
    created = store.create(entity, actor=_PLACEHOLDER_ACTOR)
    return entity_to_json_dict(created)


@router.get("/{kind}")
def list_entities(
    kind: str,
    store: Annotated[PmdfStore, Depends(get_pmdf_store_dependency)],
    product: Annotated[str | None, Query()] = None,
) -> list[dict[str, Any]]:
    _get_model_cls(kind)
    entities = store.list_all(kind)
    if product is not None:
        entities = [e for e in entities if getattr(e, "product", None) == product]
    return [entity_to_json_dict(e) for e in entities]


@router.get("/{kind}/{id}/history")
def get_entity_history(
    kind: str,
    id: str,
    store: Annotated[PmdfStore, Depends(get_pmdf_store_dependency)],
) -> list[dict[str, Any]]:
    _get_model_cls(kind)
    history = store.history(kind, id)
    if not history:
        raise HTTPException(status_code=404, detail=f"{kind}:{id} の履歴が見つかりません")
    return [
        {
            "commit_hash": h.commit_hash,
            "author": h.author,
            "committed_at": h.committed_at.isoformat(),
            "message": h.message,
        }
        for h in history
    ]


@router.get("/{kind}/{id}")
def get_entity(
    kind: str,
    id: str,
    store: Annotated[PmdfStore, Depends(get_pmdf_store_dependency)],
    ref: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    _get_model_cls(kind)
    try:
        entity = store.get(kind, id, ref=ref)
    except (FileNotFoundError, KeyError) as exc:
        raise HTTPException(status_code=404, detail=f"{kind}:{id} が見つかりません") from exc
    return entity_to_json_dict(entity)


@router.put("/{kind}/{id}")
def update_entity(
    kind: str,
    id: str,
    payload: dict[str, Any],
    store: Annotated[PmdfStore, Depends(get_pmdf_store_dependency)],
) -> dict[str, Any]:
    _get_model_cls(kind)
    try:
        store.get(kind, id)
    except (FileNotFoundError, KeyError) as exc:
        raise HTTPException(status_code=404, detail=f"{kind}:{id} が見つかりません") from exc

    payload = {**payload, "kind": kind, "id": id}
    _validate_schema_and_references(payload, kind, store)

    model_cls = _get_model_cls(kind)
    entity = model_cls.model_validate(payload)
    updated = store.update(entity, actor=_PLACEHOLDER_ACTOR)
    return entity_to_json_dict(updated)


@router.delete("/{kind}/{id}")
def delete_entity(kind: str, id: str) -> None:
    """DR-06: approval/decisionは削除不可。それ以外も物理削除APIは提供しない。"""
    if kind in _UNDELETABLE_KINDS:
        raise HTTPException(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            detail=f"{kind}は削除できません(DR-06)。訂正は新規レコードで表現してください",
        )
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="物理削除APIは提供していません。論理削除(statusフィールド更新)を使用してください。",
    )


__all__ = ["router"]
