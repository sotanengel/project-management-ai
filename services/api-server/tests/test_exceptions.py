"""共通例外ハンドラのテスト(スタックトレース非漏洩、統一エラー形式)。"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_broken_route(monkeypatch: pytest.MonkeyPatch, tmp_path) -> FastAPI:
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("PMDF_STORE_PATH", str(tmp_path))
    from api_server.main import create_app

    app = create_app()

    @app.get("/__boom__")
    def boom() -> None:
        raise RuntimeError("internal detail that must not leak")

    @app.get("/__perm__")
    def perm() -> None:
        raise PermissionError("no access")

    @app.get("/__validation__")
    def validation() -> None:
        raise ValueError("bad value")

    return app


def test_uncaught_exception_returns_500_without_leaking_stack_trace(
    app_with_broken_route: FastAPI,
) -> None:
    client = TestClient(app_with_broken_route, raise_server_exceptions=False)
    response = client.get("/__boom__")

    assert response.status_code == 500
    body = response.json()
    assert "internal detail that must not leak" not in response.text
    assert "Traceback" not in response.text
    assert body["error"]["code"] == "internal_error"


def test_permission_error_returns_403(app_with_broken_route: FastAPI) -> None:
    client = TestClient(app_with_broken_route, raise_server_exceptions=False)
    response = client.get("/__perm__")

    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "forbidden"


def test_http_404_uses_unified_error_format(app_with_broken_route: FastAPI) -> None:
    client = TestClient(app_with_broken_route, raise_server_exceptions=False)
    response = client.get("/__does_not_exist__")

    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert "code" in body["error"]
