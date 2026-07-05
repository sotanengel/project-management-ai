#!/usr/bin/env bash
# E4-5: ACTIVE_BACKEND=api|ollama により pdm-main の実バックエンドを .env のみで切替。
set -eu

case "${ACTIVE_BACKEND:-api}" in
  api)
    export PDM_MAIN_MODEL="${PDM_MAIN_MODEL:-anthropic/claude-sonnet-4-5}"
    export PDM_MAIN_API_KEY="${ANTHROPIC_API_KEY:-dummy}"
    if [[ -n "${PDM_MAIN_API_BASE:-}" ]]; then
      export PDM_MAIN_API_BASE
    else
      unset PDM_MAIN_API_BASE
    fi
    ;;
  ollama)
    local_model="${PDM_MAIN_LOCAL_MODEL:-ollama/qwen2.5:7b-instruct-q4_K_M}"
    model_name="${local_model#ollama/}"
    export PDM_MAIN_MODEL="openai/${model_name}"
    api_base="${PDM_MAIN_LOCAL_API_BASE:-http://127.0.0.1:11434}"
    api_base="${api_base%/}"
    export PDM_MAIN_API_BASE="${api_base}/v1"
    export PDM_MAIN_API_KEY="${OPENAI_API_KEY:-dummy}"
    ;;
  *)
    echo "ERROR: ACTIVE_BACKEND must be 'api' or 'ollama', got: ${ACTIVE_BACKEND}" >&2
    exit 1
    ;;
esac

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  exec "$@"
fi
