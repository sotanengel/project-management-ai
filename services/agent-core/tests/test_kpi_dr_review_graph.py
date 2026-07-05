"""業務グラフ(3) KPI監視・Decision Record・週次レビュー(E5-6)のテスト。

L3(完全自律、監査ログのみ)。承認ゲートを経由せず直接persistまで
完了することを確認する(L1グラフとの対比)。
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from agent_core.graphs.kpi_dr_review import monitor_kpi, record_decision, weekly_review
from agent_core.llm_client import LogicalModelClient
from agent_core.tools.pmdf_tools import PmdfToolClient
from httpx import ASGITransport, AsyncClient

MODEL_GATEWAY_URL = "http://model-gateway.test:4000"
PRODUCT_ID = "prod-01HAGENTAAAAAAAAAAAAAAAAAA"
METRIC_ID = "metric-01HAGENTBBBBBBBBBBBBBBBBBB"
STAKEHOLDER_ID = "stakeholder-01HAGENTCCCCCCCCCCCCCCCCCC"
PROPOSER_ID = "stakeholder-01HAGENTDDDDDDDDDDDDDDDDDD"


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
    monkeypatch.setenv("JWT_SECRET", "test-secret-kpi")
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
        agent_name="kpi-agent",
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


async def _seed_metric(
    client: AsyncClient, headers: dict[str, str], *, current_value: float, threshold_value: float
) -> None:
    response = await client.post(
        "/pmdf/metric",
        json={
            "pmdf_version": "1.0.0",
            "kind": "metric",
            "id": METRIC_ID,
            "provenance": {"created_by": "user:tester", "updated_at": "2026-01-01T00:00:00Z"},
            "attachments": [],
            "name": "解約率",
            "definition": "月次解約率",
            "calculation_method": "解約数/総顧客数",
            "target_value": 0.02,
            "threshold_value": threshold_value,
            "current_value": current_value,
            "time_series": [],
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
            "name": "承認者",
            "role": "承認者役",
            "influence": "high",
            "interests": [],
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text


@pytest.mark.asyncio
async def test_monitor_kpi_detects_threshold_breach_and_generates_hypothesis(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    async with await _http_client(app) as client:
        await _seed_product(client, _headers(auth_token))
        await _seed_metric(client, _headers(auth_token), current_value=0.08, threshold_value=0.05)

    llm_response = json.dumps(
        {"hypothesis": "オンボーディング体験の悪化が解約率上昇の原因と考えられる"},
        ensure_ascii=False,
    )
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        with respx.mock(base_url="http://test") as autonomy_mock:
            autonomy_mock.get("/autonomy/emergency-stop/status").mock(
                return_value=httpx.Response(200, json={"emergency_stopped": False})
            )
            result = await monitor_kpi(
                metric_id=METRIC_ID,
                product_id=PRODUCT_ID,
                pmdf_tool_client=pmdf_tool_client,
                llm_client=llm_client,
                api_server_url="http://test",
                auth_token=auth_token,
            )

    assert result["breached"] is True
    assert "オンボーディング" in result["report"]["summary"]
    assert result["report"]["health_assessment"] == "red"
    # E5-8(FR-PD-13): 対象metricへのPMDF参照+データ根拠が明示される。
    assert result["report"]["x_evidence"]
    assert any(
        e.get("source") == "pmdf" and e.get("id") == METRIC_ID
        for e in result["report"]["x_evidence"]
    )


@pytest.mark.asyncio
async def test_monitor_kpi_no_breach_when_within_threshold(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    async with await _http_client(app) as client:
        await _seed_product(client, _headers(auth_token))
        await _seed_metric(client, _headers(auth_token), current_value=0.01, threshold_value=0.05)

    llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)
    with respx.mock(base_url="http://test") as autonomy_mock:
        autonomy_mock.get("/autonomy/emergency-stop/status").mock(
            return_value=httpx.Response(200, json={"emergency_stopped": False})
        )
        result = await monitor_kpi(
            metric_id=METRIC_ID,
            product_id=PRODUCT_ID,
            pmdf_tool_client=pmdf_tool_client,
            llm_client=llm_client,
            api_server_url="http://test",
            auth_token=auth_token,
        )

    assert result["breached"] is False


@pytest.mark.asyncio
async def test_record_decision_creates_entity_with_all_required_fields(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    async with await _http_client(app) as client:
        await _seed_product(client, _headers(auth_token))
        await _seed_stakeholder(client, _headers(auth_token))

    llm_response = json.dumps(
        {
            "background": "レイテンシ悪化が続いている",
            "options": [
                {"name": "案A: キャッシュ導入", "pros": ["速い"], "cons": ["複雑"]},
                {"name": "案B: 何もしない", "pros": [], "cons": ["改善しない"]},
            ],
            "chosen_option": "案A: キャッシュ導入",
            "rationale": "コストパフォーマンスが最も良いため",
            "rejected_reasons": [{"option": "案B: 何もしない", "reason": "問題が解決しない"}],
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
            decision = await record_decision(
                product_id=PRODUCT_ID,
                context="レイテンシ問題への対応方針",
                approver=STAKEHOLDER_ID,
                pmdf_tool_client=pmdf_tool_client,
                llm_client=llm_client,
                api_server_url="http://test",
                auth_token=auth_token,
            )

    from pmdf.models import Decision

    Decision.model_validate(decision)
    assert decision["background"]
    assert decision["options"]
    assert decision["chosen_option"]
    assert decision["rationale"]
    assert decision["rejected_reasons"]
    assert decision["autonomy_level"] == "L3"
    assert decision["x_evidence"]


@pytest.mark.asyncio
async def test_record_decision_completes_without_approval_gate_as_l3(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    async with await _http_client(app) as client:
        await _seed_product(client, _headers(auth_token))
        await _seed_stakeholder(client, _headers(auth_token))

    llm_response = json.dumps(
        {
            "background": "背景",
            "options": [{"name": "A"}, {"name": "B"}],
            "chosen_option": "A",
            "rationale": "根拠",
            "rejected_reasons": [{"option": "B", "reason": "劣る"}],
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
            await record_decision(
                product_id=PRODUCT_ID,
                context="判断",
                approver=STAKEHOLDER_ID,
                pmdf_tool_client=pmdf_tool_client,
                llm_client=llm_client,
                api_server_url="http://test",
                auth_token=auth_token,
            )

    async with await _http_client(app) as client:
        response = await client.get("/approvals", headers=_headers(auth_token))
        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.asyncio
async def test_weekly_review_flags_decisions_needed_and_creates_approval_proposal(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    async with await _http_client(app) as client:
        await _seed_product(client, _headers(auth_token))

    llm_response = json.dumps(
        {
            "health_assessment": "yellow",
            "summary": "解約率が上昇傾向にあり要注意",
            "decisions_needed": ["価格戦略の見直しが必要"],
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
            result = await weekly_review(
                product_id=PRODUCT_ID,
                period="2026-W27",
                proposer=PROPOSER_ID,
                pmdf_tool_client=pmdf_tool_client,
                llm_client=llm_client,
                api_server_url="http://test",
                auth_token=auth_token,
            )

    assert result["report"]["decisions_needed"] == ["価格戦略の見直しが必要"]
    assert result["approval_proposal"] is not None
    assert result["approval_proposal"]["target"] == result["report"]["id"]
    assert result["report"]["x_evidence"]

    async with await _http_client(app) as client:
        response = await client.get("/approvals?status=pending", headers=_headers(auth_token))
        assert response.status_code == 200
        pending = response.json()
        assert any(p["target"] == result["report"]["id"] for p in pending)


@pytest.mark.asyncio
async def test_weekly_review_no_proposal_when_no_decisions_needed(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    async with await _http_client(app) as client:
        await _seed_product(client, _headers(auth_token))

    llm_response = json.dumps(
        {"health_assessment": "green", "summary": "順調", "decisions_needed": []},
        ensure_ascii=False,
    )
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        with respx.mock(base_url="http://test") as autonomy_mock:
            autonomy_mock.get("/autonomy/emergency-stop/status").mock(
                return_value=httpx.Response(200, json={"emergency_stopped": False})
            )
            result = await weekly_review(
                product_id=PRODUCT_ID,
                period="2026-W27",
                proposer=PROPOSER_ID,
                pmdf_tool_client=pmdf_tool_client,
                llm_client=llm_client,
                api_server_url="http://test",
                auth_token=auth_token,
            )

    assert result["approval_proposal"] is None
