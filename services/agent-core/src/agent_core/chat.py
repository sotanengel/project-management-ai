"""チャット指示インターフェース(E5-9、FR-UI-07バックエンド)。

UIからの自然文の指示を受け取り、LLM(`pdm-main`)による意図分類ノードで
対象の業務グラフ(E5-4〜E5-7)を判定し、api-server(`POST
/chat/instructions`)へタスクとして登録する。タスク実行の各段階
(受理/実行中/完了/失敗)は`POST /chat/tasks/{id}/transition`経由で
api-serverへ報告し、api-server側がWebSocketイベントバス(`agent.activity`)
へ配信する(タスクの永続化・イベント配信はapi-server側の責務、
LLMによる意図分類・実際の業務グラフディスパッチはagent-core側の責務、
という疎結合を保つ)。
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, get_args

from agent_core.llm_client import LogicalModelClient
from agent_core.tools.pmdf_tools import PmdfToolClient

#: チャット指示がディスパッチしうる業務グラフの種別(E5-4〜E5-7に対応)。
GraphKind = Literal[
    "backlog",
    "vision_roadmap_release",
    "kpi_dr_review",
    "discovery_experiment_stakeholder_initiative",
]

#: `GraphKind`の全値(意図分類結果の検証・既定値フォールバック判定に用いる)。
GRAPH_KINDS: tuple[GraphKind, ...] = get_args(GraphKind)

#: LLMが未知の値を返した場合のフォールバック先(最も汎用的なバックログ運用)。
_DEFAULT_GRAPH_KIND: GraphKind = "backlog"

#: 業務グラフディスパッチ関数のシグネチャ。
DispatchFn = Callable[..., Awaitable[dict[str, Any]]]


@dataclass
class TaskHandle:
    """`handle_chat_instruction`が返す、登録済みタスクへのハンドル。"""

    task_id: str
    kind: GraphKind


def _extract_json(content: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(content)
    return data


async def classify_intent(message: str, *, llm_client: LogicalModelClient) -> GraphKind:
    """自然文の指示から、対象とすべき業務グラフをLLM(`pdm-main`)で判定する。

    LLMが`GRAPH_KINDS`のいずれにも該当しない値を返した場合は
    `_DEFAULT_GRAPH_KIND`(backlog)へフォールバックする(未知の指示でも
    タスク登録自体は失敗させない)。
    """
    completion = await llm_client.complete(
        model="pdm-main",
        messages=[
            {
                "role": "system",
                "content": (
                    "あなたはPdMアシスタントです。ユーザーの指示文が次のいずれの業務に"
                    "該当するか判定し、"
                    '{"graph": "backlog"|"vision_roadmap_release"|"kpi_dr_review"|'
                    '"discovery_experiment_stakeholder_initiative"}'
                    "形式のJSONで出力してください。\n"
                    "- backlog: ユーザーストーリー起票・優先順位付け\n"
                    "- vision_roadmap_release: ビジョン改訂・ロードマップ変更・"
                    "リリースGo/No-Go判断\n"
                    "- kpi_dr_review: KPI監視・意思決定記録・週次レビュー\n"
                    "- discovery_experiment_stakeholder_initiative: ディスカバリー・"
                    "実験・ステークホルダー調整・施策実行"
                ),
            },
            {"role": "user", "content": message},
        ],
    )
    result = _extract_json(completion.content)
    graph = result.get("graph")
    if graph not in GRAPH_KINDS:
        return _DEFAULT_GRAPH_KIND
    return graph  # type: ignore[return-value]


async def _default_dispatch(**_kwargs: Any) -> dict[str, Any]:
    """既定のディスパッチ実装(未接続時のプレースホルダー)。

    実運用では各`GraphKind`に対応する`agent_core.graphs.*`の実行関数を
    束ねたディスパッチテーブルを注入する想定(`dispatch_overrides`で
    テスト時に差し替え可能)。
    """
    raise NotImplementedError(
        "業務グラフディスパッチ関数が指定されていません。dispatch_overridesで注入してください。"
    )


async def handle_chat_instruction(
    *,
    message: str,
    product_id: str,
    actor: str,
    llm_client: LogicalModelClient,
    pmdf_tool_client: PmdfToolClient,
    api_server_url: str,
    auth_token: str,
    dispatch_overrides: dict[GraphKind, DispatchFn] | None = None,
) -> TaskHandle:
    """自然文の指示を受け、意図分類→タスク登録→業務グラフディスパッチまでを行う。

    1. `POST /chat/instructions`でタスクを`pending`状態として登録する。
    2. LLM(`pdm-main`)による意図分類(`classify_intent`)で対象業務グラフを判定する。
    3. `POST /chat/tasks/{id}/transition`で`running`へ遷移させる。
    4. 対象業務グラフのディスパッチ関数(`dispatch_overrides`で注入、
       未指定時は`_default_dispatch`)を実行する。
    5. 成功時は`done`(結果付き)、例外発生時は`failed`(エラー内容付き)へ
       遷移させる。
    """
    create_response = await pmdf_tool_client.request(
        "POST",
        "/chat/instructions",
        json={"message": message, "product_id": product_id},
    )
    task_id = create_response.json()["id"]

    kind = await classify_intent(message, llm_client=llm_client)

    await pmdf_tool_client.request(
        "POST",
        f"/chat/tasks/{task_id}/transition",
        json={"status": "running", "intent": kind},
    )

    dispatch_table: dict[GraphKind, DispatchFn] = dict(dispatch_overrides or {})
    dispatch_fn = dispatch_table.get(kind, _default_dispatch)

    try:
        result = await dispatch_fn(
            message=message,
            product_id=product_id,
            actor=actor,
            llm_client=llm_client,
            pmdf_tool_client=pmdf_tool_client,
            api_server_url=api_server_url,
            auth_token=auth_token,
        )
    except Exception as exc:  # noqa: BLE001 - タスク失敗として報告するために意図的に捕捉
        await pmdf_tool_client.request(
            "POST",
            f"/chat/tasks/{task_id}/transition",
            json={"status": "failed", "error": str(exc)},
        )
        return TaskHandle(task_id=task_id, kind=kind)

    await pmdf_tool_client.request(
        "POST",
        f"/chat/tasks/{task_id}/transition",
        json={"status": "done", "result": result},
    )
    return TaskHandle(task_id=task_id, kind=kind)


__all__ = [
    "GRAPH_KINDS",
    "DispatchFn",
    "GraphKind",
    "TaskHandle",
    "classify_intent",
    "handle_chat_instruction",
]
