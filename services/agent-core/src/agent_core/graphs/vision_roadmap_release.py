"""業務グラフ(2) ビジョン・ロードマップ・リリース判断(E5-5)。

FR-PD-01(ビジョン管理)/FR-PD-02(ロードマップ)/FR-PD-07(リリース判断)。
いずれも既定自律レベルL1(起案→人間承認→実行)。承認ゲート(E3-6)を
経由しない限り実行が完了しないことを担保する。

- `propose_*`: 変更案をLLM(`pdm-main`)で生成し、`POST /approvals`で
  起案のみ行う。**この時点ではPMDFエンティティ自体は一切更新しない**。
- `execute_after_approval`: api-serverのL1ゲート済みエンドポイント
  (`/roadmap/{id}/confirm`, `/release/{id}/go-no-go`等)を呼び出す。
  承認が無い場合はapi-server側が403を返し、
  `ApprovalNotGrantedError`として送出する(agent-core側でも
  `PmdfToolClient.search_entities(kind="approval")`で事前チェックし、
  api-serverへの到達前に二重に検出する)。
"""

from __future__ import annotations

import json
from typing import Any

from agent_core.guards import run_node_with_guard
from agent_core.llm_client import LogicalModelClient
from agent_core.tools.pmdf_tools import PmdfToolClient

#: ビジョン・ロードマップ・リリース判断グラフの既定自律レベル(L1: 起案→承認→実行)。
AUTONOMY_LEVEL = "L1"


class ApprovalNotGrantedError(RuntimeError):
    """対象エンティティへの承認済みapprovalレコードが存在しない場合に送出される例外。"""

    def __init__(self, entity_kind: str, entity_id: str) -> None:
        super().__init__(
            f"承認レコードがありません({entity_kind}:{entity_id})。"
            "L1業務の実行には承認済みapprovalレコードが必須です(AC-06)。"
        )


