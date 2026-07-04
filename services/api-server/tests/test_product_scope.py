"""プロダクトスコープ認可のテスト(E3-5)。

`product_scopes` を持つviewerロールユーザーが、スコープ外プロダクトの
エンティティにアクセスすると403が返ることを検証する。また、管理者専用の
ユーザー管理API(`POST /admin/users`, `PUT /admin/users/{id}/scopes`)を
非管理者が呼ぶと403になることも検証する。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

PRODUCT_A = "prod-01HAAAAAAAAAAAAAAAAAAAAAAA"
PRODUCT_B = "prod-01HBBBBBBBBBBBBBBBBBBBBBBB"


def _valid_product_payload(**overrides: object) -> dict:
    payload: dict[str, Any] = {
        "pmdf_version": "1.0.0",
        "kind": "product",
        "id": PRODUCT_A,
        "provenance": {
            "created_by": "user:tester",
            "updated_at": "2026-01-01T00:00:00Z",
        },
        "attachments": [],
        "name": "テストプロダクト",
        "vision": "ビジョン",
        "lifecycle_stage": "growth",
    }
    payload.update(overrides)
    return payload


def _valid_story_payload(**overrides: object) -> dict:
    payload: dict[str, Any] = {
        "pmdf_version": "1.0.0",
        "kind": "story",
        "id": "story-01HZZZZZZZZZZZZZZZZZZZZZZZ",
        "provenance": {
            "created_by": "user:tester",
            "updated_at": "2026-01-01T00:00:00Z",
        },
        "attachments": [],
        "title": "テストストーリー",
        "as_a": "ユーザー",
        "i_want": "機能を使いたい",
        "so_that": "価値を得る",
        "acceptance_criteria": ["条件1"],
        "priority": {"method": "RICE"},
        "status": "draft",
    }
    payload.update(overrides)
    return payload


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
                    "id": "user-viewer-scoped",
                    "email": "viewer-scoped@example.com",
                    "password_hash": hash_password("viewer-pass"),
                    "role": "viewer",
                    "totp_secret": None,
                    "product_scopes": [PRODUCT_A],
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

    from api_server.pmdf_store.store import PmdfStore

    PmdfStore.init(tmp_path / "pmdf-repo")

    from api_server.main import create_app

    return create_app()


async def _login(client: AsyncClient, email: str, password: str) -> str:
    response = await client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def editor_client(client: AsyncClient) -> AsyncClient:
    token = await _login(client, "editor@example.com", "editor-pass")
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.mark.asyncio
async def test_scoped_viewer_cannot_access_story_outside_scope(
    client: AsyncClient, editor_client: AsyncClient
) -> None:
    await editor_client.post("/pmdf/product", json=_valid_product_payload(id=PRODUCT_A))
    await editor_client.post("/pmdf/product", json=_valid_product_payload(id=PRODUCT_B))
    await editor_client.post(
        "/pmdf/story",
        json=_valid_story_payload(id="story-01HSCPEB2AAAAAAAAAAAAAAAAA", product=PRODUCT_B),
    )
    del client.headers["Authorization"]

    token = await _login(client, "viewer-scoped@example.com", "viewer-pass")
    client.headers["Authorization"] = f"Bearer {token}"

    response = await client.get("/pmdf/story/story-01HSCPEB2AAAAAAAAAAAAAAAAA")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_scoped_viewer_can_access_story_within_scope(
    client: AsyncClient, editor_client: AsyncClient
) -> None:
    await editor_client.post("/pmdf/product", json=_valid_product_payload(id=PRODUCT_A))
    await editor_client.post(
        "/pmdf/story",
        json=_valid_story_payload(id="story-01HSCPEA1AAAAAAAAAAAAAAAAA", product=PRODUCT_A),
    )
    del client.headers["Authorization"]

    token = await _login(client, "viewer-scoped@example.com", "viewer-pass")
    client.headers["Authorization"] = f"Bearer {token}"

    response = await client.get("/pmdf/story/story-01HSCPEA1AAAAAAAAAAAAAAAAA")

    assert response.status_code == 200
    assert response.json()["id"] == "story-01HSCPEA1AAAAAAAAAAAAAAAAA"


@pytest.mark.asyncio
async def test_scoped_viewer_list_excludes_out_of_scope_entities(
    client: AsyncClient, editor_client: AsyncClient
) -> None:
    await editor_client.post("/pmdf/product", json=_valid_product_payload(id=PRODUCT_A))
    await editor_client.post("/pmdf/product", json=_valid_product_payload(id=PRODUCT_B))
    await editor_client.post(
        "/pmdf/story",
        json=_valid_story_payload(id="story-01HSCPEA1AAAAAAAAAAAAAAAAA", product=PRODUCT_A),
    )
    await editor_client.post(
        "/pmdf/story",
        json=_valid_story_payload(id="story-01HSCPEB2AAAAAAAAAAAAAAAAA", product=PRODUCT_B),
    )
    del client.headers["Authorization"]

    token = await _login(client, "viewer-scoped@example.com", "viewer-pass")
    client.headers["Authorization"] = f"Bearer {token}"

    response = await client.get("/pmdf/story")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids == ["story-01HSCPEA1AAAAAAAAAAAAAAAAA"]


@pytest.mark.asyncio
async def test_unscoped_admin_and_editor_access_all_products(
    client: AsyncClient, editor_client: AsyncClient
) -> None:
    await editor_client.post("/pmdf/product", json=_valid_product_payload(id=PRODUCT_A))
    await editor_client.post("/pmdf/product", json=_valid_product_payload(id=PRODUCT_B))
    await editor_client.post(
        "/pmdf/story",
        json=_valid_story_payload(id="story-01HSCPEB2AAAAAAAAAAAAAAAAA", product=PRODUCT_B),
    )

    response = await editor_client.get("/pmdf/story/story-01HSCPEB2AAAAAAAAAAAAAAAAA")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_can_create_user(client: AsyncClient) -> None:
    token = await _login(client, "admin@example.com", "admin-pass")
    client.headers["Authorization"] = f"Bearer {token}"

    response = await client.post(
        "/admin/users",
        json={
            "email": "new-viewer@example.com",
            "password": "new-pass",
            "role": "viewer",
            "product_scopes": [PRODUCT_A],
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "new-viewer@example.com"
    assert "password" not in body
    assert "password_hash" not in body


@pytest.mark.asyncio
async def test_non_admin_cannot_create_user(
    client: AsyncClient, editor_client: AsyncClient
) -> None:
    response = await editor_client.post(
        "/admin/users",
        json={
            "email": "new-viewer@example.com",
            "password": "new-pass",
            "role": "viewer",
            "product_scopes": [PRODUCT_A],
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_update_user_scopes(client: AsyncClient) -> None:
    token = await _login(client, "admin@example.com", "admin-pass")
    client.headers["Authorization"] = f"Bearer {token}"

    response = await client.put(
        "/admin/users/user-viewer-scoped/scopes",
        json={"product_scopes": [PRODUCT_A, PRODUCT_B]},
    )

    assert response.status_code == 200, response.text
    assert response.json()["product_scopes"] == [PRODUCT_A, PRODUCT_B]


@pytest.mark.asyncio
async def test_non_admin_cannot_update_user_scopes(
    client: AsyncClient, editor_client: AsyncClient
) -> None:
    response = await editor_client.put(
        "/admin/users/user-viewer-scoped/scopes",
        json={"product_scopes": [PRODUCT_A]},
    )

    assert response.status_code == 403
