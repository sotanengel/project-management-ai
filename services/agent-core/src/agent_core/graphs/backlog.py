"""業務グラフ(1) バックログ運用(E5-4、FR-PD-04)。

ユーザーストーリー起票・受入基準定義・優先順位付け(RICE/WSJF)を行う。
既定自律レベルはL2(実行→事後レビュー、承認ゲートを経由しない)。

**決定的計算の検算(本グラフの核心要件)**: LLMが提示する`reach/impact/
confidence/effort`(RICE)または`business_value/time_criticality/
risk_reduction/job_size`(WSJF)の数値から、`score`をコード側で必ず
再計算し、LLM出力の`score`は信用しない(誤ったスコアでも上書きする)。
"""

from __future__ import annotations

import json
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from pmdf.ids import generate_id

from agent_core.guards import run_node_with_guard
from agent_core.llm_client import LogicalModelClient
from agent_core.tools.pmdf_tools import PmdfToolClient

#: バックログ業務グラフの既定自律レベル(L2: 実行→事後レビュー)。
AUTONOMY_LEVEL = "L2"


def calc_rice_score(*, reach: float, impact: float, confidence: float, effort: float) -> float:
    """RICEスコアをコード側で決定的に計算する: `reach * impact * confidence / effort`。"""
    return reach * impact * confidence / effort


def calc_wsjf_score(
    *, business_value: float, time_criticality: float, risk_reduction: float, job_size: float
) -> float:
    """WSJFスコアをコード側で決定的に計算する。

    `(business_value + time_criticality + risk_reduction) / job_size`
    (Weighted Shortest Job First)。
    """
    return (business_value + time_criticality + risk_reduction) / job_size


def recalculate_priority(priority: dict[str, Any]) -> dict[str, Any]:
    """`priority.method`に応じてLLM提示の数値からscoreをコード側で再計算する。

    LLMが誤った`score`を提示していた場合でも、常にコード側の計算値で
    上書きする(RICE/WSJFいずれの場合も検算対象)。
    """
    method = priority.get("method")
    recalculated = dict(priority)
    if method == "RICE":
        recalculated["score"] = calc_rice_score(
            reach=float(priority["reach"]),
            impact=float(priority["impact"]),
            confidence=float(priority["confidence"]),
            effort=float(priority["effort"]),
        )
    elif method == "WSJF":
        recalculated["score"] = calc_wsjf_score(
            business_value=float(priority["business_value"]),
            time_criticality=float(priority["time_criticality"]),
            risk_reduction=float(priority["risk_reduction"]),
            job_size=float(priority["job_size"]),
        )
    else:
        raise ValueError(f"未対応の優先順位付け手法です: {method!r}")
    return recalculated


class BacklogState(TypedDict, total=False):
    intake_text: str
    draft: dict[str, Any]
    priority: dict[str, Any]
    story: dict[str, Any]


def _extract_json(content: str) -> dict[str, Any]:
    """LLMレスポンス本文からJSONオブジェクトをパースする。"""
    data: dict[str, Any] = json.loads(content)
    return data


def _build_graph(
    *,
    llm_client: LogicalModelClient,
    pmdf_tool_client: PmdfToolClient,
    api_server_url: str,
    auth_token: str,
) -> Any:
    async def intake_and_draft(state: BacklogState) -> BacklogState:
        completion = await llm_client.complete(
            model="pdm-main",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたはPdMアシスタントです。ユーザーの要望からストーリー"
                        "(as_a/i_want/so_that/受入基準/タイトル)とRICE優先度"
                        "(reach/impact/confidence/effort/score)をJSON形式で"
                        "出力してください。"
                    ),
                },
                {"role": "user", "content": state["intake_text"]},
            ],
        )
        draft = _extract_json(completion.content)
        return {**state, "draft": draft}

    async def calc_priority(state: BacklogState) -> BacklogState:
        draft = state["draft"]
        priority_input = {
            "method": draft.get("method", "RICE"),
            "reach": draft.get("reach"),
            "impact": draft.get("impact"),
            "confidence": draft.get("confidence"),
            "effort": draft.get("effort"),
            "business_value": draft.get("business_value"),
            "time_criticality": draft.get("time_criticality"),
            "risk_reduction": draft.get("risk_reduction"),
            "job_size": draft.get("job_size"),
            "score": draft.get("score"),
        }
        recalculated = recalculate_priority(priority_input)
        return {**state, "priority": recalculated}

    async def persist(state: BacklogState) -> BacklogState:
        draft = state["draft"]
        priority = state["priority"]
        story_payload = {
            "pmdf_version": "1.0.0",
            "kind": "story",
            "id": generate_id("story"),
            "provenance": {
                "created_by": "agent:backlog-agent@v1",
                "updated_at": "2026-01-01T00:00:00Z",
            },
            "attachments": [],
            "title": draft.get("title", ""),
            "as_a": draft["as_a"],
            "i_want": draft["i_want"],
            "so_that": draft["so_that"],
            "acceptance_criteria": draft["acceptance_criteria"],
            "priority": {
                "method": priority["method"],
                "reach": priority.get("reach"),
                "impact": priority.get("impact"),
                "confidence": priority.get("confidence"),
                "effort": priority.get("effort"),
                "score": priority["score"],
            },
            "status": "draft",
        }
        created = await pmdf_tool_client.create_entity(kind="story", data=story_payload)
        return {**state, "story": created}

    async def guarded(node: Any, state: BacklogState) -> BacklogState:
        result: BacklogState = await run_node_with_guard(
            node, state, api_server_url=api_server_url, auth_token=auth_token
        )
        return result

    async def node_intake(state: BacklogState) -> BacklogState:
        return await guarded(intake_and_draft, state)

    async def node_calc(state: BacklogState) -> BacklogState:
        return await guarded(calc_priority, state)

    async def node_persist(state: BacklogState) -> BacklogState:
        return await guarded(persist, state)

    graph = StateGraph(BacklogState)
    graph.add_node("intake", node_intake)
    graph.add_node("calc_priority", node_calc)
    graph.add_node("persist", node_persist)
    graph.set_entry_point("intake")
    graph.add_edge("intake", "calc_priority")
    graph.add_edge("calc_priority", "persist")
    graph.add_edge("persist", END)
    return graph.compile()


async def run_backlog_graph(
    *,
    intake_text: str,
    pmdf_tool_client: PmdfToolClient,
    llm_client: LogicalModelClient,
    api_server_url: str,
    auth_token: str,
) -> dict[str, Any]:
    """バックログ運用グラフ(intake -> calc_priority -> persist)を実行する。

    L2(承認ゲート非経由)。各ノード実行前に緊急停止照会(FR-AU-05)を行う。
    戻り値は永続化された`story`エンティティ(PMDF JSON表現)。
    """
    compiled = _build_graph(
        llm_client=llm_client,
        pmdf_tool_client=pmdf_tool_client,
        api_server_url=api_server_url,
        auth_token=auth_token,
    )
    result: BacklogState = await compiled.ainvoke({"intake_text": intake_text})
    return result["story"]


__all__ = [
    "AUTONOMY_LEVEL",
    "BacklogState",
    "calc_rice_score",
    "calc_wsjf_score",
    "recalculate_priority",
    "run_backlog_graph",
]
