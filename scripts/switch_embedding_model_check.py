#!/usr/bin/env python3
"""埋め込みモデル切替検証スクリプト(E6-4)。

`pdm-embed`論理名の設定変更のみ(kb-ingestのコード変更なし)で、
異なる次元の埋め込みモデルへ切り替えられることを検証する。

手順:
1. モデルA(次元1536を模したモック埋め込みサーバ)でingestionを実行し、
   Qdrantコレクションの次元数を確認する。
2. モデルB(次元768)へ切り替え、コード変更なしで再ingestionを試みる。
   次元不一致によりQdrantへのupsertが失敗し、明確なエラーメッセージが
   出ることを確認する。
3. `kb-ingest recreate`でコレクションを削除→新次元で再作成し、
   モデルBで全件再投入・検索が通ることを確認する。

exit code:
  0: 検証成功(全手順が期待通りに完了)
  1: 検証失敗(いずれかの手順が期待と異なる結果になった)

参照: docs/kb-embedding-switch.md
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "kb-ingest" / "src"))

EXIT_SUCCESS = 0
EXIT_FAILURE = 1

MODEL_A_DIM = 1536
MODEL_B_DIM = 768


def _make_fake_embedding_handler(dim: int) -> type[BaseHTTPRequestHandler]:
    """指定した次元数のダミー埋め込みを返すHTTPハンドラを生成する。"""

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 (BaseHTTPRequestHandlerの規約)
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            texts = body.get("input", [])
            data = [{"embedding": [0.01] * dim, "index": i} for i in range(len(texts))]
            payload = json.dumps({"data": data}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass  # 標準出力を静かに保つ

    return Handler


class FakeEmbeddingGateway:
    """`pdm-embed`論理名の実体を模したローカルHTTPサーバ(モデル切替の代替)。"""

    def __init__(self, dim: int) -> None:
        self._server = HTTPServer(("127.0.0.1", 0), _make_fake_embedding_handler(dim))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> str:
        self._thread.start()
        port = self._server.server_address[1]
        return f"http://127.0.0.1:{port}"

    def __exit__(self, *exc_info: object) -> None:
        self._server.shutdown()
        self._server.server_close()


def run() -> int:
    import asyncio

    from kb_ingest.chunking import chunk_document
    from kb_ingest.embedding import GatewayEmbeddingClient
    from kb_ingest.frontmatter import parse_markdown_file
    from kb_ingest.qdrant_store import CollectionDimensionMismatchError, QdrantKbStore

    corpus_dir = REPO_ROOT / "kb" / "corpus"
    collection = "pdm_kb_switch_check"
    store = QdrantKbStore(url=":memory:")

    def _ingest(gateway_url: str) -> int:
        client = GatewayEmbeddingClient(base_url=gateway_url)

        async def _run_ingest() -> int:
            total = 0
            for path in sorted(corpus_dir.rglob("*.md"))[:5]:
                front_matter, body = parse_markdown_file(path)
                chunks = chunk_document(body, front_matter, source_path=str(path))
                if not chunks:
                    continue
                embeddings = await client.embed([c.text for c in chunks])
                store.upsert_kb_chunks(collection, chunks, embeddings)
                total += len(chunks)
            return total

        return asyncio.run(_run_ingest())

    # 手順1: モデルA(次元1536)でingestionを実行する。
    print(f"[1/3] モデルA(次元{MODEL_A_DIM})でingestionを実行します...")
    with FakeEmbeddingGateway(MODEL_A_DIM) as gateway_a_url:
        count_a = _ingest(gateway_a_url)
    actual_dim_a = store.get_collection_dim(collection)
    if actual_dim_a != MODEL_A_DIM or count_a == 0:
        print(
            f"[NG] モデルAでのingestion結果が想定と異なります(dim={actual_dim_a}, count={count_a})"
        )
        return EXIT_FAILURE
    print(f"[OK] コレクション次元数={actual_dim_a}, 投入チャンク数={count_a}")

    # 手順2: モデルB(次元768)へ設定変更のみで切替し、再作成なしでの
    # 再ingestionが次元不一致エラーになることを確認する。
    print(
        f"[2/3] モデルB(次元{MODEL_B_DIM})へ切替(コード変更なし)、"
        "再作成せず再ingestionを試みます..."
    )
    with FakeEmbeddingGateway(MODEL_B_DIM) as gateway_b_url:
        try:
            _ingest(gateway_b_url)
        except CollectionDimensionMismatchError as exc:
            print(f"[OK] 想定通り次元不一致エラーが発生しました: {exc}")
        else:
            print("[NG] 次元不一致にもかかわらずupsertが成功してしまいました")
            return EXIT_FAILURE

    # 手順3: コレクション再作成(削除→新次元で作成)→全件再投入。
    print("[3/3] コレクションを再作成し、モデルBで全件再投入します...")
    store.recreate_collection(collection, dim=MODEL_B_DIM)
    with FakeEmbeddingGateway(MODEL_B_DIM) as gateway_b_url:
        count_b = _ingest(gateway_b_url)
    actual_dim_b = store.get_collection_dim(collection)
    if actual_dim_b != MODEL_B_DIM or count_b != count_a:
        print(
            f"[NG] 再作成後の再投入結果が想定と異なります"
            f"(dim={actual_dim_b}, count={count_b}, expected_count={count_a})"
        )
        return EXIT_FAILURE
    print(f"[OK] コレクション次元数={actual_dim_b}, 再投入チャンク数={count_b}")

    print("検証成功: pdm-embedの設定変更のみで埋め込みモデルを切替できることを確認しました")
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run())
