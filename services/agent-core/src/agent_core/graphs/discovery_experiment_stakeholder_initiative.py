"""業務グラフ(4) ディスカバリー・実験・SH調整・施策実行(E5-7)。

FR-PD-03(ディスカバリー)/FR-PD-06(仮説検証・実験管理)/
FR-PD-09(ステークホルダー調整)/FR-PD-10(施策のプロジェクト実行管理)。
FR-PD-14に基づき、プロダクト(ライフサイクル全体)とプロジェクト
(施策=一時的取り組み、initiative)の概念を正しく区別する
(initiativeはproduct固有のライフサイクルフィールドを持たない)。

- `run_discovery`/`run_experiment`: L2(実行→事後報告)
- `stakeholder_communication`: `draft_message`(L2、文案生成のみ)と
  `send_message`(L1、実際の送信=外部送信相当、E5-5と同様の
  承認ゲート二重チェック方式)に分離
- `run_initiative`: L2。WBS・リスク登録簿・EVM値はLLM任せにせず、
  EVM(SPI/CPI)はコード側で決定的に計算する
"""

from __future__ import annotations

import json
from typing import Any

from pmdf.ids import generate_id

from agent_core.evidence import attach_evidence, data_evidence
from agent_core.graphs.vision_roadmap_release import call_l1_gated_endpoint
from agent_core.guards import run_node_with_guard
from agent_core.llm_client import LogicalModelClient
from agent_core.tools.pmdf_tools import PmdfToolClient

#: run_discovery/run_experiment/run_initiativeの既定自律レベル(L2)。
DISCOVERY_AUTONOMY_LEVEL = "L2"
#: stakeholder_communicationのdraft_messageはL2、send_messageはL1。
DRAFT_AUTONOMY_LEVEL = "L2"
SEND_AUTONOMY_LEVEL = "L1"

_NOW = "2026-01-01T00:00:00Z"
_AGENT_ACTOR = "agent:discovery-agent@v1"


def _extract_json(content: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(content)
    return data


async def run_discovery(
    *,
    context: str,
    pmdf_tool_client: PmdfToolClient,
    llm_client: LogicalModelClient,
    api_server_url: str,
    auth_token: str,
) -> dict[str, Any]:
    """persona(属性・課題・JTBD)を生成・作成する(L2、事後報告)。"""

    async def _draft(state: dict[str, Any]) -> dict[str, Any]:
        completion = await llm_client.complete(
            model="pdm-main",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたはPdMアシスタントです。ユーザーインタビュー結果から"
                        "ペルソナを"
                        '{"name": "...", "attributes": {...}, "pain_points": [...], '
                        '"jobs": [{"situation": "...", "motivation": "...", '
                        '"outcome": "..."}]}形式のJSONで出力してください。'
                    ),
                },
                {"role": "user", "content": context},
            ],
        )
        return {**state, "draft": _extract_json(completion.content)}

    initial_state: dict[str, Any] = {}
    state = await run_node_with_guard(
        _draft, initial_state, api_server_url=api_server_url, auth_token=auth_token
    )
    draft = state["draft"]

    persona_payload = {
        "pmdf_version": "1.0.0",
        "kind": "persona",
        "id": generate_id("persona"),
        "provenance": {"created_by": _AGENT_ACTOR, "updated_at": _NOW},
        "attachments": [],
        "name": draft["name"],
        "attributes": draft.get("attributes", {}),
        "pain_points": draft.get("pain_points", []),
        "jobs": draft["jobs"],
    }
    # E5-8(FR-PD-13): ペルソナ生成の根拠(データ: インタビュー入力コンテキスト)を明示する。
    persona_payload = attach_evidence(
        persona_payload,
        [
            data_evidence(
                description="ユーザーインタビュー入力コンテキスト", data={"context": context}
            )
        ],
    )
    created: dict[str, Any] = await pmdf_tool_client.create_entity(
        kind="persona", data=persona_payload
    )
    return created


