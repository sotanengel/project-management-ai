"""E9-4: backup_restore_lib のテスト。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

from backup_restore_lib import (  # noqa: E402
    archive_contains_secret_env,
    create_backup,
    restore_backup,
)


def _git_commit_all(repo: Path) -> None:
    import os

    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "t@e.com",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "t@e.com",
    }
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, env=env)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
        env=env,
    )


def test_backup_restore_roundtrip(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    pmdf = root / "data" / "pmdf-store"
    pmdf.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=pmdf, check=True, capture_output=True)
    (pmdf / "product").mkdir()
    (pmdf / "product" / "product-01.yaml").write_text("id: product-01\n", encoding="utf-8")
    _git_commit_all(pmdf)

    kb = root / "kb" / "corpus" / "demo"
    kb.mkdir(parents=True)
    (kb / "sample.md").write_text("body", encoding="utf-8")

    (root / "data" / "learning").mkdir(parents=True)
    (root / "data" / "learning" / "sft.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "data" / "autonomy.json").write_text("{}", encoding="utf-8")
    (root / ".env").write_text("SECRET=x\n", encoding="utf-8")
    (root / ".env.example").write_text("SECRET=\n", encoding="utf-8")

    archive = create_backup(root_dir=root, dest_dir=tmp_path / "backups", pmdf_store_path=pmdf)
    assert archive.exists()
    assert archive_contains_secret_env(archive) is False

    restored = tmp_path / "restored"
    restore_backup(archive_path=archive, restore_root=restored)

    assert (restored / "data" / "pmdf-store" / "product" / "product-01.yaml").exists()
    assert (restored / "kb" / "corpus" / "demo" / "sample.md").exists()
    assert not (restored / ".env").exists()

    orig = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=pmdf,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    new = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=restored / "data" / "pmdf-store",
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert orig == new
