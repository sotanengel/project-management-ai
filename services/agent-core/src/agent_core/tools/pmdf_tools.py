"""エージェントがPMDFを操作するためのツール群(E5-2)。

設計原則3(人間監督の内蔵)/設計原則2(PMDF中心設計): エージェントは
PMDFへの直接書込を一切行わず、api-serverのREST API(`POST /pmdf/{kind}`
等)をHTTP経由で呼び出すクライアントとしてのみ振る舞う。本モジュールは
`pmdf`パッケージの永続化層(`pmdf.io`)や`api_server.pmdf_store`を
一切importしない(`tests/test_pmdf_tools.py`の静的チェックで保証)。

認証はサービスアカウント(JWT、`auth_token`として注入)。全ツール
呼び出しはapi-server側の監査ログに`actor=agent:<name>@v<version>`と
して記録される(api-server側の`_actor_from_user`はUserベースのため、
本クライアントは`X-Agent-Actor`ヘッダで実際のactor文字列をapi-server
へ伝搬する)。
"""

from __future__ import annotations

from typing import Any

import httpx

#: agent-coreからのリクエストであることをapi-server側へ伝える識別ヘッダ。
#: api-serverはこのヘッダが存在する場合、監査ログのactorをこの値で
#: 上書きする(`agent:<name>@v<version>`形式)。
AGENT_ACTOR_HEADER = "X-Agent-Actor"


class PmdfToolClient:
    """api-server経由でPMDFエンティティを操作するツールクライアント。"""

    def __init__(
        self,
        *,
        api_server_url: str,
        auth_token: str,
        agent_name: str,
        agent_version: str,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = api_server_url.rstrip("/")
        self._auth_token = auth_token
        self._agent_actor = f"agent:{agent_name}@v{agent_version}"
        self._timeout = timeout
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._auth_token}",
            AGENT_ACTOR_HEADER: self._agent_actor,
        }

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url, timeout=self._timeout, transport=self._transport
        )

    async def create_entity(self, *, kind: str, data: dict[str, Any]) -> dict[str, Any]:
        """`POST /pmdf/{kind}`を呼び出し、作成されたエンティティを返す。"""
        async with self._client() as client:
            response = await client.post(f"/pmdf/{kind}", json=data, headers=self._headers())
            response.raise_for_status()
            return dict(response.json())

    async def get_entity(self, *, kind: str, entity_id: str) -> dict[str, Any]:
        """`GET /pmdf/{kind}/{id}`を呼び出し、エンティティを返す。"""
        async with self._client() as client:
            response = await client.get(f"/pmdf/{kind}/{entity_id}", headers=self._headers())
            response.raise_for_status()
            return dict(response.json())

    async def update_entity(
        self, *, kind: str, entity_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """`PUT /pmdf/{kind}/{id}`を呼び出し、更新後のエンティティを返す。"""
        async with self._client() as client:
            response = await client.put(
                f"/pmdf/{kind}/{entity_id}", json=data, headers=self._headers()
            )
            response.raise_for_status()
            return dict(response.json())

    async def search_entities(
        self, *, kind: str, product: str | None = None
    ) -> list[dict[str, Any]]:
        """`GET /pmdf/{kind}`(一覧、`product`絞り込み対応)を呼び出す。"""
        params: dict[str, str] = {}
        if product is not None:
            params["product"] = product
        async with self._client() as client:
            response = await client.get(f"/pmdf/{kind}", params=params, headers=self._headers())
            response.raise_for_status()
            return list(response.json())

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        raise_for_status: bool = True,
    ) -> httpx.Response:
        """PMDF CRUD以外のapi-serverエンドポイント(承認・L1実行系等)を呼び出す汎用メソッド。

        `create_entity`等と同じ接続設定(base_url/認証ヘッダ/transport)を
        再利用することで、業務グラフ側がテスト用transportを個別に
        組み立てる必要をなくす。`raise_for_status=False`の場合、
        エラーレスポンス(403等)でも例外を送出せずそのまま返す
        (呼び出し側でステータスコードに応じた分岐を行いたい場合用)。
        """
        async with self._client() as client:
            response = await client.request(method, path, json=json, headers=self._headers())
            if raise_for_status:
                response.raise_for_status()
            return response


__all__ = ["AGENT_ACTOR_HEADER", "PmdfToolClient"]
