"""POST /auth/login 系のテスト(E3-4)。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


def _write_user_store(path: Path, users: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(users), encoding="utf-8")


@pytest.fixture
def user_store_path(tmp_path: Path) -> Path:
    from api_server.auth.password import hash_password

    path = tmp_path / "users.json"
    _write_user_store(
        path,
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
            {
                "id": "user-admin",
                "email": "admin@example.com",
                "password_hash": hash_password("admin-pass"),
                "role": "admin",
                "totp_secret": None,
                "product_scopes": None,
            },
        ],
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


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_login_with_correct_credentials_returns_200_and_token(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login", json={"email": "editor@example.com", "password": "editor-pass"}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "access_token" in body


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login", json={"email": "editor@example.com", "password": "wrong"}
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_with_unknown_email_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.post("/pmdf/story", json={})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_viewer_role_cannot_create_story_returns_403(client: AsyncClient) -> None:
    login_response = await client.post(
        "/auth/login", json={"email": "viewer@example.com", "password": "viewer-pass"}
    )
    token = login_response.json()["access_token"]

    response = await client.post(
        "/pmdf/story",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_editor_role_can_reach_create_story_endpoint(client: AsyncClient) -> None:
    """editorはCRUD可能(実際のバリデーションで422になっても認可自体は通ることを確認)。"""
    login_response = await client.post(
        "/auth/login", json={"email": "editor@example.com", "password": "editor-pass"}
    )
    token = login_response.json()["access_token"]

    response = await client.post(
        "/pmdf/story",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )

    # 認可(403)ではなく、ボディ不正による422/その他が返ることを確認する。
    assert response.status_code != 403
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_password_is_never_stored_as_plaintext(user_store_path: Path) -> None:
    data = json.loads(user_store_path.read_text(encoding="utf-8"))
    for user in data:
        assert user["password_hash"] != "editor-pass"
        assert user["password_hash"] != "viewer-pass"
        assert user["password_hash"].startswith("$argon2")


@pytest.mark.asyncio
async def test_totp_enabled_login_without_code_requires_additional_auth(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from api_server.auth.password import hash_password

    totp_user_store = tmp_path / "users_totp.json"
    _write_user_store(
        totp_user_store,
        [
            {
                "id": "user-totp",
                "email": "totp@example.com",
                "password_hash": hash_password("totp-pass"),
                "role": "editor",
                "totp_secret": "JBSWY3DPEHPK3PXP",
                "product_scopes": None,
            },
        ],
    )
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("PMDF_STORE_PATH", str(tmp_path / "pmdf-repo-totp"))
    monkeypatch.setenv("USER_STORE_PATH", str(totp_user_store))
    monkeypatch.setenv("TOTP_ENABLED", "true")
    from api_server.pmdf_store.store import PmdfStore

    PmdfStore.init(tmp_path / "pmdf-repo-totp")

    from api_server.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/auth/login", json={"email": "totp@example.com", "password": "totp-pass"}
        )

    assert response.status_code in (401, 428)
    body = response.json()
    assert "totp" in json.dumps(body).lower()


@pytest.mark.asyncio
async def test_totp_enabled_login_with_correct_code_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import pyotp
    from api_server.auth.password import hash_password

    secret = "JBSWY3DPEHPK3PXP"
    totp_user_store = tmp_path / "users_totp2.json"
    _write_user_store(
        totp_user_store,
        [
            {
                "id": "user-totp",
                "email": "totp2@example.com",
                "password_hash": hash_password("totp-pass"),
                "role": "editor",
                "totp_secret": secret,
                "product_scopes": None,
            },
        ],
    )
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("PMDF_STORE_PATH", str(tmp_path / "pmdf-repo-totp2"))
    monkeypatch.setenv("USER_STORE_PATH", str(totp_user_store))
    monkeypatch.setenv("TOTP_ENABLED", "true")
    from api_server.pmdf_store.store import PmdfStore

    PmdfStore.init(tmp_path / "pmdf-repo-totp2")

    from api_server.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    code = pyotp.TOTP(secret).now()
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/auth/login",
            json={"email": "totp2@example.com", "password": "totp-pass", "totp_code": code},
        )

    assert response.status_code == 200, response.text
    assert "access_token" in response.json()
