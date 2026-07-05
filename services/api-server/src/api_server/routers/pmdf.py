"""PMDF CRUD API(`/pmdf/{kind}`)。

書込前に必ずPMDFスキーマ検証・参照整合チェックを行い、不正データを422で
拒否する(FR-DF-02)。approval/decisionの削除は明示的に405で拒否する
(DR-06、E3-7で本格的に扱うがルーティング自体はここで用意する)。
"""

from __future__ import annotations

import re
from typing import Annotated, Any

import jsonschema
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pmdf.io import entity_to_json_dict
from pmdf.models import KIND_TO_MODEL
from pmdf.models.common import PmdfBase
from pmdf.schema_registry import SchemaNotFoundError, validate_entity
from pmdf.validate import validate_references

from api_server.audit.log import AuditRecord, append_record, latest_hash
from api_server.auth.dependencies import check_product_scope, get_current_user, require_role
from api_server.auth.models import User
from api_server.config import Settings, get_settings
from api_server.deps import get_pmdf_store_dependency
from api_server.events.bus import InMemoryEventBus, get_event_bus
from api_server.pmdf_store.store import PmdfStore

router = APIRouter(prefix="/pmdf", tags=["pmdf"])

#: 削除不可のエンティティ種別(DR-06)。
_UNDELETABLE_KINDS = frozenset({"approval", "decision"})

#: agent-core(E5-2)がリクエストヘッダで実際のエージェント識別子を伝える
#: ための専用ヘッダ名。値が存在する場合、監査ログ・Gitコミットのactorを
#: このヘッダの値(`agent:<name>@v<version>`形式)で上書きする。
_AGENT_ACTOR_HEADER = "X-Agent-Actor"
_AGENT_ACTOR_PATTERN = re.compile(r"^agent:[^@]+@v.+$")


def _actor_from_user(user: User, agent_actor: str | None = None) -> str:
    """認証済みユーザーからGitコミットのauthorに用いるactor文字列を組み立てる。

    `agent_actor`(`X-Agent-Actor`ヘッダの値)が`agent:<name>@v<version>`
    形式であれば、そちらを優先する(agent-coreのツール呼び出しであることを
    監査ログ・Gitコミット履歴で判別できるようにするため)。
    """
    if agent_actor is not None and _AGENT_ACTOR_PATTERN.match(agent_actor):
        return agent_actor
    return f"user:{user.id}"


def _record_pmdf_audit(*, settings: Settings, actor: str, verb: str, entity: PmdfBase) -> None:
    """PMDF書込操作(create/update)を監査ログへ追記する(FR-AU-04/SEC-04)。"""
    log_path = settings.audit_log_path
    record = AuditRecord.create(
        actor=actor,
        action=f"pmdf.{entity.kind}.{verb}",
        target_kind=entity.kind,
        target_id=entity.id,
        detail={},
        prev_hash=latest_hash(log_path),
    )
    append_record(record, log_path)


def _resolve_product_id(kind: str, entity: PmdfBase) -> str | None:
    """エンティティが属するプロダクトIDを解決する(E3-5 プロダクトスコープ認可)。

    `product`エンティティ自身はそのidがプロダクトIDそのもの。`product`
    フィールドを持つkind(story/roadmap_item/release/risk/initiative/
    report/experiment/decision)はそのフィールド値を用いる。それ以外
    (objective/metric/persona/stakeholder/approval等、プロダクト非依存の
    グローバルなエンティティ)は`None`を返し、スコープチェック対象外とする。
    """
    if kind == "product":
        return entity.id
    return getattr(entity, "product", None)


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


async def _publish_entity_changed(
    bus: InMemoryEventBus, *, kind: str, entity_id: str, verb: str
) -> None:
    """PMDFエンティティ変更をWebSocket購読者へ配信する(FR-UI-11)。"""
    await bus.publish("pmdf.entity_changed", {"kind": kind, "id": entity_id, "verb": verb})


@router.post("/{kind}", status_code=status.HTTP_201_CREATED)
async def create_entity(
    kind: str,
    payload: dict[str, Any],
    store: Annotated[PmdfStore, Depends(get_pmdf_store_dependency)],
    user: Annotated[User, Depends(require_role("admin", "editor"))],
    settings: Annotated[Settings, Depends(get_settings)],
    bus: Annotated[InMemoryEventBus, Depends(get_event_bus)],
    agent_actor: Annotated[str | None, Header(alias=_AGENT_ACTOR_HEADER)] = None,
) -> dict[str, Any]:
    payload = {**payload, "kind": kind}
    _validate_schema_and_references(payload, kind, store)

    model_cls = _get_model_cls(kind)
    entity = model_cls.model_validate(payload)
    actor = _actor_from_user(user, agent_actor)
    created = store.create(entity, actor=actor)
    _record_pmdf_audit(settings=settings, actor=actor, verb="create", entity=created)
    await _publish_entity_changed(bus, kind=kind, entity_id=created.id, verb="create")
    return entity_to_json_dict(created)


@router.get("/{kind}")
def list_entities(
    kind: str,
    store: Annotated[PmdfStore, Depends(get_pmdf_store_dependency)],
    user: Annotated[User, Depends(get_current_user)],
    product: Annotated[str | None, Query()] = None,
) -> list[dict[str, Any]]:
    _get_model_cls(kind)
    entities = store.list_all(kind)
    if product is not None:
        entities = [e for e in entities if getattr(e, "product", None) == product]
    if user.product_scopes is not None:
        entities = [
            e
            for e in entities
            if (pid := _resolve_product_id(kind, e)) is None or pid in user.product_scopes
        ]
    return [entity_to_json_dict(e) for e in entities]


@router.get("/{kind}/{id}/history")
def get_entity_history(
    kind: str,
    id: str,
    store: Annotated[PmdfStore, Depends(get_pmdf_store_dependency)],
    user: Annotated[User, Depends(get_current_user)],
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
    user: Annotated[User, Depends(get_current_user)],
    ref: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    _get_model_cls(kind)
    try:
        entity = store.get(kind, id, ref=ref)
    except (FileNotFoundError, KeyError) as exc:
        raise HTTPException(status_code=404, detail=f"{kind}:{id} が見つかりません") from exc
    check_product_scope(user, _resolve_product_id(kind, entity))
    return entity_to_json_dict(entity)


@router.put("/{kind}/{id}")
async def update_entity(
    kind: str,
    id: str,
    payload: dict[str, Any],
    store: Annotated[PmdfStore, Depends(get_pmdf_store_dependency)],
    user: Annotated[User, Depends(require_role("admin", "editor"))],
    settings: Annotated[Settings, Depends(get_settings)],
    bus: Annotated[InMemoryEventBus, Depends(get_event_bus)],
    agent_actor: Annotated[str | None, Header(alias=_AGENT_ACTOR_HEADER)] = None,
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
    actor = _actor_from_user(user, agent_actor)
    updated = store.update(entity, actor=actor)
    _record_pmdf_audit(settings=settings, actor=actor, verb="update", entity=updated)
    await _publish_entity_changed(bus, kind=kind, entity_id=updated.id, verb="update")
    return entity_to_json_dict(updated)


@router.delete("/{kind}/{id}")
def delete_entity(
    kind: str,
    id: str,
    user: Annotated[User, Depends(require_role("admin", "editor"))],
) -> None:
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
