"""緊急停止(`api_server.autonomy.emergency_stop`)のテスト(E3-8)。"""

from __future__ import annotations

from pathlib import Path


def test_is_stopped_defaults_to_false(tmp_path: Path) -> None:
    from api_server.autonomy.emergency_stop import is_stopped

    state_path = tmp_path / "emergency_stop.json"

    assert is_stopped(state_path) is False


def test_stop_then_is_stopped_true(tmp_path: Path) -> None:
    from api_server.autonomy.emergency_stop import is_stopped, stop

    state_path = tmp_path / "emergency_stop.json"

    stop(state_path)

    assert is_stopped(state_path) is True


def test_release_after_stop_returns_to_false(tmp_path: Path) -> None:
    from api_server.autonomy.emergency_stop import is_stopped, release, stop

    state_path = tmp_path / "emergency_stop.json"

    stop(state_path)
    release(state_path)

    assert is_stopped(state_path) is False
