#!/usr/bin/env python3
"""agent-coreがPMDFへ直接書込していないことを静的に検証するCIチェック(E5-2)。

設計原則3(人間監督の内蔵)/設計原則2(PMDF中心設計): エージェントは
PMDFへの直接書込を一切行わず、api-serverのREST APIをHTTP経由で
呼び出すクライアントとしてのみ振る舞う。本スクリプトは
`services/agent-core/src` 配下の全Pythonファイルを静的解析(AST)し、
以下のいずれかをimportしていないことを検証する:

- `api_server.pmdf_store`(またはそのサブモジュール): api-server内部の
  Git永続化層への直接アクセス
- `pmdf.io`: PMDFエンティティのファイル直接読み書き

exit code:
  0: 違反なし
  1: 違反を検出(該当ファイル・importを標準エラーへ出力)
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

#: 禁止するモジュール名(完全一致またはこれで始まるサブモジュール)。
FORBIDDEN_MODULE_PREFIXES = ("api_server.pmdf_store", "pmdf.io")

TARGET_DIR = Path(__file__).resolve().parents[1] / "services" / "agent-core" / "src"


@dataclass
class Violation:
    file_path: Path
    module_name: str
    lineno: int


def _is_forbidden(module_name: str) -> bool:
    return any(
        module_name == prefix or module_name.startswith(prefix + ".")
        for prefix in FORBIDDEN_MODULE_PREFIXES
    )


def _imported_modules(tree: ast.Module) -> list[tuple[str, int]]:
    modules: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append((node.module, node.lineno))
    return modules


def check_file(path: Path) -> list[Violation]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        Violation(file_path=path, module_name=module_name, lineno=lineno)
        for module_name, lineno in _imported_modules(tree)
        if _is_forbidden(module_name)
    ]


def check_directory(target_dir: Path) -> list[Violation]:
    violations: list[Violation] = []
    for path in sorted(target_dir.rglob("*.py")):
        violations.extend(check_file(path))
    return violations


def main() -> int:
    if not TARGET_DIR.exists():
        print(f"対象ディレクトリが見つかりません: {TARGET_DIR}", file=sys.stderr)
        return 0

    violations = check_directory(TARGET_DIR)
    if not violations:
        print(
            "agent-coreにPMDFへの直接書込import(api_server.pmdf_store/pmdf.io)は検出されませんでした。"
        )
        return 0

    print("agent-coreがPMDFへの直接書込を行うimportを検出しました(設計原則3違反):", file=sys.stderr)
    for v in violations:
        print(f"  {v.file_path}:{v.lineno}: import {v.module_name}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
