# kb-ingest

知識ベース(KB)コーパスの front-matter 検証、チャンク分割、
埋め込み取得(model-gateway 経由、論理名 `pdm-embed`)、Qdrant への
投入を行うサービス。E6(知識ベース)実装の一部。

## 主なモジュール

- `kb_ingest.frontmatter`: `kb/corpus/**/*.md` の YAML front-matter
  スキーマ検証(pydantic)。
- `kb_ingest.chunking`: 見出しベースのチャンク分割。
- `kb_ingest.embedding`: model-gateway(論理名 `pdm-embed`)経由の
  埋め込み取得クライアント。
- `kb_ingest.qdrant_store`: Qdrant へのコレクション作成・upsert・検索。
- `kb_ingest.pmdf_indexer`: api-server の WebSocket イベント
  (`pmdf.entity_changed`)を購読し、PMDF エンティティをベクトル化して
  Qdrant へ投入する(`source="pmdf"`)。
- `kb_ingest.cli`: `kb-ingest validate|ingest|recreate` CLI(typer)。

## CLI

```bash
uv run kb-ingest validate kb/corpus
uv run kb-ingest ingest kb/corpus --collection pdm_kb
uv run kb-ingest recreate --collection pdm_kb --dim 768
```
