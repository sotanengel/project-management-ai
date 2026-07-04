"""PMDFエンティティ変更イベントをベクトル化しQdrantへ投入するインデクサ(E6-3)。

api-server(E3-10)のWebSocketイベント(`pmdf.entity_changed`、
`{kind, id, verb}`)を購読し、変更されたエンティティの内容を取得して
テキスト表現へ変換、埋め込み取得後にQdrantへupsertする。KB由来
(`source="kb"`)とは同一コレクション内でペイロードの`source="pmdf"`に
より区別する(E5-3の`search_knowledge`が`source`パラメータで
フィルタする設計と整合させるため)。

エンティティ本体の取得はapi-serverへの依存を最小化するため、
`fetch_entity(kind, id) -> dict | None` という非同期callableとして
外部から注入する(実運用ではapi-serverの`GET /pmdf/{kind}/{id}`を
呼び出すHTTPクライアントを渡す想定。単体テストではフェイク関数を渡す)。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from kb_ingest.qdrant_store import QdrantKbStore

#: kind別のテキスト抽出フィールド定義(packages/pmdfの各モデル定義に対応)。
#: 左から優先して結合する。
_KIND_TEXT_FIELDS: dict[str, list[str]] = {
    "story": ["title", "as_a", "i_want", "so_that"],
    "decision": ["name", "background", "chosen_option", "rationale"],
    "objective": ["objective", "description"],
    "initiative": ["name", "description"],
    "risk": ["event", "response_strategy"],
    "experiment": ["hypothesis", "design", "results", "learnings"],
    "roadmap_item": ["theme"],
    "report": ["period", "summary"],
    "metric": ["name", "description"],
    "persona": ["name", "description"],
    "stakeholder": ["name", "description"],
    "product": ["name", "description"],
    "release": ["name", "description"],
}

#: kind別定義が無い場合に試すフォールバックフィールド(存在するものだけ使う)。
_FALLBACK_TEXT_FIELDS = ["title", "name", "description", "summary", "rationale"]


def extract_entity_text(kind: str, entity: dict[str, Any]) -> str:
    """PMDFエンティティのdict表現からベクトル化対象のテキストを抽出する。

    kind別に定義されたフィールド群を優先して結合し、未知のkindでは
    フォールバックフィールドのうち存在するものだけを結合する。
    """
    fields = _KIND_TEXT_FIELDS.get(kind, _FALLBACK_TEXT_FIELDS)
    parts = [str(entity[field]) for field in fields if entity.get(field)]
    return "\n".join(parts)


class EmbeddingClientProtocol(Protocol):
    """`kb_ingest.embedding.GatewayEmbeddingClient`が満たすプロトコル。"""

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


FetchEntity = Callable[[str, str], Awaitable[dict[str, Any] | None]]


class PmdfIndexer:
    """PMDFエンティティ変更イベントを受け取りQdrantへ投入するコンシューマ。"""

    def __init__(
        self,
        *,
        store: QdrantKbStore,
        embedding_client: EmbeddingClientProtocol,
        fetch_entity: FetchEntity,
        collection: str = "pdm_kb",
    ) -> None:
        self._store = store
        self._embedding_client = embedding_client
        self._fetch_entity = fetch_entity
        self._collection = collection

    async def handle_event(self, event_data: dict[str, Any]) -> None:
        """`pmdf.entity_changed`イベントの`data`部分を処理する。

        対応するエンティティが取得できない場合(削除済み・取得失敗等)は
        何もせずスキップする(例外は送出しない)。
        """
        kind = event_data["kind"]
        entity_id = event_data["id"]

        entity = await self._fetch_entity(kind, entity_id)
        if entity is None:
            return

        text = extract_entity_text(kind, entity)
        if not text:
            return

        embeddings = await self._embedding_client.embed([text])
        if not embeddings:
            return

        product_id = entity.get("product") if kind != "product" else entity.get("id")
        self._store.upsert_pmdf_entity(
            self._collection,
            pmdf_kind=kind,
            pmdf_id=entity_id,
            product_id=product_id,
            text=text,
            embedding=embeddings[0],
        )

    async def consume_forever(self, queue: Any) -> None:
        """`asyncio.Queue`(または互換オブジェクト)からイベントを取り出し続ける。

        `event["type"] == "pmdf.entity_changed"`のイベントのみ処理する
        (`api_server.events.bus.Event`形式、`{"type": ..., "data": ...}`)。
        呼び出し側で`asyncio.create_task`等により常駐させる想定。
        """
        while True:
            event = await queue.get()
            if event.get("type") == "pmdf.entity_changed":
                await self.handle_event(event["data"])


__all__ = ["EmbeddingClientProtocol", "FetchEntity", "PmdfIndexer", "extract_entity_text"]
