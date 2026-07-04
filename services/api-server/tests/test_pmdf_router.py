"""PMDF CRUD API(`/pmdf/{kind}` 系)のテスト(E3-3)。

E3-4完了に伴い、書込系エンドポイントは認証(admin/editorロール)が
必要になったため、テスト用ユーザーストアを用意しeditorとしてログイン
した状態のクライアントを使う。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from api_server.auth.password import hash_password

    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("PMDF_STORE_PATH", str(tmp_path / "pmdf-repo"))

    user_store_path = tmp_path / "users.json"
    user_store_path.write_text(
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
    monkeypatch.setenv("USER_STORE_PATH", str(user_store_path))

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


def _valid_story_payload(**overrides: object) -> dict:
    payload = {
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


@pytest.mark.asyncio
async def test_create_story_returns_201_with_id(client: AsyncClient) -> None:
    response = await client.post("/pmdf/story", json=_valid_story_payload())

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["id"] == "story-01HZZZZZZZZZZZZZZZZZZZZZZZ"


@pytest.mark.asyncio
async def test_create_story_missing_required_field_returns_422_with_field_name(
    client: AsyncClient,
) -> None:
    payload = _valid_story_payload()
    del payload["title"]

    response = await client.post("/pmdf/story", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert "title" in response.text
    assert body["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_create_story_with_missing_objective_reference_returns_422(
    client: AsyncClient,
) -> None:
    payload = _valid_story_payload(
        id="story-01HZZZZZZZZZZZZZZZZZZZZZZY",
        links={"objective": "obj-01HDAESNATEXASTAAAAAAAAAAA", "decisions": []},
    )

    response = await client.post("/pmdf/story", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert "obj-01HDAESNATEXASTAAAAAAAAAAA" in response.text
    assert body["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_get_story_returns_created_entity(client: AsyncClient) -> None:
    await client.post("/pmdf/story", json=_valid_story_payload())

    response = await client.get("/pmdf/story/story-01HZZZZZZZZZZZZZZZZZZZZZZZ")

    assert response.status_code == 200
    assert response.json()["title"] == "テストストーリー"


@pytest.mark.asyncio
async def test_get_story_not_found_returns_404(client: AsyncClient) -> None:
    response = await client.get("/pmdf/story/story-01HNATFAANDAAAAAAAAAAAAAAA")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_story_creates_new_version_and_history_grows(client: AsyncClient) -> None:
    await client.post("/pmdf/story", json=_valid_story_payload())

    updated_payload = _valid_story_payload(title="更新後タイトル")
    response = await client.put(
        "/pmdf/story/story-01HZZZZZZZZZZZZZZZZZZZZZZZ", json=updated_payload
    )

    assert response.status_code == 200, response.text
    assert response.json()["title"] == "更新後タイトル"

    history_response = await client.get("/pmdf/story/story-01HZZZZZZZZZZZZZZZZZZZZZZZ/history")
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) == 2


@pytest.mark.asyncio
async def test_get_story_with_ref_returns_past_version(client: AsyncClient) -> None:
    await client.post("/pmdf/story", json=_valid_story_payload(title="v1"))
    history_response = await client.get("/pmdf/story/story-01HZZZZZZZZZZZZZZZZZZZZZZZ/history")
    first_commit = history_response.json()[0]["commit_hash"]

    await client.put(
        "/pmdf/story/story-01HZZZZZZZZZZZZZZZZZZZZZZZ",
        json=_valid_story_payload(title="v2"),
    )

    past_response = await client.get(
        "/pmdf/story/story-01HZZZZZZZZZZZZZZZZZZZZZZZ",
        params={"ref": first_commit},
    )
    assert past_response.status_code == 200
    assert past_response.json()["title"] == "v1"


@pytest.mark.asyncio
async def test_list_stories_returns_created_entities(client: AsyncClient) -> None:
    await client.post("/pmdf/story", json=_valid_story_payload())

    response = await client.get("/pmdf/story")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == "story-01HZZZZZZZZZZZZZZZZZZZZZZZ"


def _valid_product_payload(**overrides: object) -> dict:
    payload = {
        "pmdf_version": "1.0.0",
        "kind": "product",
        "id": "prod-01HAAAAAAAAAAAAAAAAAAAAAAA",
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


@pytest.mark.asyncio
async def test_list_stories_filters_by_product(client: AsyncClient) -> None:
    product_a = "prod-01HAAAAAAAAAAAAAAAAAAAAAAA"
    product_b = "prod-01HBBBBBBBBBBBBBBBBBBBBBBBB"[:31]
    await client.post("/pmdf/product", json=_valid_product_payload(id=product_a))
    await client.post("/pmdf/product", json=_valid_product_payload(id=product_b))
    await client.post(
        "/pmdf/story",
        json=_valid_story_payload(id="story-01HAPRADAAAAAAAAAAAAAAAAAA", product=product_a),
    )
    await client.post(
        "/pmdf/story",
        json=_valid_story_payload(id="story-01HBPRADBBBBBBBBBBBBBBBBBB", product=product_b),
    )

    response = await client.get("/pmdf/story", params={"product": product_a})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == "story-01HAPRADAAAAAAAAAAAAAAAAAA"


@pytest.mark.asyncio
async def test_delete_approval_returns_405(client: AsyncClient) -> None:
    response = await client.delete("/pmdf/approval/approval-01HZZZZZZZZZZZZZZZZZZZZZZA")
    assert response.status_code == 405


@pytest.mark.asyncio
async def test_delete_decision_returns_405(client: AsyncClient) -> None:
    response = await client.delete("/pmdf/decision/dec-01HZZZZZZZZZZZZZZZZZZZZZZZ")
    assert response.status_code == 405
