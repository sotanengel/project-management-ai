"""litellm.config.yaml のロード・環境変数解決ユーティリティ。

`os.environ/VAR_NAME`形式の値を実際の環境変数値へ解決する処理を提供する
(LiteLLM本体の同等機能を模した軽量実装。実運用ではLiteLLM Proxyコンテナ
自体がこの解決を行う)。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "litellm.config.yaml"

_ENV_PREFIX = "os.environ/"


class MissingEnvVarError(RuntimeError):
    """`os.environ/VAR_NAME`参照先の環境変数が未設定の場合に送出する。"""


def resolve_env_refs(value: Any, *, strict: bool = False) -> Any:
    """設定値中の`os.environ/VAR_NAME`参照を実際の環境変数値へ再帰的に解決する。

    `strict=True`の場合、参照先の環境変数が未設定なら`MissingEnvVarError`を送出する。
    `strict=False`(既定)の場合は`None`を返す(呼び出し元でモデル選択のスキップ判定に使う)。
    """
    if isinstance(value, str) and value.startswith(_ENV_PREFIX):
        var_name = value[len(_ENV_PREFIX) :]
        resolved = os.environ.get(var_name)
        if resolved is None and strict:
            raise MissingEnvVarError(f"環境変数 {var_name!r} が未設定です(参照元: {value!r})")
        return resolved
    if isinstance(value, dict):
        return {k: resolve_env_refs(v, strict=strict) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_env_refs(v, strict=strict) for v in value]
    return value


def load_raw_config(path: Path | None = None) -> dict[str, Any]:
    """`litellm.config.yaml`を環境変数解決なしでそのままロードする。"""
    config_path = path or DEFAULT_CONFIG_PATH
    with config_path.open(encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    return loaded or {}


def load_resolved_config(path: Path | None = None, *, strict: bool = False) -> dict[str, Any]:
    """`litellm.config.yaml`をロードし、`os.environ/`参照を環境変数値へ解決して返す。"""
    raw = load_raw_config(path)
    return resolve_env_refs(raw, strict=strict)


__all__ = [
    "DEFAULT_CONFIG_PATH",
    "MissingEnvVarError",
    "load_raw_config",
    "load_resolved_config",
    "resolve_env_refs",
]
