"""kb-ingest CLI(typer)。

`kb-ingest validate <corpus_dir>`: front-matterスキーマ検証。
`kb-ingest ingest <corpus_dir>`: チャンク分割→埋め込み→Qdrant投入(E6-2)。
`kb-ingest recreate`: 埋め込み次元変更時のコレクション再作成(E6-4)。
"""

from __future__ import annotations

from pathlib import Path

import typer
from pydantic import ValidationError

from kb_ingest.frontmatter import CorpusFrontMatter, parse_markdown_file

app = typer.Typer(help="KBコーパスのfront-matter検証・ingestion CLI")


@app.command()
def validate(
    corpus_dir: Path = typer.Argument(..., help="検証対象のコーパスディレクトリ"),
) -> None:
    """`corpus_dir` 配下の全Markdownファイルのfront-matterを検証する。"""
    if not corpus_dir.is_dir():
        typer.echo(f"エラー: {corpus_dir} はディレクトリではありません", err=True)
        raise typer.Exit(code=1)

    files = sorted(corpus_dir.rglob("*.md"))
    if not files:
        typer.echo(f"警告: {corpus_dir} 配下にMarkdownファイルがありません")
        raise typer.Exit(code=0)

    errors: list[str] = []
    for path in files:
        try:
            front_matter, _body = parse_markdown_file(path)
            CorpusFrontMatter.model_validate(front_matter)
        except (ValueError, ValidationError) as exc:
            errors.append(f"{path}: {exc}")

    if errors:
        for error in errors:
            typer.echo(error, err=True)
        typer.echo(f"検証失敗: {len(errors)}/{len(files)} 件でエラー", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"検証成功: {len(files)} 件すべて有効です")


@app.command()
def ingest(
    corpus_dir: Path = typer.Argument(..., help="投入対象のコーパスディレクトリ"),
    collection: str = typer.Option("pdm_kb", help="Qdrantコレクション名"),
    qdrant_url: str = typer.Option(":memory:", help="QdrantのURL(既定はインメモリ)"),
    embedding_gateway_url: str = typer.Option(
        "http://model-gateway:4000", help="model-gatewayのベースURL"
    ),
) -> None:
    """コーパスをチャンク分割→埋め込み→Qdrantへ投入する(E6-2)。"""
    import asyncio

    from kb_ingest.chunking import chunk_document
    from kb_ingest.embedding import GatewayEmbeddingClient
    from kb_ingest.qdrant_store import QdrantKbStore

    if not corpus_dir.is_dir():
        typer.echo(f"エラー: {corpus_dir} はディレクトリではありません", err=True)
        raise typer.Exit(code=1)

    async def _run() -> int:
        client = GatewayEmbeddingClient(base_url=embedding_gateway_url)
        store = QdrantKbStore(url=qdrant_url)
        total_chunks = 0
        for path in sorted(corpus_dir.rglob("*.md")):
            front_matter, body = parse_markdown_file(path)
            CorpusFrontMatter.model_validate(front_matter)
            chunks = chunk_document(body, front_matter, source_path=str(path))
            if not chunks:
                continue
            embeddings = await client.embed([c.text for c in chunks])
            store.upsert_kb_chunks(collection, chunks, embeddings)
            total_chunks += len(chunks)
        return total_chunks

    total = asyncio.run(_run())
    typer.echo(f"投入完了: {total} チャンク")


@app.command()
def recreate(
    collection: str = typer.Option(..., help="再作成対象のQdrantコレクション名"),
    dim: int = typer.Option(..., help="新しい埋め込み次元数"),
    qdrant_url: str = typer.Option(":memory:", help="QdrantのURL(既定はインメモリ)"),
) -> None:
    """埋め込み次元数の変更に伴い、コレクションを削除・新次元で再作成する(E6-4)。"""
    from kb_ingest.qdrant_store import QdrantKbStore

    store = QdrantKbStore(url=qdrant_url)
    store.recreate_collection(collection, dim=dim)
    typer.echo(f"コレクション '{collection}' を次元数 {dim} で再作成しました")


if __name__ == "__main__":
    app()
