"""verify_registry_guard.py の結果分類ロジックに対するテスト。

実際のnpm実行やネットワークアクセスはモックし、
`classify_result` の分岐(成功/失敗/未検証)のみを検証する。
"""

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "verify_registry_guard.py"
_spec = importlib.util.spec_from_file_location("verify_registry_guard", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
verify_registry_guard = importlib.util.module_from_spec(_spec)
sys.modules["verify_registry_guard"] = verify_registry_guard
_spec.loader.exec_module(verify_registry_guard)


def test_classify_result_403_forbidden_is_success() -> None:
    result = verify_registry_guard.classify_result(
        returncode=1,
        stdout="",
        stderr=(
            "npm error code E403\n"
            "npm error 403 403 Forbidden - GET https://npm.flatt.tech/"
            "@panda-guard%2ftest-malicious - Package blocked by security policy"
        ),
    )
    assert result.exit_code == verify_registry_guard.EXIT_SUCCESS


def test_classify_result_successful_install_is_failure() -> None:
    """ブロックされずインストールが成功してしまった場合は失敗扱い。"""
    result = verify_registry_guard.classify_result(
        returncode=0,
        stdout="added 1 package in 1s",
        stderr="",
    )
    assert result.exit_code == verify_registry_guard.EXIT_FAILURE


def test_classify_result_network_unreachable_is_unverified() -> None:
    result = verify_registry_guard.classify_result(
        returncode=1,
        stdout="",
        stderr="npm error code ENOTFOUND\nnpm error errno ENOTFOUND",
    )
    assert result.exit_code == verify_registry_guard.EXIT_UNVERIFIED


def test_classify_result_other_error_is_failure() -> None:
    result = verify_registry_guard.classify_result(
        returncode=1,
        stdout="",
        stderr="npm error code E404\nnpm error 404 Not Found",
    )
    assert result.exit_code == verify_registry_guard.EXIT_FAILURE


def test_find_npm_executable_returns_none_when_missing(monkeypatch) -> None:
    monkeypatch.setattr(verify_registry_guard.shutil, "which", lambda _name: None)
    assert verify_registry_guard.find_npm_executable() is None
