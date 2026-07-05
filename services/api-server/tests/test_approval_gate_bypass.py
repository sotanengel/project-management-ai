"""承認ゲート(L1強制)の網羅的バイパステスト(E3-6, AC-06直結)。

L1業務の実行エンドポイントは、承認済み(`decision == "approved"`)の
`Approval`(PMDF)エンティティが存在しない限り、API直叩きであっても
**全パス**で403が返ることを検証する。`L1_GATED_ENDPOINTS`
(`api_server.routers.l1_execution`)に定義された全エンドポイントを
パラメータ化して網羅する。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

DECISION_ID = "dec-01HGATEAAAAAAAAAAAAAAAAAAA"
ROADMAP_ID = "roadmap-01HGATEAAAAAAAAAAAAAAAAAAA"
RELEASE_ID = "release-01HGATEAAAAAAAAAAAAAAAAAAA"
STAKEHOLDER_ID = "stakeholder-01HGATESENDAAAAAAAAAAAAAAA"
PRODUCT_ID = "prod-01HGATEAAAAAAAAAAAAAAAAAAA"
OBJECTIVE_ID = "obj-01HGATEAAAAAAAAAAAAAAAAAAA"
PROPOSER_ID = "stakeholder-01HPRP1AAAAAAAAAAAAAAAAAAA"
APPROVER_ID = "stakeholder-01HAPR2AAAAAAAAAAAAAAAAAAA"

#: (HTTPメソッド, パス, 対象kind, 対象id) のタプル一覧。
#: `api_server.routers.l1_execution.L1_GATED_ENDPOINTS` と対応するエンドポイント全てを
#: 網羅する(新規L1エンドポイント追加時は両方に追記すること)。
L1_ENDPOINTS: list[tuple[str, str, str, str]] = [
    ("POST", "/pmdf/decision/{id}/execute", "decision", DECISION_ID),
    ("POST", "/roadmap/{id}/confirm", "roadmap_item", ROADMAP_ID),
    ("POST", "/release/{id}/go-no-go", "release", RELEASE_ID),
    ("POST", "/stakeholder/{id}/send-message", "stakeholder", STAKEHOLDER_ID),
]


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


def _valid_decision_payload(**overrides: object) -> dict:
    payload: dict[str, Any] = {
        "pmdf_version": "1.0.0",
        "kind": "decision",
        "id": DECISION_ID,
        "provenance": {"created_by": "user:tester", "updated_at": "2026-01-01T00:00:00Z"},
        "attachments": [],
        "product": PRODUCT_ID,
        "background": "背景",
        "options": [{"name": "案A"}],
        "chosen_option": "案A",
        "rationale": "根拠",
        "rejected_reasons": [],
        "autonomy_level": "L1",
    }
    payload.update(overrides)
    return payload


def _valid_objective_payload(**overrides: object) -> dict:
    payload: dict[str, Any] = {
        "pmdf_version": "1.0.0",
        "kind": "objective",
        "id": OBJECTIVE_ID,
        "provenance": {"created_by": "user:tester", "updated_at": "2026-01-01T00:00:00Z"},
        "attachments": [],
        "objective": "テスト目標",
        "key_results": [{"description": "KR1", "target_value": 100.0}],
        "period": "2026-Q1",
    }
    payload.update(overrides)
    return payload


def _valid_roadmap_item_payload(**overrides: object) -> dict:
    payload: dict[str, Any] = {
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
    }
    payload.update(overrides)
    return payload


def _valid_release_payload(**overrides: object) -> dict:
    payload: dict[str, Any] = {
        "pmdf_version": "1.0.0",
        "kind": "release",
        "id": RELEASE_ID,
        "provenance": {"created_by": "user:tester", "updated_at": "2026-01-01T00:00:00Z"},
        "attachments": [],
        "product": PRODUCT_ID,
        "name": "テストリリース",
        "scope": [],
        "go_no_go": "pending",
    }
    payload.update(overrides)
    return payload


def _valid_stakeholder_payload(**overrides: object) -> dict:
    payload: dict[str, Any] = {
        "pmdf_version": "1.0.0",
        "kind": "stakeholder",
        "id": STAKEHOLDER_ID,
        "provenance": {"created_by": "user:tester", "updated_at": "2026-01-01T00:00:00Z"},
        "attachments": [],
        "name": "テスト関係者",
        "role": "スポンサー",
        "influence": "high",
        "interests": [],
    }
    payload.update(overrides)
    return payload


_KIND_TO_CREATE_PAYLOAD = {
    "decision": ("/pmdf/decision", _valid_decision_payload),
    "roadmap_item": ("/pmdf/roadmap_item", _valid_roadmap_item_payload),
    "release": ("/pmdf/release", _valid_release_payload),
    "stakeholder": ("/pmdf/stakeholder", _valid_stakeholder_payload),
}


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


async def _create_target_entities(client: AsyncClient) -> None:
    """L1エンドポイントのテスト対象となるproduct+objective+各kindのエンティティを作成する。"""
    await client.post("/pmdf/product", json=_valid_product_payload())
    await client.post("/pmdf/objective", json=_valid_objective_payload())
    for kind, (path, payload_fn) in _KIND_TO_CREATE_PAYLOAD.items():
        response = await client.post(path, json=payload_fn())
        assert response.status_code == 201, (kind, response.text)


async def _propose_and_decide(
    client: AsyncClient, *, target: str, decision: str, reason: str = "検証のため"
) -> None:
    propose_response = await client.post(
        "/approvals", json={"target": target, "proposer": PROPOSER_ID}
    )
    assert propose_response.status_code == 201, propose_response.text
    proposal_id = propose_response.json()["id"]

    decide_response = await client.post(
        f"/approvals/{proposal_id}/decide",
        json={"decision": decision, "approver": APPROVER_ID, "reason": reason},
    )
    assert decide_response.status_code == 200, decide_response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path_template,kind,entity_id", L1_ENDPOINTS)
async def test_l1_endpoint_without_approval_returns_403(
    client: AsyncClient, method: str, path_template: str, kind: str, entity_id: str
) -> None:
    """AC-06: 承認レコードなしでL1エンドポイントを直叩きすると、全パスで403が返る。"""
    await _create_target_entities(client)

    path = path_template.format(id=entity_id)
    response = await client.request(method, path)

    assert response.status_code == 403, (path, response.text)


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path_template,kind,entity_id", L1_ENDPOINTS)
async def test_l1_endpoint_with_approved_record_returns_200(
    client: AsyncClient, method: str, path_template: str, kind: str, entity_id: str
) -> None:
    """承認済みapprovalレコードが存在する場合のみ、対応するL1エンドポイントは200になる。"""
    await _create_target_entities(client)
    await _propose_and_decide(client, target=entity_id, decision="approved")

    path = path_template.format(id=entity_id)
    response = await client.request(method, path)

    assert response.status_code == 200, (path, response.text)


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path_template,kind,entity_id", L1_ENDPOINTS)
async def test_l1_endpoint_with_rejected_record_still_returns_403(
    client: AsyncClient, method: str, path_template: str, kind: str, entity_id: str
) -> None:
    """差し戻し(rejected)の場合は実行が403のままであることを確認する。"""
    await _create_target_entities(client)
    await _propose_and_decide(client, target=entity_id, decision="rejected")

    path = path_template.format(id=entity_id)
    response = await client.request(method, path)

    assert response.status_code == 403, (path, response.text)


@pytest.mark.asyncio
async def test_decide_without_reason_returns_422(client: AsyncClient) -> None:
    """承認理由(reason)が未入力の場合、decide自体が422で拒否される。"""
    propose_response = await client.post(
        "/approvals", json={"target": DECISION_ID, "proposer": PROPOSER_ID}
    )
    proposal_id = propose_response.json()["id"]

    response = await client.post(
        f"/approvals/{proposal_id}/decide",
        json={"decision": "approved", "approver": APPROVER_ID, "reason": ""},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_decide_missing_reason_field_returns_422(client: AsyncClient) -> None:
    """reasonフィールド自体が存在しない場合も422になることを確認する。"""
    propose_response = await client.post(
        "/approvals", json={"target": DECISION_ID, "proposer": PROPOSER_ID}
    )
    proposal_id = propose_response.json()["id"]

    response = await client.post(
        f"/approvals/{proposal_id}/decide",
        json={"decision": "approved", "approver": APPROVER_ID},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_all_l1_router_endpoints_are_covered_by_test_matrix() -> None:
    """`l1_execution.router`に定義された全ルートが`L1_ENDPOINTS`(このテストの
    パラメータ化対象)に網羅されていることを検証する(エンドポイント網羅性チェック)。
    """
    from api_server.routers.l1_execution import router
    from fastapi.routing import APIRoute

    declared = {
        (method, route.path)
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in route.methods or set()
        if method != "HEAD"
    }
    tested = {(method, path_template) for method, path_template, _, _ in L1_ENDPOINTS}

    assert declared == tested, (declared, tested)
