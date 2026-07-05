#!/usr/bin/env bash
# Test helper: apply ACTIVE_BACKEND mapping and print selected env vars.
set -eu

active_backend="${1:?ACTIVE_BACKEND argument required}"
export ACTIVE_BACKEND="$active_backend"
export PDM_MAIN_MODEL="${PDM_MAIN_MODEL:-anthropic/claude-sonnet-4-5}"
export PDM_MAIN_LOCAL_MODEL="${PDM_MAIN_LOCAL_MODEL:-ollama/qwen2.5:7b-instruct-q4_K_M}"
export PDM_MAIN_LOCAL_API_BASE="${PDM_MAIN_LOCAL_API_BASE:-http://ollama:11434}"

source "$(dirname "$0")/../docker-entrypoint.sh"

printf 'PDM_MAIN_MODEL=%s\n' "$PDM_MAIN_MODEL"
printf 'PDM_MAIN_API_BASE=%s\n' "${PDM_MAIN_API_BASE:-}"
printf 'PDM_MAIN_API_KEY=%s\n' "${PDM_MAIN_API_KEY:-}"
