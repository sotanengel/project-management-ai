"""E4-5: ACTIVE_BACKEND による pdm-main バックエンド切替のユニットテスト。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PROBE_SCRIPT = "services/model-gateway/tests/_run_entrypoint_probe.sh"


def _run_entrypoint(active_backend: str) -> dict[str, str]:
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PDM_MAIN_MODEL": "anthropic/claude-sonnet-4-5",
        "PDM_MAIN_LOCAL_MODEL": "ollama/qwen2.5:7b-instruct-q4_K_M",
        "PDM_MAIN_LOCAL_API_BASE": "http://ollama:11434",
        "ANTHROPIC_API_KEY": "dummy",
    }
    result = subprocess.run(
        ["bash", PROBE_SCRIPT, active_backend],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=True,
    )
    parsed: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            parsed[key] = value
    return parsed


def test_active_backend_api_sets_online_model() -> None:
    env = _run_entrypoint("api")
    assert env["PDM_MAIN_MODEL"] == "anthropic/claude-sonnet-4-5"
    assert env.get("PDM_MAIN_API_BASE", "") == ""


def test_active_backend_ollama_sets_local_model_and_api_base() -> None:
    env = _run_entrypoint("ollama")
    assert env["PDM_MAIN_MODEL"] == "openai/qwen2.5:7b-instruct-q4_K_M"
    assert env["PDM_MAIN_API_BASE"] == "http://ollama:11434/v1"


def test_active_backend_invalid_value_fails() -> None:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        ["bash", PROBE_SCRIPT, "invalid"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert result.returncode != 0
