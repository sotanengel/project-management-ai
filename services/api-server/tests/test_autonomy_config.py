"""自律レベル設定(`api_server.autonomy.config`)のテスト(E3-8)。"""

from __future__ import annotations

from pathlib import Path


def test_get_level_returns_default_l0_when_unset(tmp_path: Path) -> None:
    from api_server.autonomy.config import get_level

    config_path = tmp_path / "autonomy.json"

    level = get_level(config_path, product_id="prod-A", business_function="roadmap")

    assert level == "L0"


def test_set_level_then_get_level_roundtrip(tmp_path: Path) -> None:
    from api_server.autonomy.config import get_level, set_level

    config_path = tmp_path / "autonomy.json"

    set_level(config_path, product_id="prod-A", business_function="roadmap", level="L2")
    level = get_level(config_path, product_id="prod-A", business_function="roadmap")

    assert level == "L2"


def test_set_level_does_not_affect_other_product_or_function(tmp_path: Path) -> None:
    from api_server.autonomy.config import get_level, set_level

    config_path = tmp_path / "autonomy.json"

    set_level(config_path, product_id="prod-A", business_function="roadmap", level="L2")

    assert get_level(config_path, product_id="prod-B", business_function="roadmap") == "L0"
    assert get_level(config_path, product_id="prod-A", business_function="backlog") == "L0"


def test_list_all_returns_all_configured_entries(tmp_path: Path) -> None:
    from api_server.autonomy.config import list_all, set_level

    config_path = tmp_path / "autonomy.json"
    set_level(config_path, product_id="prod-A", business_function="roadmap", level="L2")
    set_level(config_path, product_id="prod-A", business_function="backlog", level="L1")

    entries = list_all(config_path)

    assert len(entries) == 2
    levels = {(e.product_id, e.business_function): e.level for e in entries}
    assert levels[("prod-A", "roadmap")] == "L2"
    assert levels[("prod-A", "backlog")] == "L1"


def test_invalid_business_function_raises_value_error(tmp_path: Path) -> None:
    import pytest
    from api_server.autonomy.config import set_level

    config_path = tmp_path / "autonomy.json"

    with pytest.raises(ValueError):
        set_level(config_path, product_id="prod-A", business_function="not_a_function", level="L1")
