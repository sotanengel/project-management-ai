"""Qdrantへのコレクション作成・upsert・検索を行うストア層(E6-2/E6-3/E6-4)。

KB由来(`source="kb"`)とPMDF由来(`source="pmdf"`)は同一コレクション内で
ペイロードの `source` フィールドにより区別する(E5-3の `search_knowledge`
の設計と整合させるため)。
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from kb_ingest.chunking import Chunk

#: コレクション未作成時の既定の距離指標。
DEFAULT_DISTANCE = Distance.COSINE


def _stable_point_id(*parts: str) -> str:
    """安定したQdrantポイントID(UUID文字列)を`parts`の内容から決定的に生成する。

    同一の`parts`からは常に同一のUUIDが得られるため、再投入時に
    自然に上書き(upsert)される(冪等性の担保)。
    """
    digest = hashlib.sha256("::".join(parts).encode("utf-8")).digest()
    return str(uuid.UUID(bytes=digest[:16]))


def kb_chunk_point_id(source_path: str, chunk_index: int) -> str:
    """KBチャンク用の安定ポイントIDを生成する。"""
    return _stable_point_id("kb", source_path, str(chunk_index))


def pmdf_point_id(pmdf_kind: str, pmdf_id: str) -> str:
    """PMDFエンティティ用の安定ポイントIDを生成する(E6-3)。

    エンティティ単位で1ポイントとするため、`chunk_index`は含めない
    (同一エンティティの再インデックス時に確実に上書きされるようにする)。
    """
    return _stable_point_id("pmdf", pmdf_kind, pmdf_id)


class CollectionDimensionMismatchError(RuntimeError):
    """既存コレクションの次元数と投入しようとしたベクトルの次元数が異なる場合の例外(E6-4)。"""

    def __init__(self, collection: str, existing_dim: int, new_dim: int) -> None:
        super().__init__(
            f"コレクション '{collection}' の既存次元数({existing_dim})と"
            f"投入しようとした埋め込みの次元数({new_dim})が一致しません。"
            "埋め込みモデルの次元数を変更した場合は "
            "`kb-ingest recreate --collection <name> --dim <new_dim>` で"
            "コレクションを削除・再作成してから再投入してください。"
        )
        self.collection = collection
        self.existing_dim = existing_dim
        self.new_dim = new_dim


class QdrantKbStore:
    """KB/PMDFベクトルを投入・検索するQdrantストア。"""

    def __init__(self, url: str = ":memory:") -> None:
        self._client = QdrantClient(url) if url == ":memory:" else QdrantClient(url=url)

    @property
    def client(self) -> QdrantClient:
        return self._client

    def _ensure_collection(self, collection: str, dim: int) -> None:
        if not self._client.collection_exists(collection):
            self._client.create_collection(
                collection,
                vectors_config=VectorParams(size=dim, distance=DEFAULT_DISTANCE),
            )
            return

        existing_dim = self.get_collection_dim(collection)
        if existing_dim != dim:
            raise CollectionDimensionMismatchError(collection, existing_dim, dim)

    def get_collection_dim(self, collection: str) -> int:
        """コレクションのベクトル次元数を返す。"""
        info = self._client.get_collection(collection)
        vectors_config = info.config.params.vectors
        size = vectors_config.size  # type: ignore[union-attr]
        return int(size)

    def count(self, collection: str) -> int:
        """コレクション内のポイント数を返す。"""
        return int(self._client.count(collection).count)

    def upsert_kb_chunks(
        self,
        collection: str,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> None:
        """KBチャンクを埋め込みとともにQdrantへupsertする(`source="kb"`)。"""
        if not chunks:
            return
        if len(chunks) != len(embeddings):
            raise ValueError("chunksとembeddingsの件数が一致しません")

        dim = len(embeddings[0])
        self._ensure_collection(collection, dim)

        points = [
            PointStruct(
                id=kb_chunk_point_id(chunk.source_path, chunk.chunk_index),
                vector=embedding,
                payload={
                    "source": "kb",
                    "domain": chunk.domain,
                    "framework": chunk.framework,
                    "pm_principle": chunk.pm_principle,
                    "title": chunk.title,
                    "file_path": chunk.source_path,
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                },
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        self._client.upsert(collection, points=points)

    def upsert_pmdf_entity(
        self,
        collection: str,
        *,
        pmdf_kind: str,
        pmdf_id: str,
        product_id: str | None,
        text: str,
        embedding: list[float],
    ) -> None:
        """PMDFエンティティ1件をQdrantへupsertする(`source="pmdf"`、E6-3)。"""
        self._ensure_collection(collection, len(embedding))
        point = PointStruct(
            id=pmdf_point_id(pmdf_kind, pmdf_id),
            vector=embedding,
            payload={
                "source": "pmdf",
                "pmdf_kind": pmdf_kind,
                "pmdf_id": pmdf_id,
                "product_id": product_id,
                "text": text,
            },
        )
        self._client.upsert(collection, points=[point])

    def scroll_all(self, collection: str) -> list[Any]:
        """コレクション内の全ポイントを返す(テスト用途)。"""
        points, _next_offset = self._client.scroll(collection, limit=10_000)
        return points

    def search(
        self,
        collection: str,
        query_vector: list[float],
        *,
        source: str | None = None,
        extra_filter: dict[str, str] | None = None,
        top_k: int = 5,
    ) -> list[Any]:
        """`query_vector` に近いポイントを検索する。

        `source`("kb"/"pmdf")や`extra_filter`(domain等の追加条件)で
        ペイロードフィルタを掛けられる(E5-3 `search_knowledge` から利用)。
        """
        must: list[Any] = []
        if source is not None:
            must.append(FieldCondition(key="source", match=MatchValue(value=source)))
        if extra_filter:
            for key, value in extra_filter.items():
                must.append(FieldCondition(key=key, match=MatchValue(value=value)))

        query_filter = Filter(must=must) if must else None
        result = self._client.query_points(
            collection,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
        )
        return result.points

    def recreate_collection(self, collection: str, *, dim: int) -> None:
        """コレクションを削除し、新しい次元数で再作成する(E6-4)。"""
        if self._client.collection_exists(collection):
            self._client.delete_collection(collection)
        self._client.create_collection(
            collection,
            vectors_config=VectorParams(size=dim, distance=DEFAULT_DISTANCE),
        )


__all__ = [
    "CollectionDimensionMismatchError",
    "QdrantKbStore",
    "kb_chunk_point_id",
    "pmdf_point_id",
]
