# 実装状況(IMPLEMENTATION_STATE)

このドキュメントは、新規セッション(このファイルと `CLAUDE.md` 以外の
記憶を持たないエージェント)が最小限の情報で作業を再開できることを
目的とする。作業を再開する前に、このファイルと `CLAUDE.md` を必ず読むこと。

## 現在のフェーズ

- **Phase 0(リポジトリ基盤と開発環境, E1)**: 実施中。E1-1〜E1-5は完了、
  E1-6(Takumi Guard)は要人間対応(`needs-human`ラベル)で保留の可能性あり。
- **Phase 1(E2: PMDFパッケージ)**: **完了**。E2-1〜E2-9(#18〜#26)、
  親issue #2 全てクローズ済み。次は Phase 2(E3: pmdf-store + api-server、
  E4: model-gateway + compose統合)へ進む。
- **アクティブブランチ: `develop`**。全実装作業は `develop` ブランチ上で
  行う。`main` への切替・PRマージはユーザーが手動で行う方針のため、
  実装エージェントは `main` へのswitchや `gh pr merge` を行わない。

## 再開手順

1. `git switch develop && git pull` でローカルを最新化する。
2. `gh issue list --repo sotanengel/project-management-ai --state open --label in-progress`
   で中断中のイシューを確認する。
3. 見つかった場合、そのイシューの最新コメントで「完了内容/残作業/次の一手」
   を確認し、そこから再開する。
4. 見つからない場合、下記のエピック対応表を phase 番号の小さい順・
   エピック番号の小さい順に走査し、状態が「未着手」の最小番号の
   イシュー(親イシューまたは先頭のsub-issue)に着手する。
5. 着手前に `gh issue view <番号>` で受け入れ条件を確認し、
   `gh issue edit <番号> --add-label in-progress` を付与してから実装する。

## エピック→GitHub issue番号 対応表

| エピック | issue番号 | 内容                          | phase      | 状態                               |
| -------- | --------- | ----------------------------- | ---------- | ---------------------------------- |
| E1       | #1        | リポジトリ基盤と開発環境      | phase:0    | 進行中(E1-1〜E1-5完了、E1-6要確認) |
| E2       | #2        | PMDFパッケージ(packages/pmdf) | phase:1    | **完了**(E2-1〜E2-9 = #18〜#26)    |
| E3       | #3        | pmdf-store + api-server       | phase:2    | 未着手                             |
| E4       | #4        | model-gateway + compose統合   | phase:2    | 未着手                             |
| E5       | #5        | agent-core                    | phase:3    | 未着手                             |
| E6       | #6        | 知識ベース                    | phase:3    | 未着手                             |
| E7       | #7        | web-ui                        | phase:3    | 未着手                             |
| E8       | #8        | 自己学習ループ                | phase:4    | 未着手                             |
| E9       | #9        | 運用機能                      | phase:5    | 未着手                             |
| E10      | #10       | E2E受け入れとドキュメント     | phase:5    | 未着手                             |
| E11      | #11       | Tier-S AWSデプロイ            | (deferred) | 保留(ラベル`deferred`)             |

サブイシュー番号は各エピックissue本文またはGitHub上のsub-issueリンクを参照。
E1のサブイシューは #12(E1-1)〜#17(E1-6)。

## packages/pmdf 公開インターフェース(E3以降が利用する想定)

