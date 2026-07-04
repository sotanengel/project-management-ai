"""kb_ingest.qdrant_store のテスト(E6-2)。

qdrant-clientの:memory:モードで、コーパスをchunk->embed(モック)->upsert
した後、コレクション内のポイント数がチャンク数と一致すること、
各ポイントのペイロードにdomain/framework/pm_principle/source="kb"が
含まれることを検証する。
"""

from __future__ import annotations

from kb_ingest.chunking import chunk_document
from kb_ingest.qdrant_store import QdrantKbStore

SAMPLE_MD_BODIES = [
    (
        "あ" * 1200,
        {
            "domain": "discovery",
            "framework": "jtbd",
            "pm_principle": None,
            "title": "サンプル1",
            "source": "original",
            "license": "internal",
        },
        "kb/corpus/discovery/sample1.md",
    ),
    (
        "い" * 300,
        {
            "domain": "project_management",
            "framework": None,
            "pm_principle": "tailoring",
            "title": "サンプル2",
            "source": "original",
            "license": "internal",
        },
        "kb/corpus/project_management/sample2.md",
    ),
]


def _fake_embed(chunks: list) -> list[list[float]]:
    # 決定的なダミー埋め込み(次元4)を返す。
    return [[float(i), 0.0, 0.0, 0.0] for i in range(len(chunks))]


def test_upsert_kb_chunks_point_count_matches_chunk_count() -> None:
    store = QdrantKbStore(url=":memory:")
    all_chunks = []
    for body, front_matter, path in SAMPLE_MD_BODIES:
        chunks = chunk_document(body, front_matter, source_path=path, max_chars=500)
        all_chunks.extend(chunks)

    embeddings = _fake_embed(all_chunks)
    store.upsert_kb_chunks("pdm_kb", all_chunks, embeddings)

    count = store.count("pdm_kb")
    assert count == len(all_chunks)
    assert len(all_chunks) > 2  # 長文が複数チャンクに分割されていることの確認


def test_upsert_kb_chunks_payload_contains_required_metadata() -> None:
    store = QdrantKbStore(url=":memory:")
    body, front_matter, path = SAMPLE_MD_BODIES[0]
    chunks = chunk_document(body, front_matter, source_path=path, max_chars=500)
    embeddings = _fake_embed(chunks)
    store.upsert_kb_chunks("pdm_kb", chunks, embeddings)

    points = store.scroll_all("pdm_kb")
    assert len(points) == len(chunks)
    for point in points:
        payload = point.payload
        assert payload["source"] == "kb"
        assert payload["domain"] == "discovery"
        assert payload["framework"] == "jtbd"
        assert payload["pm_principle"] is None
        assert payload["file_path"] == path
        assert "text" in payload


def test_upsert_kb_chunks_creates_collection_with_dynamic_dim() -> None:
    store = QdrantKbStore(url=":memory:")
    body, front_matter, path = SAMPLE_MD_BODIES[1]
    chunks = chunk_document(body, front_matter, source_path=path)
    embeddings = [[0.1, 0.2, 0.3, 0.4, 0.5] for _ in chunks]  # 次元5
    store.upsert_kb_chunks("pdm_kb_dim5", chunks, embeddings)

    info = store.get_collection_dim("pdm_kb_dim5")
    assert info == 5
