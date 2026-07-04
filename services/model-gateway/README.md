# model-gateway

全LLM・埋め込み呼び出しの単一窓口となるLiteLLM Proxyの設定
(`litellm.config.yaml`)とコンテナ定義(`Dockerfile`)を提供するサービス。
エピックE4で実装。

論理名(`pdm-main` / `pdm-teacher` / `pdm-judge` / `pdm-embed`)から実モデル・
実バックエンド(Anthropic API / OpenAI API / AWS Bedrock / Ollama等の
OpenAI互換ローカルサーバ)への対応関係は本サービスの設定にのみ記述し、
呼び出し側(agent-core等)には実モデル名をハードコードしない(AR-01, AR-02)。

`src/model_gateway/` はCI環境で`litellm`パッケージ本体を追加できない制約
(litellm 1.90.2 が要求する `typer<0.26` 系と、`packages/pmdf` が要求する
`typer>=0.26.8` が競合するため)の下で、`litellm.config.yaml` のルーティング・
フォールバック・リトライ契約をrespx等でモック検証するための軽量参照実装。
実運用のプロキシ処理自体は公式`ghcr.io/berriai/litellm`イメージが担う。

詳細は `docs/IMPLEMENTATION_STATE.md` を参照。
