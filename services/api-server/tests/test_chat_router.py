"""チャット指示インターフェースAPI(`/chat`系、E5-9、FR-UI-07)のテスト。

`POST /chat/instructions`(タスク受付)、`POST /chat/tasks/{id}/transition`
(agent-coreランナーからの状態遷移報告)、`GET /chat/tasks/{id}`(実行状況取得)
の3エンドポイントと、各段階での`agent.activity`イベント配信を検証する。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

PRODUCT_ID = "prod-01HCHATAAAAAAAAAAAAAAAAAAA"


@pytest.fixture
def user_store_path(tmp_path: Path) -> Path:
    from api_server.auth.password import hash_password

    path = tmp_path / "users.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "user-editor",
                    "email": "editor@example.com",
                    "password_hash": hash_password("editor-pass"),
                    "role": "editor",
                    "totp_secret": None,
                    "product_scopes": None,
                },
                {
                    "id": "user-viewer",
                    "email": "viewer@example.com",
                    "password_hash": hash_password("viewer-pass"),
                    "role": "viewer",
                    "totp_secret": None,
                    "product_scopes": None,
                },
            ]
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, user_store_path: Path):
    monkeypatch.setenv("JWT_SECRET", "test-secret-chat")
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
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        login_response = await c.post(
            "/auth/login", json={"email": "editor@example.com", "password": "editor-pass"}
        )
        token = login_response.json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c


@pytest.fixture
async def viewer_client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        login_response = await c.post(
            "/auth/login", json={"email": "viewer@example.com", "password": "viewer-pass"}
        )
        token = login_response.json()["access_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        yield c


@pytest.mark.asyncio
async def test_post_instructions_requires_authentication(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.post(
            "/chat/instructions",
            json={"message": "ロードマップを見直して", "product_id": PRODUCT_ID},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_post_instructions_creates_pending_task(client: AsyncClient) -> None:
    response = await client.post(
        "/chat/instructions",
        json={
            "message": "このプロダクトの来週のロードマップ見直しを検討して",
            "product_id": PRODUCT_ID,
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["message"] == "このプロダクトの来週のロードマップ見直しを検討して"
    assert body["product_id"] == PRODUCT_ID
    assert body["id"]


@pytest.mark.asyncio
async def test_get_task_returns_current_status(client: AsyncClient) -> None:
    create_response = await client.post(
        "/chat/instructions", json={"message": "バックログを整理して", "product_id": PRODUCT_ID}
    )
    task_id = create_response.json()["id"]

    response = await client.get(f"/chat/tasks/{task_id}")

    assert response.status_code == 200, response.text
    assert response.json()["id"] == task_id
    assert response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_list_tasks_returns_all_tasks_newest_first(client: AsyncClient) -> None:
    """E7-6のエージェント活動ログ画面向け一覧API。新しいタスクが先頭に来る。"""
    first = await client.post(
        "/chat/instructions", json={"message": "1件目", "product_id": PRODUCT_ID}
    )
    second = await client.post(
        "/chat/instructions", json={"message": "2件目", "product_id": PRODUCT_ID}
    )

    response = await client.get("/chat/tasks")

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 2
    assert body[0]["id"] == second.json()["id"]
    assert body[1]["id"] == first.json()["id"]


@pytest.mark.asyncio
async def test_list_tasks_filters_by_status(client: AsyncClient) -> None:
    create_response = await client.post(
        "/chat/instructions", json={"message": "実行中タスク", "product_id": PRODUCT_ID}
    )
    task_id = create_response.json()["id"]
    await client.post(f"/chat/tasks/{task_id}/transition", json={"status": "running"})
    await client.post(
        "/chat/instructions", json={"message": "待機中タスク", "product_id": PRODUCT_ID}
    )

    response = await client.get("/chat/tasks", params={"status": "running"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == task_id


@pytest.mark.asyncio
async def test_get_unknown_task_returns_404(client: AsyncClient) -> None:
    response = await client.get("/chat/tasks/task-does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_transition_updates_task_status(client: AsyncClient) -> None:
    create_response = await client.post(
        "/chat/instructions", json={"message": "実験を計画して", "product_id": PRODUCT_ID}
    )
    task_id = create_response.json()["id"]

    running_response = await client.post(
        f"/chat/tasks/{task_id}/transition",
        json={"status": "running"},
    )
    assert running_response.status_code == 200, running_response.text
    assert running_response.json()["status"] == "running"

    done_response = await client.post(
        f"/chat/tasks/{task_id}/transition",
        json={"status": "done", "result": {"graph": "discovery"}},
    )
    assert done_response.status_code == 200, done_response.text
    assert done_response.json()["status"] == "done"
    assert done_response.json()["result"] == {"graph": "discovery"}

    get_response = await client.get(f"/chat/tasks/{task_id}")
    assert get_response.json()["status"] == "done"


@pytest.mark.asyncio
async def test_transition_to_failed_records_error(client: AsyncClient) -> None:
    create_response = await client.post(
        "/chat/instructions", json={"message": "実験を計画して", "product_id": PRODUCT_ID}
    )
    task_id = create_response.json()["id"]

    response = await client.post(
        f"/chat/tasks/{task_id}/transition",
        json={"status": "failed", "error": "LLM呼び出し失敗"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "failed"
    assert response.json()["error"] == "LLM呼び出し失敗"


@pytest.mark.asyncio
async def test_transition_on_unknown_task_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        "/chat/tasks/task-does-not-exist/transition", json={"status": "running"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_viewer_cannot_post_instructions(viewer_client: AsyncClient) -> None:
    response = await viewer_client.post(
        "/chat/instructions", json={"message": "指示", "product_id": PRODUCT_ID}
    )
    assert response.status_code == 403


def test_instruction_lifecycle_publishes_agent_activity_events(app) -> None:
    """受理→実行中→完了の各段階で`agent.activity`イベントが配信されることを確認する。"""
    with TestClient(app) as client:
        login_response = client.post(
            "/auth/login", json={"email": "editor@example.com", "password": "editor-pass"}
        )
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        with client.websocket_connect(f"/ws/events?token={token}") as ws:
            create_response = client.post(
                "/chat/instructions",
                json={"message": "ロードマップ見直し", "product_id": PRODUCT_ID},
                headers=headers,
            )
            task_id = create_response.json()["id"]
            received_message = ws.receive_json()

            client.post(
                f"/chat/tasks/{task_id}/transition",
                json={"status": "running"},
                headers=headers,
            )
            running_message = ws.receive_json()

            client.post(
                f"/chat/tasks/{task_id}/transition",
                json={"status": "done", "result": {}},
                headers=headers,
            )
            done_message = ws.receive_json()

    assert received_message["type"] == "agent.activity"
    assert received_message["data"]["task_id"] == task_id
    assert received_message["data"]["status"] == "pending"

    assert running_message["type"] == "agent.activity"
    assert running_message["data"]["status"] == "running"

    assert done_message["type"] == "agent.activity"
    assert done_message["data"]["status"] == "done"
