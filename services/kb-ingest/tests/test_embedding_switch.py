"""埋め込みモデル切替検証(E6-4)。

`pdm-embed`論理名の設定変更のみ(コード変更なし)で異なる次元の埋め込み
モデルへ切り替えられること、次元不一致時にコレクション再作成が必要な
旨の明確なエラーが出ること、再作成後は新次元で投入・検索が通ることを
検証する。
"""

from __future__ import annotations

import pytest
from kb_ingest.chunking import chunk_document
from kb_ingest.qdrant_store import CollectionDimensionMismatchError, QdrantKbStore

FRONT_MATTER = {
    "domain": "discovery",
    "title": "切替検証用",
    "source": "original",
    "license": "internal",
}


def _chunks() -> list:
    return chunk_document("サンプル本文です。" * 10, FRONT_MATTER, source_path="kb/corpus/x.md")


def test_ingest_with_model_a_dim_1536() -> None:
    store = QdrantKbStore(url=":memory:")
    chunks = _chunks()
    embeddings_a = [[0.1] * 1536 for _ in chunks]
    store.upsert_kb_chunks("pdm_kb_switch", chunks, embeddings_a)
    assert store.get_collection_dim("pdm_kb_switch") == 1536
    assert store.count("pdm_kb_switch") == len(chunks)


def test_switching_to_model_b_dim_768_without_recreate_raises_clear_error() -> None:
    store = QdrantKbStore(url=":memory:")
    chunks = _chunks()
    embeddings_a = [[0.1] * 1536 for _ in chunks]
    store.upsert_kb_chunks("pdm_kb_switch2", chunks, embeddings_a)

    embeddings_b = [[0.2] * 768 for _ in chunks]
    with pytest.raises(CollectionDimensionMismatchError) as exc_info:
        store.upsert_kb_chunks("pdm_kb_switch2", chunks, embeddings_b)

    message = str(exc_info.value)
    assert "1536" in message
    assert "768" in message
    assert "recreate" in message


def test_recreate_collection_then_reingest_with_new_dim_succeeds() -> None:
    store = QdrantKbStore(url=":memory:")
    chunks = _chunks()
    embeddings_a = [[0.1] * 1536 for _ in chunks]
    store.upsert_kb_chunks("pdm_kb_switch3", chunks, embeddings_a)

    # コレクション再作成(削除→新次元768で作成)。
    store.recreate_collection("pdm_kb_switch3", dim=768)
    assert store.count("pdm_kb_switch3") == 0
    assert store.get_collection_dim("pdm_kb_switch3") == 768

    # 全件再投入。
    embeddings_b = [[0.2] * 768 for _ in chunks]
    store.upsert_kb_chunks("pdm_kb_switch3", chunks, embeddings_b)
    assert store.count("pdm_kb_switch3") == len(chunks)

    # 新次元での検索が通ることを確認する。
    results = store.search("pdm_kb_switch3", [0.2] * 768, top_k=3)
    assert len(results) > 0


def test_recreate_cli_command(tmp_path) -> None:
    from kb_ingest.cli import app
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "recreate",
            "--collection",
            "pdm_kb_cli_recreate",
            "--dim",
            "768",
            "--qdrant-url",
            ":memory:",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "768" in result.output
