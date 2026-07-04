"""業務グラフ(3) KPI監視・Decision Record・週次レビュー(E5-6)。

FR-PD-05(KPI監視)/FR-PD-08(Decision Record)/FR-PD-11(定常レビュー)。
いずれも既定自律レベルL3(完全自律、監査ログのみ)。承認ゲート(E3-6)を
経由せず直接persistされるが、`weekly_review`が要判断事項を検出した
場合はapproval起案(L1業務への橋渡し)を行う。
"""

from __future__ import annotations

import json
from typing import Any

from pmdf.ids import generate_id

from agent_core.evidence import attach_evidence, data_evidence
from agent_core.guards import run_node_with_guard
from agent_core.llm_client import LogicalModelClient
from agent_core.tools.pmdf_tools import PmdfToolClient

#: KPI監視・Decision Record・週次レビューグラフの既定自律レベル(L3: 完全自律)。
AUTONOMY_LEVEL = "L3"

_NOW = "2026-01-01T00:00:00Z"


def _extract_json(content: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(content)
    return data


def is_threshold_breached(*, current_value: float, threshold_value: float) -> bool:
    """現在値が閾値を超過(悪化方向、値が大きいほど悪いメトリクスを想定)しているか判定する。"""
    return current_value > threshold_value


async def monitor_kpi(
    *,
    metric_id: str,
    product_id: str,
    pmdf_tool_client: PmdfToolClient,
    llm_client: LogicalModelClient,
    api_server_url: str,
    auth_token: str,
) -> dict[str, Any]:
    """metricエンティティの現在値を閾値と比較し、超過時はLLMで原因仮説を生成しreportへ記録する。

    閾値判定はコード側(`is_threshold_breached`)で行い、LLMには超過が
    確定した場合の原因仮説生成のみを依頼する(判定自体はLLMに委ねない)。
    """

    async def _fetch_and_check(state: dict[str, Any]) -> dict[str, Any]:
        metric = await pmdf_tool_client.get_entity(kind="metric", entity_id=metric_id)
        current_value = metric.get("current_value")
        threshold_value = metric.get("threshold_value")
        breached = (
            current_value is not None
            and threshold_value is not None
            and is_threshold_breached(current_value=current_value, threshold_value=threshold_value)
        )
        return {**state, "metric": metric, "breached": breached}

    initial_state: dict[str, Any] = {}
    state = await run_node_with_guard(
        _fetch_and_check, initial_state, api_server_url=api_server_url, auth_token=auth_token
    )

    if not state["breached"]:
        return {"breached": False, "metric": state["metric"], "report": None}

    async def _hypothesize(inner_state: dict[str, Any]) -> dict[str, Any]:
        completion = await llm_client.complete(
            model="pdm-main",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたはPdMアシスタントです。KPI閾値超過の原因仮説を"
                        '{"hypothesis": "..."}形式のJSONで出力してください。'
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"メトリクス: {inner_state['metric'].get('name')}, "
                        f"現在値: {inner_state['metric'].get('current_value')}, "
                        f"閾値: {inner_state['metric'].get('threshold_value')}"
                    ),
                },
            ],
        )
        hypothesis = _extract_json(completion.content)["hypothesis"]
        return {**inner_state, "hypothesis": hypothesis}

    state = await run_node_with_guard(
        _hypothesize, state, api_server_url=api_server_url, auth_token=auth_token
    )

    report_payload = {
        "pmdf_version": "1.0.0",
        "kind": "report",
        "id": generate_id("report"),
        "provenance": {"created_by": "agent:kpi-agent@v1", "updated_at": _NOW},
        "attachments": [],
        "product": product_id,
        "period": "kpi-alert",
        "health_assessment": "red",
        "decisions_needed": [],
        "summary": state["hypothesis"],
    }
    # E5-8(FR-PD-13): PMDF参照(対象metric)+データ根拠(実測値・閾値)を明示する。
    report_payload = attach_evidence(
        report_payload,
        [
            {"source": "pmdf", "kind": "metric", "id": metric_id},
            data_evidence(
                description="KPI閾値超過の実測値",
                data={
                    "current_value": state["metric"].get("current_value"),
                    "threshold_value": state["metric"].get("threshold_value"),
                },
            ),
        ],
    )
    created_report = await pmdf_tool_client.create_entity(kind="report", data=report_payload)
    return {"breached": True, "metric": state["metric"], "report": created_report}


