# model-gateway: LiteLLM Proxyコンテナ定義。
#
# 公式イメージをベースに、論理名ルーティング設定(litellm.config.yaml)を
# コピーする。実際のバックエンド選択・APIキーは環境変数(.env)経由で注入する
# (SEC-01: シークレットの直書き禁止)。
FROM ghcr.io/berriai/litellm:main-stable

WORKDIR /app

COPY litellm.config.yaml /app/litellm.config.yaml
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 4000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["litellm", "--config", "/app/litellm.config.yaml", "--port", "4000"]