async def run_experiment(
    *,
    product_id: str,
    context: str,
    pmdf_tool_client: PmdfToolClient,
    llm_client: LogicalModelClient,
    api_server_url: str,
    auth_token: str,
) -> dict[str, Any]:
    """experimentエンティティ(仮説・設計・成功基準・結果・学び)を作成する(L2)。"""

    async def _draft(state: dict[str, Any]) -> dict[str, Any]:
        completion = await llm_client.complete(
            model="pdm-main",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたはPdMアシスタントです。実験(仮説検証)の記録を"
                        '{"hypothesis": "...", "design": "...", '
                        '"success_criteria": [...], "status": '
                        '"planned"|"running"|"completed"|"aborted", '
                        '"results": "..."|null, "learnings": "..."|null}'
                        "形式のJSONで出力してください。"
                    ),
                },
                {"role": "user", "content": context},
            ],
        )
        return {**state, "draft": _extract_json(completion.content)}

    initial_state: dict[str, Any] = {}
    state = await run_node_with_guard(
        _draft, initial_state, api_server_url=api_server_url, auth_token=auth_token
    )
    draft = state["draft"]

    experiment_payload = {
        "pmdf_version": "1.0.0",
        "kind": "experiment",
        "id": generate_id("experiment"),
        "provenance": {"created_by": _AGENT_ACTOR, "updated_at": _NOW},
        "attachments": [],
        "product": product_id,
        "hypothesis": draft["hypothesis"],
        "design": draft["design"],
        "success_criteria": draft["success_criteria"],
        "status": draft["status"],
        "results": draft.get("results"),
        "learnings": draft.get("learnings"),
    }
    # E5-8(FR-PD-13): 実験記録の根拠(PMDF参照: 対象product、データ: 入力コンテキスト)を明示する。
    experiment_payload = attach_evidence(
        experiment_payload,
        [
            {"source": "pmdf", "kind": "product", "id": product_id},
            data_evidence(description="実験設計の入力コンテキスト", data={"context": context}),
        ],
    )
    created: dict[str, Any] = await pmdf_tool_client.create_entity(
        kind="experiment", data=experiment_payload
    )
    return created


async def draft_message(
    *,
    stakeholder_id: str,
    context: str,
    llm_client: LogicalModelClient,
    api_server_url: str,
    auth_token: str,
) -> dict[str, Any]:
    """ステークホルダー向けメッセージ文案を生成する(L2、文案生成のみ・送信は行わない)。"""

    async def _draft(state: dict[str, Any]) -> dict[str, Any]:
        completion = await llm_client.complete(
            model="pdm-main",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたはPdMアシスタントです。ステークホルダー向けの"
                        '定例報告メッセージ文案を{"message": "..."}形式のJSONで'
                        "出力してください。"
                    ),
                },
                {"role": "user", "content": context},
            ],
        )
        return {**state, "draft": _extract_json(completion.content)}

    initial_state: dict[str, Any] = {"stakeholder_id": stakeholder_id}
    state = await run_node_with_guard(
        _draft, initial_state, api_server_url=api_server_url, auth_token=auth_token
    )
    result: dict[str, Any] = state["draft"]
    return result


async def send_message(
    *,
    stakeholder_id: str,
    message: str,
    pmdf_tool_client: PmdfToolClient,
    api_server_url: str,
    auth_token: str,
) -> dict[str, Any]:
    """ステークホルダーへのメッセージ送信を実行する(L1、承認ゲート必須)。

    `draft_message`とは異なり、実際の送信(外部送信相当のアクション)は
    api-serverの`POST /stakeholder/{id}/send-message`(L1ゲート済み)
    経由でのみ実行できる。未承認の場合は403を受け取り
    `ApprovalNotGrantedError`を送出する(E5-5と同じ方式)。
    """
    return await call_l1_gated_endpoint(
        entity_kind="stakeholder",
        entity_id=stakeholder_id,
        confirm_path=f"/stakeholder/{stakeholder_id}/send-message",
        pmdf_tool_client=pmdf_tool_client,
        api_server_url=api_server_url,
        auth_token=auth_token,
    )


def calc_evm(*, planned_value: float, earned_value: float, actual_cost: float) -> dict[str, float]:
    """EVM値(SPI/CPI)をコード側で決定的に計算する。

    SPI(Schedule Performance Index) = earned_value / planned_value
    CPI(Cost Performance Index) = earned_value / actual_cost
    """
    return {
        "planned_value": planned_value,
        "earned_value": earned_value,
        "actual_cost": actual_cost,
        "spi": earned_value / planned_value,
        "cpi": earned_value / actual_cost,
    }


