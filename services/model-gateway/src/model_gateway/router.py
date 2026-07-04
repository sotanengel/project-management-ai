"""litellm.config.yaml を参照して論理名→バックエンドのルーティングを行う軽量Router。

実運用ではLiteLLM Proxyコンテナ自身がこのルーティング・フォールバック・
リトライ処理を行う。本モジュールはCI環境でlitellmパッケージ本体を追加
できない制約(pmdfのtyperバージョン要件との衝突)の下で、
`litellm.config.yaml`が記述するルーティング契約(AR-01〜AR-03)を
respx等でモック可能な形でPythonから直接検証するためのテスト用参照実装。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from model_gateway.config import load_raw_config, resolve_env_refs


@dataclass
class Deployment:
    """`model_list`の1エントリ(1バックエンド定義)。"""

    model_name: str
    model: str | None
    api_base: str | None
    api_key: str | None
    extra: dict[str, Any] = field(default_factory=dict)


class AllBackendsFailedError(RuntimeError):
    """論理名に紐づく全デプロイメント(フォールバック含む)が失敗した場合に送出する。"""


class RequestTimeoutError(RuntimeError):
    """設定されたタイムアウトを超過した場合に送出する。"""


class GatewayRouter:
    """`litellm.config.yaml`のmodel_list/router_settingsを解釈する最小限のRouter。

    - 論理名(model_name)ごとのデプロイメント一覧を保持する。
    - `router_settings.fallbacks`に従い、主デプロイメント失敗時に予備へフォールバックする。
    - `router_settings.num_retries`回まで同一デプロイメントへリトライする。
    - `router_settings.timeout`(秒)を超えるレスポンスは`RequestTimeoutError`とする。
    """

    def __init__(self, config: dict[str, Any], *, client: httpx.AsyncClient | None = None) -> None:
        self._config = config
        self._client = client or httpx.AsyncClient()
        self._deployments: dict[str, list[Deployment]] = {}
        for entry in config.get("model_list", []):
            params = dict(entry["litellm_params"])
            model_name = entry["model_name"]
            deployment = Deployment(
                model_name=model_name,
                model=params.pop("model", None),
                api_base=params.pop("api_base", None),
                api_key=params.pop("api_key", None),
                extra=params,
            )
            self._deployments.setdefault(model_name, []).append(deployment)

        router_settings = config.get("router_settings", {}) or {}
        self.num_retries: int = router_settings.get("num_retries", 0)
        self.timeout: float = router_settings.get("timeout", 30)
        self.cooldown_time: float = router_settings.get("cooldown_time", 0)
        self._fallback_map: dict[str, list[str]] = {}
        for mapping in router_settings.get("fallbacks", []) or []:
            for primary, fallback_names in mapping.items():
                self._fallback_map[primary] = list(fallback_names)

    @classmethod
    def from_yaml(cls, path: Path, *, client: httpx.AsyncClient | None = None) -> GatewayRouter:
        raw = load_raw_config(path)
        resolved = resolve_env_refs(raw, strict=False)
        return cls(resolved, client=client)

    def deployments_for(self, logical_name: str) -> list[Deployment]:
        return self._deployments.get(logical_name, [])

    def _fallback_chain(self, logical_name: str) -> list[str]:
        """`logical_name`自身を先頭に、フォールバック先を順に並べたモデル名リストを返す。"""
        chain = [logical_name]
        chain.extend(self._fallback_map.get(logical_name, []))
        return chain

    @staticmethod
    def _default_api_base(model: str | None) -> str:
        """`model`のプロバイダプレフィックス(`anthropic/`, `openai/`, `bedrock/`等)から
        既定のAPIベースURLを推定する(`api_base`が明示されていない場合のみ使用)。
        """
        if model is None:
            return "https://api.anthropic.com"
        if model.startswith("openai/"):
            return "https://api.openai.com"
        if model.startswith("bedrock/"):
            return "https://bedrock-runtime.amazonaws.com"
        # anthropic/ プレフィックス、または未知プレフィックスは既定でAnthropicとする。
        return "https://api.anthropic.com"

    async def _call_deployment(
        self, deployment: Deployment, *, payload: dict[str, Any]
    ) -> httpx.Response:
        base_url = deployment.api_base or self._default_api_base(deployment.model)
        url = f"{base_url.rstrip('/')}/v1/messages"
        headers = {}
        if deployment.api_key:
            headers["x-api-key"] = deployment.api_key

        start = time.monotonic()
        request_body = {**payload, "model": deployment.model}
        try:
            response = await asyncio.wait_for(
                self._client.post(url, json=request_body, headers=headers),
                timeout=self.timeout,
            )
        except TimeoutError as exc:
            elapsed = time.monotonic() - start
            raise RequestTimeoutError(
                f"{deployment.model_name} ({url}) がタイムアウトしました"
                f"({self.timeout}秒、経過{elapsed:.2f}秒)"
            ) from exc
        if response.status_code >= 500:
            raise httpx.HTTPStatusError(
                f"backend error: {response.status_code}",
                request=response.request,
                response=response,
            )
        return response

    async def completion(
        self, logical_name: str, *, payload: dict[str, Any] | None = None
    ) -> httpx.Response:
        """論理名でリクエストを送信する。

        - 主デプロイメントへ`num_retries`回までリトライする。
        - 全リトライ失敗後、`router_settings.fallbacks`に定義されたフォールバック先へ
          順に切り替える。
        - 全経路が失敗した場合は`AllBackendsFailedError`を送出する。
        """
        payload = payload or {"messages": [{"role": "user", "content": "ping"}]}
        last_error: Exception | None = None

        for candidate_name in self._fallback_chain(logical_name):
            deployments = self.deployments_for(candidate_name)
            if not deployments:
                continue
            deployment = deployments[0]

            attempts = 1 + max(self.num_retries, 0)
            for _attempt in range(attempts):
                try:
                    return await self._call_deployment(deployment, payload=payload)
                except RequestTimeoutError as exc:
                    last_error = exc
                    continue
                except (httpx.HTTPStatusError, httpx.ConnectError) as exc:
                    last_error = exc
                    continue

        raise AllBackendsFailedError(
            f"論理名 {logical_name!r} の全バックエンド(フォールバック含む)が失敗しました"
        ) from last_error


__all__ = [
    "AllBackendsFailedError",
    "Deployment",
    "GatewayRouter",
    "RequestTimeoutError",
]
