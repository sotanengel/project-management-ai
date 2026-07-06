"""E9-2: 予算超過フラグとコストAPI拡張のテスト。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from api_server.costs.budget_state import is_learning_blocked, set_learning_blocked


def test_budget_state_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "budget_exceeded.json"
    assert is_learning_blocked(path) is False
    set_learning_blocked(path, blocked=True)
    assert is_learning_blocked(path) is True
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"learning_blocked": True}
