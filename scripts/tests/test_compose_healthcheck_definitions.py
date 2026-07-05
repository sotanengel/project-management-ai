"""E4-4: docker-compose の常時稼働サービスに実ヘルスチェックが定義されていることを検証する。"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"

# api-only プロファイルで起動する常時稼働サービス(E4-4 AC-01)
API_ONLY_ALWAYS_ON = frozenset(
    {
        "web-ui",
        "api-server",
        "agent-core",
        "pmdf-store",
        "model-gateway",
        "qdrant",
        "minio",
        "mlflow",
        "scheduler",
    }
)

STUB_HEALTHCHECK = ["CMD", "true"]


def _load_compose() -> dict:
    with COMPOSE_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_api_only_services_have_non_stub_healthchecks() -> None:
    compose = _load_compose()
    services = compose["services"]
    missing: list[str] = []
    stubbed: list[str] = []

    for name in sorted(API_ONLY_ALWAYS_ON):
        if name not in services:
            missing.append(name)
            continue
        healthcheck = services[name].get("healthcheck") or {}
        test_cmd = healthcheck.get("test")
        if test_cmd == STUB_HEALTHCHECK:
            stubbed.append(name)

    assert not missing, f"compose に未定義の常時稼働サービス: {missing}"
    assert not stubbed, f"スタブ healthcheck (CMD true) のまま: {stubbed}"


def test_api_only_services_use_build_not_placeholder_image() -> None:
    compose = _load_compose()
    services = compose["services"]
    placeholders: list[str] = []

    for name in (
        "web-ui",
        "api-server",
        "agent-core",
        "pmdf-store",
        "model-gateway",
        "scheduler",
    ):
        svc = services[name]
        if "build" not in svc and svc.get("image") == "python:3.12-slim":
            placeholders.append(name)

    assert not placeholders, f"プレースホルダ image のまま: {placeholders}"
