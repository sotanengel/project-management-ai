"""E9-4: バックアップ/リストアのコアロジック (FR-OP-03)。"""

from __future__ import annotations

import shutil
import tarfile
from datetime import UTC, datetime
from pathlib import Path

SECRET_FILENAMES = {".env"}


def create_backup(
    *,
    root_dir: Path,
    dest_dir: Path,
    pmdf_store_path: Path | None = None,
) -> Path:
    """pmdf-store / kb / data / 非秘密設定を tarball 化する。`.env` は含めない。"""
    dest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive_path = dest_dir / f"pmai-backup-{timestamp}.tar.gz"
    staging = dest_dir / f".staging-{timestamp}"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)

    pmdf_src = pmdf_store_path or (root_dir / "data" / "pmdf-store")
    if pmdf_src.exists():
        shutil.copytree(pmdf_src, staging / "pmdf-store", dirs_exist_ok=True)

    kb_src = root_dir / "kb" / "corpus"
    if kb_src.exists():
        shutil.copytree(kb_src, staging / "kb" / "corpus", dirs_exist_ok=True)

    data_src = root_dir / "data"
    if data_src.exists():
        for child in data_src.iterdir():
            if child.name == "pmdf-store":
                continue
            target = staging / "data" / "data" / child.name
            if child.is_dir():
                shutil.copytree(child, target, dirs_exist_ok=True)
            elif child.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(child, target)

    for rel in ["services/trainer/data", "services/agent-core/data"]:
        src = root_dir / rel
        if src.exists():
            target = staging / "data" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, target, dirs_exist_ok=True)

    for rel in [
        "data/autonomy.json",
        "data/emergency_stop.json",
        "data/budget_exceeded.json",
        ".env.example",
    ]:
        src = root_dir / rel
        if src.is_file():
            target = staging / "config" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)

    with tarfile.open(archive_path, "w:gz") as tar:
        for item in staging.iterdir():
            tar.add(item, arcname=item.name)

    shutil.rmtree(staging, ignore_errors=True)
    return archive_path


def restore_backup(*, archive_path: Path, restore_root: Path) -> None:
    """tarball から `restore_root` へ復元する。"""
    restore_root.mkdir(parents=True, exist_ok=True)
    staging = restore_root / ".restore-staging"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir()

    with tarfile.open(archive_path, "r:gz") as tar:
        tar.extractall(staging)

    pmdf = staging / "pmdf-store"
    if pmdf.exists():
        target = restore_root / "data" / "pmdf-store"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(pmdf, target, dirs_exist_ok=True)

    kb = staging / "kb" / "corpus"
    if kb.exists():
        target = restore_root / "kb" / "corpus"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(kb, target, dirs_exist_ok=True)

    data = staging / "data"
    if data.exists():
        shutil.copytree(data, restore_root / "data", dirs_exist_ok=True)

    config = staging / "config"
    if config.exists():
        for path in config.rglob("*"):
            if path.is_file():
                rel = path.relative_to(config)
                if rel.name in SECRET_FILENAMES:
                    continue
                target = restore_root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)

    shutil.rmtree(staging, ignore_errors=True)


def archive_contains_secret_env(archive_path: Path) -> bool:
    with tarfile.open(archive_path, "r:gz") as tar:
        for member in tar.getmembers():
            name = Path(member.name).name
            if name == ".env":
                return True
    return False


__all__ = ["archive_contains_secret_env", "create_backup", "restore_backup"]
