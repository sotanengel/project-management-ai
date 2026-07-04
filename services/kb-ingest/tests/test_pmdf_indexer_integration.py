"""api-serverの実WebSocketイベント・実REST APIを用いたPmdfIndexerの結合テスト(E6-3)。

E6-3の受け入れ条件:
- テスト用WebSocketイベント(`pmdf.entity_changed`、story更新)を発行
  すると、`PmdfIndexer`がQdrantへ該当storyのベクトルをupsertする。
- 同一storyを2回更新すると、Qdrant内のポイントが重複せず1件のまま
  内容が更新される(upsert冪等性)。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from kb_ingest.pmdf_indexer import PmdfIndexer
from kb_ingest.qdrant_store import QdrantKbStore

STORY_ID = "story-01HKBAAAAAAAAAAAAAAAAAAAAA"


class FakeEmbeddingClient:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t) % 11), 0.0, 1.0, 0.0] for t in texts]


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
    monkeypatch.setenv("JWT_SECRET", "test-secret-integration")
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


def _story_payload(title: str) -> dict:
    return {
        "pmdf_version": "1.0.0",
        "kind": "story",
        "id": STORY_ID,
        "provenance": {"created_by": "user:tester", "updated_at": "2026-01-01T00:00:00Z"},
        "attachments": [],
        "title": title,
        "as_a": "利用者",
        "i_want": "検索したい",
        "so_that": "業務を早く終えたい",
        "acceptance_criteria": ["検索結果が3秒以内に表示される"],
        "priority": {"method": "RICE"},
        "status": "draft",
    }


def test_ws_event_triggers_pmdf_indexing_via_real_api(app, token: str) -> None:
    store = QdrantKbStore(url=":memory:")
    embedding_client = FakeEmbeddingClient()

    def _make_fetch_entity(client: TestClient):
        async def _fetch_entity(kind: str, entity_id: str) -> dict | None:
            response = client.get(
                f"/pmdf/{kind}/{entity_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code != 200:
                return None
            return response.json()

        return _fetch_entity

    with TestClient(app) as client:
        indexer = PmdfIndexer(
            store=store,
            embedding_client=embedding_client,
            fetch_entity=_make_fetch_entity(client),
            collection="pdm_kb",
        )

        with client.websocket_connect(f"/ws/events?token={token}") as ws:
            create_response = client.post(
                "/pmdf/story",
                json=_story_payload("初版タイトル"),
                headers={"Authorization": f"Bearer {token}"},
            )
            assert create_response.status_code == 201, create_response.text

            message = ws.receive_json()
            assert message["type"] == "pmdf.entity_changed"
            assert message["data"]["kind"] == "story"
            assert message["data"]["id"] == STORY_ID

        import asyncio

        asyncio.run(indexer.handle_event(message["data"]))

        points = store.scroll_all("pdm_kb")
        assert len(points) == 1
        assert points[0].payload["source"] == "pmdf"
        assert points[0].payload["pmdf_kind"] == "story"
        assert points[0].payload["pmdf_id"] == STORY_ID
        assert "初版タイトル" in points[0].payload["text"]

        # 同一storyを更新し、再度イベントを処理する(upsert冪等性の検証)。
        with client.websocket_connect(f"/ws/events?token={token}") as ws:
            update_payload = _story_payload("更新後タイトル")
            update_response = client.put(
                f"/pmdf/story/{STORY_ID}",
                json=update_payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            assert update_response.status_code == 200, update_response.text
            update_message = ws.receive_json()

        asyncio.run(indexer.handle_event(update_message["data"]))

        points_after_update = store.scroll_all("pdm_kb")
        assert len(points_after_update) == 1, "ポイントが重複せず1件のままであること"
        assert "更新後タイトル" in points_after_update[0].payload["text"]
        assert "初版タイトル" not in points_after_update[0].payload["text"]
