"""E8-8: 昇格時 Ollama アダプタ差替フック(FR-SL-08)。"""

from __future__ import annotations

import httpx


async def promote_model(adapter_path: str, ollama_url: str) -> None:
    """昇格判定後に Ollama へアダプタ差替リクエストを送る。"""
    base = ollama_url.rstrip("/")
    payload = {
        "name": "pdm-student-promoted",
        "adapter": adapter_path,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(f"{base}/api/adapters/load", json=payload)
        response.raise_for_status()
