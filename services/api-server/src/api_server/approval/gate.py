"""承認ゲート: L1業務の実行APIに対する`require_approval`FastAPI依存関数。

FR-AU-02 / AC-06: L1業務の実行APIは、対象エンティティに対する承認済み
(`decision == "approved"`)の`Approval`(PMDF)エンティティが存在しない
限り呼び出せない。この検証はルーティング層(依存性注入)で行うため、
エンドポイント実装者がチェックを書き忘れてもエンドポイント自体が
機能しない(依存関数を宣言し忘れた場合は
`tests/test_approval_gate_bypass.py`のエンドポイント網羅性チェックで検出する)。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import Depends, HTTPException, status

from api_server.deps import get_pmdf_store_dependency
from api_server.pmdf_store.store import PmdfStore

AutonomyLevel = Literal["L1"]


def _has_approved_record(store: PmdfStore, target_id: str) -> bool:
    """`target_id`を対象とする承認済み(approved)の`Approval`エンティティが存在するか判定する。

    同一targetに対し複数のapprovalレコードが存在しうる(差し戻し後の再起案等)。
    そのうち1件でも`decision == "approved"`であれば承認済みとみなす
    (差し戻しレコードのみの場合はFalse)。
    """
    approvals = store.list_all("approval")
    return any(
        approval.target == target_id and getattr(approval, "decision", None) == "approved"
        for approval in approvals
    )


def require_approval(
    entity_kind: str, autonomy_level: AutonomyLevel = "L1"
) -> Callable[[str, PmdfStore], None]:
    """`entity_kind`のL1業務実行エンドポイント向けの承認済みチェック依存関数を生成する。

    生成された依存関数は、パスパラメータ`id`(対象エンティティのid)を受け取り、
    `<entity_kind>:<id>`をtargetとする承認済みレコードが無ければ403を送出する。
    """

    def _dependency(
        id: str,
        store: Annotated[PmdfStore, Depends(get_pmdf_store_dependency)],
    ) -> None:
        if not _has_approved_record(store, id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"承認レコードがありません({entity_kind}:{id}, "
                    f"autonomy_level={autonomy_level})。承認ゲートによりL1業務の"
                    "実行は承認済みapprovalレコードが必須です(FR-AU-02)。"
                ),
            )

    return _dependency


__all__ = ["require_approval"]
