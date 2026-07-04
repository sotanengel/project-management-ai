"""check_agent_core_isolation.py の検証ロジックに対するテスト(E5-2)。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "check_agent_core_isolation.py"
_spec = importlib.util.spec_from_file_location("check_agent_core_isolation", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
check_agent_core_isolation = importlib.util.module_from_spec(_spec)
sys.modules["check_agent_core_isolation"] = check_agent_core_isolation
_spec.loader.exec_module(check_agent_core_isolation)


def test_check_file_detects_pmdf_store_import(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad_tool.py"
    bad_file.write_text("from api_server.pmdf_store.store import PmdfStore\n", encoding="utf-8")

    violations = check_agent_core_isolation.check_file(bad_file)

    assert len(violations) == 1
    assert violations[0].module_name == "api_server.pmdf_store.store"


def test_check_file_detects_pmdf_io_import(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad_tool2.py"
    bad_file.write_text("import pmdf.io\n", encoding="utf-8")

    violations = check_agent_core_isolation.check_file(bad_file)

    assert len(violations) == 1
    assert violations[0].module_name == "pmdf.io"


def test_check_file_allows_http_client_only_module(tmp_path: Path) -> None:
    good_file = tmp_path / "good_tool.py"
    good_file.write_text("import httpx\nfrom pmdf.models import KIND_TO_MODEL\n", encoding="utf-8")

    violations = check_agent_core_isolation.check_file(good_file)

    assert violations == []


def test_check_directory_aggregates_violations_across_files(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("import pmdf.io\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("import httpx\n", encoding="utf-8")

    violations = check_agent_core_isolation.check_directory(tmp_path)

    assert len(violations) == 1


def test_actual_agent_core_source_has_no_violations() -> None:
    """実際の`services/agent-core/src`が違反を含まないことを回帰的に確認する。"""
    violations = check_agent_core_isolation.check_directory(check_agent_core_isolation.TARGET_DIR)
    assert violations == []


def test_main_returns_zero_when_no_violations() -> None:
    assert check_agent_core_isolation.main() == 0
