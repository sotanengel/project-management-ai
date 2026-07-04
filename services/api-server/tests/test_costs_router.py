"""コストAPI(`POST /costs/usage`, `GET /costs/summary`)のテスト(E4-3, AR-04)。

受け入れ条件:
- usage記録複数件に対し、GET /costs/summaryがモデル別・論理名別の集計値を返す
- 月次予算の80%相当でwarning、100%以上でexceeded、80%未満でokを返す
- 認証必須(閲覧はviewer以上、記録はadmin/editor)
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
    monkeypatch.setenv("COST_USAGE_LOG_PATH", str(tmp_path / "costs" / "usage.jsonl"))
    monkeypatch.setenv("BUDGET_MONTHLY_JPY", "1000")

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


@pytest.fixture
async def viewer_client(client: AsyncClient) -> AsyncClient:
    token = await _login(client, "viewer@example.com", "viewer-pass")
    client.headers["Authorization"] = f"Bearer {token}"
    return client


def _usage_payload(**overrides: object) -> dict:
    payload = {
        "logical_name": "pdm-main",
        "model": "claude-sonnet-4-5",
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "latency_ms": 200.0,
        "cost_jpy": 100.0,
        "actor": "agent-core",
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_usage_endpoint_requires_authentication(client: AsyncClient) -> None:
    response = await client.post("/costs/usage", json=_usage_payload())
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_viewer_cannot_record_usage(viewer_client: AsyncClient) -> None:
    response = await viewer_client.post("/costs/usage", json=_usage_payload())
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_editor_can_record_usage(editor_client: AsyncClient) -> None:
    response = await editor_client.post("/costs/usage", json=_usage_payload())
    assert response.status_code == 201, response.text


@pytest.mark.asyncio
async def test_summary_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/costs/summary")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_viewer_can_read_summary(
    editor_client: AsyncClient, viewer_client: AsyncClient
) -> None:
    await editor_client.post("/costs/usage", json=_usage_payload())

    response = await viewer_client.get("/costs/summary")
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_summary_aggregates_by_model_and_logical_name(admin_client: AsyncClient) -> None:
    await admin_client.post(
        "/costs/usage",
        json=_usage_payload(model="claude-sonnet-4-5", logical_name="pdm-main", cost_jpy=100.0),
    )
    await admin_client.post(
        "/costs/usage",
        json=_usage_payload(model="claude-sonnet-4-5", logical_name="pdm-main", cost_jpy=150.0),
    )
    await admin_client.post(
        "/costs/usage",
        json=_usage_payload(model="gpt-4o", logical_name="pdm-judge", cost_jpy=50.0),
    )

    response = await admin_client.get("/costs/summary")
    assert response.status_code == 200, response.text
    body = response.json()

    by_model = {entry["key"]: entry for entry in body["by_model"]}
    assert by_model["claude-sonnet-4-5"]["total_cost_jpy"] == pytest.approx(250.0)
    assert by_model["claude-sonnet-4-5"]["call_count"] == 2
    assert by_model["gpt-4o"]["total_cost_jpy"] == pytest.approx(50.0)

    by_logical_name = {entry["key"]: entry for entry in body["by_logical_name"]}
    assert by_logical_name["pdm-main"]["total_cost_jpy"] == pytest.approx(250.0)
    assert by_logical_name["pdm-judge"]["total_cost_jpy"] == pytest.approx(50.0)


@pytest.mark.asyncio
async def test_summary_reports_ok_status_below_80_percent(admin_client: AsyncClient) -> None:
    # 予算1000円に対し500円(50%)消化 -> ok
    await admin_client.post("/costs/usage", json=_usage_payload(cost_jpy=500.0))

    response = await admin_client.get("/costs/summary")
    body = response.json()

    assert body["budget_monthly_jpy"] == pytest.approx(1000.0)
    assert body["total_spend_jpy"] == pytest.approx(500.0)
    assert body["consumption_ratio"] == pytest.approx(0.5)
    assert body["budget_status"] == "ok"


@pytest.mark.asyncio
async def test_summary_reports_warning_status_at_80_percent(admin_client: AsyncClient) -> None:
    # 予算1000円に対し800円(80%)消化 -> warning
    await admin_client.post("/costs/usage", json=_usage_payload(cost_jpy=800.0))

    response = await admin_client.get("/costs/summary")
    body = response.json()

    assert body["consumption_ratio"] == pytest.approx(0.8)
    assert body["budget_status"] == "warning"


@pytest.mark.asyncio
async def test_summary_reports_exceeded_status_at_100_percent(admin_client: AsyncClient) -> None:
    # 予算1000円に対し1200円(120%)消化 -> exceeded
    await admin_client.post("/costs/usage", json=_usage_payload(cost_jpy=1200.0))

    response = await admin_client.get("/costs/summary")
    body = response.json()

    assert body["consumption_ratio"] == pytest.approx(1.2)
    assert body["budget_status"] == "exceeded"


@pytest.mark.asyncio
async def test_usage_endpoint_rejects_negative_cost(editor_client: AsyncClient) -> None:
    response = await editor_client.post("/costs/usage", json=_usage_payload(cost_jpy=-1.0))
    assert response.status_code == 422
