"""業務グラフ(1) バックログ運用(`agent_core.graphs.backlog`)のテスト(E5-4)。

RICE/WSJFの決定的検算(LLM出力の数値を信用しない)、L2(承認ゲート
非経由)でのPMDF永続化を検証する。
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from agent_core.graphs.backlog import calc_rice_score, calc_wsjf_score, run_backlog_graph
from agent_core.llm_client import LogicalModelClient
from agent_core.tools.pmdf_tools import PmdfToolClient
from httpx import ASGITransport, AsyncClient

MODEL_GATEWAY_URL = "http://model-gateway.test:4000"


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


def test_calc_rice_score_matches_formula() -> None:
    score = calc_rice_score(reach=100, impact=2, confidence=0.8, effort=4)
    assert score == pytest.approx((100 * 2 * 0.8) / 4)


def test_calc_wsjf_score_matches_formula() -> None:
    # WSJF = (business_value + time_criticality + risk_reduction) / job_size
    score = calc_wsjf_score(business_value=5, time_criticality=3, risk_reduction=2, job_size=2)
    assert score == pytest.approx((5 + 3 + 2) / 2)


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
    monkeypatch.setenv("JWT_SECRET", "test-secret-backlog")
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
        agent_name="backlog-agent",
        agent_version="1",
        transport=transport,
    )


@pytest.mark.asyncio
async def test_run_backlog_graph_persists_story_with_code_recalculated_rice_score(
    pmdf_tool_client: PmdfToolClient, app, auth_token: str
) -> None:
    """LLMが誤ったRICEスコアを提示しても、コード側検算値で上書きされてPMDFへ保存されることを確認する。"""
    llm_response_payload = json.dumps(
        {
            "as_a": "利用者",
            "i_want": "検索を高速化したい",
            "so_that": "業務を早く終えたい",
            "acceptance_criteria": ["検索が3秒以内に完了する"],
            "title": "検索高速化",
            "reach": 100,
            "impact": 2,
            "confidence": 0.8,
            "effort": 4,
            "score": 9999.0,  # 誤ったスコア(コード側で上書きされるべき)
        },
        ensure_ascii=False,
    )

    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response_payload))

        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)
        with respx.mock(base_url="http://test") as autonomy_mock:
            autonomy_mock.get("/autonomy/emergency-stop/status").mock(
                return_value=httpx.Response(200, json={"emergency_stopped": False})
            )
            result = await run_backlog_graph(
                intake_text="検索が遅くて困っている",
                pmdf_tool_client=pmdf_tool_client,
                llm_client=llm_client,
                api_server_url="http://test",
                auth_token=auth_token,
            )

    expected_score = (100 * 2 * 0.8) / 4
    assert result["priority"]["score"] == pytest.approx(expected_score)
    assert result["priority"]["score"] != pytest.approx(9999.0)

    created_story = await pmdf_tool_client.get_entity(kind="story", entity_id=result["id"])
    assert created_story["priority"]["score"] == pytest.approx(expected_score)


@pytest.mark.asyncio
async def test_run_backlog_graph_conforms_to_story_schema(
    pmdf_tool_client: PmdfToolClient, app, auth_token: str
) -> None:
    llm_response_payload = json.dumps(
        {
            "as_a": "利用者",
            "i_want": "検索を高速化したい",
            "so_that": "業務を早く終えたい",
            "acceptance_criteria": ["検索が3秒以内に完了する"],
            "title": "検索高速化",
            "reach": 50,
            "impact": 1,
            "confidence": 0.5,
            "effort": 2,
            "score": 0,
        },
        ensure_ascii=False,
    )

    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response_payload))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        with respx.mock(base_url="http://test") as autonomy_mock:
            autonomy_mock.get("/autonomy/emergency-stop/status").mock(
                return_value=httpx.Response(200, json={"emergency_stopped": False})
            )
            result = await run_backlog_graph(
                intake_text="検索が遅い",
                pmdf_tool_client=pmdf_tool_client,
                llm_client=llm_client,
                api_server_url="http://test",
                auth_token=auth_token,
            )

    from pmdf.models import Story

    Story.model_validate(result)


@pytest.mark.asyncio
async def test_run_backlog_graph_attaches_evidence_to_persisted_story(
    pmdf_tool_client: PmdfToolClient, app, auth_token: str
) -> None:
    """E5-8(FR-PD-13): 永続化されたstoryに`x_evidence`(根拠)が最低1件含まれること。"""
    llm_response_payload = json.dumps(
        {
            "as_a": "利用者",
            "i_want": "検索を高速化したい",
            "so_that": "業務を早く終えたい",
            "acceptance_criteria": ["検索が3秒以内に完了する"],
            "title": "検索高速化",
            "reach": 50,
            "impact": 1,
            "confidence": 0.5,
            "effort": 2,
            "score": 0,
        },
        ensure_ascii=False,
    )

    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response_payload))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        with respx.mock(base_url="http://test") as autonomy_mock:
            autonomy_mock.get("/autonomy/emergency-stop/status").mock(
                return_value=httpx.Response(200, json={"emergency_stopped": False})
            )
            result = await run_backlog_graph(
                intake_text="検索が遅い",
                pmdf_tool_client=pmdf_tool_client,
                llm_client=llm_client,
                api_server_url="http://test",
                auth_token=auth_token,
            )

    assert result["x_evidence"]
    assert len(result["x_evidence"]) >= 1

    created_story = await pmdf_tool_client.get_entity(kind="story", entity_id=result["id"])
    assert created_story["x_evidence"]


@pytest.mark.asyncio
async def test_run_backlog_graph_completes_without_approval_gate_as_l2(
    pmdf_tool_client: PmdfToolClient, app, auth_token: str
) -> None:
    """L2として、承認ゲート(approvalエンティティの起案)を経由せず直接persistまで完了することを確認する。"""
    llm_response_payload = json.dumps(
        {
            "as_a": "利用者",
            "i_want": "x",
            "so_that": "y",
            "acceptance_criteria": ["z"],
            "title": "t",
            "reach": 10,
            "impact": 1,
            "confidence": 1.0,
            "effort": 1,
            "score": 0,
        },
        ensure_ascii=False,
    )

    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response_payload))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        with respx.mock(base_url="http://test") as autonomy_mock:
            autonomy_mock.get("/autonomy/emergency-stop/status").mock(
                return_value=httpx.Response(200, json={"emergency_stopped": False})
            )
            await run_backlog_graph(
                intake_text="要望",
                pmdf_tool_client=pmdf_tool_client,
                llm_client=llm_client,
                api_server_url="http://test",
                auth_token=auth_token,
            )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/approvals", headers={"Authorization": f"Bearer {auth_token}"})
        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.asyncio
async def test_run_backlog_graph_raises_when_emergency_stopped(
    pmdf_tool_client: PmdfToolClient, auth_token: str
) -> None:
    from agent_core.guards import EmergencyStopError

    llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

    with respx.mock(base_url="http://test") as autonomy_mock:
        autonomy_mock.get("/autonomy/emergency-stop/status").mock(
            return_value=httpx.Response(200, json={"emergency_stopped": True})
        )
        with pytest.raises(EmergencyStopError):
            await run_backlog_graph(
                intake_text="要望",
                pmdf_tool_client=pmdf_tool_client,
                llm_client=llm_client,
                api_server_url="http://test",
                auth_token=auth_token,
            )


def test_calc_wsjf_score_used_when_priority_method_is_wsjf() -> None:
    from agent_core.graphs.backlog import recalculate_priority

    llm_priority = {
        "method": "WSJF",
        "business_value": 5,
        "time_criticality": 3,
        "risk_reduction": 2,
        "job_size": 2,
        "score": -1,  # 誤った値
    }

    recalculated = recalculate_priority(llm_priority)

    assert recalculated["score"] == pytest.approx((5 + 3 + 2) / 2)


def test_recalculate_priority_rice_used_when_priority_method_is_rice() -> None:
    from agent_core.graphs.backlog import recalculate_priority

    llm_priority = {
        "method": "RICE",
        "reach": 100,
        "impact": 2,
        "confidence": 0.8,
        "effort": 4,
        "score": -1,
    }

    recalculated = recalculate_priority(llm_priority)

    assert recalculated["score"] == pytest.approx((100 * 2 * 0.8) / 4)
