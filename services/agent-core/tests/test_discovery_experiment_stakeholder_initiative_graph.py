"""業務グラフ(4) ディスカバリー・実験・SH調整・施策実行(E5-7)のテスト。

run_discovery/run_experiment(L2)、stakeholder_communication
(draft=L2/send=L1混在)、run_initiative(L2、WBS・リスク登録簿・EVM値は
コード側計算)を検証する。
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from agent_core.graphs.discovery_experiment_stakeholder_initiative import (
    calc_evm,
    draft_message,
    run_discovery,
    run_experiment,
    run_initiative,
    send_message,
)
from agent_core.graphs.vision_roadmap_release import ApprovalNotGrantedError
from agent_core.llm_client import LogicalModelClient
from agent_core.tools.pmdf_tools import PmdfToolClient
from httpx import ASGITransport, AsyncClient

MODEL_GATEWAY_URL = "http://model-gateway.test:4000"
PRODUCT_ID = "prod-01HAGENTAAAAAAAAAAAAAAAAAA"
STAKEHOLDER_ID = "stakeholder-01HAGENTBBBBBBBBBBBBBBBBBB"
PROPOSER_ID = "stakeholder-01HAGENTCCCCCCCCCCCCCCCCCC"
APPROVER_ID = "stakeholder-01HAGENTDDDDDDDDDDDDDDDDDD"


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
    monkeypatch.setenv("JWT_SECRET", "test-secret-discovery")
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
        agent_name="discovery-agent",
        agent_version="1",
        transport=transport,
    )


async def _http_client(app) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}"}


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
            "vision": "ビジョン",
            "lifecycle_stage": "growth",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text


async def _seed_stakeholder(client: AsyncClient, headers: dict[str, str]) -> None:
    response = await client.post(
        "/pmdf/stakeholder",
        json={
            "pmdf_version": "1.0.0",
            "kind": "stakeholder",
            "id": STAKEHOLDER_ID,
            "provenance": {"created_by": "user:tester", "updated_at": "2026-01-01T00:00:00Z"},
            "attachments": [],
            "name": "経営層",
            "role": "スポンサー",
            "influence": "high",
            "interests": [],
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


@pytest.mark.asyncio
async def test_run_discovery_creates_persona_conforming_to_schema(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    llm_response = json.dumps(
        {
            "name": "多忙なマネージャー",
            "attributes": {"age": "40代"},
            "pain_points": ["時間が足りない"],
            "jobs": [
                {
                    "situation": "週次レビューの時間が取れない",
                    "motivation": "効率化したい",
                    "outcome": "短時間で判断したい",
                }
            ],
        },
        ensure_ascii=False,
    )
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        with respx.mock(base_url="http://test") as autonomy_mock:
            autonomy_mock.get("/autonomy/emergency-stop/status").mock(
                return_value=httpx.Response(200, json={"emergency_stopped": False})
            )
            persona = await run_discovery(
                context="マネージャー層へのインタビュー結果",
                pmdf_tool_client=pmdf_tool_client,
                llm_client=llm_client,
                api_server_url="http://test",
                auth_token=auth_token,
            )

    from pmdf.models import Persona

    Persona.model_validate(persona)
    assert persona["x_evidence"]


@pytest.mark.asyncio
async def test_run_experiment_records_results_and_learnings(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    async with await _http_client(app) as client:
        await _seed_product(client, _headers(auth_token))

    llm_response = json.dumps(
        {
            "hypothesis": "オンボーディング動画を追加すると定着率が上がる",
            "design": "A/Bテスト、2週間",
            "success_criteria": ["定着率+5pt"],
            "status": "completed",
            "results": "定着率が+7pt改善した",
            "learnings": "動画は効果的だが尺は短い方が良い",
        },
        ensure_ascii=False,
    )
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        with respx.mock(base_url="http://test") as autonomy_mock:
            autonomy_mock.get("/autonomy/emergency-stop/status").mock(
                return_value=httpx.Response(200, json={"emergency_stopped": False})
            )
            experiment = await run_experiment(
                product_id=PRODUCT_ID,
                context="オンボーディング動画の効果検証",
                pmdf_tool_client=pmdf_tool_client,
                llm_client=llm_client,
                api_server_url="http://test",
                auth_token=auth_token,
            )

    from pmdf.models import Experiment

    Experiment.model_validate(experiment)
    assert experiment["results"] == "定着率が+7pt改善した"
    assert experiment["learnings"]
    assert experiment["x_evidence"]
    assert any(
        e.get("source") == "pmdf" and e.get("id") == PRODUCT_ID for e in experiment["x_evidence"]
    )


@pytest.mark.asyncio
async def test_draft_message_completes_without_approval(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    llm_response = json.dumps(
        {"message": "今週のプロダクト状況をご報告します。"}, ensure_ascii=False
    )
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        with respx.mock(base_url="http://test") as autonomy_mock:
            autonomy_mock.get("/autonomy/emergency-stop/status").mock(
                return_value=httpx.Response(200, json={"emergency_stopped": False})
            )
            draft = await draft_message(
                stakeholder_id=STAKEHOLDER_ID,
                context="週次報告",
                llm_client=llm_client,
                api_server_url="http://test",
                auth_token=auth_token,
            )

    assert "ご報告" in draft["message"]


@pytest.mark.asyncio
async def test_send_message_blocked_without_approval(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    """送信(send_message)はL1: 未承認では実行されない。"""
    async with await _http_client(app) as client:
        await _seed_stakeholder(client, _headers(auth_token))

    with respx.mock(base_url="http://test") as autonomy_mock:
        autonomy_mock.get("/autonomy/emergency-stop/status").mock(
            return_value=httpx.Response(200, json={"emergency_stopped": False})
        )
        with pytest.raises(ApprovalNotGrantedError):
            await send_message(
                stakeholder_id=STAKEHOLDER_ID,
                message="今週のプロダクト状況をご報告します。",
                pmdf_tool_client=pmdf_tool_client,
                api_server_url="http://test",
                auth_token=auth_token,
            )


@pytest.mark.asyncio
async def test_send_message_succeeds_when_approved(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    async with await _http_client(app) as client:
        await _seed_stakeholder(client, _headers(auth_token))
        await _approve(client, _headers(auth_token), target=STAKEHOLDER_ID)

    with respx.mock(base_url="http://test") as autonomy_mock:
        autonomy_mock.get("/autonomy/emergency-stop/status").mock(
            return_value=httpx.Response(200, json={"emergency_stopped": False})
        )
        result = await send_message(
            stakeholder_id=STAKEHOLDER_ID,
            message="今週のプロダクト状況をご報告します。",
            pmdf_tool_client=pmdf_tool_client,
            api_server_url="http://test",
            auth_token=auth_token,
        )

    assert result["sent"] is True


def test_calc_evm_computes_spi_and_cpi() -> None:
    evm = calc_evm(planned_value=100.0, earned_value=80.0, actual_cost=90.0)

    assert evm["planned_value"] == 100.0
    assert evm["earned_value"] == 80.0
    assert evm["actual_cost"] == 90.0
    assert evm["spi"] == pytest.approx(80.0 / 100.0)
    assert evm["cpi"] == pytest.approx(80.0 / 90.0)


@pytest.mark.asyncio
async def test_run_initiative_includes_wbs_risk_and_evm_conforming_to_schema(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    async with await _http_client(app) as client:
        await _seed_product(client, _headers(auth_token))
        await _seed_stakeholder(client, _headers(auth_token))

    llm_response = json.dumps(
        {
            "charter": "新機能開発プロジェクト憲章",
            "approach": "hybrid",
            "wbs": [
                {
                    "id": "wbs-1",
                    "name": "要件定義",
                    "children": [{"id": "wbs-1-1", "name": "ヒアリング", "children": []}],
                }
            ],
            "planned_value": 100.0,
            "earned_value": 60.0,
            "actual_cost": 70.0,
            "risks": [
                {
                    "event": "スコープ膨張のリスク",
                    "probability_score": 3,
                    "impact_score": 4,
                    "response_strategy": "mitigate",
                }
            ],
        },
        ensure_ascii=False,
    )
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        with respx.mock(base_url="http://test") as autonomy_mock:
            autonomy_mock.get("/autonomy/emergency-stop/status").mock(
                return_value=httpx.Response(200, json={"emergency_stopped": False})
            )
            result = await run_initiative(
                product_id=PRODUCT_ID,
                context="新機能開発の施策実行",
                risk_owner=STAKEHOLDER_ID,
                pmdf_tool_client=pmdf_tool_client,
                llm_client=llm_client,
                api_server_url="http://test",
                auth_token=auth_token,
            )

    from pmdf.models import Initiative, Risk

    Initiative.model_validate(result["initiative"])
    assert result["initiative"]["wbs"]
    assert result["initiative"]["evm"]["spi"] == pytest.approx(60.0 / 100.0)
    assert result["initiative"]["evm"]["cpi"] == pytest.approx(60.0 / 70.0)

    for risk in result["risks"]:
        Risk.model_validate(risk)
    assert result["risks"]

    # E5-8(FR-PD-13): initiative(EVM計算根拠)・risk(起因initiativeへの参照)双方に
    # x_evidenceが付与されること。
    assert result["initiative"]["x_evidence"]
    for risk in result["risks"]:
        assert risk["x_evidence"]

    # FR-PD-14: initiativeがproduct固有のライフサイクルフィールド(vision等)を持たないことの確認。
    assert "vision" not in result["initiative"]
    assert "lifecycle_stage" not in result["initiative"]
