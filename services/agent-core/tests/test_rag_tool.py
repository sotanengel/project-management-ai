"""`agent_core.tools.rag_tool.search_knowledge`のテスト(E5-3)。

`qdrant-client`の`:memory:`モードでテスト用コレクションを作り、KB
チャンク・PMDFエンティティのダミーデータを投入した状態で、
source/domain/frameworkフィルタや出典メタデータが正しく機能する
ことを検証する。埋め込みはモック(次元4の決定的ベクトル)を使う。
"""

from __future__ import annotations

import pytest
from agent_core.tools.rag_tool import SearchResult, search_knowledge
from kb_ingest.chunking import Chunk
from kb_ingest.qdrant_store import QdrantKbStore

COLLECTION = "pdm_kb_test"


class FakeEmbeddingClient:
    """`embed`呼び出し回数・入力を記録しつつ、決定的な4次元ベクトルを返す。"""

    def __init__(self, vector: list[float] | None = None) -> None:
        self.calls: list[list[str]] = []
        self._vector = vector or [1.0, 0.0, 0.0, 0.0]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [self._vector for _ in texts]


def _kb_chunk(*, domain: str, framework: str | None, text: str, index: int) -> Chunk:
    return Chunk(
        text=text,
        domain=domain,
        framework=framework,
        pm_principle=None,
        title=f"title-{index}",
        source_path=f"kb/corpus/{domain}/sample.md",
        chunk_index=index,
    )


@pytest.fixture
def store_with_data() -> QdrantKbStore:
    store = QdrantKbStore(url=":memory:")

    kb_chunks = [
        _kb_chunk(domain="discovery", framework="jtbd", text="JTBDの説明文", index=0),
        _kb_chunk(domain="project_management", framework=None, text="PMBOKの説明文", index=1),
    ]
    # 同一方向ベクトル(類似度が高くなるよう単純化)。
    store.upsert_kb_chunks(COLLECTION, kb_chunks, [[1.0, 0.0, 0.0, 0.0], [0.9, 0.1, 0.0, 0.0]])

    store.upsert_pmdf_entity(
        COLLECTION,
        pmdf_kind="story",
        pmdf_id="story-01HAGENTCCCCCCCCCCCCCCCCCC",
        product_id="prod-01HAGENTAAAAAAAAAAAAAAAAAA",
        text="検索機能を使いたいというストーリー",
        embedding=[0.0, 1.0, 0.0, 0.0],
    )

    return store


@pytest.mark.asyncio
async def test_search_knowledge_source_kb_returns_only_kb_results(
    store_with_data: QdrantKbStore,
) -> None:
    embedding_client = FakeEmbeddingClient(vector=[1.0, 0.0, 0.0, 0.0])

    results = await search_knowledge(
        "JTBDとは",
        source="kb",
        store=store_with_data,
        embedding_client=embedding_client,
        collection=COLLECTION,
    )

    assert results
    assert all(r.source == "kb" for r in results)


@pytest.mark.asyncio
async def test_search_knowledge_source_pmdf_returns_only_pmdf_results(
    store_with_data: QdrantKbStore,
) -> None:
    embedding_client = FakeEmbeddingClient(vector=[0.0, 1.0, 0.0, 0.0])

    results = await search_knowledge(
        "ストーリーを探したい",
        source="pmdf",
        store=store_with_data,
        embedding_client=embedding_client,
        collection=COLLECTION,
    )

    assert results
    assert all(r.source == "pmdf" for r in results)
    assert results[0].pmdf_kind == "story"
    assert results[0].pmdf_id == "story-01HAGENTCCCCCCCCCCCCCCCCCC"


@pytest.mark.asyncio
async def test_search_knowledge_domain_filter(store_with_data: QdrantKbStore) -> None:
    embedding_client = FakeEmbeddingClient(vector=[1.0, 0.0, 0.0, 0.0])

    results = await search_knowledge(
        "ディスカバリーの原則",
        source="kb",
        domain="discovery",
        store=store_with_data,
        embedding_client=embedding_client,
        collection=COLLECTION,
    )

    assert results
    assert all(r.domain == "discovery" for r in results)


@pytest.mark.asyncio
async def test_search_knowledge_results_include_evidence_metadata(
    store_with_data: QdrantKbStore,
) -> None:
    embedding_client = FakeEmbeddingClient(vector=[1.0, 0.0, 0.0, 0.0])

    results = await search_knowledge(
        "JTBDとは",
        source="kb",
        store=store_with_data,
        embedding_client=embedding_client,
        collection=COLLECTION,
    )

    assert results
    first = results[0]
    assert isinstance(first, SearchResult)
    assert first.text
    assert first.score is not None
    assert first.source == "kb"
    assert first.domain == "discovery"
    assert first.framework == "jtbd"
    assert first.pmdf_kind is None
    assert first.pmdf_id is None


@pytest.mark.asyncio
async def test_search_knowledge_all_returns_both_sources(store_with_data: QdrantKbStore) -> None:
    embedding_client = FakeEmbeddingClient(vector=[0.5, 0.5, 0.0, 0.0])

    results = await search_knowledge(
        "何でも検索",
        source="all",
        store=store_with_data,
        embedding_client=embedding_client,
        collection=COLLECTION,
        top_k=10,
    )

    sources = {r.source for r in results}
    assert sources == {"kb", "pmdf"}


@pytest.mark.asyncio
async def test_search_knowledge_uses_embedding_client_with_query_text(
    store_with_data: QdrantKbStore,
) -> None:
    embedding_client = FakeEmbeddingClient(vector=[1.0, 0.0, 0.0, 0.0])

    await search_knowledge(
        "テストクエリ文字列",
        source="kb",
        store=store_with_data,
        embedding_client=embedding_client,
        collection=COLLECTION,
    )

    assert embedding_client.calls == [["テストクエリ文字列"]]


def test_search_result_to_evidence_dict_for_kb_source() -> None:
    result = SearchResult(
        text="本文",
        score=0.9,
        source="kb",
        domain="discovery",
        framework="jtbd",
        pmdf_kind=None,
        pmdf_id=None,
    )

    evidence = result.to_evidence_dict()

    assert evidence == {
        "source": "kb",
        "domain": "discovery",
        "framework": "jtbd",
        "excerpt": "本文",
    }


def test_search_result_to_evidence_dict_for_pmdf_source() -> None:
    result = SearchResult(
        text="本文",
        score=0.9,
        source="pmdf",
        domain=None,
        framework=None,
        pmdf_kind="story",
        pmdf_id="story-01HAGENTCCCCCCCCCCCCCCCCCC",
    )

    evidence = result.to_evidence_dict()

    assert evidence == {
        "source": "pmdf",
        "kind": "story",
        "id": "story-01HAGENTCCCCCCCCCCCCCCCCCC",
    }
