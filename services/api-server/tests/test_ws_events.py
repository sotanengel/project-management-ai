"""WebSocketイベント配信(`WS /ws/events`)のテスト(E3-10)。

受け入れ条件:
- PMDFエンティティ変更で`pmdf.entity_changed`イベントが配信される
- 承認レコード新規作成で`approval.count_changed`イベントが配信される
- 未認証でのWebSocket接続は拒否される
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PRODUCT_ID = "prod-01HGATEAAAAAAAAAAAAAAAAAAA"
DECISION_ID = "dec-01HGATEAAAAAAAAAAAAAAAAAAA"
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
                }
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
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "audit.log.jsonl"))

    from api_server.pmdf_store.store import PmdfStore

    PmdfStore.init(tmp_path / "pmdf-repo")

    from api_server.main import create_app

    return create_app()


@pytest.fixture
def token(app) -> str:
    with TestClient(app) as client:
        response = client.post(
            "/auth/login", json={"email": "editor@example.com", "password": "editor-pass"}
        )
        assert response.status_code == 200, response.text
        return response.json()["access_token"]


def _valid_product_payload(**overrides: object) -> dict:
    payload: dict = {
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


def test_unauthenticated_ws_connection_is_rejected(app) -> None:
    with TestClient(app) as client, pytest.raises(Exception):  # noqa: B017, PT011
        with client.websocket_connect("/ws/events"):
            pass


def test_pmdf_entity_change_publishes_event(app, token: str) -> None:
    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/events?token={token}") as ws:
            response = client.post(
                "/pmdf/product",
                json=_valid_product_payload(),
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 201, response.text

            message = ws.receive_json()

    assert message["type"] == "pmdf.entity_changed"
    assert message["data"]["kind"] == "product"
    assert message["data"]["id"] == PRODUCT_ID


def test_approval_creation_publishes_count_changed_event(app, token: str) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/pmdf/decision",
            json={
                "pmdf_version": "1.0.0",
                "kind": "decision",
                "id": DECISION_ID,
                "provenance": {
                    "created_by": "user:tester",
                    "updated_at": "2026-01-01T00:00:00Z",
                },
                "attachments": [],
                "background": "背景",
                "options": [{"name": "案A"}],
                "chosen_option": "案A",
                "rationale": "根拠",
                "rejected_reasons": [],
                "autonomy_level": "L1",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201, response.text

        with client.websocket_connect(f"/ws/events?token={token}") as ws:
            propose_response = client.post(
                "/approvals",
                json={"target": DECISION_ID, "proposer": PROPOSER_ID},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert propose_response.status_code == 201, propose_response.text
            proposal_id = propose_response.json()["id"]

            decide_response = client.post(
                f"/approvals/{proposal_id}/decide",
                json={"decision": "approved", "approver": APPROVER_ID, "reason": "検証のため"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert decide_response.status_code == 200, decide_response.text

            message = ws.receive_json()

    assert message["type"] == "approval.count_changed"
