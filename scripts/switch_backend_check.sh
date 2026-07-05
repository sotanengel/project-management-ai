#!/usr/bin/env bash
# E4-5 (AC-02): .env の ACTIVE_BACKEND 変更のみで pdm-main のルーティング先が
# オンラインAPI⇄Ollama(モック)へ切り替わることを検証する。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

MOCK_API_PORT="${MOCK_API_PORT:-18080}"
MOCK_OLLAMA_PORT="${MOCK_OLLAMA_PORT:-11435}"
GATEWAY_PORT="${MODEL_GATEWAY_PORT:-4000}"
MOCK_API_PID=""
MOCK_OLLAMA_PID=""
GATEWAY_STARTED=0

cleanup() {
  local exit_code=$?
  echo "[cleanup] stopping resources (exit=${exit_code})..."
  if [[ "${GATEWAY_STARTED}" -eq 1 ]]; then
    docker compose --profile api-only stop model-gateway >/dev/null 2>&1 || true
    docker compose --profile api-only rm -f model-gateway >/dev/null 2>&1 || true
  fi
  if [[ -n "${MOCK_API_PID}" ]] && kill -0 "${MOCK_API_PID}" 2>/dev/null; then
    kill "${MOCK_API_PID}" 2>/dev/null || true
  fi
  if [[ -n "${MOCK_OLLAMA_PID}" ]] && kill -0 "${MOCK_OLLAMA_PID}" 2>/dev/null; then
    kill "${MOCK_OLLAMA_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

CONFIG_BASELINE_HASH="$(
  git hash-object docker-compose.yml services/model-gateway/litellm.config.yaml | sha256sum | awk '{print $1}'
)"

echo "[setup] starting mock servers..."
uv run python services/model-gateway/tests/mock_openai_compatible_server.py \
  --port "${MOCK_API_PORT}" --backend-label online-api &
MOCK_API_PID=$!
uv run python services/model-gateway/tests/mock_openai_compatible_server.py \
  --port "${MOCK_OLLAMA_PORT}" --backend-label ollama &
MOCK_OLLAMA_PID=$!
sleep 1

start_gateway() {
  docker compose --profile api-only up -d --no-deps model-gateway
  GATEWAY_STARTED=1
  for _ in $(seq 1 30); do
    if docker compose --profile api-only exec -T model-gateway python -c \
      "import urllib.request; urllib.request.urlopen('http://localhost:4000/health/liveliness')" \
      >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "ERROR: model-gateway did not become healthy" >&2
  return 1
}

request_pdm_main() {
  docker compose --profile api-only exec -T model-gateway python -c "
import json, urllib.request
payload = json.dumps({'model': 'pdm-main', 'messages': [{'role': 'user', 'content': 'ping'}]}).encode()
req = urllib.request.Request(
    'http://localhost:4000/v1/chat/completions',
    data=payload,
    headers={'Content-Type': 'application/json', 'Authorization': 'Bearer dummy'},
    method='POST',
)
resp = urllib.request.urlopen(req, timeout=30)
print(resp.read().decode())
"
}

echo "[step1] ACTIVE_BACKEND=api"
export ACTIVE_BACKEND=api
unset PDM_MAIN_MODEL
unset PDM_MAIN_API_BASE
export PDM_MAIN_API_BASE="http://host.docker.internal:${MOCK_API_PORT}"
export ANTHROPIC_API_KEY=dummy
export OPENAI_API_KEY=dummy
start_gateway
RESP_API="$(request_pdm_main)"
echo "${RESP_API}" | grep -q "mock-response-from-online-api"

echo "[step2] ACTIVE_BACKEND=ollama (code/config unchanged)"
docker compose --profile api-only stop model-gateway >/dev/null
docker compose --profile api-only rm -f model-gateway >/dev/null
export ACTIVE_BACKEND=ollama
unset PDM_MAIN_API_BASE
export PDM_MAIN_LOCAL_API_BASE="http://host.docker.internal:${MOCK_OLLAMA_PORT}"
start_gateway
RESP_OLLAMA="$(request_pdm_main)"
echo "${RESP_OLLAMA}" | grep -q "mock-response-from-ollama"

echo "[step3] verify tracked config files unchanged during run"
CONFIG_CURRENT_HASH="$(
  git hash-object docker-compose.yml services/model-gateway/litellm.config.yaml | sha256sum | awk '{print $1}'
)"
if [[ "${CONFIG_BASELINE_HASH}" != "${CONFIG_CURRENT_HASH}" ]]; then
  echo "ERROR: docker-compose.yml or litellm.config.yaml changed during switch check" >&2
  exit 1
fi

echo "switch_backend_check: OK (api + ollama routing verified)"
