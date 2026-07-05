"""根拠明示の共通機構(E5-8、FR-PD-13)。

全業務グラフ(E5-4〜E5-7)の成果物生成ノードが出力するPMDF書込ペイロードに
対し、FR-PD-13が定める根拠(KB出典・PMDF内の参照エンティティ・データ)の
いずれかを最低1件`x_evidence`拡張フィールド(PMDFのx_接頭辞拡張、E2-1)
として付与することを強制する。

- KB出典: `{source: "kb", domain, framework, excerpt}`
- PMDF参照: `{source: "pmdf", kind, id}`
- データ根拠: `{source: "data", description, data}`(決定的計算の入力値
  ・KPI実測値等、KB/PMDFいずれにも該当しない数値・事実的根拠に用いる。
  `data_evidence()`で組み立てる)

`agent_core.tools.rag_tool.SearchResult.to_evidence_dict()`が生成する形式
そのままの辞書、または`SearchResult`インスタンスそのものを受け付ける。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from agent_core.tools.rag_tool import SearchResult

EvidenceItem = SearchResult | dict[str, Any]


def data_evidence(*, description: str, data: dict[str, Any]) -> dict[str, Any]:
    """データ根拠(FR-PD-13の「データ」)を`x_evidence`形式で組み立てる。

    KB出典・PMDF参照エンティティのいずれにも該当しない、決定的計算の
    入力値(RICE/WSJFの構成値、EVMのplanned_value等)やKPI実測値を根拠と
    して明示する場合に用いる。
    """
    return {"source": "data", "description": description, "data": data}


class MissingEvidenceError(ValueError):
    """成果物に根拠(evidence)が1件も付与されない場合に送出される例外。"""

    def __init__(self) -> None:
        super().__init__(
            "成果物にはKB出典またはPMDF参照エンティティを最低1件、"
            "根拠(evidence)として明示する必要があります(FR-PD-13)。"
        )


def _to_evidence_dict(item: EvidenceItem) -> dict[str, Any]:
    if isinstance(item, SearchResult):
        return item.to_evidence_dict()
    return dict(item)


def attach_evidence(payload: dict[str, Any], evidence: list[EvidenceItem] | None) -> dict[str, Any]:
    """`payload`のコピーに`x_evidence`拡張フィールドを付与して返す。

    `evidence`が空または`None`の場合は`MissingEvidenceError`を送出し、
    根拠なしの成果物がPMDFへ書き込まれることを防ぐ(全業務グラフの
    書込境界で必ず経由させる想定)。元の`payload`は変更しない。
    """
    if not evidence:
        raise MissingEvidenceError()

    return {**payload, "x_evidence": [_to_evidence_dict(item) for item in evidence]}


def evidence_guard(
    node: Callable[..., Awaitable[tuple[dict[str, Any], list[EvidenceItem]]]],
) -> Callable[..., Awaitable[dict[str, Any]]]:
    """成果物生成ノードへ1行のデコレータ追加で適用できる根拠明示強制デコレータ。

    デコレート対象の関数は`(payload, evidence)`のタプルを返す必要がある。
    `evidence_guard`は`attach_evidence`を適用した`x_evidence`付きpayloadを
    返す(evidenceが空の場合は`MissingEvidenceError`を送出しノード実行を
    失敗させる)。既存の4業務グラフへは各成果物生成ノードにこの
    デコレータを追加するだけで統合できる設計とする。
    """

    @wraps(node)
    async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        payload, evidence = await node(*args, **kwargs)
        return attach_evidence(payload, evidence)

    return wrapper


__all__ = [
    "EvidenceItem",
    "MissingEvidenceError",
    "attach_evidence",
    "data_evidence",
    "evidence_guard",
]
