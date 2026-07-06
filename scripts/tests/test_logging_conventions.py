"""E9-3: 構造化ログ規約のテスト。"""

from __future__ import annotations

import json
from pathlib import Path

from agent_core.logging import configure_logging, get_logger


def test_logging_conventions_doc_exists() -> None:
    doc = Path("docs/logging-conventions.md")
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "timestamp" in text
    assert "trace_id" in text


def test_agent_core_logger_emits_json(capsys: object) -> None:
    configure_logging()
    logger = get_logger("test")
    logger.info("hello", trace_id="trace-1")
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    line = captured.out.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload.get("message") == "hello" or payload.get("event") == "hello"
    assert payload["service"] == "agent-core"
    assert "timestamp" in payload
    assert payload.get("trace_id") == "trace-1"
