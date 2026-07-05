# pmdf-store: Git 永続化ボリュームの初期化(E4-4 スケルトン)
FROM alpine:3.21

RUN apk add --no-cache git bash

COPY services/pmdf-store/docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME ["/data/pmdf"]

HEALTHCHECK --interval=30s --timeout=5s --retries=5 --start-period=5s \
    CMD test -d /data/pmdf

ENTRYPOINT ["/entrypoint.sh"]
