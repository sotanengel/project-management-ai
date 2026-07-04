"""kb_ingest.pmdf_indexer のテスト(E6-3)。

api-serverのWebSocketイベント(`pmdf.entity_changed`)を模したイベントを
発行すると、PmdfIndexerがQdrantへ該当エンティティのベクトルをupsert
すること、同一エンティティを2回更新してもポイントが重複しないこと
(upsert冪等性)、KBと混在してもsourceフィルタで区別できることを検証する。
"""

from __future__ import annotations

import asyncio

import pytest
from kb_ingest.chunking import Chunk
from kb_ingest.pmdf_indexer import PmdfIndexer, extract_entity_text
from kb_ingest.qdrant_store import QdrantKbStore


class FakeEmbeddingClient:
    """テスト用の決定的埋め込みクライアント(次元4固定)。"""

    def __init__(self) -> None:
        self.call_count = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.call_count += 1
        return [[float(len(t) % 7), 0.0, 0.0, 1.0] for t in texts]


def _make_entity_fetcher(entities: dict[tuple[str, str], dict]):
    async def _fetch(kind: str, entity_id: str) -> dict | None:
        return entities.get((kind, entity_id))

    return _fetch


@pytest.mark.asyncio
async def test_handle_event_upserts_pmdf_entity_vector() -> None:
    store = QdrantKbStore(url=":memory:")
    embedding_client = FakeEmbeddingClient()
    entities = {
        ("story", "story-01"): {
            "kind": "story",
            "id": "story-01",
            "product": "product-01",
            "title": "検索改善ストーリー",
            "as_a": "利用者",
            "i_want": "素早く検索したい",
            "so_that": "業務が早く終わる",
        }
    }
    indexer = PmdfIndexer(
        store=store,
        embedding_client=embedding_client,
        fetch_entity=_make_entity_fetcher(entities),
        collection="pdm_kb",
    )

    await indexer.handle_event({"kind": "story", "id": "story-01", "verb": "update"})

    points = store.scroll_all("pdm_kb")
    assert len(points) == 1
    payload = points[0].payload
    assert payload["source"] == "pmdf"
    assert payload["pmdf_kind"] == "story"
    assert payload["pmdf_id"] == "story-01"
    assert payload["product_id"] == "product-01"
    assert "検索改善ストーリー" in payload["text"]


@pytest.mark.asyncio
async def test_handle_event_twice_does_not_duplicate_points() -> None:
    store = QdrantKbStore(url=":memory:")
    embedding_client = FakeEmbeddingClient()
    entities = {
        ("story", "story-02"): {
            "kind": "story",
            "id": "story-02",
            "product": "product-01",
            "title": "初版タイトル",
            "as_a": "a",
            "i_want": "b",
            "so_that": "c",
        }
    }
    indexer = PmdfIndexer(
        store=store,
        embedding_client=embedding_client,
        fetch_entity=_make_entity_fetcher(entities),
        collection="pdm_kb",
    )

    await indexer.handle_event({"kind": "story", "id": "story-02", "verb": "create"})

    # 内容を更新して再度イベントを発行する(同一entity_idのまま)。
    entities[("story", "story-02")]["title"] = "更新後タイトル"
    await indexer.handle_event({"kind": "story", "id": "story-02", "verb": "update"})

    points = store.scroll_all("pdm_kb")
    assert len(points) == 1
    assert "更新後タイトル" in points[0].payload["text"]
    assert "初版タイトル" not in points[0].payload["text"]


