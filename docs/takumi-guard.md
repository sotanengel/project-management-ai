# Takumi Guard(Shisho)セットアップ手順

サプライチェーン攻撃対策として、パッケージレジストリを
[Takumi Guard(Shisho)](https://shisho.dev/docs/ja/t/guard/quickstart/index.md)
経由のミラーへ切り替える。

**重要**: トークン(`tg_anon_` プレフィックス、メール認証レベル)は
**ユーザーレベル設定にのみ**配置し、リポジトリ・コミット・issueコメントには
絶対に含めないこと。本ドキュメント中のトークンはすべて `<YOUR_TOKEN>`
というプレースホルダで表記している。

## npm / pnpm / yarn / bun

レジストリURL: `https://npm.flatt.tech/`

### npm

```bash
npm config set registry https://npm.flatt.tech/
npm config set //npm.flatt.tech/:_authToken <YOUR_TOKEN>
```

またはユーザーレベルの `~/.npmrc`(Windowsでは `%USERPROFILE%\.npmrc`)に
直接記述する(**プロジェクトの `.npmrc` には書かない**):

```ini
registry=https://npm.flatt.tech/
//npm.flatt.tech/:_authToken=<YOUR_TOKEN>
```

### pnpm

```bash
pnpm config set registry https://npm.flatt.tech/
```

認証が必要な場合は、上記と同様にユーザーレベルの `.npmrc` にトークンを追記する。

### yarn

- **yarn v1**: `.npmrc` の設定をそのまま読み込むため、npmと同じ手順で構成する。
- **yarn berry (v2+)**: `.yarnrc.yml` に以下を追記する。

```yaml
npmRegistryServer: "https://npm.flatt.tech/"
npmRegistries:
  "https://npm.flatt.tech/":
    npmAuthToken: "<YOUR_TOKEN>"
```

### bun

公式クイックスタートにbun固有の記載はない。npm/yarnと同様に
`~/.npmrc` のレジストリ設定を踏襲する運用とする。

## pip / uv / poetry

### pip

匿名利用:

```bash
pip config set global.index-url https://pypi.flatt.tech/simple/
```

トークン利用(メール認証):

```bash
pip config set global.index-url https://token:<YOUR_TOKEN>@pypi.flatt.tech/simple/
```

設定ファイルの場所:

- Linux/macOS: `~/.config/pip/pip.conf`
- Windows: `%APPDATA%\pip\pip.ini`

```ini
[global]
index-url = https://token:<YOUR_TOKEN>@pypi.flatt.tech/simple/
```

### uv

uvはpipの設定を参照しないため、独立した設定が必要。

ユーザーレベルの `uv.toml`(Windowsでは `%APPDATA%\uv\uv.toml`、
Linux/macOSでは `~/.config/uv/uv.toml`)に設定する
(**プロジェクトの `pyproject.toml` にトークンを書かないこと**):

```toml
[[index]]
url = "https://token:<YOUR_TOKEN>@pypi.flatt.tech/simple/"
default = true
```

環境変数での設定も可能:

```bash
export UV_DEFAULT_INDEX=https://token:<YOUR_TOKEN>@pypi.flatt.tech/simple/
```

### poetry

```bash
poetry source add --priority=primary takumi-guard https://pypi.flatt.tech/simple/
poetry config http-basic.takumi-guard token <YOUR_TOKEN>
```

- ソース設定(`pyproject.toml` の `[[tool.poetry.source]]`)はリポジトリに
  含めてよいが、トークン自体は `poetry config` により端末ごとの
  `auth.toml`(自動生成、ユーザーレベル)に保存されるため安全。

## Bundler(参考情報、本プロジェクトはRuby未使用)

```bash
bundle config set --global mirror.https://rubygems.org https://rubygems.flatt.tech/
```

トークン付き(ダウンロード追跡・侵害通知を有効化):

```bash
bundle config set --global mirror.https://rubygems.org https://token:<YOUR_TOKEN>@rubygems.flatt.tech/
```

`Gemfile` の変更は不要(Bundlerがミラー設定を自動適用する)。

## 検証

`@panda-guard/test-malicious` パッケージのインストールを試み、
**403 Forbidden** で失敗することを確認する。

```bash
npm install @panda-guard/test-malicious
```

リポジトリには `scripts/verify_registry_guard.py` を用意しており、
以下のコマンドで自動検証できる:

```bash
uv run python scripts/verify_registry_guard.py
```

- レジストリ設定済み・403応答が確認できた場合: 成功(exit code 0)。
- npm自体が無い、レジストリが未設定、またはトークン未設定と判断できる
  場合: 「未検証・要人手確認」として扱い、失敗とは異なるexit codeで終了する。

確認後、誤ってインストールされてしまった場合は該当パッケージを削除すること
(通常は403で失敗するためインストールされない)。
