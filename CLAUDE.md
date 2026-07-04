# CLAUDE.md (project-management-ai)

このリポジトリで実装作業を行う全エージェントが守るべき規約。
作業再開時は本ファイルと `docs/IMPLEMENTATION_STATE.md` を先に読むこと。

## ブランチ運用

- **すべての実装作業は `develop` ブランチ上で行う。**
- `main` への `git switch`/`git checkout` は行わない。
- `gh pr merge` 等によるPRマージは行わない(ユーザーが手動で実施する方針)。
- サブイシュー1件の実装が完了するたびに、`develop` に対して
  `git add` → `git commit` → `git push origin develop` を行う
  (中断への備え。作業を溜めない)。

## TDD(Red → Green → Refactor)

- 仕様に沿った**テストを先に**追加・修正し、そのテストが失敗すること
  (Red)を確認してから実装(Green)する。その後必要に応じてリファクタリング
  する(Refactor)。
- 新機能・バグ修正では、再現テストまたは回帰テストを必ず追加する。
- 設定ファイル類(CI定義、compose定義等)でテストが困難なものは、
  検証コマンドの実行結果(exit code、`config` 出力等)をもって
  代替のエビデンスとする。

## コミット規約

- [Conventional Commits](https://www.conventionalcommits.org/) 準拠:
  `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:` 等のprefixを使う。
- イシュー番号を伴う実装コミットは
  `feat(scope): 要約 (#イシュー番号)` の形式とする。
- コミットメッセージ末尾に空行を挟み、必ず以下を付与する:

  ```
  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```

- 既存コミットの `--amend` は原則禁止。pre-commitフック失敗時は
  修正後に新規コミットを作成する。

## イシュー運用

- 実装前に、適切な粒度で全てのissue・sub-issueを追加する。
- 大きなタスクは親issueとsub-issueに分割し、進捗を追跡可能にする。
- 着手前に対象issueの受け入れ条件・スコープを明確化してから実装を始める。
- 着手時: `gh issue edit <番号> --add-label in-progress`
- 完了時: 受け入れ条件との対応をコメントに記載して
  `gh issue close <番号> --comment "..."`(in-progressラベルは外す)。
- 完了できない場合はWIPでもコミット+pushし、イシューコメントに
  「完了内容/残作業/次の一手」を記録して `in-progress` のまま残す。

## モック方針(単体テスト)

- **LLM API呼び出し**: 単体テストでは実APIを呼ばず、
  [`respx`](https://lundberg.github.io/respx/)(httpx向け)等でモックする。
  実APIキーを要するテストはCIで実行しない。
- **Qdrant(ベクトルDB)**: 単体テストでは `:memory:` モードのクライアント、
  またはインメモリフェイクを使用する。
- **GPU / ローカルLLM(ollama等)**: 単体テストでは極小モデル、または
  モックレスポンスを使用し、実GPU推論はCIで行わない。
- 上記に該当する統合テスト・E2Eテストは明示的にマークし
  (例: `@pytest.mark.integration`)、通常のCIジョブから除外するか、
  必要なシークレットが無い環境ではスキップされるようにする。

## コーディング規約

- 改行コードはLF統一(`.gitattributes` 準拠)。
- シークレット・APIキー・トークンはコードやコミットに直書きしない。
  環境変数(`.env`、`.gitignore`対象)、Secrets Manager、SSM Parameter
  Store等で管理する。
- Python: `ruff`(lint + format)を使用し、`uv run ruff check .` /
  `uv run ruff format --check .` がクリーンであること。型チェックは
  `mypy`(設定は緩めに開始し、段階的に厳格化する)。
- コミット前に `uv tool run pre-commit run --all-files` がクリーンで
  あることを確認する。

## CI

- `.github/workflows/ci-python.yml`: Python系(lint/format/mypy/pytest)。
- `.github/workflows/ci-web.yml`: Web系(`services/web-ui` 追加後に
  有効化される。存在チェックにより未実装時は該当ステップをスキップ)。
- `.github/workflows/ci-compose.yml`: `docker-compose.yml` の
  `config` 検証(実起動はしない)。
- 実装後は `gh run list` でCIが実際に成功しているか確認すること。

## 参照

- 実装状況・再開手順: `docs/IMPLEMENTATION_STATE.md`
- Takumi Guard(Shisho)セットアップ: `docs/takumi-guard.md`
