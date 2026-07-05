"""監査ログ検索API(`GET /audit/records`、E7-6)のテスト。

`api_server.audit.log`は追記専用のJSONL永続化層(E3-7)を提供済みだが、
actor/action/target_kind/期間での検索フィルタを備えたHTTP APIはまだ
無かったため、本サブイシュー(E7-6)で追加する。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
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
                }
            ]
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def audit_log_path(tmp_path: Path) -> Path:
    from api_server.audit.log import AuditRecord, append_record

    path = tmp_path / "audit.log.jsonl"
    records = [
        AuditRecord.create(
            actor="user:editor",
            action="pmdf.story.create",
            target_kind="story",
            target_id="story-01",
            detail={},
            prev_hash=None,
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        ),
    ]
    append_record(records[0], path)
    records.append(
        AuditRecord.create(
            actor="agent:backlog@v1",
            action="pmdf.story.update",
            target_kind="story",
            target_id="story-02",
            detail={},
            prev_hash=records[0].hash,
            timestamp=datetime(2026, 2, 1, tzinfo=UTC),
        )
    )
    append_record(records[1], path)
    return path


@pytest.fixture
def app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    user_store_path: Path,
    audit_log_path: Path,
):
    monkeypatch.setenv("JWT_SECRET", "test-secret-audit")
    monkeypatch.setenv("PMDF_STORE_PATH", str(tmp_path / "pmdf-repo"))
    monkeypatch.setenv("USER_STORE_PATH", str(user_store_path))
    monkeypatch.setenv("AUDIT_LOG_PATH", str(audit_log_path))

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


@pytest.mark.asyncio
async def test_list_records_returns_all_newest_first(client: AsyncClient) -> None:
    response = await client.get("/audit/records")

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 2
    assert body[0]["target_id"] == "story-02"
    assert body[1]["target_id"] == "story-01"


@pytest.mark.asyncio
async def test_filter_by_actor(client: AsyncClient) -> None:
    response = await client.get("/audit/records", params={"actor": "agent:backlog@v1"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert body[0]["actor"] == "agent:backlog@v1"


@pytest.mark.asyncio
async def test_filter_by_action(client: AsyncClient) -> None:
    response = await client.get("/audit/records", params={"action": "pmdf.story.create"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert body[0]["action"] == "pmdf.story.create"


@pytest.mark.asyncio
async def test_filter_by_kind(client: AsyncClient) -> None:
    response = await client.get("/audit/records", params={"kind": "story"})

    assert response.status_code == 200, response.text
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_filter_by_date_range(client: AsyncClient) -> None:
    response = await client.get(
        "/audit/records",
        params={"date_from": "2026-01-15T00:00:00Z", "date_to": "2026-03-01T00:00:00Z"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert body[0]["target_id"] == "story-02"


@pytest.mark.asyncio
async def test_requires_authentication(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.get("/audit/records")
    assert response.status_code == 401