async def run_initiative(
    *,
    product_id: str,
    context: str,
    risk_owner: str,
    pmdf_tool_client: PmdfToolClient,
    llm_client: LogicalModelClient,
    api_server_url: str,
    auth_token: str,
) -> dict[str, Any]:
    """initiativeエンティティ(憲章・アプローチ・WBS・スケジュール・リスク登録簿・EVM値)を作成する(L2)。

    EVM値(SPI/CPI)はLLM出力の`planned_value`/`earned_value`/
    `actual_cost`からコード側(`calc_evm`)で決定的に計算する。
    FR-PD-14: initiativeはproduct固有のライフサイクルフィールド
    (vision/lifecycle_stage等)を一切持たない(スキーマレベルで区別)。
    """

    async def _draft(state: dict[str, Any]) -> dict[str, Any]:
        completion = await llm_client.complete(
            model="pdm-main",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたはPdMアシスタントです。施策(プロジェクト)の実行計画を"
                        '{"charter": "...", "approach": '
                        '"predictive"|"adaptive"|"hybrid", '
                        '"wbs": [{"id": "...", "name": "...", "children": [...]}], '
                        '"planned_value": 0.0, "earned_value": 0.0, '
                        '"actual_cost": 0.0, "risks": [{"event": "...", '
                        '"probability_score": 1, "impact_score": 1, '
                        '"response_strategy": "avoid"|"transfer"|"mitigate"|"accept"}]}'
                        "形式のJSONで出力してください。"
                    ),
                },
                {"role": "user", "content": context},
            ],
        )
        return {**state, "draft": _extract_json(completion.content)}

    initial_state: dict[str, Any] = {}
    state = await run_node_with_guard(
        _draft, initial_state, api_server_url=api_server_url, auth_token=auth_token
    )
    draft = state["draft"]

    evm = calc_evm(
        planned_value=float(draft["planned_value"]),
        earned_value=float(draft["earned_value"]),
        actual_cost=float(draft["actual_cost"]),
    )

    initiative_payload = {
        "pmdf_version": "1.0.0",
        "kind": "initiative",
        "id": generate_id("initiative"),
        "provenance": {"created_by": _AGENT_ACTOR, "updated_at": _NOW},
        "attachments": [],
        "product": product_id,
        "charter": draft["charter"],
        "approach": draft["approach"],
        "wbs": draft.get("wbs", []),
        "evm": evm,
    }
    # E5-8(FR-PD-13): EVM計算の入力値(データ根拠)を明示する。
    initiative_payload = attach_evidence(
        initiative_payload,
        [data_evidence(description="EVM計算の入力値", data=evm)],
    )
    created_initiative = await pmdf_tool_client.create_entity(
        kind="initiative", data=initiative_payload
    )

    created_risks: list[dict[str, Any]] = []
    for risk_draft in draft.get("risks", []):
        risk_payload = {
            "pmdf_version": "1.0.0",
            "kind": "risk",
            "id": generate_id("risk"),
            "provenance": {"created_by": _AGENT_ACTOR, "updated_at": _NOW},
            "attachments": [],
            "product": product_id,
            "event": risk_draft["event"],
            "probability_score": risk_draft["probability_score"],
            "impact_score": risk_draft["impact_score"],
            "response_strategy": risk_draft["response_strategy"],
            "owner": risk_owner,
        }
        # E5-8(FR-PD-13): リスク登録の根拠(PMDF参照: 起因initiative)を明示する。
        risk_payload = attach_evidence(
            risk_payload, [{"source": "pmdf", "kind": "initiative", "id": created_initiative["id"]}]
        )
        created_risk = await pmdf_tool_client.create_entity(kind="risk", data=risk_payload)
        created_risks.append(created_risk)

    return {"initiative": created_initiative, "risks": created_risks}


__all__ = [
    "DISCOVERY_AUTONOMY_LEVEL",
    "DRAFT_AUTONOMY_LEVEL",
    "SEND_AUTONOMY_LEVEL",
    "calc_evm",
    "draft_message",
    "run_discovery",
    "run_experiment",
    "run_initiative",
    "send_message",
]
