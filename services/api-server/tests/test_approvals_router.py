"""承認ワークフローAPI(`/approvals`系)のテスト(E3-6)。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

TARGET_ID = "dec-01HGATEAAAAAAAAAAAAAAAAAAA"
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
async def test_propose_returns_201_with_proposed_status(client: AsyncClient) -> None:
    response = await client.post("/approvals", json={"target": TARGET_ID, "proposer": PROPOSER_ID})

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "proposed"
    assert body["target"] == TARGET_ID


@pytest.mark.asyncio
async def test_list_pending_approvals_returns_proposed_only(client: AsyncClient) -> None:
    propose_response = await client.post(
        "/approvals", json={"target": TARGET_ID, "proposer": PROPOSER_ID}
    )
    proposal_id = propose_response.json()["id"]
    await client.post(
        f"/approvals/{proposal_id}/decide",
        json={"decision": "approved", "approver": APPROVER_ID, "reason": "問題なし"},
    )
    await client.post("/approvals", json={"target": TARGET_ID, "proposer": PROPOSER_ID})

    response = await client.get("/approvals", params={"status": "pending"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["status"] == "proposed"


@pytest.mark.asyncio
async def test_decide_approved_creates_approval_pmdf_entity(client: AsyncClient) -> None:
    propose_response = await client.post(
        "/approvals", json={"target": TARGET_ID, "proposer": PROPOSER_ID}
    )
    proposal_id = propose_response.json()["id"]

    response = await client.post(
        f"/approvals/{proposal_id}/decide",
        json={"decision": "approved", "approver": APPROVER_ID, "reason": "問題なし"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "approved"
    approval_entity_id = body["approval_entity_id"]
    assert approval_entity_id is not None

    entity_response = await client.get(f"/pmdf/approval/{approval_entity_id}")
    assert entity_response.status_code == 200
    assert entity_response.json()["decision"] == "approved"
    assert entity_response.json()["target"] == TARGET_ID


@pytest.mark.asyncio
async def test_decide_twice_returns_409(client: AsyncClient) -> None:
    propose_response = await client.post(
        "/approvals", json={"target": TARGET_ID, "proposer": PROPOSER_ID}
    )
    proposal_id = propose_response.json()["id"]
    await client.post(
        f"/approvals/{proposal_id}/decide",
        json={"decision": "approved", "approver": APPROVER_ID, "reason": "初回"},
    )

    response = await client.post(
        f"/approvals/{proposal_id}/decide",
        json={"decision": "rejected", "approver": APPROVER_ID, "reason": "再決定"},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_decide_unknown_proposal_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        "/approvals/proposal-does-not-exist/decide",
        json={"decision": "approved", "approver": APPROVER_ID, "reason": "問題なし"},
    )

    assert response.status_code == 404
