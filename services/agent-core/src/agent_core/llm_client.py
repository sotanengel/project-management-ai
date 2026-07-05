"""model-gateway経由(OpenAI互換 `/chat/completions`)のLLMクライアント(E5-1)。

AR-01: モデル指定は論理名のみ(`pdm-main`/`pdm-teacher`/`pdm-judge`/
`pdm-embed`)。接続先はコンストラクタで受け取る`model_gateway_url`の
みであり、プロバイダSDKを直接呼び出すことは無い。`model`引数の型を
`LogicalModelName`(4値のLiteral)に限定することで、未定義の論理名
(実モデル名の直接指定等)を渡すコードがmypyでコンパイルエラーになる
ことを型レベルで強制する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, get_args

import httpx

#: agent-coreがLLM呼び出しに使用できる論理名(実モデル名は一切扱わない)。
LogicalModelName = Literal["pdm-main", "pdm-teacher", "pdm-judge", "pdm-embed"]

#: `LogicalModelName`の全値(実行時検証・テストで利用)。
LOGICAL_MODEL_NAMES: tuple[LogicalModelName, ...] = get_args(LogicalModelName)

Message = dict[str, str]


@dataclass
class CompletionResult:
    """`/chat/completions`のレスポンスをパースした結果。"""

    content: str
    raw: dict[str, Any] = field(default_factory=dict)


class LogicalModelClient:
    """model-gateway(LiteLLM Proxy、OpenAI互換)経由のLLM呼び出しクライアント。

    実モデル名・実バックエンドは一切保持しない。`model_gateway_url`
    (環境変数`MODEL_GATEWAY_URL`から注入する想定)のみを接続先とする。
    """

    def __init__(self, model_gateway_url: str, timeout: float = 60.0) -> None:
        self._base_url = model_gateway_url.rstrip("/")
        self._timeout = timeout

    async def complete(
        self,
        *,
        model: LogicalModelName,
        messages: list[Message],
        **extra: Any,
    ) -> CompletionResult:
        """`model`(論理名)を指定してchat completionを実行し、結果をパースして返す。"""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                json={"model": model, "messages": messages, **extra},
            )
            response.raise_for_status()
            body: dict[str, Any] = response.json()

        content = body["choices"][0]["message"]["content"]
        return CompletionResult(content=content, raw=body)


__all__ = ["LOGICAL_MODEL_NAMES", "CompletionResult", "LogicalModelClient", "LogicalModelName"]
