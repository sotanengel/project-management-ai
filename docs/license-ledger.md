# ライセンス台帳

Tier-L で利用する主要 OSS のライセンス概要です。商用利用・改変・出力物の
取り扱いは各ライセンス全文を必ず参照してください。

| コンポーネント                                              | 用途                   | ライセンス | 改変 | 商用 | 出力物・備考                                     |
| ----------------------------------------------------------- | ---------------------- | ---------- | ---- | ---- | ------------------------------------------------ |
| [Transformers](https://github.com/huggingface/transformers) | モデル読込・推論       | Apache-2.0 | 可   | 可   | モデルウェイトは各モデルカードのライセンスに従う |
| [TRL](https://github.com/huggingface/trl)                   | SFT/DPO 学習           | Apache-2.0 | 可   | 可   | 学習成果物の配布条件はベースモデルに依存         |
| [peft](https://github.com/huggingface/peft)                 | LoRA/QLoRA             | Apache-2.0 | 可   | 可   | アダプタはベースモデルライセンスと併記           |
| [LiteLLM](https://github.com/BerriAI/litellm)               | model-gateway プロキシ | MIT        | 可   | 可   | 上流 API の利用規約が別途適用                    |
| [LangGraph](https://github.com/langchain-ai/langgraph)      | agent-core グラフ      | MIT        | 可   | 可   | LangChain エコシステムの依存に注意               |
| [Qdrant](https://github.com/qdrant/qdrant)                  | ベクトル DB            | Apache-2.0 | 可   | 可   | クライアントは Apache-2.0                        |
| [MLflow](https://github.com/mlflow/mlflow)                  | 実験追跡               | Apache-2.0 | 可   | 可   | トラッキングサーバは自ホスト                     |
| [FastAPI](https://github.com/fastapi/fastapi)               | api-server             | MIT        | 可   | 可   | —                                                |
| [React](https://github.com/facebook/react)                  | web-ui                 | MIT        | 可   | 可   | —                                                |
| [Playwright](https://github.com/microsoft/playwright)       | E2E テスト             | Apache-2.0 | 可   | 可   | テスト実行時のみ                                 |

## モデルウェイト

ローカル GPU 推論で使用する GGUF / HF モデルは、Hugging Face または配布元の
ライセンス (Llama 等のコミュニティライセンスを含む) を個別に確認し、
本番配布前に法務レビューを行ってください。

## 更新手順

1. 依存追加時に本表へ行を追加する PR を出す。
2. `uv.lock` / `pnpm-lock.yaml` 更新とセットでレビューする。
3. 四半期ごとに `security-scan.yml` と合わせて棚卸しする。
