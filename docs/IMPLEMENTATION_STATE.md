# 実装状況(IMPLEMENTATION_STATE)

このドキュメントは、新規セッション(このファイルと `CLAUDE.md` 以外の
記憶を持たないエージェント)が最小限の情報で作業を再開できることを
目的とする。作業を再開する前に、このファイルと `CLAUDE.md` を必ず読むこと。

## 現在のフェーズ

- **Phase 0(リポジトリ基盤と開発環境, E1)**: 実施中。E1-1〜E1-5は完了、
  E1-6(Takumi Guard)は要人間対応(`needs-human`ラベル)で保留の可能性あり。
- **Phase 1(E2: PMDFパッケージ)**: **完了**。E2-1〜E2-9(#18〜#26)、
  親issue #2 全てクローズ済み。
- **Phase 2(E3: pmdf-store + api-server)**: **完了**。E3-1〜E3-10
  (#27〜#36)、親issue #3 全てクローズ済み。E3が提供するREST/WS API・
  認証方式・承認ゲートの使い方は本ファイル末尾の
  「api-server 公開インターフェース(E4以降が利用する想定)」を参照。
- **Phase 2 残り(E4: model-gateway + compose統合)**: **E4-1〜E4-3完了**
  (#37, #83, #84)。**E4-4(compose統合起動)・E4-5(バックエンド無改修
  切替検証、#85, #86)は未着手**。E7-1(web-ui骨格)完成後にPhase 3末で
  まとめて実施する方針のため、**親issue #4はopenのまま維持**している
  (E4-4/E4-5着手までクローズしないこと)。model-gatewayの論理名・
  エンドポイント・環境変数は本ファイル末尾の
  「model-gateway 公開インターフェース(E5以降が利用する想定)」を参照。
- **Phase 3(E6: 知識ベース)**: **完了**。E6-1〜E6-4(#47〜#50)、
  親issue #6 全てクローズ済み。`kb/corpus/`(独自著作コーパス)・
  `services/kb-ingest`(front-matter検証・チャンク分割・埋め込み・
  Qdrant投入・PMDFインデクサ・次元切替検証)を実装。E5(agent-core)が
  KB/PMDF横断検索を実装する際に使うインターフェースは本ファイル末尾の
  「kb-ingest 公開インターフェース(E5以降が利用する想定)」を参照。
- **Phase 3(E5: agent-core)**: **完了**。E5-1〜E5-9(#38〜#46)、
  親issue #5 全てクローズ済み。`services/agent-core`(LangGraphベースの
  4業務グラフ・PMDFツール・RAG検索・根拠明示・差戻フィードバック・
  チャット指示インターフェース)を実装。E7(web-ui)・E8(自己学習ループ)が
  利用するインターフェースは本ファイル末尾の
  「agent-core 公開インターフェース(E7/E8以降が利用する想定)」を参照。
- **アクティブブランチ: `develop`**。全実装作業は `develop` ブランチ上で
  行う。`main` への切替・PRマージはユーザーが手動で行う方針のため、
  実装エージェントは `main` へのswitchや `gh pr merge` を行わない。
- **Phase 3(E7: web-ui)**: **E7-1〜E7-6完了**(#51 be34c88 / #52
  bfab912 / #53 32bdbe3 / #54 8b052b0 / #55 d20a781 / #56 978dc63)。
  web-ui骨格(認証・APIクライアント(`openapi-typescript`生成型)・
  レイアウト・WebSocketクライアント・承認バッジ・プロダクトダッシュ
  ボード)に加え、承認キュー(PMDF diff表示・承認/差し戻し・履歴)、
  ドキュメントビューア(PMDF全14種kind別レンダリング+Git履歴ベースの
  版間diff)、エージェント活動ログ(タスク一覧・根拠(x_evidence)表示・
  監査ログ検索)を実装済み。**E7-7〜E7-9は未着手**。起動方法は
  `services/web-ui`で`pnpm install`(初回のみ)→`pnpm dev`(Vite開発
  サーバ、既定`http://localhost:5173`。APIサーバ接続先は`.env`の
  `VITE_API_BASE_URL`、既定`http://localhost:8000`)。検証は
  `pnpm lint && pnpm test && pnpm build`。
  E7-4〜E7-6で追加したapi-server側インターフェース(E7-7以降・
  E8/E9が参照する可能性あり):
  - `POST /approvals`の`ProposeRequest`/`ProposalResponse`に
    任意項目`draft`(起案内容の辞書)を追加。従来`target`
    (対象エンティティid)のみで変更後の値を復元できなかったため、
    承認キューのPMDF diff表示に必要な提案内容を持ち回れるようにした。
  - `GET /chat/tasks`(一覧、`status`フィルタ対応、新しい順)を追加。
    従来`GET /chat/tasks/{id}`のみで一覧取得手段が無かった。
  - `GET /audit/records`(`actor`/`action`/`kind`/`date_from`/
    `date_to`フィルタ、新しい順)を`api_server.routers.audit`として
    新設。E3-7は追記専用JSONL永続化層(`api_server.audit.log`)のみ
    提供しており、HTTP経由の検索APIが無かったため追加した。

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

| エピック | issue番号 | 内容                          | phase      | 状態                                                               |
| -------- | --------- | ----------------------------- | ---------- | ------------------------------------------------------------------ |
| E1       | #1        | リポジトリ基盤と開発環境      | phase:0    | 進行中(E1-1〜E1-5完了、E1-6要確認)                                 |
| E2       | #2        | PMDFパッケージ(packages/pmdf) | phase:1    | **完了**(E2-1〜E2-9 = #18〜#26)                                    |
| E3       | #3        | pmdf-store + api-server       | phase:2    | **完了**(E3-1〜E3-10 = #27〜#36)                                   |
| E4       | #4        | model-gateway + compose統合   | phase:2    | 一部完了(E4-1〜3=#37,#83,#84完了。E4-4,#85/E4-5,#86はE7-1後に実施) |
| E5       | #5        | agent-core                    | phase:3    | **完了**(E5-1〜E5-9 = #38〜#46)                                    |
| E6       | #6        | 知識ベース                    | phase:3    | **完了**(E6-1〜E6-4 = #47〜#50)                                    |
| E7       | #7        | web-ui                        | phase:3    | 一部完了(E7-1〜6=#51,#52,#53,#54,#55,#56完了。E7-7以降は未着手)    |
| E8       | #8        | 自己学習ループ                | phase:4    | 未着手                                                             |
| E9       | #9        | 運用機能                      | phase:5    | 未着手                                                             |
| E10      | #10       | E2E受け入れとドキュメント     | phase:5    | 未着手                                                             |
| E11      | #11       | Tier-S AWSデプロイ            | (deferred) | 保留(ラベル`deferred`)                                             |

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

## api-server 公開インターフェース(E4以降が利用する想定)

`services/api-server` はE3で実装完了。以降のエピック(E4:
model-gateway+compose統合、E5: agent-core、E7: web-ui 等)は本サービスの
REST/WebSocket APIを介してPMDF操作・認証・承認・監査・自律レベル制御を
行う。アプリ組み立ては `api_server.main.create_app()`(FastAPI)。

### 認証方式

- `POST /auth/login`(email+password、TOTP_ENABLED=true環境では
  追加で`totp_code`)→ `{access_token, token_type: "bearer"}`(JWT、
  `Authorization: Bearer <token>` ヘッダで以降のAPIに付与)。
- `POST /auth/refresh`(`{access_token}` → 新規トークン発行)。
- ロール: `admin`(全権限)/ `editor`(PMDF CRUD可・承認不可)/
  `viewer`(読み取りのみ)。`User.product_scopes`(`list[str] | None`)で
  viewerに対しプロダクト限定スコープを付与可能(`None`は全プロダクト
  アクセス可)。
- 管理者専用ユーザー管理: `POST /admin/users`,
  `PUT /admin/users/{id}/scopes`。
- ユーザーストア: `Settings.user_store_path`が指すJSONファイル
  (`api_server.auth.user_store`)。パスワードはargon2ハッシュのみ保持。

### PMDF CRUD API(`/pmdf`)

- `POST /pmdf/{kind}`(作成、admin/editor必須)、
  `GET /pmdf/{kind}`(一覧、`?product=<id>`で絞り込み)、
  `GET /pmdf/{kind}/{id}`(取得、`?ref=<commit>`で過去版取得)、
  `GET /pmdf/{kind}/{id}/history`(Gitコミット履歴)、
  `PUT /pmdf/{kind}/{id}`(更新、admin/editor必須)、
  `DELETE /pmdf/{kind}/{id}`(常に405、物理削除API無し。
  approval/decisionは明示メッセージ付き405、DR-06)。
- 書込前に必ずJSON Schema検証+参照整合チェックを行い、不正データは
  422で拒否(FR-DF-02)。
- プロダクトスコープ認可: viewerの`product_scopes`外エンティティへの
  GETは403(一覧は自動的にスコープ外を除外)。product自身・
  story/roadmap_item/release/risk/initiative/report/experiment/decision
  はスコープ対象、objective/metric/persona/stakeholder/approvalは
  グローバル扱い(スコープ対象外)。

### 承認ゲート(AC-06、最重要の安全機構)

- `POST /approvals`(起案、admin/editor):
  `{target, proposer}` → `{id, status: "proposed", ...}`。
- `POST /approvals/{id}/decide`(承認/差し戻し、admin/editor):
  `{decision: "approved"|"rejected", approver, reason}`
  (`reason`必須・空文字は422)。決定時に`Approval`(PMDF)エンティティを
  Git履歴として1コミット永続化。同一プロポーザルへの再decideは409。
- `GET /approvals?status=pending`(承認キュー一覧、E7-4のバックエンド)。
- L1業務の実行系エンドポイントは`api_server.approval.gate.
require_approval(entity_kind, autonomy_level="L1")`
  依存関数を**必ず**宣言すること。対象targetへの`approved`決定の
  `Approval`エンティティが無ければ403(承認レコードなしでは
  API直叩きを含め実行不可)。実証実装:
  `POST /pmdf/decision/{id}/execute`, `POST /roadmap/{id}/confirm`,
  `POST /release/{id}/go-no-go`
  (`api_server.routers.l1_execution.L1_GATED_ENDPOINTS`)。
  **E5で新規L1エンドポイントを追加する場合は、`require_approval`と
  `autonomy.emergency_stop.check_not_stopped`の両方を依存関数として
  宣言し、`L1_GATED_ENDPOINTS`と対応するテストの網羅性チェックにも
  追記すること**(依存関数の宣言漏れは自動テストで検出する運用)。

### 監査ログ(追記専用)

- `api_server.audit.log`: `AuditRecord`(timestamp/actor/action/
  target_kind/target_id/detail/prev_hash/hash、SHA-256ハッシュ連鎖)を
  `Settings.audit_log_path`(既定`data/audit/audit.log.jsonl`)へJSONL
  追記専用で記録。`append_record`/`verify_chain`(改ざん検知、該当行を
  報告)/`latest_hash`。書込系操作(PMDF create/update、承認decide、
  バンドルapply、自律レベル変更、緊急停止操作)から呼び出し済み。
  新規の書込系APIを追加する際は必ず`append_record`呼び出しを追加する
  こと。

### 自律レベル設定・緊急停止

- `GET /autonomy`(全設定一覧)、
  `PUT /autonomy/{product_id}/{business_function}`(admin専用、
  `{level: "L0"|"L1"|"L2"|"L3"}`)。`business_function`は
  vision/roadmap/discovery/backlog/kpi_monitoring/experiment/release/
  decision_record/stakeholder/initiative/periodic_review
  (FR-PD-01〜11)。未設定時はL0(最も保守的)。
- `POST /autonomy/emergency-stop` / `emergency-stop/release`
  (admin専用)。`api_server.autonomy.emergency_stop.check_not_stopped`
  依存関数をエージェント実行系エンドポイントに付与すると、停止中は409。
  **PMDF CRUD・UI向け閲覧/編集APIには付与しない**(AR-06: エージェント
  非依存でUI・PMDFは稼働し続ける)。

### import/export API(バンドル)

- `POST /bundles/export`(`{product_ids, kinds}`、省略時は全件) →
  `*.pmdf.tar.gz`をレスポンスボディで返却(`application/gzip`)。
- `POST /bundles/import/validate`(multipartファイルアップロード) →
  スキーマ検証+差分プレビュー(JSON、`is_valid`/`diffs`)。不正バンドルは
  422。
- `POST /bundles/import/apply`(multipart、`resolutions`はJSON文字列の
  Formフィールド、conflict時のid→`"incoming"|"existing"`解決方針) →
  ストアへ1コミットとして適用(`PmdfStore.save_all`)。監査ログに1
  エントリ記録。

### WebSocketイベント配信(FR-UI-11)

- `WS /ws/events?token=<JWT>`(クエリパラメータでJWT認証。無効・
  未提供はクローズコード1008で拒否)。
- イベント種別: `pmdf.entity_changed`(`{kind, id, verb}`、PMDF
  create/update時)、`approval.count_changed`(`{count}`、
  承認起案・決定時のpending件数)、`agent.activity`(`{task_id, status,
product_id, intent}`、E5-9のチャットタスク受理/実行中/完了/失敗時。
  下記チャットAPIを参照)。
- `api_server.events.bus.get_event_bus()`で共有`InMemoryEventBus`
  シングルトンを取得し`await bus.publish(event_type, data)`で配信
  (単一プロセス前提のasyncio.Queue実装。将来複数レプリカ構成では
  `EventBus` Protocolを満たすRedis pub/sub等に差し替え可能)。

### チャット指示API(`/chat`、E5-9、FR-UI-07バックエンド)

- `POST /chat/instructions`(admin/editor必須、201): UIからの自然文指示
  を受け付け、`pending`状態のチャットタスクとして登録する。ボディ:
  `{message, product_id}`。レスポンスは`ChatTask`
  (`{id, message, product_id, actor, status, result, error, intent}`)。
  登録時に`agent.activity`(`status: "pending"`)イベントを配信する。
- `GET /chat/tasks/{task_id}`(認証必須、200): チャットタスクの現在の
  実行状況を返す。未知のidは404。
- `POST /chat/tasks/{task_id}/transition`(admin/editor必須、200):
  agent-coreランナー(`agent_core.chat.handle_chat_instruction`)が
  タスク状態(`running`/`done`/`failed`)を報告するための内部API。
  ボディ: `{status, result, error, intent}`(`result`/`error`/`intent`は
  任意)。許可されない遷移(`done`/`failed`からの再遷移等)は409。
  遷移毎に`agent.activity`イベントを配信する。
- 実際のLLMによる意図分類・業務グラフディスパッチはagent-core側
  (`services/agent-core/src/agent_core/chat.py`)の責務であり、
  api-server側はタスクの受付・状態永続化(`api_server.chat.task_store`、
  JSONファイル、`approval.proposal_store`と同様のパターン)・
  イベント配信のみを担う(api-serverはagent-coreをimportしない、
  依存方向はagent-core→api-serverのみを維持)。

### コストAPI(`/costs`、E4-3)

- `POST /costs/usage`(admin/editor必須、201): LLM呼び出し1件分の
  usageを記録する。ボディ: `{logical_name, model, prompt_tokens,
completion_tokens, latency_ms, cost_jpy, actor, detail}`
  (全て概ね任意、`logical_name`/`model`のみ必須。数値系は`ge=0`)。
  `agent-core`(E5)・学習ジョブ(E8)はLiteLLM呼び出し毎にこのAPIへ
  実績を報告する運用を想定する(LiteLLM自体のDB spend
  trackingは未接続の軽量構成のため)。
- `GET /costs/summary`(admin/editor/viewer、200): 当月の
  `total_spend_jpy`・`consumption_ratio`(0〜1、予算に対する消化率)・
  `budget_status`(`ok`/`warning`/`exceeded`、80%/100%閾値)、および
  `by_model`/`by_logical_name`/`by_day`(各`{key, call_count,
total_tokens, total_cost_jpy, total_latency_ms}`の配列)を返す。
- 判定ロジックは`api_server.costs.budget.check_budget_threshold(ratio)`
  (E9-2の予算監視・自動停止から再利用する想定)。
  usage永続化は`api_server.costs.usage_store`(JSONL追記専用、
  監査ログと同様のパターン)。

### 設定値(`api_server.config.Settings`、全て環境変数から読込)

`JWT_SECRET`(必須)、`PMDF_STORE_PATH`(必須)、`CORS_ORIGINS`、
`JWT_EXPIRES_MINUTES`(既定30)、`TOTP_ENABLED`(既定false)、
`USER_STORE_PATH`(既定`data/users.json`)、
`AUDIT_LOG_PATH`(既定`data/audit/audit.log.jsonl`)、
`AUTONOMY_CONFIG_PATH`(既定`data/autonomy.json`)、
`EMERGENCY_STOP_PATH`(既定`data/emergency_stop.json`)、
`PROPOSAL_STORE_PATH`(既定`data/proposals.json`)、
`BUDGET_MONTHLY_JPY`(既定50000、E4-3)、
`COST_USAGE_LOG_PATH`(既定`data/costs/usage.jsonl`、E4-3)、
`CHAT_TASK_STORE_PATH`(既定`data/chat_tasks.json`、E5-9)。

## model-gateway 公開インターフェース(E5以降が利用する想定)

`services/model-gateway`(E4-1〜E4-3で実装)は、全LLM・埋め込み呼び出しの
単一窓口となるLiteLLM Proxy設定(`litellm.config.yaml`)を提供する。
**E4-4(compose統合起動)は未実施のため、実際にコンテナとして起動できる
状態ではまだない**(現時点では設定ファイル・コンテナ定義・検証テストの
みが揃っている)。E5(agent-core)実装時は下記を前提にクライアントを
実装すること。

### 論理名(AR-01: 実モデル名をコードにハードコードしないこと)

- `pdm-main`: 通常のエージェント推論用メインモデル。
- `pdm-main-local`: `pdm-main`のローカルOllama切替例
  (`.env`の`PDM_MAIN_LOCAL_MODEL`/`PDM_MAIN_LOCAL_API_BASE`を設定した
  場合の代替エントリ。E4-5で無改修切替を検証予定)。
- `pdm-main-fallback`: `pdm-main`障害時のフォールバック先
  (Bedrock経由、`router_settings.fallbacks`で自動的に使われる)。
- `pdm-teacher`: 自己学習ループの教師role(E8で使用、高精度・低頻度)。
- `pdm-judge`: 評価・LLM-as-judge用。
- `pdm-embed`: 埋め込み(RAG/知識ベース、E6で使用)。

いずれもコード側は論理名のみを指定し、実モデル名・実バックエンドは
`services/model-gateway/litellm.config.yaml`にのみ記述する
(モデル指定を変更する場合は`.env`の`PDM_*_MODEL`系変数のみを変更する)。

### エンドポイント(E4-4完了後の想定。現時点では未起動)

- ベースURL: `.env`の`MODEL_GATEWAY_URL`(既定
  `http://model-gateway:4000`、compose内部ネットワーク名前解決)。
- LiteLLM Proxyの標準API(`POST /chat/completions`等、OpenAI互換)を
  `model`パラメータに論理名(`pdm-main`等)を指定して呼び出す
  (LiteLLM Proxy自体の標準的な使い方に準拠。api-server側の独自
  ラッパーエンドポイントは無い)。
- 障害時のフォールバック・リトライ・タイムアウトは
  `litellm.config.yaml`の`router_settings`
  (`fallbacks`/`num_retries`/`timeout`/`cooldown_time`)に従い
  ゲートウェイ側で自動的に処理される(呼び出し元での実装は不要)。

### 環境変数(`.env.example`参照、model-gateway関連)

`PDM_MAIN_MODEL`/`PDM_TEACHER_MODEL`/`PDM_JUDGE_MODEL`/
`PDM_EMBED_MODEL`(論理名ごとの実モデル割当)、
`PDM_MAIN_LOCAL_MODEL`/`PDM_MAIN_LOCAL_API_BASE`(ローカルOllama切替例)、
`PDM_MAIN_FALLBACK_MODEL`(Bedrockフォールバック例)、
`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`AWS_ACCESS_KEY_ID`/
`AWS_SECRET_ACCESS_KEY`/`AWS_REGION`(各バックエンドの認証情報)、
`LITELLM_DATABASE_URL`(spend tracking用DB、Tier-Lでは未接続でも可、
その場合api-server側の`/costs/usage`報告方式で代替)。

### コスト計測との連携(E4-3)

LiteLLM自体のspend tracking DBは本フェーズでは未接続(軽量構成)。
agent-core(E5)・学習ジョブ(E8)は各LLM呼び出し後、
`POST http://api-server:8000/costs/usage`へ
`{logical_name, model, prompt_tokens, completion_tokens, latency_ms,
cost_jpy, actor}`を報告することで、`GET /costs/summary`
(月次予算消化率の可視化、AR-04)に反映される。

### テスト用参照実装(`services/model-gateway/src/model_gateway/`)

`litellm`パッケージ本体はワークスペースの`packages/pmdf`が要求する
`typer>=0.26.8`と衝突する(litellm 1.90.2は`typer<0.26`要求)ため、
Python依存としては追加していない。`model_gateway.router.GatewayRouter`
は`litellm.config.yaml`のルーティング・フォールバック・リトライ契約を
respxモックで検証するための軽量参照実装であり、**実運用のプロキシ
処理自体は公式`ghcr.io/berriai/litellm`イメージ(コンテナ)が担う**
(E5実装時にこのPythonモジュールをそのまま利用する想定ではない)。

## kb-ingest 公開インターフェース(E5以降が利用する想定)

`services/kb-ingest`(E6で実装完了)は、KB(知識ベース)コーパスと
PMDFエンティティを共にベクトル化してQdrantへ投入する。E5
(agent-core)のRAGツール(E5-3 `search_knowledge`)は本サービスの
以下のAPIをそのまま利用する想定(agent-core側で埋め込み・Qdrant
投入ロジックを再実装する必要はない)。

### コーパス・front-matter

- `kb/corpus/<domain>/<slug>.md`: front-matter付きMarkdown
  (必須: `domain`, `title`, `source`, `license`。任意: `framework`,
  `pm_principle`)。PdM本体ドメイン11件、PM隣接ドメイン
  (`project_management`)6件のサンプル済み(いずれも独自著作、
  `kb/CORPUS_LICENSE_CHECKLIST.md`のレビュー観点に準拠)。
- `kb_ingest.frontmatter`: `CorpusFrontMatter`(pydanticスキーマ、
  `domain`は`KNOWN_DOMAINS`のいずれかのみ許容)、
  `parse_markdown_file(path) -> tuple[dict, str]`(front-matterと
  本文を分離)。

### チャンク分割・埋め込み

- `kb_ingest.chunking.chunk_document(body, front_matter, *,
source_path, max_chars=500, overlap=50) -> list[Chunk]`:
  見出しベース分割+固定長オーバーラップ分割。各`Chunk`は
  `domain`/`framework`/`pm_principle`/`title`を継承する。
- `kb_ingest.embedding.GatewayEmbeddingClient(base_url)`:
  model-gateway経由(論理名`pdm-embed`固定、実モデル名はコードに
  一切持たない)の`/embeddings`(OpenAI互換)呼び出し。
  `await client.embed(texts: list[str]) -> list[list[float]]`。

### Qdrantストア(KB/PMDF共通)

- `kb_ingest.qdrant_store.QdrantKbStore(url)`: KBチャンク
  (`upsert_kb_chunks`、`source="kb"`ペイロード)とPMDFエンティティ
  (`upsert_pmdf_entity`、`source="pmdf"`ペイロード)を**同一
  コレクション**に投入し、ペイロードの`source`フィールドで区別する
  設計(E5-3の`search_knowledge(source="kb"|"pmdf"|"all")`が
  そのままフィルタとして使える)。
- `store.search(collection, query_vector, *, source=None,
extra_filter=None, top_k=5) -> list[ScoredPoint]`:
  `source`(`"kb"`/`"pmdf"`)、`extra_filter`(例
  `{"domain": "discovery"}`)でペイロードフィルタを掛けられる。
  E5-3の`search_knowledge`はこのメソッドをラップし、埋め込み取得
  (`GatewayEmbeddingClient`)と組み合わせて実装する想定。
- 埋め込み次元数が異なるモデルへの切替時は
  `store.recreate_collection(collection, dim=...)`
  でコレクションを再作成する(`CollectionDimensionMismatchError`が
  再作成の必要性を明示的に通知する)。手順は
  `docs/kb-embedding-switch.md`参照。
- ポイントIDはKB(`source_path`+`chunk_index`)・PMDF
  (`pmdf_kind`+`pmdf_id`)の内容から決定的に導出するUUIDのため、
  再投入時は自然に上書きされる(冪等)。

### PMDFインデクサ

- `kb_ingest.pmdf_indexer.PmdfIndexer(store, embedding_client,
fetch_entity, collection)`: api-serverのWebSocketイベント
  (`pmdf.entity_changed`、`{kind, id, verb}`)を受け取り
  `await indexer.handle_event(event_data)`を呼ぶと、対応する
  エンティティを`fetch_entity(kind, id) -> dict | None`
  (実運用では`GET /pmdf/{kind}/{id}`を叩くHTTPクライアントを注入)
  で取得し、kind別テキスト抽出(`extract_entity_text`)→埋め込み→
  Qdrant upsertまで行う。
- E5(agent-core)側での常駐運用は、api-serverの
  `WS /ws/events?token=<JWT>`に接続し、受信イベントのうち
  `type == "pmdf.entity_changed"`のものを`PmdfIndexer.handle_event`
  へ渡すループを実装すること(`PmdfIndexer.consume_forever(queue)`
  はasyncio.Queueを介した接続例)。

### CLI

- `uv run kb-ingest validate kb/corpus`: front-matterスキーマ検証。
- `uv run kb-ingest ingest kb/corpus --collection pdm_kb`:
  チャンク分割→埋め込み→Qdrant投入の一気通貫実行。
- `uv run kb-ingest recreate --collection pdm_kb --dim <n>`:
  埋め込み次元変更時のコレクション再作成。

## agent-core 公開インターフェース(E7/E8以降が利用する想定)

`services/agent-core`(E5で実装完了)は、LangGraphベースの4業務グラフ・
PMDFツール・RAG検索・根拠明示・差戻フィードバック・チャット指示
インターフェースを提供する。全PMDF書込はapi-server経由(`PmdfToolClient`、
直接ストア書込は`scripts/check_agent_core_isolation.py`のCI静的チェックで
禁止)、全LLM呼び出しはmodel-gateway経由の論理名のみで行う(疎結合の徹底)。

### 業務グラフ(`agent_core.graphs.*`)

- `backlog`(L2): `run_backlog_graph(intake_text, ...)` — ストーリー起票+
  RICE/WSJF優先順位付け(スコアはコード側`calc_rice_score`/
  `calc_wsjf_score`で必ず検算、LLM出力の数値は信用しない)。
- `vision_roadmap_release`(L1): `propose_vision_update`/
  `propose_roadmap_update`/`propose_release_decision`(起案のみ、
  `POST /approvals`)、`execute_after_approval`/`call_l1_gated_endpoint`
  (承認済みの場合のみapi-serverのL1ゲート済みエンドポイントを実行、
  未承認は`ApprovalNotGrantedError`)。
- `kpi_dr_review`(L3): `monitor_kpi`(閾値判定はコード側
  `is_threshold_breached`、超過時のみLLMで原因仮説生成)、
  `record_decision`(Decision Record自動記録)、`weekly_review`
  (要判断事項検出時は`POST /approvals`でL1業務へ橋渡し)。
- `discovery_experiment_stakeholder_initiative`: `run_discovery`/
  `run_experiment`(L2)、`draft_message`(L2、文案生成のみ)/
  `send_message`(L1、実送信は承認ゲート必須)、`run_initiative`(L2、
  EVM(SPI/CPI)は`calc_evm`でコード側決定的計算)。

### 根拠明示・差戻フィードバック(E5-8、`agent_core.evidence`/`feedback_loop`)

- `evidence.attach_evidence(payload, evidence) -> dict`: PMDF書込
  ペイロードへ`x_evidence`拡張フィールドを付与する。`evidence`が空/Noneの
  場合は`MissingEvidenceError`を送出する(FR-PD-13: 根拠なし成果物の
  書込を防ぐ)。`evidence`要素は`agent_core.tools.rag_tool.SearchResult`
  (`.to_evidence_dict()`でKB/PMDF出典形式に変換)、または
  `evidence.data_evidence(description, data)`(決定的計算の入力値等
  「データ」根拠)で組み立てた辞書を渡す。既存4業務グラフの各成果物
  生成・起案箇所に統合済み(参考実装として利用可能)。
- `feedback_loop.on_rejection(approval, *, queue_dir, original_draft,
revised_draft) -> Message | None`: `approval["decision"] ==
"rejected"`の場合のみ、(1)差戻理由を次回起案コンテキストへ注入する
  `{"role": "user", "content": "..."}`形式のメッセージを返し、
  (2)差し戻しペアを`queue_dir`配下へ日付単位のJSONL
  (`FeedbackRecord.to_dict()`: `approval_id`/`target`/`original_draft`/
  `reason`/`revised_draft`)として追記する(E8-5の学習データ取込の
  入力想定)。差し戻し検知そのもの(WebSocket購読・ポーリング等)は
  呼び出し側の責務。

### チャット指示インターフェース(E5-9、`agent_core.chat`)

- `handle_chat_instruction(*, message, product_id, actor, llm_client,
pmdf_tool_client, api_server_url, auth_token, dispatch_overrides=None)
-> TaskHandle`: (1)`POST /chat/instructions`でタスク登録、
  (2)`classify_intent`(`pdm-main`)で対象業務グラフ(`GraphKind`:
  `backlog`/`vision_roadmap_release`/`kpi_dr_review`/
  `discovery_experiment_stakeholder_initiative`。LLMが未知の値を返した
  場合は`backlog`へフォールバック)を判定、(3)`running`へ状態遷移報告、
  (4)`dispatch_overrides`(`GraphKind`→実行関数の辞書。実運用では
  上記4業務グラフの実行関数を束ねる)で対象グラフを実行、
  (5)成否に応じ`done`(結果付き)/`failed`(エラー内容付き)へ状態遷移
  報告する。各段階の状態遷移はapi-server側`POST
/chat/tasks/{id}/transition`経由でHTTP越しに報告し、api-server側が
  `agent.activity`イベントとしてWebSocket配信する(具体的なAPI仕様は
  上記「api-server 公開インターフェース」の「チャット指示API」を参照)。
- E7(web-ui)のチャットUIは`POST /chat/instructions`で指示を送信し、
  `WS /ws/events`で`agent.activity`イベント(`{task_id, status,
product_id, intent}`)を購読してリアルタイムに実行状況を表示する
  想定。実行完了後の詳細は`GET /chat/tasks/{task_id}`で取得できる。

### 常駐ランナー実装時の注意(E7/E8/E9で実プロセス化する際)

現時点(E5)では、4業務グラフ・チャット指示ハンドラは全て「呼び出せば
1回分実行して結果を返す」関数として実装されており、常駐プロセス
(スケジューラからの定期起動、チャットタスクキューのポーリング等)は
未実装。E9(運用機能)またはE7/E8の中で、`agent_core.task_queue.TaskQueue`
(E5-1)の`dequeue()`ループ、またはapi-serverの`/chat/tasks`をポーリングする
ワーカープロセスとして実装する想定(本ファイルのAPI仕様・関数シグネチャは
そのまま利用可能)。

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

| 日付       | 決定内容                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | 理由                                                                                                                                                                                                                                                                                                                   |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-07-04 | 全実装を `develop` ブランチ上で行う一本運用に変更。PRマージはユーザーが手動で行う                                                                                                                                                                                                                                                                                                                                                                                                                  | 複数セッション・複数エージェントによる並行実装でブランチ管理コストを下げつつ、最終マージの可否判断をユーザーに残すため                                                                                                                                                                                                 |
| 2026-07-04 | E1-1〜E1-4の検証はローカル環境(uv 0.10.10, Docker 29.5.3, npm 11.11.0)で実施し、実CIの発火結果もpush後に `gh run list` で確認する運用とした                                                                                                                                                                                                                                                                                                                                                        | ローカル検証のみでは実際のGitHub Actions環境固有の差異(OS、キャッシュ等)を見逃す可能性があるため                                                                                                                                                                                                                       |
| 2026-07-04 | E2完了。story.priority等のOptionalフィールドは`entity_to_json_dict()`(`exclude_none=True`)経由でJSON化する規約とした                                                                                                                                                                                                                                                                                                                                                                               | Pydanticの`model_dump(mode="json")`はNoneを明示出力するが、JSON Schema側はnull非許容の型定義が多く、バンドルimportでのスキーマ再検証時に型不一致が発生するため                                                                                                                                                         |
| 2026-07-04 | E2-7の`apply_bundle`はストア層を`PmdfStore` Protocol(`save(entity)`のみ)経由で受け取る設計とした                                                                                                                                                                                                                                                                                                                                                                                                   | `packages/pmdf`単体はストアの永続化方式(Git等)に依存させず、E3のpmdf-store層が具象実装を注入できるようにするため                                                                                                                                                                                                       |
| 2026-07-04 | CIの`uv run mypy .`(リポジトリ全体)とローカル検証コマンドの乖離により、テストコードのmypyエラーがCIでのみ顕在化しCIが継続的に失敗していた問題を修正(コミット29ea48a)。以降mypy検証は必ず`uv run mypy .`をリポジトリルートから実行する運用とした                                                                                                                                                                                                                                                    | ローカルで`services/api-server/src`のみを対象にmypyを実行しており、testsディレクトリのエラーを見逃していたため。E3-4〜E3-6の3コミット分、CIが赤のまま気づかず進行していた                                                                                                                                              |
| 2026-07-04 | E3-6の承認プロポーザル(決定前`proposed`状態)はPMDFエンティティではなく、api-server独自のJSONファイルストア(`api_server.approval.proposal_store`)で管理する設計とした                                                                                                                                                                                                                                                                                                                               | `Approval`(PMDF)エンティティの`decision`フィールドが必須のため、決定前状態をPMDFエンティティとして表現できない(スキーマ上approved/rejectedのみ許容)ため                                                                                                                                                                |
| 2026-07-04 | E3-9のバンドル適用(`apply_bundle`)は`PmdfStore.save_all`(新規追加した複数エンティティ一括1コミットAPI)へ委譲するアダプタ(`_BatchSaveAdapter`)を介して呼び出す設計とした                                                                                                                                                                                                                                                                                                                            | `apply_bundle`は`save(entity)`をエンティティ毎に呼び出すが、E3-9の要件(バンドル適用は1コミット)を満たすには、save呼び出し中はバッファリングし最後に一括コミットする必要があったため                                                                                                                                    |
| 2026-07-04 | E3全10サブイシュー(#27〜#36)完了、親issue #3クローズ。api-server公開インターフェースを本ファイルに追記した                                                                                                                                                                                                                                                                                                                                                                                         | E4(model-gateway+compose統合)・E5(agent-core)・E7(web-ui)実装時に、新規セッションが本ファイルのみで必要なAPI仕様(認証方式、承認ゲートの使い方、L1エンドポイント追加時の必須依存関数等)を把握できるようにするため                                                                                                       |
| 2026-07-05 | E4-1〜E4-3(#37, #83, #84)完了。`litellm`パッケージ本体はワークスペースの依存関係解決に追加せず(`packages/pmdf`の`typer>=0.26.8`要件とlitellm 1.90.2の`typer<0.26`要件が衝突するため)、YAML構造検証+respxモックによる軽量参照実装(`model_gateway.router.GatewayRouter`)でルーティング・フォールバック・リトライ契約を検証する方針とした                                                                                                                                                             | ワークスペース全体で単一lockfileを共有するuv workspace構成のため、1サービスがlitellmを追加するとpmdfのCLI依存(typer)が壊れる。実運用のプロキシ処理は公式コンテナイメージが担うため、Python依存としてのlitellm追加は必須ではない                                                                                        |
| 2026-07-05 | E4-3のコスト計測は、LiteLLM自体のspend tracking DBに接続せず、api-server側の軽量usage記録ストア(JSONL追記専用、`POST /costs/usage`)で代替する設計とした                                                                                                                                                                                                                                                                                                                                            | イシュー本文が「DB無し構成なら軽量実装で可」を許容しており、Tier-Lの単純運用ではDB(Postgres等)を追加運用するコストを避けつつAR-04(トークン数・レイテンシ・概算コストの記録と月次予算消化率の可視化)を満たせるため                                                                                                      |
| 2026-07-05 | E4完了はE4-1〜3のみとし、E4-4(compose統合起動)・E4-5(バックエンド無改修切替検証、#85, #86)はE7-1(web-ui骨格)完成後に着手する方針とし、親issue #4はopenのまま維持した                                                                                                                                                                                                                                                                                                                               | ユーザー指示により、compose統合起動・切替検証はweb-ui完成後にまとめて実施する運用としたため。E4-4/E4-5着手前に誤って親issueをクローズしないよう明記する必要があるため                                                                                                                                                  |
| 2026-07-05 | E6(知識ベース)は`services/agent-core`が未実装(E5未着手)の段階で着手したため、KB/PMDF関連の全実装を新設した独立ワークスペースメンバー`services/kb-ingest`に配置する設計とした(イシュー本文が許容する「独立パッケージとして切り出してもよい」選択肢を採用)。KB由来(`source="kb"`)・PMDF由来(`source="pmdf"`)は同一Qdrantコレクション内でペイロードの`source`フィールドにより区別する方式に統一した                                                                                                   | E5-3の`search_knowledge`が実装される前に、その依存先となるベクトルストア層を先に用意する必要があった。agent-core本体(LangGraph・タスクキュー等)はE6のスコープ外のため作らず、E5実装時に`kb_ingest`をそのままインポートして`search_knowledge`を組み立てられるようインターフェースを整理した                             |
| 2026-07-05 | E6全4サブイシュー(#47〜#50)完了、親issue #6クローズ。kb-ingest公開インターフェースを本ファイルに追記した                                                                                                                                                                                                                                                                                                                                                                                           | E5(agent-core)実装時に、新規セッションが本ファイルのみでKB検索に必要なAPI仕様(チャンク分割・埋め込み・Qdrantストア・PMDFインデクサ・CLI)を把握できるようにするため                                                                                                                                                     |
| 2026-07-05 | E5-8(根拠明示・差戻フィードバック)は、KB出典・PMDF参照に加え「データ」根拠(決定的計算の入力値・KPI実測値等)を`x_evidence`の第3の`source`種別として追加した(`evidence.data_evidence`)。既存4業務グラフへの統合は各成果物生成・起案ノードの永続化直前に`attach_evidence`呼び出しを1〜数行追加する形とし、グラフの構造自体は変更しなかった                                                                                                                                                            | FR-PD-13の要件文言(「KB出典、PMDF内の参照エンティティ、データ」)がKB/PMDF以外の根拠(RICE/WSJF・EVMの計算入力値、KPI実測値等)も許容しており、これらは検索結果ではなくグラフ内部で既に持っている値であるため、無理にKB/PMDF検索を挟まずデータそのものを根拠として明示する経路を用意する方が実態に即していたため          |
| 2026-07-05 | E5-9(チャット指示インターフェース)は、チャットタスクの永続化・状態遷移・イベント配信をapi-server側(`api_server.chat.task_store`、E3-6の`proposal_store`と同様のJSONファイルストア)に置き、agent-core側の`chat.py`はHTTP経由でタスク登録(`POST /chat/instructions`)と状態遷移報告(`POST /chat/tasks/{id}/transition`)を行うクライアントとして実装する設計とした(agent-coreのE5-1タスクキューはプロセス内実装のため、チャットタスクの実行状況をUIと共有するにはapi-server側の永続化が必要と判断した) | 依存方向(agent-core→api-serverの一方向のみ、api-serverはagent-coreをimportしない)を崩さずにUI⇄api-server⇄agent-coreランナー間でチャットタスクの状態を共有するには、状態の単一の真実源をapi-server側に置く必要があったため                                                                                              |
| 2026-07-05 | E5全9サブイシュー(#38〜#46)完了、親issue #5クローズ。agent-core公開インターフェースを本ファイルに追記した                                                                                                                                                                                                                                                                                                                                                                                          | E7(web-ui)・E8(自己学習ループ)実装時に、新規セッションが本ファイルのみでagent-coreの業務グラフ・根拠明示・差戻フィードバック・チャット指示APIの仕様を把握できるようにするため                                                                                                                                          |
| 2026-07-05 | E7-4(承認キュー)実装にあたり、api-serverの`Proposal`/`ProposeRequest`/`ProposalResponse`に任意項目`draft`(起案内容の辞書)を追加した                                                                                                                                                                                                                                                                                                                                                                | 従来のプロポーザルは`target`(対象エンティティid)のみを保持しており、承認キュー画面でPMDF diff(変更前後の比較)を表示するために必要な「変更後の値」を復元する手段が無かったため。agent-core側の`_propose`は既にdraftをレスポンスに含めていた(サーバ側で永続化されず破棄されていた)ため、永続化対象に追加する形で解消した |
| 2026-07-05 | E7-5(ドキュメントビューア)のPMDF diffは、承認キュー(E7-4)用に実装した「現在値vs部分オブジェクト(draft)」比較(`computeDraftDiffs`)と、版間diff用の「完全スナップショット同士」比較(`computeFullSnapshotDiffs`)を別関数として分離し、`FieldDiffTable`(描画)を共有する設計とした                                                                                                                                                                                                                      | draftは変更予定フィールドのみを含む部分オブジェクトのため「draftに存在するキーのみ比較」が正しいが、版間diffは両版とも完全なスナップショットのため「和集合キーで比較(削除されたフィールドも検出)」が正しく、同一の比較関数では要件を両立できなかったため                                                               |
| 2026-07-05 | E7-6(エージェント活動ログ)実装にあたり、api-serverに`GET /chat/tasks`(タスク一覧、新しい順、statusフィルタ対応)と`GET /audit/records`(actor/action/kind/期間フィルタ、新しい順、`api_server.routers.audit`として新設)を追加した                                                                                                                                                                                                                                                                    | E5-9時点では`GET /chat/tasks/{id}`(単件取得)のみ実装されており一覧取得手段が無かった。E3-7時点では監査ログは追記専用JSONL永続化層(`api_server.audit.log`)のみでHTTP経由の検索APIが未実装だった。いずれもE7-6の受け入れ条件(タスク一覧表示、監査ログ検索)を満たすために必要な最小限のAPI追加として実施した              |
| 2026-07-05 | E7全体のうちE7-1〜E7-6(#51〜#56)完了。エピック#7はE7-7〜E7-9が残るためopenのまま維持する(ユーザー指示によりスコープ外)                                                                                                                                                                                                                                                                                                                                                                             | 今回のセッションのスコープがE7-4〜E7-6の3画面実装に限定されていたため                                                                                                                                                                                                                                                  |