`packages/pmdf` はE2で実装完了。以降のエピック(E3: pmdf-store/api-server、
E5: agent-core 等)は本パッケージの以下のAPIを介してPMDFを操作する
(schemas/pmdf/v1/*.schema.jsonがフォーマットの正であることに変わりはない)。

- `pmdf.schema_registry`: `validate_entity(data, kind=None)` / `get_validator(kind)`
  — JSON Schemaによる検証。`jsonschema.exceptions.ValidationError`を送出。
- `pmdf.models`: `KIND_TO_MODEL: dict[str, type[PmdfBase]]`(14エンティティ全種)。
  各モデルは`model_config = ConfigDict(extra="allow")`+`x_`接頭辞以外の
  未知フィールド拒否バリデータを持つ`PmdfBase`を継承。
- `pmdf.io`: `load_entity(path) -> PmdfBase` / `save_entity(entity, base_dir) -> Path`
  (1エンティティ1ファイル規約 `<kind>/<id>.yaml`)、
  `dict_to_yaml` / `yaml_to_dict`(ruamel.yaml round-trip)、
  `entity_to_json_dict(entity) -> dict`(**Noneフィールドを省略**するJSON変換。
  JSON Schema再検証を伴う経路では必ずこちらを使うこと。単純な
  `model_dump(mode="json")`はNoneを明示出力しスキーマ不整合を起こし得る)。
- `pmdf.ids`: `generate_id(kind) -> str`(接頭辞付き・単調増加ULID、
  スレッドセーフ)、`KIND_TO_PREFIX`。
- `pmdf.validate`: `validate_references(entities: list[PmdfBase]) -> list[ReferenceError]`
  (各モデルの`Field(json_schema_extra={"ref_kind": ...})`メタデータから
  参照フィールドを動的収集。新しい参照フィールドはモデル側にメタデータを
  追加するだけで自動的に検証対象になる)。
- `pmdf.bundle.export`: `export_bundle(entities, scope: ExportScope, output_path, ...)`
  (`*.pmdf.tar.gz`生成、`sanitize_profile`引数でE2-8のサニタイズを適用可)。
- `pmdf.bundle.import_`: `validate_bundle` / `diff_preview` / `apply_bundle`。
  `apply_bundle`は`PmdfStore`という`Protocol`(`save(entity) -> None`のみ要求)
  経由でストア層に書き込む。**E3のpmdf-store層はこのProtocolを満たす
  具象クラスを実装し、`apply_bundle`に注入する想定**(本パッケージは
  ストアの永続化方式(Git等)に一切依存しない)。
- `pmdf.sanitize`: `SanitizeProfile` / `load_sanitize_profile(path)` /
  `sanitize_entity(entity_dict, profile)`。
- `pmdf.convert.csv_` / `pmdf.convert.markdown`: story/roadmap_itemのCSV化、
  decision/reportのMarkdown化。
- `pmdf.migrate`: `MIGRATIONS`レジストリ、`register_migration`、
  `migrate_entity(data, target_version)`(BFSで複数ホップの変換チェーンを
  探索)。
- `pmdf.cli`(`app = typer.Typer()`): `pmdf validate/export/import/convert/migrate`。
  `project.scripts`経由で`pmdf`コマンドとして利用可能(`uv run pmdf --help`)。

### 実装中に発見・修正した重要な設計上の注意点(E3以降も踏襲すること)

1. **Pydanticの`model_dump(mode="json")`はOptionalフィールドを常に明示
   `null`で出力する**が、対応するJSON Schemaは`null`非許容の型定義が多い
   (JSON Schemaの「フィールド省略可」とPydanticの「値はnull」は等価ではない)。
   YAML保存・バンドルexport・スキーマ再検証を伴う箇所は必ず
   `pmdf.io.entity_to_json_dict()`(`exclude_none=True`)を経由すること。
2. **tar/zip等アーカイブ内のパスは`pathlib.Path`の`/`結合ではなく
   `.as_posix()`で明示的にPOSIX形式にすること**(Windows上で`Path`を
   そのまま文字列化するとバックスラッシュ区切りになり、Linux上で作られた
   バンドルと互換性が失われる)。
3. ULID(接頭辞付きID)のパターンは`^[a-z]+-[0-9A-HJKMNP-TV-Z]{26}$`
   (Crockford Base32、`I`/`L`/`O`/`U`を含まない)。テストフィクスチャで
   ID文字列を手書きする際は必ず26文字・上記文字集合であることを
   スクリプトで検証してから使うこと(本実装中に複数回、桁数・使用禁止
   文字の誤りによる回帰を作り込みかけた)。

## 環境メモ

- **OS**: Windows 11。開発は Git Bash 経由のBashツール、または PowerShell
  を使用。
- **改行コード**: リポジトリ内は `.gitattributes`(`* text=auto eol=lf`)に
  よりLF強制。Windows側のエディタ設定に関わらずコミット時にLF化される。
- **パス長制限**: Windows既定では260文字のMAX_PATH制限がある場合がある。
  深い階層のパッケージ構成では `git config core.longpaths true` の設定や、
  Windows側の長パス有効化(グループポリシー/レジストリ)を検討すること。
  本プロジェクトでは2026-07-04時点で長パスに起因する問題は未発生。
- **Python**: `uv` がPython 3.12を管理・提供する
  (`uv python install 3.12` / `uv python pin 3.12`)。システムの
  `python`/`python3` ランチャーが破損している場合があるため、
  Pythonコマンドは必ず `uv run python ...` 経由で実行すること。
- **Takumi Guard(Shisho)トークン**: `tg_anon_...` 形式のメール認証レベル
  トークンは **ユーザーレベル設定のみ**(`%USERPROFILE%\.npmrc` 等)に置く。
  リポジトリ内のファイル・イシューコメント・コミットメッセージには
  絶対に含めないこと。詳細は `docs/takumi-guard.md` を参照。
- **`.env`**: `.env.example` をコピーして `.env` を作成する。`.env` 自体は
  `.gitignore` によりコミット対象外。実運用のシークレットはSecrets
  Manager / SSM Parameter Store等で管理し、コードに直書きしない。

## 決定事項ログ

| 日付       | 決定内容                                                                                                                                    | 理由                                                                                                                                                           |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-07-04 | 全実装を `develop` ブランチ上で行う一本運用に変更。PRマージはユーザーが手動で行う                                                           | 複数セッション・複数エージェントによる並行実装でブランチ管理コストを下げつつ、最終マージの可否判断をユーザーに残すため                                         |
| 2026-07-04 | E1-1〜E1-4の検証はローカル環境(uv 0.10.10, Docker 29.5.3, npm 11.11.0)で実施し、実CIの発火結果もpush後に `gh run list` で確認する運用とした | ローカル検証のみでは実際のGitHub Actions環境固有の差異(OS、キャッシュ等)を見逃す可能性があるため                                                               |
| 2026-07-04 | E2完了。story.priority等のOptionalフィールドは`entity_to_json_dict()`(`exclude_none=True`)経由でJSON化する規約とした                        | Pydanticの`model_dump(mode="json")`はNoneを明示出力するが、JSON Schema側はnull非許容の型定義が多く、バンドルimportでのスキーマ再検証時に型不一致が発生するため |
| 2026-07-04 | E2-7の`apply_bundle`はストア層を`PmdfStore` Protocol(`save(entity)`のみ)経由で受け取る設計とした                                            | `packages/pmdf`単体はストアの永続化方式(Git等)に依存させず、E3のpmdf-store層が具象実装を注入できるようにするため                                               |
