"""PMDFツール群(`agent_core.tools.pmdf_tools`)のテスト(E5-2)。

api-serverの実FastAPIアプリをASGITransport経由で使い、HTTPリクエストが
実際にapi-serverへ到達すること(pmdf-storeへの直接書込ではないこと)を
検証する。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agent_core.tools.pmdf_tools import PmdfToolClient
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def user_store_path(tmp_path: Path) -> Path:
    from api_server.auth.password import hash_password

    path = tmp_path / "users.json"
    path.write_text(
        json.dumps(
            [
                {
                    "id": "agent-service-account",
                    "email": "agent@example.com",
                    "password_hash": hash_password("agent-pass"),
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
    monkeypatch.setenv("JWT_SECRET", "test-secret-pmdf-tools")
    monkeypatch.setenv("PMDF_STORE_PATH", str(tmp_path / "pmdf-repo"))
    monkeypatch.setenv("USER_STORE_PATH", str(user_store_path))
    monkeypatch.setenv("PROPOSAL_STORE_PATH", str(tmp_path / "proposals.json"))
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "audit.log.jsonl"))

    from api_server.pmdf_store.store import PmdfStore

    PmdfStore.init(tmp_path / "pmdf-repo")

    from api_server.main import create_app

    return create_app()


@pytest.fixture
async def auth_token(app) -> str:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/auth/login", json={"email": "agent@example.com", "password": "agent-pass"}
        )
        assert response.status_code == 200, response.text
        return str(response.json()["access_token"])


@pytest.fixture
def tool_client(app, auth_token: str) -> PmdfToolClient:
    transport = ASGITransport(app=app)
    return PmdfToolClient(
        api_server_url="http://test",
        auth_token=auth_token,
        agent_name="backlog-agent",
        agent_version="1",
        transport=transport,
    )


def _story_payload(*, id_: str, title: str = "サンプルストーリー") -> dict:
    return {
        "pmdf_version": "1.0.0",
        "kind": "story",
        "id": id_,
        "provenance": {"created_by": "user:tester", "updated_at": "2026-01-01T00:00:00Z"},
        "attachments": [],
        "title": title,
        "as_a": "利用者",
        "i_want": "機能を使いたい",
        "so_that": "価値を得たい",
        "acceptance_criteria": ["条件1"],
        "priority": {"method": "RICE"},
        "status": "draft",
    }


STORY_ID = "story-01HAGENTBBBBBBBBBBBBBBBBBB"


@pytest.mark.asyncio
async def test_create_entity_posts_to_api_server(tool_client: PmdfToolClient) -> None:
    created = await tool_client.create_entity(kind="story", data=_story_payload(id_=STORY_ID))

    assert created["id"] == STORY_ID
    assert created["kind"] == "story"


@pytest.mark.asyncio
async def test_create_entity_records_audit_actor_with_agent_prefix(
    tool_client: PmdfToolClient, app, auth_token: str, tmp_path: Path
) -> None:
    await tool_client.create_entity(kind="story", data=_story_payload(id_=STORY_ID))

    from api_server.config import get_settings

    audit_path = get_settings().audit_log_path
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    records = [json.loads(line) for line in lines]
    story_records = [r for r in records if r["target_id"] == STORY_ID]
    assert story_records, "監査ログにstory作成レコードが記録されていること"
    assert story_records[0]["actor"] == "agent:backlog-agent@v1"


@pytest.mark.asyncio
async def test_get_entity_returns_created_entity(tool_client: PmdfToolClient) -> None:
    await tool_client.create_entity(kind="story", data=_story_payload(id_=STORY_ID))

    fetched = await tool_client.get_entity(kind="story", entity_id=STORY_ID)

    assert fetched["id"] == STORY_ID


@pytest.mark.asyncio
async def test_update_entity_persists_change(tool_client: PmdfToolClient) -> None:
    await tool_client.create_entity(kind="story", data=_story_payload(id_=STORY_ID))

    updated = await tool_client.update_entity(
        kind="story",
        entity_id=STORY_ID,
        data=_story_payload(id_=STORY_ID, title="更新後タイトル"),
    )

    assert updated["title"] == "更新後タイトル"


@pytest.mark.asyncio
async def test_search_entities_filters_by_kind_and_product(tool_client: PmdfToolClient) -> None:
    await tool_client.create_entity(kind="story", data=_story_payload(id_=STORY_ID))

    results = await tool_client.search_entities(kind="story")

    assert any(r["id"] == STORY_ID for r in results)


@pytest.mark.asyncio
async def test_create_entity_raises_on_schema_validation_error(
    tool_client: PmdfToolClient,
) -> None:
    invalid_payload = _story_payload(id_=STORY_ID)
    del invalid_payload["title"]

    with pytest.raises(Exception):  # noqa: B017 - httpx.HTTPStatusError(422)を期待
        await tool_client.create_entity(kind="story", data=invalid_payload)


def test_pmdf_tools_module_does_not_import_pmdf_store_directly() -> None:
    """設計原則3: agent-coreはPMDFへの直接書込を行わない(pmdf-store非import)を静的に保証する。"""
    import ast
    from pathlib import Path as _Path

    source_path = (
        _Path(__file__).resolve().parents[1] / "src" / "agent_core" / "tools" / "pmdf_tools.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    forbidden = [m for m in imported_modules if "pmdf_store" in m or m == "pmdf.io"]
    assert not forbidden, f"pmdf-storeへの直接importが検出されました: {forbidden}"
