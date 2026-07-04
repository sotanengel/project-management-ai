"""`kb-ingest ingest` CLIコマンドの結合テスト(E6-2)。

respxでmodel-gatewayの埋め込みエンドポイントをモックし、qdrant-clientの
:memory:モードへ実際にingestionが行われることを確認する。
"""

from __future__ import annotations

from pathlib import Path

import httpx
import respx
from kb_ingest.chunking import chunk_document
from kb_ingest.frontmatter import parse_markdown_file
from typer.testing import CliRunner

runner = CliRunner()


def _write_sample_corpus(corpus_dir: Path) -> None:
    (corpus_dir / "discovery").mkdir(parents=True)
    (corpus_dir / "discovery" / "a.md").write_text(
        "---\ndomain: discovery\ntitle: t1\nsource: original\nlicense: internal\n---\n"
        + ("本文。" * 100),
        encoding="utf-8",
    )
    (corpus_dir / "project_management").mkdir(parents=True)
    (corpus_dir / "project_management" / "b.md").write_text(
        "---\ndomain: project_management\npm_principle: tailoring\n"
        "title: t2\nsource: original\nlicense: internal\n---\n短い本文。",
        encoding="utf-8",
    )


def test_ingest_end_to_end_with_mocked_embeddings(tmp_path: Path) -> None:
    corpus_dir = tmp_path / "corpus"
    _write_sample_corpus(corpus_dir)

    # 期待されるチャンク総数を独立に計算しておく(CLIの結果と突き合わせる)。
    expected_chunk_count = 0
    for path in sorted(corpus_dir.rglob("*.md")):
        front_matter, body = parse_markdown_file(path)
        expected_chunk_count += len(chunk_document(body, front_matter, source_path=str(path)))

    with respx.mock:

        def _embeddings_response(request: httpx.Request) -> httpx.Response:
            import json

            payload = json.loads(request.content)
            n = len(payload["input"])
            return httpx.Response(
                200,
                json={"data": [{"embedding": [0.1, 0.2, 0.3], "index": i} for i in range(n)]},
            )

        respx.post("http://model-gateway:4000/embeddings").mock(side_effect=_embeddings_response)

        from kb_ingest.cli import app

        result = runner.invoke(
            app,
            [
                "ingest",
                str(corpus_dir),
                "--collection",
                "pdm_kb_test",
                "--qdrant-url",
                ":memory:",
                "--embedding-gateway-url",
                "http://model-gateway:4000",
            ],
        )

    assert result.exit_code == 0, result.output
    assert str(expected_chunk_count) in result.output
