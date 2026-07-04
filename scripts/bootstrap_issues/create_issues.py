#!/usr/bin/env python3
"""GitHubイシュー一括登録スクリプト。

scripts/bootstrap_issues/issues.yaml を読み込み、`gh` CLI経由で
親エピック+サブイシューをGitHubへ登録する。

冪等性:
- 実行前に既存イシュー一覧(タイトル)を取得し、同一タイトルのイシューは
  作成をスキップする。
- サブイシューの親子紐付け(GitHub sub-issues API)も、既存の紐付け一覧を
  確認してから実行する。

これにより、途中でエラーが発生してもスクリプトを再実行すれば続きから
処理を再開できる。

使い方:
    uv run --with pyyaml python scripts/bootstrap_issues/create_issues.py
    または
    python -m pip install --user pyyaml
    python scripts/bootstrap_issues/create_issues.py

環境:
- `gh` CLI が認証済みであること
- リポジトリのルートで実行すること(REPO定数を必要に応じて変更)
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Windows環境ではデフォルトのコンソールエンコーディングがcp932となり、
# 日本語イシュータイトル中の一部記号(⇄等)でUnicodeEncodeErrorが発生する
# ため、標準出力・標準エラーをUTF-8に強制する。
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )
if sys.stderr.encoding is None or sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace"
    )

try:
    import yaml
except ImportError:  # pragma: no cover - フォールバック案内
    print(
        "PyYAMLが見つかりません。以下のいずれかで導入してください:\n"
        "  uv run --with pyyaml python scripts/bootstrap_issues/create_issues.py\n"
        "  python -m pip install --user pyyaml",
        file=sys.stderr,
    )
    raise

REPO = "sotanengel/project-management-ai"
YAML_PATH = Path(__file__).parent / "issues.yaml"
SLEEP_SECONDS = 0.7


@dataclass
class RunResult:
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    linked: list[str] = field(default_factory=list)
    link_skipped: list[str] = field(default_factory=list)
    link_failed: list[str] = field(default_factory=list)


def run_gh(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """gh CLIコマンドを実行するヘルパー。エラーハンドリング付き。"""
    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"gh コマンドがタイムアウトしました: {args}") from exc
    if check and result.returncode != 0:
        raise RuntimeError(
            f"gh コマンド失敗 (exit={result.returncode}): {' '.join(args)}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result


def fetch_existing_issues() -> dict[str, int]:
    """既存イシューのタイトル→番号マッピングを取得する(冪等性のため)。"""
    print("既存イシュー一覧を取得中...")
    result = run_gh(
        [
            "issue",
            "list",
            "--repo",
            REPO,
            "--state",
            "all",
            "--limit",
            "200",
            "--json",
            "number,title",
        ]
    )
    issues = json.loads(result.stdout)
    mapping = {issue["title"]: issue["number"] for issue in issues}
    print(f"既存イシュー {len(mapping)} 件を検出しました。")
    return mapping


def create_issue(title: str, body: str, labels: list[str]) -> int | None:
    """イシューを作成し、番号を返す。失敗時はNoneを返す。"""
    label_args: list[str] = []
    for label in labels:
        label_args.extend(["--label", label])

    # 本文を一時ファイル経由で渡す(改行・特殊文字の安全な受け渡しのため)
    with_body_file = Path(f".tmp_issue_body_{abs(hash(title))}.md")
    try:
        with_body_file.write_text(body, encoding="utf-8")
        args = [
            "issue",
            "create",
            "--repo",
            REPO,
            "--title",
            title,
            "--body-file",
            str(with_body_file),
            *label_args,
        ]
        result = run_gh(args, check=False)
        if result.returncode != 0:
            print(f"  [失敗] イシュー作成失敗: {title}\n  {result.stderr.strip()}")
            return None
        # gh issue create は作成されたイシューのURLを出力する
        url = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
        number_str = url.rstrip("/").split("/")[-1]
        try:
            return int(number_str)
        except ValueError:
            print(f"  [警告] イシュー番号の抽出に失敗: {url}")
            return None
    finally:
        if with_body_file.exists():
            with_body_file.unlink()


def get_issue_node_id_and_dbid(issue_number: int) -> int | None:
    """イシューの内部ID(sub-issues API用、issue.id)を取得する。"""
    result = run_gh(
        [
            "api",
            f"repos/{REPO}/issues/{issue_number}",
            "--jq",
            ".id",
        ],
        check=False,
    )
    if result.returncode != 0:
        print(f"  [失敗] issue.id取得失敗 (#{issue_number}): {result.stderr.strip()}")
        return None
    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def get_linked_sub_issue_numbers(parent_number: int) -> set[int]:
    """親イシューに既に紐付けられているサブイシュー番号一覧を取得する。"""
    result = run_gh(
        [
            "api",
            f"repos/{REPO}/issues/{parent_number}/sub_issues",
            "--jq",
            ".[].number",
        ],
        check=False,
    )
    if result.returncode != 0:
        # サブイシューがまだ1件もない場合、404や空配列になることがある
        return set()
    numbers: set[int] = set()
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if line.isdigit():
            numbers.add(int(line))
    return numbers


def link_sub_issue(parent_number: int, sub_issue_id: int) -> bool:
    """GitHub sub-issues APIでサブイシューを親に紐付ける。"""
    result = run_gh(
        [
            "api",
            "-X",
            "POST",
            f"repos/{REPO}/issues/{parent_number}/sub_issues",
            "-F",
            f"sub_issue_id={sub_issue_id}",
        ],
        check=False,
    )
    if result.returncode != 0:
        print(
            f"  [失敗] サブイシュー紐付け失敗 (親#{parent_number}, "
            f"sub_issue_id={sub_issue_id}): {result.stderr.strip()}"
        )
        return False
    return True


def process_issue(
    title: str,
    body: str,
    labels: list[str],
    existing: dict[str, int],
    result: RunResult,
) -> int | None:
    """1件のイシュー(エピックまたはサブ)を作成またはスキップする。"""
    if title in existing:
        number = existing[title]
        print(f"  [スキップ] 既存: {title} (#{number})")
        result.skipped.append(title)
        return number

    print(f"  [作成中] {title}")
    number = create_issue(title, body, labels)
    if number is None:
        result.failed.append(title)
        return None

    print(f"  [作成完了] {title} (#{number})")
    result.created.append(title)
    existing[title] = number
    time.sleep(SLEEP_SECONDS)
    return number


def main() -> int:
    if not YAML_PATH.exists():
        print(f"issues.yaml が見つかりません: {YAML_PATH}", file=sys.stderr)
        return 1

    with YAML_PATH.open(encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f)

    epics = data.get("epics", [])
    if not epics:
        print("issues.yaml にエピックが定義されていません。", file=sys.stderr)
        return 1

    existing = fetch_existing_issues()
    result = RunResult()

    epic_number_map: dict[str, int] = {}

    # --- フェーズ1: 親エピック作成 ---
    print("\n=== 親エピック作成 ===")
    for epic in epics:
        key = epic["key"]
        title = epic["title"]
        labels = epic.get("labels", [])
        body = epic.get("body", "")
        number = process_issue(title, body, labels, existing, result)
        if number is not None:
            epic_number_map[key] = number

    # --- フェーズ2: サブイシュー作成 ---
    print("\n=== サブイシュー作成 ===")
    sub_number_map: dict[str, int] = {}
    epic_of_sub: dict[str, str] = {}
    for epic in epics:
        epic_key = epic["key"]
        for sub in epic.get("subs", []):
            sub_key = sub["key"]
            title = sub["title"]
            labels = sub.get("labels", [])
            body = sub.get("body", "")
            number = process_issue(title, body, labels, existing, result)
            if number is not None:
                sub_number_map[sub_key] = number
                epic_of_sub[sub_key] = epic_key

    # --- フェーズ3: sub-issues API紐付け ---
    print("\n=== サブイシュー紐付け(GitHub sub-issues API) ===")
    for sub_key, sub_number in sub_number_map.items():
        epic_key = epic_of_sub[sub_key]
        parent_number = epic_number_map.get(epic_key)
        if parent_number is None:
            print(
                f"  [失敗] 親エピック番号が不明のため紐付けスキップ: "
                f"{sub_key} (epic={epic_key})"
            )
            result.link_failed.append(f"{sub_key}->{epic_key}")
            continue

        linked_numbers = get_linked_sub_issue_numbers(parent_number)
        if sub_number in linked_numbers:
            print(f"  [スキップ] 既に紐付け済み: #{parent_number} <- #{sub_number}")
            result.link_skipped.append(f"{sub_key}->{epic_key}")
            continue

        sub_issue_id = get_issue_node_id_and_dbid(sub_number)
        if sub_issue_id is None:
            result.link_failed.append(f"{sub_key}->{epic_key}")
            continue

        print(f"  [紐付け中] #{parent_number} <- #{sub_number} ({sub_key})")
        ok = link_sub_issue(parent_number, sub_issue_id)
        if ok:
            print(f"  [紐付け完了] #{parent_number} <- #{sub_number}")
            result.linked.append(f"{sub_key}->{epic_key}")
        else:
            result.link_failed.append(f"{sub_key}->{epic_key}")
        time.sleep(SLEEP_SECONDS)

    # --- サマリ出力 ---
    print("\n=== 実行サマリ ===")
    print(f"作成: {len(result.created)} 件")
    print(f"スキップ(既存): {len(result.skipped)} 件")
    print(f"失敗: {len(result.failed)} 件")
    if result.failed:
        for t in result.failed:
            print(f"  - {t}")
    print(f"紐付け成功: {len(result.linked)} 件")
    print(f"紐付けスキップ(既存): {len(result.link_skipped)} 件")
    print(f"紐付け失敗: {len(result.link_failed)} 件")
    if result.link_failed:
        for t in result.link_failed:
            print(f"  - {t}")

    print("\n=== エピック番号対応表 ===")
    for epic in epics:
        key = epic["key"]
        number = epic_number_map.get(key, "N/A")
        print(f"  {key}: #{number}")

    if result.failed or result.link_failed:
        print("\n一部失敗がありました。スクリプトを再実行すると再開できます。")
        return 1

    print("\n全イシューの作成・紐付けが完了しました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
