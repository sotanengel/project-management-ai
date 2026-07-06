"""E10-1: サンプルプロダクト PMDF シード投入。"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import yaml
from pmdf.io import load_entity
from pmdf.models.common import PmdfBase

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(__file__).resolve().parent / "data"
FIXTURES_DIR = REPO_ROOT / "packages" / "pmdf" / "tests" / "fixtures" / "valid"


def materialize_data_dir() -> None:
    """data/ が無い場合、フィクスチャから一式を生成する(冪等)。"""
    if (DATA_DIR / "product").exists():
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for src in FIXTURES_DIR.glob("*.yaml"):
        kind = yaml.safe_load(src.read_text(encoding="utf-8"))["kind"]
        dest_dir = DATA_DIR / kind
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest_dir / f"{src.stem}.yaml")

    rejected = {
        "pmdf_version": "1.0.0",
        "kind": "approval",
        "id": "approval-01JZX8RJCT01BBBBCCCCDDDREJ",
        "provenance": {
            "created_by": "user:vp-hanako",
            "updated_at": "2026-07-01T10:00:00+09:00",
        },
        "attachments": [],
        "target": "dec-01JZX3DDDD01BBBBCCCCDDDDEF",
        "proposer": "stakeholder-01JZX0SSSS01BBBBCCCCDDDDEF",
        "approver": "stakeholder-01JZX0SSSS01BBBBCCCCDDDDEF",
        "decision": "rejected",
        "reason": "追加のセキュリティレビューが必要なため差し戻し",
    }
    (DATA_DIR / "approval" / "approval_rejected.yaml").write_text(
        yaml.safe_dump(rejected, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    decision_path = DATA_DIR / "decision" / "decision_example.yaml"
    decision = yaml.safe_load(decision_path.read_text(encoding="utf-8"))
    decision["attachments"] = [
        {
            "path": "guest-order-spec.pdf",
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        }
    ]
    decision_path.write_text(
        yaml.safe_dump(decision, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def iter_seed_entities() -> list[PmdfBase]:
    materialize_data_dir()
    entities: list[PmdfBase] = []
    for path in sorted(DATA_DIR.rglob("*.yaml")):
        entities.append(load_entity(path))
    return entities


def seed_store(store_path: Path, *, skip_existing: bool = True) -> int:
    """pmdf-store へエンティティを投入する。戻り値は新規投入件数。"""
    from api_server.pmdf_store.store import PmdfStore
    from pmdf.io import entity_relative_path

    PmdfStore.init(store_path)
    store = PmdfStore(store_path)
    written = 0
    for entity in iter_seed_entities():
        rel = entity_relative_path(entity.kind, entity.id)
        if skip_existing and (store_path / rel).exists():
            continue
        store.create(entity, actor="seed:sample-product")
        written += 1
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="サンプルプロダクト PMDF シード")
    parser.add_argument(
        "--store-path",
        type=Path,
        default=REPO_ROOT / "data" / "pmdf-store",
        help="pmdf-store Git リポジトリパス",
    )
    parser.add_argument("--force", action="store_true", help="既存エンティティも上書き投入")
    args = parser.parse_args()
    count = seed_store(args.store_path, skip_existing=not args.force)
    print(f"Seeded {count} entities into {args.store_path}")


if __name__ == "__main__":
    main()