def _extract_json(content: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(content)
    return data


async def _has_approved_record(pmdf_tool_client: PmdfToolClient, target_id: str) -> bool:
    """agent-core側での事前二重チェック(api-serverの`require_approval`と同等の判定)。"""
    approvals = await pmdf_tool_client.search_entities(kind="approval")
    return any(a.get("target") == target_id and a.get("decision") == "approved" for a in approvals)


async def _propose(
    *,
    target_id: str,
    llm_client: LogicalModelClient,
    system_prompt: str,
    user_content: str,
    api_server_url: str,
    auth_token: str,
    pmdf_tool_client: PmdfToolClient,
    proposer: str,
) -> dict[str, Any]:
    async def _draft(state: dict[str, Any]) -> dict[str, Any]:
        completion = await llm_client.complete(
            model="pdm-main",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        return {**state, "draft": _extract_json(completion.content)}

    initial_state: dict[str, Any] = {}
    state = await run_node_with_guard(
        _draft, initial_state, api_server_url=api_server_url, auth_token=auth_token
    )

    response = await pmdf_tool_client.request(
        "POST", "/approvals", json={"target": target_id, "proposer": proposer}
    )
    proposal: dict[str, Any] = response.json()

    proposal["draft"] = state["draft"]
    return proposal


async def propose_vision_update(
    *,
    product_id: str,
    context: str,
    pmdf_tool_client: PmdfToolClient,
    llm_client: LogicalModelClient,
    api_server_url: str,
    auth_token: str,
    proposer: str,
) -> dict[str, Any]:
    """product.visionの変更案を生成し、approval起案のみ行う(product自体は更新しない)。"""
    return await _propose(
        target_id=product_id,
        llm_client=llm_client,
        system_prompt=(
            "あなたはPdMアシスタントです。プロダクトビジョンの改訂案を"
            '{"vision": "..."}形式のJSONで出力してください。'
        ),
        user_content=context,
        api_server_url=api_server_url,
        auth_token=auth_token,
        pmdf_tool_client=pmdf_tool_client,
        proposer=proposer,
    )


async def propose_roadmap_update(
    *,
    roadmap_item_id: str,
    context: str,
    pmdf_tool_client: PmdfToolClient,
    llm_client: LogicalModelClient,
    api_server_url: str,
    auth_token: str,
    proposer: str,
) -> dict[str, Any]:
    """roadmap_itemのトレードオフ提示+変更案生成、approval起案のみ行う。"""
    return await _propose(
        target_id=roadmap_item_id,
        llm_client=llm_client,
        system_prompt=(
            "あなたはPdMアシスタントです。ロードマップ項目の変更案を"
            '{"theme": "..."}形式のJSONで出力してください。'
        ),
        user_content=context,
        api_server_url=api_server_url,
        auth_token=auth_token,
        pmdf_tool_client=pmdf_tool_client,
        proposer=proposer,
    )


async def propose_release_decision(
    *,
    release_id: str,
    context: str,
    pmdf_tool_client: PmdfToolClient,
    llm_client: LogicalModelClient,
    api_server_url: str,
    auth_token: str,
    proposer: str,
) -> dict[str, Any]:
    """release.go_no_goの推奨(Go/No-Go)材料整理、approval起案のみ行う。"""
    return await _propose(
        target_id=release_id,
        llm_client=llm_client,
        system_prompt=(
            "あなたはPdMアシスタントです。リリースのGo/No-Go推奨を"
            '{"recommendation": "go"|"no_go", "rationale": "..."}'
            "形式のJSONで出力してください。"
        ),
        user_content=context,
        api_server_url=api_server_url,
        auth_token=auth_token,
        pmdf_tool_client=pmdf_tool_client,
        proposer=proposer,
    )


async def call_l1_gated_endpoint(
    *,
    entity_kind: str,
    entity_id: str,
    confirm_path: str,
    pmdf_tool_client: PmdfToolClient,
    api_server_url: str,
    auth_token: str,
) -> dict[str, Any]:
    """api-serverのL1ゲート済みエンドポイント(confirm/go-no-go等)を呼び出す。

    api-server側の`require_approval`依存関数が最終防衛線であり、承認済み
    レコードが無い場合はここで403を受け取り`ApprovalNotGrantedError`と
    して送出する(AC-06)。
    """

    async def _confirm(state: dict[str, Any]) -> dict[str, Any]:
        response = await pmdf_tool_client.request("POST", confirm_path, raise_for_status=False)
        if response.status_code == 403:
            raise ApprovalNotGrantedError(entity_kind, entity_id)
        response.raise_for_status()
        return {**state, "result": response.json()}

    initial_state: dict[str, Any] = {}
    result_state = await run_node_with_guard(
        _confirm, initial_state, api_server_url=api_server_url, auth_token=auth_token
    )
    result: dict[str, Any] = result_state["result"]
    return result


async def execute_after_approval(
    *,
    entity_kind: str,
    entity_id: str,
    confirm_path: str,
    pmdf_tool_client: PmdfToolClient,
    api_server_url: str,
    auth_token: str,
) -> dict[str, Any]:
    """承認済みと分かった場合のみ、api-serverのL1ゲート済みエンドポイントを実行する。

    agent-core側でも`_has_approved_record`により事前チェックする
    (api-server側の`require_approval`依存関数が最終防衛線だが、
    二重チェックとしてここでも承認レコードの有無を確認する)。
    """
    if not await _has_approved_record(pmdf_tool_client, entity_id):
        raise ApprovalNotGrantedError(entity_kind, entity_id)

    return await call_l1_gated_endpoint(
        entity_kind=entity_kind,
        entity_id=entity_id,
        confirm_path=confirm_path,
        pmdf_tool_client=pmdf_tool_client,
        api_server_url=api_server_url,
        auth_token=auth_token,
    )


__all__ = [
    "AUTONOMY_LEVEL",
    "ApprovalNotGrantedError",
    "call_l1_gated_endpoint",
    "execute_after_approval",
    "propose_release_decision",
    "propose_roadmap_update",
    "propose_vision_update",
]
