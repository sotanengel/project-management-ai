# web-ui: Vite ビルド + nginx 静的配信
FROM node:22-alpine AS build

WORKDIR /app

RUN corepack enable

COPY services/web-ui/package.json services/web-ui/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY services/web-ui/tsconfig.json services/web-ui/tsconfig.app.json services/web-ui/tsconfig.node.json services/web-ui/vite.config.ts services/web-ui/index.html ./
COPY services/web-ui/src ./src

ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN pnpm build

FROM nginx:1.27-alpine

RUN apk add --no-cache curl

COPY services/web-ui/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=5 --start-period=10s \
    CMD curl -f http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
