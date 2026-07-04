"""import/export API(`/bundles`系)のテスト(E3-9)。

AC-07: PMDFバンドルのエクスポート→別環境へのインポートで、全エンティティ・
参照整合・添付ハッシュが一致することをAPI層で検証する。
"""

from __future__ import annotations

import json
import tarfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

PRODUCT_ID = "prod-01HGATEAAAAAAAAAAAAAAAAAAA"


def _valid_product_payload(**overrides: object) -> dict:
    payload: dict[str, Any] = {
        "pmdf_version": "1.0.0",
        "kind": "product",
        "id": PRODUCT_ID,
        "provenance": {"created_by": "user:tester", "updated_at": "2026-01-01T00:00:00Z"},
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
        "provenance": {"created_by": "user:tester", "updated_at": "2026-01-01T00:00:00Z"},
        "attachments": [],
        "product": PRODUCT_ID,
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


def _make_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, user_store_path: Path, name: str):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("PMDF_STORE_PATH", str(tmp_path / f"pmdf-repo-{name}"))
    monkeypatch.setenv("USER_STORE_PATH", str(user_store_path))
    monkeypatch.setenv("PROPOSAL_STORE_PATH", str(tmp_path / "proposals.json"))
    monkeypatch.setenv("AUTONOMY_CONFIG_PATH", str(tmp_path / "autonomy.json"))
    monkeypatch.setenv("EMERGENCY_STOP_PATH", str(tmp_path / "emergency_stop.json"))
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / f"audit-{name}.log.jsonl"))

    from api_server.pmdf_store.store import PmdfStore

    PmdfStore.init(tmp_path / f"pmdf-repo-{name}")

    from api_server.main import create_app

    return create_app()


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, user_store_path: Path):
    return _make_app(monkeypatch, tmp_path, user_store_path, "src")


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


async def _seed_entities(client: AsyncClient) -> None:
    response = await client.post("/pmdf/product", json=_valid_product_payload())
    assert response.status_code == 201, response.text
    response = await client.post("/pmdf/story", json=_valid_story_payload())
    assert response.status_code == 201, response.text


@pytest.mark.asyncio
async def test_export_returns_tarball_with_manifest_and_entities(client: AsyncClient) -> None:
    await _seed_entities(client)

    response = await client.post("/bundles/export", json={})

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] in (
        "application/gzip",
        "application/x-gzip",
        "application/octet-stream",
    )

    with tarfile.open(fileobj=BytesIO(response.content), mode="r:gz") as tar:
        names = tar.getnames()
        assert "manifest.json" in names
        assert any(name.startswith("entities/product/") for name in names)
        assert any(name.startswith("entities/story/") for name in names)

        manifest_member = tar.extractfile("manifest.json")
        assert manifest_member is not None
        manifest = json.loads(manifest_member.read())
        assert manifest["entity_count"]["total"] == 2


@pytest.mark.asyncio
async def test_export_with_scope_filters_by_kind(client: AsyncClient) -> None:
    await _seed_entities(client)

    response = await client.post("/bundles/export", json={"kinds": ["product"]})

    assert response.status_code == 200, response.text
    with tarfile.open(fileobj=BytesIO(response.content), mode="r:gz") as tar:
        names = tar.getnames()
        assert any(name.startswith("entities/product/") for name in names)
        assert not any(name.startswith("entities/story/") for name in names)


@pytest.mark.asyncio
async def test_import_validate_with_invalid_bundle_returns_422(client: AsyncClient) -> None:
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="manifest.json")
        content = b"{}"
        info.size = len(content)
        tar.addfile(info, BytesIO(content))
    buffer.seek(0)

    response = await client.post(
        "/bundles/import/validate",
        files={"file": ("bad.pmdf.tar.gz", buffer, "application/gzip")},
    )

    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_export_then_import_validate_and_apply_round_trip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, user_store_path: Path
) -> None:
    """AC-07: エクスポート→別ストアへのimport(validate→apply)で全エンティティが復元される。"""
    source_app = _make_app(monkeypatch, tmp_path, user_store_path, "source")
    source_transport = ASGITransport(app=source_app)
    async with AsyncClient(transport=source_transport, base_url="http://test") as source_client:
        login_response = await source_client.post(
            "/auth/login", json={"email": "editor@example.com", "password": "editor-pass"}
        )
        token = login_response.json()["access_token"]
        source_client.headers["Authorization"] = f"Bearer {token}"

        await _seed_entities(source_client)
        export_response = await source_client.post("/bundles/export", json={})
        assert export_response.status_code == 200, export_response.text
        bundle_bytes = export_response.content

    target_app = _make_app(monkeypatch, tmp_path, user_store_path, "target")
    target_transport = ASGITransport(app=target_app)
    async with AsyncClient(transport=target_transport, base_url="http://test") as target_client:
        login_response = await target_client.post(
            "/auth/login", json={"email": "editor@example.com", "password": "editor-pass"}
        )
        token = login_response.json()["access_token"]
        target_client.headers["Authorization"] = f"Bearer {token}"

        validate_response = await target_client.post(
            "/bundles/import/validate",
            files={"file": ("bundle.pmdf.tar.gz", BytesIO(bundle_bytes), "application/gzip")},
        )
        assert validate_response.status_code == 200, validate_response.text
        validate_body = validate_response.json()
        assert validate_body["is_valid"] is True
        assert len(validate_body["diffs"]) == 2
        assert all(d["diff_type"] == "new" for d in validate_body["diffs"])

        apply_response = await target_client.post(
            "/bundles/import/apply",
            files={"file": ("bundle.pmdf.tar.gz", BytesIO(bundle_bytes), "application/gzip")},
            data={"resolutions": "{}"},
        )
        assert apply_response.status_code == 200, apply_response.text
        apply_body = apply_response.json()
        assert set(apply_body["applied_ids"]) == {PRODUCT_ID, "story-01HZZZZZZZZZZZZZZZZZZZZZZZ"}

        product_response = await target_client.get(f"/pmdf/product/{PRODUCT_ID}")
        assert product_response.status_code == 200
        story_response = await target_client.get("/pmdf/story/story-01HZZZZZZZZZZZZZZZZZZZZZZZ")
        assert story_response.status_code == 200
        assert story_response.json()["product"] == PRODUCT_ID

        history_response = await target_client.get(f"/pmdf/product/{PRODUCT_ID}/history")
        assert history_response.status_code == 200
        assert len(history_response.json()) == 1
