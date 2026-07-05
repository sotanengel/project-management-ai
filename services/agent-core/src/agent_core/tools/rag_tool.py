"""RAG検索ツール(E5-3、FR-KB-04)。

kb-ingestが投入したQdrantコレクション(KB由来`source="kb"`/PMDF由来
`source="pmdf"`が同一コレクション内でペイロード区別されている)から、
model-gateway経由(論理名`pdm-embed`固定)の埋め込みを使って検索する。
結果は出典メタデータ(KB: domain/framework、PMDF: kind/id)を含み、
E5-8(根拠明示)でそのまま`x_evidence`へ変換できる形式にする。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

#: `search_knowledge`が受け付ける検索対象種別。
SearchSource = Literal["kb", "pmdf", "all"]


class EmbeddingClient(Protocol):
    """`GatewayEmbeddingClient`(kb_ingest.embedding)互換のプロトコル。"""

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class VectorStore(Protocol):
    """`QdrantKbStore`(kb_ingest.qdrant_store)互換のプロトコル。"""

    def search(
        self,
        collection: str,
        query_vector: list[float],
        *,
        source: str | None = None,
        extra_filter: dict[str, str] | None = None,
        top_k: int = 5,
    ) -> list[Any]: ...


@dataclass
class SearchResult:
    """`search_knowledge`の1検索結果(出典メタデータ付き)。"""

    text: str
    score: float | None
    source: Literal["kb", "pmdf"]
    domain: str | None = None
    framework: str | None = None
    pmdf_kind: str | None = None
    pmdf_id: str | None = None

    def to_evidence_dict(self) -> dict[str, Any]:
        """E5-8の`x_evidence`拡張フィールド形式へ変換する。

        KB由来: `{source: "kb", domain, framework, excerpt}`
        PMDF由来: `{source: "pmdf", kind, id}`
        """
        if self.source == "pmdf":
            return {"source": "pmdf", "kind": self.pmdf_kind, "id": self.pmdf_id}
        return {
            "source": "kb",
            "domain": self.domain,
            "framework": self.framework,
            "excerpt": self.text,
        }


def _to_search_result(point: Any) -> SearchResult:
    payload = point.payload or {}
    source = payload.get("source")
    if source == "pmdf":
        return SearchResult(
            text=payload.get("text", ""),
            score=getattr(point, "score", None),
            source="pmdf",
            pmdf_kind=payload.get("pmdf_kind"),
            pmdf_id=payload.get("pmdf_id"),
        )
    return SearchResult(
        text=payload.get("text", ""),
        score=getattr(point, "score", None),
        source="kb",
        domain=payload.get("domain"),
        framework=payload.get("framework"),
    )


async def search_knowledge(
    query: str,
    source: SearchSource = "all",
    domain: str | None = None,
    framework: str | None = None,
    *,
    store: VectorStore,
    embedding_client: EmbeddingClient,
    collection: str,
    top_k: int = 5,
) -> list[SearchResult]:
    """`query`をKB/PMDF横断(または片方限定)で検索し、出典付き結果を返す。

    `store`/`embedding_client`/`collection`は呼び出し側から注入する
    (テストでは`:memory:`モードの`QdrantKbStore`とモック埋め込み
    クライアントを渡す。実運用ではE6の`QdrantKbStore`/
    `GatewayEmbeddingClient`をそのまま利用する想定)。
    """
    [query_vector] = await embedding_client.embed([query])

    extra_filter: dict[str, str] = {}
    if domain is not None:
        extra_filter["domain"] = domain
    if framework is not None:
        extra_filter["framework"] = framework

    search_source = None if source == "all" else source
    points = store.search(
        collection,
        query_vector,
        source=search_source,
        extra_filter=extra_filter or None,
        top_k=top_k,
    )
    return [_to_search_result(point) for point in points]


__all__ = ["EmbeddingClient", "SearchResult", "SearchSource", "VectorStore", "search_knowledge"]
