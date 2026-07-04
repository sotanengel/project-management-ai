# KB埋め込みモデル切替手順(E6-4)

本ドキュメントは、KB(知識ベース)・PMDFインデクシングで使用する埋め込み
モデル(論理名 `pdm-embed`)を切り替える際の手順を示す(FR-KB-05)。

## 前提

- 埋め込みモデルの実体は `services/model-gateway/litellm.config.yaml` の
  `pdm-embed` エントリでのみ指定する(AR-01: コード側は論理名
  `pdm-embed` のみを扱い、実モデル名を一切ハードコードしない)。
- `services/kb-ingest` は `kb_ingest.qdrant_store.QdrantKbStore` を通じて
  Qdrantコレクションを管理する。コレクションは作成時に決定した
  ベクトル次元数を保持し、既存コレクションと異なる次元数のベクトルを
  upsertしようとすると
  `kb_ingest.qdrant_store.CollectionDimensionMismatchError` が送出される。

## ケース1: 同一次元数のモデルへの切替

同じ次元数を持つ別モデルへ切り替える場合、`.env`(または
`litellm.config.yaml`)の `pdm-embed` エントリを変更するだけでよい。
コレクションの再作成・既存ベクトルの再投入は不要(ただし、意味的な
埋め込み空間はモデルごとに異なるため、検索精度を保つには全件の
再ingestionを推奨する)。

```bash
# .env の PDM_EMBED_MODEL を変更するのみ(kb-ingestのコード変更は不要)
uv run kb-ingest ingest kb/corpus --collection pdm_kb
```

## ケース2: 異なる次元数のモデルへの切替

次元数が変わる場合(例: 1536次元 → 768次元)、既存コレクションへは
そのままupsertできない。以下の手順でコレクションを再作成する。

1. **切替前の次元数を確認する**

   ```bash
   uv run python -c "
   from kb_ingest.qdrant_store import QdrantKbStore
   store = QdrantKbStore(url='<QDRANT_URL>')
   print(store.get_collection_dim('pdm_kb'))
   "
   ```

2. **`.env` の `PDM_EMBED_MODEL`(および必要なら
   `litellm.config.yaml`)を新モデルに変更する。**

3. **変更後にそのまま `kb-ingest ingest` を実行すると、次元不一致で
   明確なエラーメッセージとともに失敗する。** これは想定された
   ガードレールであり、意図せず異なる次元のベクトルが混在すること
   を防ぐ。

   ```text
   コレクション 'pdm_kb' の既存次元数(1536)と投入しようとした埋め込みの
   次元数(768)が一致しません。埋め込みモデルの次元数を変更した場合は
   `kb-ingest recreate --collection <name> --dim <new_dim>` で
   コレクションを削除・再作成してから再投入してください。
   ```

4. **コレクションを削除・新次元で再作成する。**

   ```bash
   uv run kb-ingest recreate --collection pdm_kb --dim 768 --qdrant-url <QDRANT_URL>
   ```

   `recreate` は既存コレクションを削除するため、**既存ベクトルは
   すべて失われる**(次元が変わるため既存ベクトルの流用はできない)。

5. **KBコーパス・PMDFエンティティを全件再投入する。**

   ```bash
   uv run kb-ingest ingest kb/corpus --collection pdm_kb --qdrant-url <QDRANT_URL>
   ```

   PMDF由来ベクトル(`source="pmdf"`)は `kb_ingest.pmdf_indexer.PmdfIndexer`
   による再インデックス(E6-3)で復元する。運用上は、全PMDFエンティティに
   対して`pmdf.entity_changed`相当のイベントを再送する、またはストアの
   全エンティティを走査して`PmdfIndexer.handle_event`相当の処理を
   バッチ実行するスクリプトを用意することを推奨する。

## ダウンタイムの考慮事項

- 手順4(`recreate`)実行中から手順5(全件再投入)完了までの間、当該
  コレクションでの検索(`search_knowledge`、E5-3)は空または不完全な
  結果を返す。運用時間帯を考慮し、トラフィックの少ない時間帯に実施する
  か、切替中は新コレクション名(例: `pdm_kb_v2`)を用意して並行運用し、
  再投入完了後にコレクション参照先を切り替える(ブルーグリーン方式)
  ことを推奨する。
- `services/kb-ingest`自体はダウンタイムなしの自動フェイルオーバーを
  実装していない(Tier-Lの軽量構成のため)。ダウンタイムを許容しない
  要件がある場合は、上記のブルーグリーン方式の採用を検討すること。

## 検証スクリプト

`scripts/switch_embedding_model_check.sh`(実体は
`scripts/switch_embedding_model_check.py`)は、上記の切替シナリオを
モック埋め込みサーバ(次元1536→768)でシミュレートし、下記を自動検証する。

1. モデルA(次元1536)でのingestionが成功し、コレクション次元数が
   1536であること。
2. `.env`相当の設定変更のみ(kb-ingestのコード変更なし)でモデルB
   (次元768)へ切替後、再作成せずに再ingestionを試みると
   `CollectionDimensionMismatchError` が発生すること。
3. `recreate` でコレクションを削除・新次元(768)で再作成した後、
   モデルBで全件再投入・検索が正常に行えること。

```bash
bash scripts/switch_embedding_model_check.sh
```

終了コード `0` は検証成功、`1` は失敗、`2` は前提コマンド(`uv`)が
見つからない場合を示す。
