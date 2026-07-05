"""業務グラフ(2) ビジョン・ロードマップ・リリース判断(E5-5)のテスト。

L1(起案→人間承認→実行)。AC-06(未承認では実行されない)の統合テストを
実サーバ(ASGITransport)で検証する。
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from agent_core.graphs.vision_roadmap_release import (
    ApprovalNotGrantedError,
    call_l1_gated_endpoint,
    execute_after_approval,
    propose_release_decision,
    propose_roadmap_update,
    propose_vision_update,
)
from agent_core.llm_client import LogicalModelClient
from agent_core.tools.pmdf_tools import PmdfToolClient
from httpx import ASGITransport, AsyncClient

MODEL_GATEWAY_URL = "http://model-gateway.test:4000"
PRODUCT_ID = "prod-01HAGENTAAAAAAAAAAAAAAAAAA"
OBJECTIVE_ID = "obj-01HAGENTBBBBBBBBBBBBBBBBBB"
ROADMAP_ID = "roadmap-01HAGENTCCCCCCCCCCCCCCCCCC"
RELEASE_ID = "release-01HAGENTDDDDDDDDDDDDDDDDDD"
PROPOSER_ID = "stakeholder-01HAGENTEEEEEEEEEEEEEEEEEE"
APPROVER_ID = "stakeholder-01HAGENTFFFFFFFFFFFFFFFFFF"


def _chat_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-1",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
        },
    )


@pytest.fixture
def user_store_path(tmp_path: Path) -> Path:
    from api_server.auth.password import hash_password

    path = tmp_path / "users.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "agent-service-account",
                    "email": "agent@example.com",
                    "password_hash": hash_password("agent-pass"),
                    "role": "editor",
                    "totp_secret": None,
                    "product_scopes": None,
                }
            ]
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, user_store_path: Path):
    monkeypatch.setenv("JWT_SECRET", "test-secret-vrr")
    monkeypatch.setenv("PMDF_STORE_PATH", str(tmp_path / "pmdf-repo"))
    monkeypatch.setenv("USER_STORE_PATH", str(user_store_path))
    monkeypatch.setenv("PROPOSAL_STORE_PATH", str(tmp_path / "proposals.json"))
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "audit.log.jsonl"))
    monkeypatch.setenv("EMERGENCY_STOP_PATH", str(tmp_path / "emergency_stop.json"))

    from api_server.pmdf_store.store import PmdfStore

    PmdfStore.init(tmp_path / "pmdf-repo")

    from api_server.main import create_app

    return create_app()


@pytest.fixture
async def auth_token(app) -> str:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/auth/login", json={"email": "agent@example.com", "password": "agent-pass"}
        )
        assert response.status_code == 200, response.text
        return str(response.json()["access_token"])


@pytest.fixture
def pmdf_tool_client(app, auth_token: str) -> PmdfToolClient:
    transport = ASGITransport(app=app)
    return PmdfToolClient(
        api_server_url="http://test",
        auth_token=auth_token,
        agent_name="roadmap-agent",
        agent_version="1",
        transport=transport,
    )


async def _http_client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def _seed_product(client: AsyncClient, headers: dict[str, str]) -> None:
    response = await client.post(
        "/pmdf/product",
        json={
            "pmdf_version": "1.0.0",
            "kind": "product",
            "id": PRODUCT_ID,
            "provenance": {"created_by": "user:tester", "updated_at": "2026-01-01T00:00:00Z"},
            "attachments": [],
            "name": "テストプロダクト",
            "vision": "初期ビジョン",
            "lifecycle_stage": "growth",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text


async def _seed_roadmap(client: AsyncClient, headers: dict[str, str]) -> None:
    await _seed_product(client, headers)
    await client.post(
        "/pmdf/objective",
        json={
            "pmdf_version": "1.0.0",
            "kind": "objective",
            "id": OBJECTIVE_ID,
            "provenance": {"created_by": "user:tester", "updated_at": "2026-01-01T00:00:00Z"},
            "attachments": [],
            "objective": "テスト目標",
            "key_results": [{"description": "KR1", "target_value": 100.0}],
            "period": "2026-Q1",
        },
        headers=headers,
    )
    response = await client.post(
        "/pmdf/roadmap_item",
        json={
            "pmdf_version": "1.0.0",
            "kind": "roadmap_item",
            "id": ROADMAP_ID,
            "provenance": {"created_by": "user:tester", "updated_at": "2026-01-01T00:00:00Z"},
            "attachments": [],
            "product": PRODUCT_ID,
            "theme": "初期テーマ",
            "period": "2026-Q1",
            "status": "planned",
            "dependencies": [],
            "objective": OBJECTIVE_ID,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text


async def _seed_release(client: AsyncClient, headers: dict[str, str]) -> None:
    response = await client.post(
        "/pmdf/release",
        json={
            "pmdf_version": "1.0.0",
            "kind": "release",
            "id": RELEASE_ID,
            "provenance": {"created_by": "user:tester", "updated_at": "2026-01-01T00:00:00Z"},
            "attachments": [],
            "product": PRODUCT_ID,
            "name": "テストリリース",
            "scope": [],
            "go_no_go": "pending",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text


async def _approve(client: AsyncClient, headers: dict[str, str], *, target: str) -> None:
    propose_response = await client.post(
        "/approvals", json={"target": target, "proposer": PROPOSER_ID}, headers=headers
    )
    assert propose_response.status_code == 201, propose_response.text
    proposal_id = propose_response.json()["id"]
    decide_response = await client.post(
        f"/approvals/{proposal_id}/decide",
        json={"decision": "approved", "approver": APPROVER_ID, "reason": "検証のため"},
        headers=headers,
    )
    assert decide_response.status_code == 200, decide_response.text


def _headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.mark.asyncio
async def test_propose_vision_update_does_not_modify_product_and_creates_approval_proposal(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    async with await _http_client(app) as client:
        await _seed_product(client, _headers(auth_token))

    llm_response = json.dumps({"vision": "更新後ビジョン"}, ensure_ascii=False)
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        with respx.mock(base_url="http://test") as autonomy_mock:
            autonomy_mock.get("/autonomy/emergency-stop/status").mock(
                return_value=httpx.Response(200, json={"emergency_stopped": False})
            )
            proposal = await propose_vision_update(
                product_id=PRODUCT_ID,
                context="来期に向けたビジョン見直し",
                pmdf_tool_client=pmdf_tool_client,
                llm_client=llm_client,
                api_server_url="http://test",
                auth_token=auth_token,
                proposer=PROPOSER_ID,
            )

    assert proposal["target"] == PRODUCT_ID
    assert proposal["status"] == "proposed"

    unchanged_product = await pmdf_tool_client.get_entity(kind="product", entity_id=PRODUCT_ID)
    assert unchanged_product["vision"] == "初期ビジョン"


@pytest.mark.asyncio
async def test_propose_vision_update_attaches_evidence_to_draft(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    """E5-8(FR-PD-13): 起案内容(draft)に`x_evidence`(根拠)が最低1件含まれること。"""
    async with await _http_client(app) as client:
        await _seed_product(client, _headers(auth_token))

    llm_response = json.dumps({"vision": "更新後ビジョン"}, ensure_ascii=False)
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        with respx.mock(base_url="http://test") as autonomy_mock:
            autonomy_mock.get("/autonomy/emergency-stop/status").mock(
                return_value=httpx.Response(200, json={"emergency_stopped": False})
            )
            proposal = await propose_vision_update(
                product_id=PRODUCT_ID,
                context="来期に向けたビジョン見直し",
                pmdf_tool_client=pmdf_tool_client,
                llm_client=llm_client,
                api_server_url="http://test",
                auth_token=auth_token,
                proposer=PROPOSER_ID,
            )

    assert proposal["draft"]["x_evidence"]


@pytest.mark.asyncio
async def test_execute_after_approval_blocked_when_not_approved(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    """AC-06: 未承認でexecute_after_approvalを呼ぶと、api-serverが403を返しグラフが中断される。"""
    async with await _http_client(app) as client:
        await _seed_roadmap(client, _headers(auth_token))

    with pytest.raises(ApprovalNotGrantedError):
        await execute_after_approval(
            entity_kind="roadmap_item",
            entity_id=ROADMAP_ID,
            confirm_path=f"/roadmap/{ROADMAP_ID}/confirm",
            pmdf_tool_client=pmdf_tool_client,
            api_server_url="http://test",
            auth_token=auth_token,
        )


@pytest.mark.asyncio
async def test_call_l1_gated_endpoint_receives_403_from_real_api_server_when_not_approved(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    """AC-06統合テスト: agent-core側の事前チェックを経由せず、api-server自体が
    承認ゲート(`require_approval`)により403を返し、グラフが中断されることを確認する。
    """
    async with await _http_client(app) as client:
        await _seed_roadmap(client, _headers(auth_token))

    with respx.mock(base_url="http://test") as autonomy_mock:
        autonomy_mock.get("/autonomy/emergency-stop/status").mock(
            return_value=httpx.Response(200, json={"emergency_stopped": False})
        )
        with pytest.raises(ApprovalNotGrantedError):
            await call_l1_gated_endpoint(
                entity_kind="roadmap_item",
                entity_id=ROADMAP_ID,
                confirm_path=f"/roadmap/{ROADMAP_ID}/confirm",
                pmdf_tool_client=pmdf_tool_client,
                api_server_url="http://test",
                auth_token=auth_token,
            )


@pytest.mark.asyncio
async def test_execute_after_approval_succeeds_when_approved(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    async with await _http_client(app) as client:
        await _seed_roadmap(client, _headers(auth_token))
        await _approve(client, _headers(auth_token), target=ROADMAP_ID)

    with respx.mock(base_url="http://test") as autonomy_mock:
        autonomy_mock.get("/autonomy/emergency-stop/status").mock(
            return_value=httpx.Response(200, json={"emergency_stopped": False})
        )
        result = await execute_after_approval(
            entity_kind="roadmap_item",
            entity_id=ROADMAP_ID,
            confirm_path=f"/roadmap/{ROADMAP_ID}/confirm",
            pmdf_tool_client=pmdf_tool_client,
            api_server_url="http://test",
            auth_token=auth_token,
        )

    assert result["confirmed"] is True


@pytest.mark.asyncio
async def test_propose_roadmap_update_creates_proposal_without_modifying_roadmap_item(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    async with await _http_client(app) as client:
        await _seed_roadmap(client, _headers(auth_token))

    llm_response = json.dumps({"theme": "更新後テーマ"}, ensure_ascii=False)
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        with respx.mock(base_url="http://test") as autonomy_mock:
            autonomy_mock.get("/autonomy/emergency-stop/status").mock(
                return_value=httpx.Response(200, json={"emergency_stopped": False})
            )
            proposal = await propose_roadmap_update(
                roadmap_item_id=ROADMAP_ID,
                context="優先度見直し",
                pmdf_tool_client=pmdf_tool_client,
                llm_client=llm_client,
                api_server_url="http://test",
                auth_token=auth_token,
                proposer=PROPOSER_ID,
            )

    assert proposal["target"] == ROADMAP_ID
    unchanged = await pmdf_tool_client.get_entity(kind="roadmap_item", entity_id=ROADMAP_ID)
    assert unchanged["theme"] == "初期テーマ"


@pytest.mark.asyncio
async def test_propose_release_decision_creates_proposal_without_modifying_release(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    async with await _http_client(app) as client:
        await _seed_product(client, _headers(auth_token))
        await _seed_release(client, _headers(auth_token))

    llm_response = json.dumps(
        {"recommendation": "go", "rationale": "品質基準を満たしている"}, ensure_ascii=False
    )
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        with respx.mock(base_url="http://test") as autonomy_mock:
            autonomy_mock.get("/autonomy/emergency-stop/status").mock(
                return_value=httpx.Response(200, json={"emergency_stopped": False})
            )
            proposal = await propose_release_decision(
                release_id=RELEASE_ID,
                context="リリース可否検討",
                pmdf_tool_client=pmdf_tool_client,
                llm_client=llm_client,
                api_server_url="http://test",
                auth_token=auth_token,
                proposer=PROPOSER_ID,
            )

    assert proposal["target"] == RELEASE_ID
    unchanged = await pmdf_tool_client.get_entity(kind="release", entity_id=RELEASE_ID)
    assert unchanged["go_no_go"] == "pending"


@pytest.mark.asyncio
async def test_execute_after_approval_for_release_go_no_go(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    async with await _http_client(app) as client:
        await _seed_product(client, _headers(auth_token))
        await _seed_release(client, _headers(auth_token))
        await _approve(client, _headers(auth_token), target=RELEASE_ID)

    with respx.mock(base_url="http://test") as autonomy_mock:
        autonomy_mock.get("/autonomy/emergency-stop/status").mock(
            return_value=httpx.Response(200, json={"emergency_stopped": False})
        )
        result = await execute_after_approval(
            entity_kind="release",
            entity_id=RELEASE_ID,
            confirm_path=f"/release/{RELEASE_ID}/go-no-go",
            pmdf_tool_client=pmdf_tool_client,
            api_server_url="http://test",
            auth_token=auth_token,
        )

    assert result["go"] is True
