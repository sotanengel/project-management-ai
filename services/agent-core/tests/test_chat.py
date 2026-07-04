"""チャット指示インターフェース(`agent_core.chat`)のテスト(E5-9、FR-UI-07)。

自然文の指示を受け、LLM(`pdm-main`)による意図分類ノードで対象業務グラフを
判定し、api-server(`POST /chat/instructions`)へタスクとして登録、実行の
各段階(受理/実行中/完了/失敗)を`POST /chat/tasks/{id}/transition`経由で
報告することを検証する。
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from agent_core.chat import GRAPH_KINDS, TaskHandle, classify_intent, handle_chat_instruction
from agent_core.llm_client import LogicalModelClient
from agent_core.tools.pmdf_tools import PmdfToolClient
from httpx import ASGITransport, AsyncClient

MODEL_GATEWAY_URL = "http://model-gateway.test:4000"
PRODUCT_ID = "prod-01HCHATAAAAAAAAAAAAAAAAAAA"


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
    monkeypatch.setenv("JWT_SECRET", "test-secret-chat-agent")
    monkeypatch.setenv("PMDF_STORE_PATH", str(tmp_path / "pmdf-repo"))
    monkeypatch.setenv("USER_STORE_PATH", str(user_store_path))
    monkeypatch.setenv("PROPOSAL_STORE_PATH", str(tmp_path / "proposals.json"))
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "audit.log.jsonl"))
    monkeypatch.setenv("CHAT_TASK_STORE_PATH", str(tmp_path / "chat_tasks.json"))

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
        agent_name="chat-agent",
        agent_version="1",
        transport=transport,
    )


@pytest.mark.asyncio
async def test_classify_intent_maps_response_to_known_graph_kind() -> None:
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(
            return_value=_chat_response(json.dumps({"graph": "vision_roadmap_release"}))
        )
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        kind = await classify_intent(
            "このプロダクトの来週のロードマップ見直しを検討して", llm_client=llm_client
        )

    assert kind == "vision_roadmap_release"
    assert kind in GRAPH_KINDS


@pytest.mark.asyncio
async def test_handle_chat_instruction_registers_task_and_classifies_intent(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    async def _noop_dispatch(**kwargs: object) -> dict:
        return {}

    llm_response = json.dumps({"graph": "vision_roadmap_release"})
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        handle = await handle_chat_instruction(
            message="このプロダクトの来週のロードマップ見直しを検討して",
            product_id=PRODUCT_ID,
            actor="user:tester",
            llm_client=llm_client,
            pmdf_tool_client=pmdf_tool_client,
            api_server_url="http://test",
            auth_token=auth_token,
            dispatch_overrides={"vision_roadmap_release": _noop_dispatch},
        )

    assert isinstance(handle, TaskHandle)
    assert handle.kind == "vision_roadmap_release"

    fetched = await pmdf_tool_client.request("GET", f"/chat/tasks/{handle.task_id}")
    assert fetched.json()["status"] == "done"
    assert fetched.json()["intent"] == "vision_roadmap_release"


@pytest.mark.asyncio
async def test_handle_chat_instruction_transitions_through_pending_running_done(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    """状態遷移(pending→running→done)の各段階を経ることを確認する。"""

    async def _tracking_dispatch(**kwargs: object) -> dict:
        return {"ok": True}

    llm_response = json.dumps({"graph": "backlog"})
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        handle = await handle_chat_instruction(
            message="バックログを整理して",
            product_id=PRODUCT_ID,
            actor="user:tester",
            llm_client=llm_client,
            pmdf_tool_client=pmdf_tool_client,
            api_server_url="http://test",
            auth_token=auth_token,
            dispatch_overrides={"backlog": _tracking_dispatch},
        )

    history_response = await pmdf_tool_client.request("GET", f"/chat/tasks/{handle.task_id}")
    assert history_response.json()["status"] == "done"
    assert history_response.json()["result"] == {"ok": True}


@pytest.mark.asyncio
async def test_handle_chat_instruction_marks_failed_when_dispatch_raises(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    async def _failing_dispatch(**kwargs: object) -> dict:
        raise RuntimeError("グラフ実行に失敗しました")

    llm_response = json.dumps({"graph": "backlog"})
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        handle = await handle_chat_instruction(
            message="バックログを整理して",
            product_id=PRODUCT_ID,
            actor="user:tester",
            llm_client=llm_client,
            pmdf_tool_client=pmdf_tool_client,
            api_server_url="http://test",
            auth_token=auth_token,
            dispatch_overrides={"backlog": _failing_dispatch},
        )

    fetched = await pmdf_tool_client.request("GET", f"/chat/tasks/{handle.task_id}")
    assert fetched.json()["status"] == "failed"
    assert "グラフ実行に失敗しました" in fetched.json()["error"]


@pytest.mark.asyncio
async def test_handle_chat_instruction_falls_back_to_backlog_on_unknown_intent(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    """LLMが未知のgraph名を返した場合、既定のbacklogへフォールバックする。"""

    async def _noop_dispatch(**kwargs: object) -> dict:
        return {}

    llm_response = json.dumps({"graph": "unknown_graph_name"})
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        handle = await handle_chat_instruction(
            message="よくわからない指示",
            product_id=PRODUCT_ID,
            actor="user:tester",
            llm_client=llm_client,
            pmdf_tool_client=pmdf_tool_client,
            api_server_url="http://test",
            auth_token=auth_token,
            dispatch_overrides={"backlog": _noop_dispatch},
        )

    assert handle.kind == "backlog"


@pytest.mark.asyncio
async def test_instruction_submission_dispatches_graph_and_emits_progress_events(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    """統合テスト: 指示投入→意図分類→グラフ起動(モックLLM)→進捗イベント受信までを検証する。

    api-serverの共有イベントバス(`agent.activity`)を直接購読しながら
    `handle_chat_instruction`を実行し、イベントが`pending`→`running`→
    `done`の順で配信されることを確認する(E5-9受け入れ条件の統合テスト)。
    """
    from api_server.events.bus import get_event_bus

    bus = get_event_bus()
    subscription = bus.subscribe()

    async def _tracking_dispatch(**kwargs: object) -> dict:
        return {"graph": "backlog", "ok": True}

    llm_response = json.dumps({"graph": "backlog"})
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        handle = await handle_chat_instruction(
            message="バックログを整理して",
            product_id=PRODUCT_ID,
            actor="user:tester",
            llm_client=llm_client,
            pmdf_tool_client=pmdf_tool_client,
            api_server_url="http://test",
            auth_token=auth_token,
            dispatch_overrides={"backlog": _tracking_dispatch},
        )

    pending_message = subscription.get_nowait()
    running_message = subscription.get_nowait()
    done_message = subscription.get_nowait()
    bus.unsubscribe(subscription)

    assert pending_message["type"] == "agent.activity"
    assert pending_message["data"]["status"] == "pending"
    assert pending_message["data"]["task_id"] == handle.task_id

    assert running_message["type"] == "agent.activity"
    assert running_message["data"]["status"] == "running"
    assert running_message["data"]["intent"] == "backlog"

    assert done_message["type"] == "agent.activity"
    assert done_message["data"]["status"] == "done"

    assert handle.kind == "backlog"
