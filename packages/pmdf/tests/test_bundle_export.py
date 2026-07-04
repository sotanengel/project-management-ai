"""E2-6: バンドルexport(`*.pmdf.tar.gz`)のテスト。"""

from __future__ import annotations

import json
import tarfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from pmdf.bundle.export import ExportScope, export_bundle
from pmdf.models import Product, Provenance, Story
from pmdf.models.story import Priority


def _extract(tar: tarfile.TarFile, name: str) -> bytes:
    member = tar.extractfile(name)
    assert member is not None, f"{name} がtar内に存在しません"
    return member.read()


def _provenance(updated_at: datetime | None = None) -> Provenance:
    return Provenance(
        created_by="user:tester",
        updated_at=updated_at or datetime(2026, 6, 1, tzinfo=UTC),
    )


def _product(product_id: str, name: str, updated_at: datetime | None = None) -> Product:
    return Product(
        pmdf_version="1.0.0",
        kind="product",
        id=product_id,
        provenance=_provenance(updated_at),
        name=name,
        vision="vision",
        lifecycle_stage="growth",
    )


def _story(story_id: str, product_id: str, updated_at: datetime | None = None) -> Story:
    return Story(
        pmdf_version="1.0.0",
        kind="story",
        id=story_id,
        provenance=_provenance(updated_at),
        product=product_id,
        title="title",
        as_a="a",
        i_want="b",
        so_that="c",
        acceptance_criteria=["AC1"],
        priority=Priority(method="RICE"),
        status="ready",
    )


PROD_A = "prod-01JZXAAAAA01BBBBCCCCDDDDEE"
PROD_B = "prod-01JZXBBBBB01BBBBCCCCDDDDEE"
STORY_A1 = "story-01JZXSASSA01BBBBCCCCDDDDEE"
STORY_B1 = "story-01JZXSBSSB01BBBBCCCCDDDDEE"


@pytest.fixture
def sample_entities() -> list:
    return [
        _product(PROD_A, "Product A"),
        _product(PROD_B, "Product B"),
        _story(STORY_A1, PROD_A),
        _story(STORY_B1, PROD_B),
    ]


def test_export_bundle_creates_tarball_with_manifest_and_entities(
    tmp_path: Path, sample_entities: list
) -> None:
    output = tmp_path / "out.pmdf.tar.gz"
    scope = ExportScope()
    result = export_bundle(sample_entities, scope, output, generated_env="test-env")
    assert result == output
    assert output.exists()

    with tarfile.open(output, "r:gz") as tar:
        names = tar.getnames()
        assert "manifest.json" in names
        assert f"entities/product/{PROD_A}.yaml" in names
        assert f"entities/story/{STORY_A1}.yaml" in names

        manifest_bytes = _extract(tar, "manifest.json")
        manifest = json.loads(manifest_bytes)
        assert manifest["schema_version"] == "1.0.0"
        assert manifest["generated_env"] == "test-env"
        assert manifest["entity_count"]["total"] == 4
        assert manifest["entity_count"]["by_kind"]["story"] == 2
        assert "content_hash" in manifest
        assert "generated_at" in manifest

        story_bytes = _extract(tar, f"entities/story/{STORY_A1}.yaml")
        story_data = yaml.safe_load(story_bytes)
        assert story_data["id"] == STORY_A1


def test_export_bundle_filters_by_product_ids(tmp_path: Path, sample_entities: list) -> None:
    output = tmp_path / "out.pmdf.tar.gz"
    scope = ExportScope(product_ids=[PROD_A])
    export_bundle(sample_entities, scope, output)

    with tarfile.open(output, "r:gz") as tar:
        names = tar.getnames()
        assert f"entities/product/{PROD_A}.yaml" in names
        assert f"entities/story/{STORY_A1}.yaml" in names
        assert f"entities/product/{PROD_B}.yaml" not in names
        assert f"entities/story/{STORY_B1}.yaml" not in names


def test_export_bundle_filters_by_kind(tmp_path: Path, sample_entities: list) -> None:
    output = tmp_path / "out.pmdf.tar.gz"
    scope = ExportScope(kinds=["story"])
    export_bundle(sample_entities, scope, output)

    with tarfile.open(output, "r:gz") as tar:
        names = tar.getnames()
        assert f"entities/story/{STORY_A1}.yaml" in names
        assert f"entities/story/{STORY_B1}.yaml" in names
        assert f"entities/product/{PROD_A}.yaml" not in names


def test_export_bundle_filters_by_period(tmp_path: Path) -> None:
    old_story = _story(STORY_A1, PROD_A, updated_at=datetime(2020, 1, 1, tzinfo=UTC))
    new_story = _story(STORY_B1, PROD_A, updated_at=datetime(2026, 6, 1, tzinfo=UTC))
    output = tmp_path / "out.pmdf.tar.gz"
    scope = ExportScope(since=datetime(2025, 1, 1, tzinfo=UTC))
    export_bundle([old_story, new_story], scope, output)

    with tarfile.open(output, "r:gz") as tar:
        names = tar.getnames()
        assert f"entities/story/{STORY_B1}.yaml" in names
        assert f"entities/story/{STORY_A1}.yaml" not in names


def test_export_bundle_without_attachments_keeps_reference_only(tmp_path: Path) -> None:
    from pmdf.models.common import Attachment

    story = _story(STORY_A1, PROD_A)
    story = story.model_copy(
        update={"attachments": [Attachment(path="design.png", sha256="a" * 64)]}
    )
    attachments_source = tmp_path / "source_attachments"
    attachments_source.mkdir()
    (attachments_source / "design.png").write_bytes(b"binary-content")

    output_with = tmp_path / "with.pmdf.tar.gz"
    export_bundle(
        [story],
        ExportScope(),
        output_with,
        include_attachments=True,
        attachments_dir=attachments_source,
    )
    with tarfile.open(output_with, "r:gz") as tar:
        names = tar.getnames()
        assert f"attachments/{STORY_A1}/design.png" in names
        story_yaml = yaml.safe_load(_extract(tar, f"entities/story/{STORY_A1}.yaml"))
        assert story_yaml["attachments"][0]["path"] == "design.png"
        assert story_yaml["attachments"][0]["sha256"] == "a" * 64

    output_without = tmp_path / "without.pmdf.tar.gz"
    export_bundle(
        [story],
        ExportScope(),
        output_without,
        include_attachments=False,
        attachments_dir=attachments_source,
    )
    with tarfile.open(output_without, "r:gz") as tar:
        names = tar.getnames()
        assert not any(name.startswith("attachments/") for name in names)
        story_yaml = yaml.safe_load(_extract(tar, f"entities/story/{STORY_A1}.yaml"))
        # 参照(path+sha256)は保持される
        assert story_yaml["attachments"][0]["path"] == "design.png"
        assert story_yaml["attachments"][0]["sha256"] == "a" * 64


def test_content_hash_is_deterministic(tmp_path: Path, sample_entities: list) -> None:
    output1 = tmp_path / "out1.pmdf.tar.gz"
    output2 = tmp_path / "out2.pmdf.tar.gz"
    export_bundle(sample_entities, ExportScope(), output1, generated_env="env")
    export_bundle(list(reversed(sample_entities)), ExportScope(), output2, generated_env="env")

    def _read_manifest(path: Path) -> dict:
        with tarfile.open(path, "r:gz") as tar:
            return json.loads(_extract(tar, "manifest.json"))

    manifest1 = _read_manifest(output1)
    manifest2 = _read_manifest(output2)
    assert manifest1["content_hash"] == manifest2["content_hash"]
