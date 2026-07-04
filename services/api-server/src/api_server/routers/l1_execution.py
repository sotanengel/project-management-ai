"""L1業務の実行系エンドポイント群(E3-6 承認ゲート実証実装)。

E5(agent-core)で本格的なエージェント実行APIが追加されるまでの間、
承認ゲート(`api_server.approval.gate.require_approval`)の適用対象となる
具体的なL1エンドポイントの雛形をここに置く。すべてのエンドポイントは
`require_approval(entity_kind, autonomy_level="L1")` 依存関数を必ず
宣言すること(`tests/test_approval_gate_bypass.py`のエンドポイント網羅性
チェックにより、新規追加時に依存関数の宣言漏れを検出する)。
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from api_server.approval.gate import require_approval
from api_server.auth.dependencies import get_current_user
from api_server.auth.models import User
from api_server.autonomy.emergency_stop import check_not_stopped
from api_server.deps import get_pmdf_store_dependency
from api_server.pmdf_store.store import PmdfStore

router = APIRouter(tags=["l1-execution"])

#: `tests/test_approval_gate_bypass.py`が参照する、承認ゲート対象の
#: L1エンドポイント一覧(網羅性チェック用)。新規L1エンドポイントを
#: 追加した場合、必ずここにも追記すること。
L1_GATED_ENDPOINTS: list[tuple[str, str]] = [
    ("POST", "/pmdf/decision/{id}/execute"),
    ("POST", "/roadmap/{id}/confirm"),
    ("POST", "/release/{id}/go-no-go"),
]


@router.post("/pmdf/decision/{id}/execute")
def execute_decision(
    id: str,
    store: Annotated[PmdfStore, Depends(get_pmdf_store_dependency)],
    user: Annotated[User, Depends(get_current_user)],
    _approval: Annotated[None, Depends(require_approval("decision", autonomy_level="L1"))],
    _not_stopped: Annotated[None, Depends(check_not_stopped)],
) -> dict[str, Any]:
    """decisionの実行(L1)。承認ゲート通過後、対象decisionを返す(実行内容自体はE5で拡張)。"""
    try:
        entity = store.get("decision", id)
    except (FileNotFoundError, KeyError) as exc:
        raise HTTPException(status_code=404, detail=f"decision:{id} が見つかりません") from exc
    return {"executed": True, "target": entity.id}


@router.post("/roadmap/{id}/confirm")
def confirm_roadmap_item(
    id: str,
    store: Annotated[PmdfStore, Depends(get_pmdf_store_dependency)],
    user: Annotated[User, Depends(get_current_user)],
    _approval: Annotated[None, Depends(require_approval("roadmap_item", autonomy_level="L1"))],
    _not_stopped: Annotated[None, Depends(check_not_stopped)],
) -> dict[str, Any]:
    """roadmap_itemの確定(L1)。承認ゲート通過後、対象roadmap_itemを返す。"""
    try:
        entity = store.get("roadmap_item", id)
    except (FileNotFoundError, KeyError) as exc:
        raise HTTPException(status_code=404, detail=f"roadmap_item:{id} が見つかりません") from exc
    return {"confirmed": True, "target": entity.id}


@router.post("/release/{id}/go-no-go")
def release_go_no_go(
    id: str,
    store: Annotated[PmdfStore, Depends(get_pmdf_store_dependency)],
    user: Annotated[User, Depends(get_current_user)],
    _approval: Annotated[None, Depends(require_approval("release", autonomy_level="L1"))],
    _not_stopped: Annotated[None, Depends(check_not_stopped)],
) -> dict[str, Any]:
    """releaseのgo/no-go判定実行(L1)。承認ゲート通過後、対象releaseを返す。"""
    try:
        entity = store.get("release", id)
    except (FileNotFoundError, KeyError) as exc:
        raise HTTPException(status_code=404, detail=f"release:{id} が見つかりません") from exc
    return {"go": True, "target": entity.id}


__all__ = ["L1_GATED_ENDPOINTS", "router"]
