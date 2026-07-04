"""kb_ingest.chunking のテスト(E6-2)。

見出し/段落ベースのチャンク分割、サイズ上限、front-matterメタデータの
継承を検証する。
"""

from __future__ import annotations

from kb_ingest.chunking import Chunk, chunk_document


def test_short_document_becomes_single_chunk() -> None:
    body = "短い本文です。"
    front_matter = {
        "domain": "discovery",
        "framework": "jtbd",
        "pm_principle": None,
        "title": "サンプル",
        "source": "original",
        "license": "internal",
    }
    chunks = chunk_document(body, front_matter, source_path="kb/corpus/discovery/x.md")
    assert len(chunks) == 1
    assert chunks[0].text.strip() == body
    assert chunks[0].domain == "discovery"
    assert chunks[0].framework == "jtbd"
    assert chunks[0].pm_principle is None
    assert chunks[0].source_path == "kb/corpus/discovery/x.md"


def test_long_document_is_split_into_multiple_chunks() -> None:
    # 500字上限を大きく超える長文(段落区切りなし)を用意する。
    body = "あ" * 1500
    front_matter = {
        "domain": "metrics",
        "title": "長文サンプル",
        "source": "original",
        "license": "internal",
    }
    chunks = chunk_document(
        body, front_matter, source_path="kb/corpus/metrics/long.md", max_chars=500
    )
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.text) <= 500
        # 全チャンクがfront-matterメタデータを継承していること
        assert chunk.domain == "metrics"
        assert chunk.source_path == "kb/corpus/metrics/long.md"


def test_chunk_document_splits_on_headings() -> None:
    body = "# 見出し1\n本文1の内容がここに入る。\n\n# 見出し2\n本文2の内容がここに入る。\n"
    front_matter = {
        "domain": "discovery",
        "title": "見出しテスト",
        "source": "original",
        "license": "internal",
    }
    chunks = chunk_document(body, front_matter, source_path="p.md", max_chars=5000)
    assert len(chunks) == 2
    assert "見出し1" in chunks[0].text
    assert "見出し2" in chunks[1].text


def test_empty_body_produces_no_chunks() -> None:
    front_matter = {
        "domain": "discovery",
        "title": "空",
        "source": "original",
        "license": "internal",
    }
    chunks = chunk_document("   \n\n  ", front_matter, source_path="p.md")
    assert chunks == []


def test_chunk_dataclass_fields() -> None:
    chunk = Chunk(
        text="text",
        domain="discovery",
        framework=None,
        pm_principle=None,
        title="t",
        source_path="p.md",
        chunk_index=0,
    )
    assert chunk.text == "text"
    assert chunk.chunk_index == 0
