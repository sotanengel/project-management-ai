#!/usr/bin/env python3
"""Takumi Guard(Shisho)レジストリ切替の検証スクリプト。

`@panda-guard/test-malicious` パッケージのインストールを試み、
403 Forbidden で失敗することを確認する。

exit code:
  0: 検証成功(403 Forbiddenを確認)
  1: 検証失敗(レジストリは疎通したが403以外の結果、またはブロックされずに
     インストールが成功してしまった = ガードが機能していない)
  2: 未検証・要人手確認(npm未インストール、レジストリ未設定、タイムアウト等)

参照: docs/takumi-guard.md, https://shisho.dev/docs/ja/t/guard/quickstart/index.md
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass

TARGET_PACKAGE = "@panda-guard/test-malicious"
NPM_TIMEOUT_SECONDS = 60

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_UNVERIFIED = 2


@dataclass
class VerifyResult:
    exit_code: int
    message: str


def find_npm_executable() -> str | None:
    """npm実行ファイルのパスを返す。見つからない場合はNone。"""
    return shutil.which("npm")


def run_npm_install(npm_path: str, package: str, cwd: str) -> subprocess.CompletedProcess[str]:
    """指定パッケージのインストールを試行する(subprocess経由)。"""
    return subprocess.run(  # noqa: S603
        [npm_path, "install", "--no-save", package],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=NPM_TIMEOUT_SECONDS,
    )


def classify_result(returncode: int, stdout: str, stderr: str) -> VerifyResult:
    """npm installの結果を分類する。"""
    combined = f"{stdout}\n{stderr}"

    if returncode == 0:
        return VerifyResult(
            EXIT_FAILURE,
            "インストールが成功してしまいました。Takumi Guardによる"
            f"ブロックが機能していない可能性があります: {TARGET_PACKAGE}",
        )

    if "403" in combined and ("forbidden" in combined.lower() or "blocked" in combined.lower()):
        return VerifyResult(
            EXIT_SUCCESS,
            "403 Forbiddenを確認しました。Takumi Guardによるレジストリ"
            "ガードが正しく機能しています。",
        )

    if any(
        keyword in combined for keyword in ("ENOTFOUND", "ETIMEDOUT", "ECONNREFUSED", "getaddrinfo")
    ):
        return VerifyResult(
            EXIT_UNVERIFIED,
            "レジストリに到達できませんでした。Takumi Guardレジストリが"
            "設定されていないか、ネットワークに問題がある可能性があります。"
            "docs/takumi-guard.md を参照し、user-level設定を確認してください。",
        )

    return VerifyResult(
        EXIT_FAILURE,
        f"予期しない結果です(403以外のエラー)。詳細を確認してください:\n{combined.strip()}",
    )


def verify() -> VerifyResult:
    npm_path = find_npm_executable()
    if npm_path is None:
        return VerifyResult(
            EXIT_UNVERIFIED,
            "npmが見つかりませんでした。npmをインストールするか、"
            "このスクリプトをnpmが利用可能な環境で実行してください。",
        )

    try:
        with tempfile.TemporaryDirectory(prefix="verify-registry-guard-") as tmp_dir:
            proc = run_npm_install(npm_path, TARGET_PACKAGE, cwd=tmp_dir)
    except subprocess.TimeoutExpired:
        return VerifyResult(
            EXIT_UNVERIFIED,
            f"npm installが{NPM_TIMEOUT_SECONDS}秒でタイムアウトしました。"
            "レジストリ未到達の可能性があります。",
        )
    except OSError as exc:
        return VerifyResult(
            EXIT_UNVERIFIED,
            f"npm実行中にエラーが発生しました: {exc}",
        )

    return classify_result(proc.returncode, proc.stdout, proc.stderr)


def main() -> int:
    # Windowsのコンソールエンコーディング(cp932等)で日本語が文字化けするのを防ぐ。
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure) and (sys.stdout.encoding or "").lower() != "utf-8":
        reconfigure(encoding="utf-8")

    result = verify()
    print(result.message)
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
