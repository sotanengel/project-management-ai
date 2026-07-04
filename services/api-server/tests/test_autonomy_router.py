"""自律レベル設定API・緊急停止APIのテスト(E3-8)。

受け入れ条件:
- 自律レベル変更APIは管理者のみ実行可能(編集者・閲覧者は403)
- 緊急停止発動後、エージェント実行系エンドポイントは409
- 緊急停止中でもPMDF CRUDは通常通り200系で成功する(AR-06)
- 緊急停止解除後、エージェント実行系エンドポイントは再び成功する
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

PRODUCT_ID = "prod-01HGATEAAAAAAAAAAAAAAAAAAA"
OBJECTIVE_ID = "obj-01HGATEAAAAAAAAAAAAAAAAAAA"
ROADMAP_ID = "roadmap-01HGATEAAAAAAAAAAAAAAAAAAA"
PROPOSER_ID = "stakeholder-01HPRP1AAAAAAAAAAAAAAAAAAA"
APPROVER_ID = "stakeholder-01HAPR2AAAAAAAAAAAAAAAAAAA"


@pytest.fixture
def user_store_path(tmp_path: Path) -> Path:
    from api_server.auth.password import hash_password

    path = tmp_path / "users.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "user-admin",
                    "email": "admin@example.com",
                    "password_hash": hash_password("admin-pass"),
                    "role": "admin",
                    "totp_secret": None,
                    "product_scopes": None,
                },
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
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("PMDF_STORE_PATH", str(tmp_path / "pmdf-repo"))
    monkeypatch.setenv("USER_STORE_PATH", str(user_store_path))
    monkeypatch.setenv("PROPOSAL_STORE_PATH", str(tmp_path / "proposals.json"))
    monkeypatch.setenv("AUTONOMY_CONFIG_PATH", str(tmp_path / "autonomy.json"))
    monkeypatch.setenv("EMERGENCY_STOP_PATH", str(tmp_path / "emergency_stop.json"))

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
async def admin_client(client: AsyncClient) -> AsyncClient:
    token = await _login(client, "admin@example.com", "admin-pass")
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture
async def editor_client(client: AsyncClient) -> AsyncClient:
    token = await _login(client, "editor@example.com", "editor-pass")
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.mark.asyncio
async def test_admin_can_change_autonomy_level(admin_client: AsyncClient) -> None:
    response = await admin_client.put(f"/autonomy/{PRODUCT_ID}/roadmap", json={"level": "L2"})

    assert response.status_code == 200, response.text
    assert response.json()["level"] == "L2"


@pytest.mark.asyncio
async def test_editor_cannot_change_autonomy_level(editor_client: AsyncClient) -> None:
    response = await editor_client.put(f"/autonomy/{PRODUCT_ID}/roadmap", json={"level": "L2"})

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_change_autonomy_level(client: AsyncClient) -> None:
    token = await _login(client, "viewer@example.com", "viewer-pass")
    client.headers["Authorization"] = f"Bearer {token}"

    response = await client.put(f"/autonomy/{PRODUCT_ID}/roadmap", json={"level": "L2"})

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_autonomy_lists_configured_levels(admin_client: AsyncClient) -> None:
    await admin_client.put(f"/autonomy/{PRODUCT_ID}/roadmap", json={"level": "L2"})

    response = await admin_client.get("/autonomy")

    assert response.status_code == 200
    body = response.json()
    assert any(
        e["product_id"] == PRODUCT_ID and e["business_function"] == "roadmap" and e["level"] == "L2"
        for e in body
    )


async def _create_roadmap_target(client: AsyncClient) -> None:
    await client.post(
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
    )
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
            "theme": "テストテーマ",
            "period": "2026-Q1",
            "status": "planned",
            "dependencies": [],
            "objective": OBJECTIVE_ID,
        },
    )
    assert response.status_code == 201, response.text


async def _approve(client: AsyncClient, *, target: str) -> None:
    propose_response = await client.post(
        "/approvals", json={"target": target, "proposer": PROPOSER_ID}
    )
    proposal_id = propose_response.json()["id"]
    decide_response = await client.post(
        f"/approvals/{proposal_id}/decide",
        json={"decision": "approved", "approver": APPROVER_ID, "reason": "検証のため"},
    )
    assert decide_response.status_code == 200, decide_response.text


@pytest.mark.asyncio
async def test_emergency_stop_blocks_l1_execution_endpoint(
    editor_client: AsyncClient, admin_client: AsyncClient
) -> None:
    await _create_roadmap_target(editor_client)
    await _approve(editor_client, target=ROADMAP_ID)

    stop_response = await admin_client.post("/autonomy/emergency-stop", json={})
    assert stop_response.status_code == 200, stop_response.text

    response = await editor_client.post(f"/roadmap/{ROADMAP_ID}/confirm")

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_emergency_stop_does_not_block_pmdf_crud(
    editor_client: AsyncClient, admin_client: AsyncClient
) -> None:
    stop_response = await admin_client.post("/autonomy/emergency-stop", json={})
    assert stop_response.status_code == 200, stop_response.text

    await _create_roadmap_target(editor_client)
    response = await editor_client.get("/pmdf/roadmap_item")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_emergency_stop_release_restores_l1_execution(
    editor_client: AsyncClient, admin_client: AsyncClient
) -> None:
    await _create_roadmap_target(editor_client)
    await _approve(editor_client, target=ROADMAP_ID)

    await admin_client.post("/autonomy/emergency-stop", json={})
    blocked_response = await editor_client.post(f"/roadmap/{ROADMAP_ID}/confirm")
    assert blocked_response.status_code == 409

    release_response = await admin_client.post("/autonomy/emergency-stop/release", json={})
    assert release_response.status_code == 200, release_response.text

    response = await editor_client.post(f"/roadmap/{ROADMAP_ID}/confirm")

    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_non_admin_cannot_trigger_emergency_stop(editor_client: AsyncClient) -> None:
    response = await editor_client.post("/autonomy/emergency-stop", json={})

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_emergency_stop_status_defaults_to_false_for_any_authenticated_role(
    editor_client: AsyncClient,
) -> None:
    """E5-1: agent-coreが毎ステップ照会するステータス取得API(管理者以外も参照可)。"""
    response = await editor_client.get("/autonomy/emergency-stop/status")

    assert response.status_code == 200, response.text
    assert response.json() == {"emergency_stopped": False}


@pytest.mark.asyncio
async def test_emergency_stop_status_reflects_stop_state(
    editor_client: AsyncClient, admin_client: AsyncClient
) -> None:
    await admin_client.post("/autonomy/emergency-stop", json={})

    response = await editor_client.get("/autonomy/emergency-stop/status")

    assert response.status_code == 200, response.text
    assert response.json() == {"emergency_stopped": True}


@pytest.mark.asyncio
async def test_emergency_stop_status_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/autonomy/emergency-stop/status")

    assert response.status_code == 401
