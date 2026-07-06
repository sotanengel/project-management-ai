# 構造化ログ規約 (FR-OP-02)

Tier-L では Docker Compose の標準ログドライバ (`json-file`) と
`docker compose logs` による横断確認を既定運用とする。将来の ELK / Loki
等への拡張時も、本規約の JSON フィールドを維持すること。

## 必須フィールド

| フィールド | 説明 |
|-----------|------|
| `timestamp` | ISO 8601 (`TimeStamper(fmt="iso")`) |
| `level` | `info` / `warning` / `error` 等 |
| `service` | サービス名 (`api-server`, `agent-core`, `scheduler` 等) |
| `message` | 人間可読の要約 |
| `trace_id` | 分散トレース ID（取得可能な場合のみ。未設定時は省略可） |

## サービス別設定

| サービス | 実装 | 起動時初期化 |
|---------|------|-------------|
| api-server | `api_server.logging.configure_logging` | `create_app()` 内 |
| agent-core | `agent_core.logging.configure_logging` | `agent_core.__main__` |
| scheduler | `scheduler.logging.configure_logging` | `scheduler.main` |

## ログ確認

```bash
docker compose --profile api-only logs -f api-server
docker compose --profile api-only logs --tail=50
```

## 拡張ポイント (スコープ外)

- ログ集約基盤 (Loki, CloudWatch Logs 等) への ship は E11 以降で検討
- `trace_id` は OpenTelemetry 導入時に contextvars から注入する想定