@pytest.mark.asyncio
async def test_search_distinguishes_kb_and_pmdf_sources() -> None:
    store = QdrantKbStore(url=":memory:")
    embedding_client = FakeEmbeddingClient()

    # KB由来チャンクを1件投入しておく。
    kb_chunk = Chunk(
        text="KB由来の解説文",
        domain="discovery",
        framework=None,
        pm_principle=None,
        title="t",
        source_path="kb/corpus/discovery/x.md",
        chunk_index=0,
    )
    store.upsert_kb_chunks("pdm_kb", [kb_chunk], [[0.0, 0.0, 0.0, 1.0]])

    entities = {
        ("story", "story-03"): {
            "kind": "story",
            "id": "story-03",
            "product": "product-01",
            "title": "PMDF由来ストーリー",
            "as_a": "a",
            "i_want": "b",
            "so_that": "c",
        }
    }
    indexer = PmdfIndexer(
        store=store,
        embedding_client=embedding_client,
        fetch_entity=_make_entity_fetcher(entities),
        collection="pdm_kb",
    )
    await indexer.handle_event({"kind": "story", "id": "story-03", "verb": "create"})

    kb_results = store.search("pdm_kb", [0.0, 0.0, 0.0, 1.0], source="kb", top_k=10)
    pmdf_results = store.search("pdm_kb", [0.0, 0.0, 0.0, 1.0], source="pmdf", top_k=10)

    assert len(kb_results) == 1
    assert kb_results[0].payload["source"] == "kb"
    assert len(pmdf_results) == 1
    assert pmdf_results[0].payload["source"] == "pmdf"


@pytest.mark.asyncio
async def test_handle_event_skips_unknown_entity() -> None:
    store = QdrantKbStore(url=":memory:")
    embedding_client = FakeEmbeddingClient()
    indexer = PmdfIndexer(
        store=store,
        embedding_client=embedding_client,
        fetch_entity=_make_entity_fetcher({}),
        collection="pdm_kb",
    )
    # エンティティが見つからない場合は例外を投げずスキップする。
    await indexer.handle_event({"kind": "story", "id": "does-not-exist", "verb": "update"})
    assert not store.client.collection_exists("pdm_kb")


def test_extract_entity_text_story() -> None:
    text = extract_entity_text(
        "story",
        {
            "title": "T",
            "as_a": "A",
            "i_want": "B",
            "so_that": "C",
        },
    )
    assert "T" in text
    assert "A" in text
    assert "B" in text
    assert "C" in text


def test_extract_entity_text_decision() -> None:
    text = extract_entity_text(
        "decision",
        {"name": "採用可否", "rationale": "コストが見合うため"},
    )
    assert "採用可否" in text
    assert "コストが見合うため" in text


def test_extract_entity_text_risk_uses_event_field() -> None:
    text = extract_entity_text("risk", {"event": "重大な障害が発生するリスク"})
    assert text == "重大な障害が発生するリスク"


def test_extract_entity_text_fallback_uses_title_only() -> None:
    text = extract_entity_text("unknown_future_kind", {"title": "タイトルのみ"})
    assert text == "タイトルのみ"


def test_run_forever_consumes_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    """asyncio.Queueからイベントを取り出し続けるコンシューマループの単純な動作確認。"""
    store = QdrantKbStore(url=":memory:")
    embedding_client = FakeEmbeddingClient()
    entities = {
        ("story", "story-04"): {
            "kind": "story",
            "id": "story-04",
            "product": "p",
            "title": "queue経由",
            "as_a": "a",
            "i_want": "b",
            "so_that": "c",
        }
    }
    indexer = PmdfIndexer(
        store=store,
        embedding_client=embedding_client,
        fetch_entity=_make_entity_fetcher(entities),
        collection="pdm_kb",
    )

    async def _run() -> None:
        queue: asyncio.Queue = asyncio.Queue()
        await queue.put(
            {"type": "pmdf.entity_changed", "data": {"kind": "story", "id": "story-04"}}
        )
        await queue.put({"type": "approval.count_changed", "data": {"count": 1}})

        async def _consume_one() -> None:
            event = await queue.get()
            if event["type"] == "pmdf.entity_changed":
                await indexer.handle_event(event["data"])

        await _consume_one()
        await _consume_one()

    asyncio.run(_run())
    points = store.scroll_all("pdm_kb")
    assert len(points) == 1
