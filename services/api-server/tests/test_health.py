"""GET /healthz のテスト。"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("PMDF_STORE_PATH", str(tmp_path))
    from api_server.main import create_app

    return create_app()


@pytest.mark.asyncio
async def test_healthz_returns_ok(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_openapi_json_is_valid_openapi_document(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")

    assert response.status_code == 200
    document = response.json()
    assert document["openapi"].startswith("3.")
    assert "paths" in document
    assert "/healthz" in document["paths"]
