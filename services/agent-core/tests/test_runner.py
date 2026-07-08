"""常駐ランナー(`agent_core.runner`)のテスト。

api-server(`GET /chat/tasks?status=pending`)をポーリングし、保留中の
チャットタスクを`agent_core.chat.execute_chat_task`経由で実行することを
検証する。緊急停止中はディスパッチをスキップしつつポーリングは継続する
こと、ディスパッチ以外(意図分類等)で例外が起きた場合もタスクを`failed`
へ遷移させループを継続することを確認する。
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from agent_core.llm_client import LogicalModelClient
from agent_core.runner import poll_once
from agent_core.tools.pmdf_tools import PmdfToolClient
from httpx import ASGITransport, AsyncClient

MODEL_GATEWAY_URL = "http://model-gateway.test:4000"
PRODUCT_ID = "prod-01HRUNNERAAAAAAAAAAAAAAAAA"


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
def emergency_stop_path(tmp_path: Path) -> Path:
    return tmp_path / "emergency_stop.json"


@pytest.fixture
def budget_exceeded_path(tmp_path: Path) -> Path:
    return tmp_path / "budget_exceeded.json"


@pytest.fixture
def app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    user_store_path: Path,
    emergency_stop_path: Path,
    budget_exceeded_path: Path,
):
    monkeypatch.setenv("JWT_SECRET", "test-secret-runner-agent")
    monkeypatch.setenv("PMDF_STORE_PATH", str(tmp_path / "pmdf-repo"))
    monkeypatch.setenv("USER_STORE_PATH", str(user_store_path))
    monkeypatch.setenv("PROPOSAL_STORE_PATH", str(tmp_path / "proposals.json"))
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "audit.log.jsonl"))
    monkeypatch.setenv("CHAT_TASK_STORE_PATH", str(tmp_path / "chat_tasks.json"))
    monkeypatch.setenv("EMERGENCY_STOP_PATH", str(emergency_stop_path))
    monkeypatch.setenv("BUDGET_EXCEEDED_PATH", str(budget_exceeded_path))

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
        agent_name="runner-agent",
        agent_version="1",
        transport=transport,
    )


async def _submit_pending_task(pmdf_tool_client: PmdfToolClient, message: str) -> str:
    response = await pmdf_tool_client.request(
        "POST",
        "/chat/instructions",
        json={"message": message, "product_id": PRODUCT_ID},
    )
    return str(response.json()["id"])


@pytest.mark.asyncio
async def test_poll_once_dispatches_pending_task_to_done(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    """保留中タスクをポーリングで取得し、ディスパッチ後にdoneへ遷移する。"""
    transport = ASGITransport(app=app)
    task_id = await _submit_pending_task(pmdf_tool_client, "バックログを整理して")

    async def _tracking_dispatch(**kwargs: object) -> dict:
        return {"ok": True}

    llm_response = json.dumps({"graph": "backlog"})
    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        await poll_once(
            pmdf_tool_client=pmdf_tool_client,
            llm_client=llm_client,
            api_server_url="http://test",
            auth_token=auth_token,
            transport=transport,
            dispatch_overrides={"backlog": _tracking_dispatch},
        )

    fetched = await pmdf_tool_client.request("GET", f"/chat/tasks/{task_id}")
    assert fetched.json()["status"] == "done"
    assert fetched.json()["result"] == {"ok": True}


@pytest.mark.asyncio
async def test_poll_once_skips_dispatch_when_emergency_stopped(
    app,
    auth_token: str,
    pmdf_tool_client: PmdfToolClient,
    emergency_stop_path: Path,
) -> None:
    """緊急停止中は、ポーリングは行うがディスパッチはスキップし、タスクはpendingのままとなる。"""
    from api_server.autonomy.emergency_stop import stop

    transport = ASGITransport(app=app)
    task_id = await _submit_pending_task(pmdf_tool_client, "バックログを整理して")
    stop(emergency_stop_path)

    dispatch_called = False

    async def _tracking_dispatch(**kwargs: object) -> dict:
        nonlocal dispatch_called
        dispatch_called = True
        return {"ok": True}

    llm_response = json.dumps({"graph": "backlog"})
    with respx.mock(base_url=MODEL_GATEWAY_URL, assert_all_called=False) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        await poll_once(
            pmdf_tool_client=pmdf_tool_client,
            llm_client=llm_client,
            api_server_url="http://test",
            auth_token=auth_token,
            transport=transport,
            dispatch_overrides={"backlog": _tracking_dispatch},
        )

    assert dispatch_called is False
    fetched = await pmdf_tool_client.request("GET", f"/chat/tasks/{task_id}")
    assert fetched.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_poll_once_skips_dispatch_when_learning_blocked(
    app,
    auth_token: str,
    pmdf_tool_client: PmdfToolClient,
    budget_exceeded_path: Path,
) -> None:
    """予算超過による学習ブロック中も、ディスパッチをスキップしタスクはpendingのままとなる。"""
    from api_server.costs.budget_state import set_learning_blocked

    transport = ASGITransport(app=app)
    task_id = await _submit_pending_task(pmdf_tool_client, "バックログを整理して")
    set_learning_blocked(budget_exceeded_path, blocked=True)

    dispatch_called = False

    async def _tracking_dispatch(**kwargs: object) -> dict:
        nonlocal dispatch_called
        dispatch_called = True
        return {"ok": True}

    llm_response = json.dumps({"graph": "backlog"})
    with respx.mock(base_url=MODEL_GATEWAY_URL, assert_all_called=False) as mock:
        mock.post("/chat/completions").mock(return_value=_chat_response(llm_response))
        llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

        await poll_once(
            pmdf_tool_client=pmdf_tool_client,
            llm_client=llm_client,
            api_server_url="http://test",
            auth_token=auth_token,
            transport=transport,
            dispatch_overrides={"backlog": _tracking_dispatch},
        )

    assert dispatch_called is False
    fetched = await pmdf_tool_client.request("GET", f"/chat/tasks/{task_id}")
    assert fetched.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_poll_once_marks_task_failed_when_intent_classification_raises(
    app, auth_token: str, pmdf_tool_client: PmdfToolClient
) -> None:
    """ディスパッチ以前(意図分類のLLM呼び出し)で例外が発生した場合も、タスクをfailedへ遷移させ
    ループ自体はクラッシュせず継続できることを確認する(2回目のpoll_onceも正常終了する)。
    """
    transport = ASGITransport(app=app)
    task_id = await _submit_pending_task(pmdf_tool_client, "バックログを整理して")

    llm_client = LogicalModelClient(model_gateway_url=MODEL_GATEWAY_URL)

    with respx.mock(base_url=MODEL_GATEWAY_URL) as mock:
        mock.post("/chat/completions").mock(
            side_effect=httpx.ConnectError("model-gatewayに接続できません")
        )

        # 1回目: 意図分類が例外を送出するが、poll_once自体は例外を伝播させず、
        # タスクをfailedへ遷移させる。
        await poll_once(
            pmdf_tool_client=pmdf_tool_client,
            llm_client=llm_client,
            api_server_url="http://test",
            auth_token=auth_token,
            transport=transport,
            dispatch_overrides={},
        )

        fetched = await pmdf_tool_client.request("GET", f"/chat/tasks/{task_id}")
        assert fetched.json()["status"] == "failed"
        assert fetched.json()["error"]

        # 2回目: 対象タスクはもう`pending`ではないため、クラッシュせず正常終了する。
        await poll_once(
            pmdf_tool_client=pmdf_tool_client,
            llm_client=llm_client,
            api_server_url="http://test",
            auth_token=auth_token,
            transport=transport,
            dispatch_overrides={},
        )