async def record_decision(
    *,
    product_id: str,
    context: str,
    approver: str,
    pmdf_tool_client: PmdfToolClient,
    llm_client: LogicalModelClient,
    api_server_url: str,
    auth_token: str,
) -> dict[str, Any]:
    """重要判断が発生した際、必須項目(背景/選択肢/根拠/却下案)を全て埋めたdecisionを自動記録する。

    必須項目のいずれかが欠落した場合はE2-3のPydanticバリデーション
    (api-server側のスキーマ検証)により422で拒否される。
    """

    async def _draft(state: dict[str, Any]) -> dict[str, Any]:
        completion = await llm_client.complete(
            model="pdm-main",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたはPdMアシスタントです。意思決定記録(Decision Record)を"
                        '{"background": "...", "options": [{"name": "...", '
                        '"pros": [...], "cons": [...]}], "chosen_option": "...", '
                        '"rationale": "...", "rejected_reasons": '
                        '[{"option": "...", "reason": "..."}]}'
                        "形式のJSONで出力してください。背景・選択肢・採用案・根拠・"
                        "却下理由は全て必須です。"
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

    decision_payload = {
        "pmdf_version": "1.0.0",
        "kind": "decision",
        "id": generate_id("decision"),
        "provenance": {"created_by": "agent:kpi-agent@v1", "updated_at": _NOW},
        "attachments": [],
        "product": product_id,
        "background": draft["background"],
        "options": draft["options"],
        "chosen_option": draft["chosen_option"],
        "rationale": draft["rationale"],
        "rejected_reasons": draft["rejected_reasons"],
        "approver": approver,
        "autonomy_level": AUTONOMY_LEVEL,
    }
    # E5-8(FR-PD-13): 意思決定の根拠(データ: 背景・根拠テキスト)を明示する。
    decision_payload = attach_evidence(
        decision_payload,
        [
            data_evidence(
                description="意思決定記録の根拠",
                data={"background": draft["background"], "rationale": draft["rationale"]},
            )
        ],
    )
    created: dict[str, Any] = await pmdf_tool_client.create_entity(
        kind="decision", data=decision_payload
    )
    return created


async def weekly_review(
    *,
    product_id: str,
    period: str,
    proposer: str,
    pmdf_tool_client: PmdfToolClient,
    llm_client: LogicalModelClient,
    api_server_url: str,
    auth_token: str,
) -> dict[str, Any]:
    """週次でプロダクト健全性を評価しreportを生成する。要判断事項を検出した場合はapproval起案する。"""

    async def _assess(state: dict[str, Any]) -> dict[str, Any]:
        completion = await llm_client.complete(
            model="pdm-main",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "あなたはPdMアシスタントです。週次のプロダクト健全性評価を"
                        '{"health_assessment": "green"|"yellow"|"red", '
                        '"summary": "...", "decisions_needed": ["..."]}'
                        "形式のJSONで出力してください。"
                    ),
                },
                {"role": "user", "content": f"対象期間: {period}"},
            ],
        )
        return {**state, "assessment": _extract_json(completion.content)}

    initial_state: dict[str, Any] = {}
    state = await run_node_with_guard(
        _assess, initial_state, api_server_url=api_server_url, auth_token=auth_token
    )
    assessment = state["assessment"]

    report_payload = {
        "pmdf_version": "1.0.0",
        "kind": "report",
        "id": generate_id("report"),
        "provenance": {"created_by": "agent:kpi-agent@v1", "updated_at": _NOW},
        "attachments": [],
        "product": product_id,
        "period": period,
        "health_assessment": assessment["health_assessment"],
        "decisions_needed": assessment["decisions_needed"],
        "summary": assessment["summary"],
    }
    # E5-8(FR-PD-13): 週次評価の根拠(データ: 対象期間・評価サマリ)を明示する。
    report_payload = attach_evidence(
        report_payload,
        [data_evidence(description="週次評価の根拠", data={"period": period})],
    )
    created_report = await pmdf_tool_client.create_entity(kind="report", data=report_payload)

    approval_proposal: dict[str, Any] | None = None
    if created_report["decisions_needed"]:
        response = await pmdf_tool_client.request(
            "POST",
            "/approvals",
            json={"target": created_report["id"], "proposer": proposer},
        )
        approval_proposal = response.json()

    return {"report": created_report, "approval_proposal": approval_proposal}


__all__ = [
    "AUTONOMY_LEVEL",
    "is_threshold_breached",
    "monitor_kpi",
    "record_decision",
    "weekly_review",
]
