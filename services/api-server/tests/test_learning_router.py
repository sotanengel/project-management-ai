"""学習状況API(`GET /learning/status`)のテスト(E8-8関連)。

受け入れ条件:
- 学習履歴が無い場合、`has_activity: false` の空状態を返す
- 学習履歴がある場合、直近ジョブと評価ゲート履歴(promote/reject)を返す
- 認証必須(閲覧はviewer以上)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


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
def learning_status_path(tmp_path: Path) -> Path:
    return tmp_path / "learning" / "status.jsonl"


@pytest.fixture
def app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    user_store_path: Path,
    learning_status_path: Path,
):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("PMDF_STORE_PATH", str(tmp_path / "pmdf-repo"))
    monkeypatch.setenv("USER_STORE_PATH", str(user_store_path))
    monkeypatch.setenv("PROPOSAL_STORE_PATH", str(tmp_path / "proposals.json"))
    monkeypatch.setenv("AUTONOMY_CONFIG_PATH", str(tmp_path / "autonomy.json"))
    monkeypatch.setenv("EMERGENCY_STOP_PATH", str(tmp_path / "emergency_stop.json"))
    monkeypatch.setenv("COST_USAGE_LOG_PATH", str(tmp_path / "costs" / "usage.jsonl"))
    monkeypatch.setenv("LEARNING_STATUS_PATH", str(learning_status_path))

    from api_server.pmdf_store.store import PmdfStore

    PmdfStore.init(tmp_path / "pmdf-repo")

    from api_server.main import create_app

    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
async def editor_client(client: AsyncClient) -> AsyncClient:
    token = await _login(client, "editor@example.com", "editor-pass")
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture
async def viewer_client(client: AsyncClient) -> AsyncClient:
    token = await _login(client, "viewer@example.com", "viewer-pass")
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.mark.asyncio
async def test_status_endpoint_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/learning/status")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_status_returns_empty_state_when_no_history(viewer_client: AsyncClient) -> None:
    response = await viewer_client.get("/learning/status")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["has_activity"] is False
    assert body["latest_job"] is None
    assert body["gate_history"] == []


@pytest.mark.asyncio
async def test_status_returns_latest_job_and_gate_history(
    viewer_client: AsyncClient, learning_status_path: Path
) -> None:
    learning_status_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        {
            "timestamp": "2026-07-01T00:00:00Z",
            "job_type": "sft",
            "status": "completed",
            "metrics": {"train_steps": 10},
            "decision": None,
        },
        {
            "timestamp": "2026-07-02T00:00:00Z",
            "job_type": "eval",
            "status": "completed",
            "metrics": {"pdm_delta": 12.0},
            "decision": "promote",
        },
    ]
    learning_status_path.write_text(
        "\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8"
    )

    response = await viewer_client.get("/learning/status")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["has_activity"] is True
    assert body["latest_job"]["job_type"] == "eval"
    assert len(body["gate_history"]) == 1
    assert body["gate_history"][0]["decision"] == "promote"
