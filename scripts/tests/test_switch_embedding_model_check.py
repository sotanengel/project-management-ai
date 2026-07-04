"""scripts/switch_embedding_model_check.py の結合テスト(E6-4)。

`pdm-embed`設定変更のみ(コード変更なし)で異なる次元の埋め込みモデルへ
切替できること、次元不一致時に明確なエラーとなること、
`kb-ingest recreate`相当のコレクション再作成後は新次元での投入・検索が
通ることをスクリプト全体の終了コードで検証する。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "switch_embedding_model_check.py"


def test_switch_embedding_model_check_script_succeeds() -> None:
    # Windows既定のコンソールコードページ(cp932等)によるデコードエラーを避けるため、
    # 子プロセスの標準出力エンコーディングを明示的にUTF-8に固定する。
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=60,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "モデルA" in result.stdout
    assert "モデルB" in result.stdout
    assert "次元不一致エラーが発生しました" in result.stdout
    assert "検証成功" in result.stdout
