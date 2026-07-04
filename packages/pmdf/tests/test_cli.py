"""E2-9: pmdf CLI(typer)の統合テスト。"""

from __future__ import annotations

import io
import tarfile
from datetime import UTC, datetime
from pathlib import Path

from pmdf.cli import app
from pmdf.io import save_entity
from pmdf.models import Provenance, Story
from pmdf.models.story import Priority
from typer.testing import CliRunner

runner = CliRunner()

STORY_ID = "story-01JZXSASSA01BBBBCCCCDDDDEE"


def _story() -> Story:
    return Story(
        pmdf_version="1.0.0",
        kind="story",
        id=STORY_ID,
        provenance=Provenance(
            created_by="user:tester", updated_at=datetime(2026, 6, 1, tzinfo=UTC)
        ),
        title="タイトル",
        as_a="a",
        i_want="b",
        so_that="c",
        acceptance_criteria=["AC1"],
        priority=Priority(method="RICE", score=100),
        status="ready",
    )


def test_validate_command_succeeds_on_valid_directory(tmp_path: Path) -> None:
    save_entity(_story(), tmp_path)
    result = runner.invoke(app, ["validate", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output


def test_validate_command_fails_on_invalid_file(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.yaml"
    bad_file.write_text(
        "pmdf_version: '1.0.0'\nkind: story\nid: not-a-valid-id\n", encoding="utf-8"
    )
    result = runner.invoke(app, ["validate", str(tmp_path)])
    assert result.exit_code == 1
    assert "NG" in result.output


def test_validate_command_fails_on_nonexistent_path() -> None:
    result = runner.invoke(app, ["validate", "C:/does/not/exist"])
    assert result.exit_code != 0


def test_export_then_validate_bundle_round_trip(tmp_path: Path) -> None:
    entities_dir = tmp_path / "entities"
    save_entity(_story(), entities_dir)
    output = tmp_path / "out.pmdf.tar.gz"

    result = runner.invoke(
        app,
        ["export", str(entities_dir), "--output", str(output), "--kind", "story"],
    )
    assert result.exit_code == 0, result.output
    assert output.exists()

    with tarfile.open(output, "r:gz") as tar:
        assert f"entities/story/{STORY_ID}.yaml" in tar.getnames()


def test_import_dry_run_reports_new_entity(tmp_path: Path) -> None:
    entities_dir = tmp_path / "entities"
    save_entity(_story(), entities_dir)
    output = tmp_path / "out.pmdf.tar.gz"
    runner.invoke(app, ["export", str(entities_dir), "--output", str(output)])

    store_dir = tmp_path / "store"
    result = runner.invoke(app, ["import", str(output), "--store", str(store_dir), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert STORY_ID in result.output
    # dry-runなのでストアには何も書き込まれない
    assert not store_dir.exists() or not any(store_dir.rglob("*.yaml"))


def test_import_real_run_writes_to_store(tmp_path: Path) -> None:
    entities_dir = tmp_path / "entities"
    save_entity(_story(), entities_dir)
    output = tmp_path / "out.pmdf.tar.gz"
    runner.invoke(app, ["export", str(entities_dir), "--output", str(output)])

    store_dir = tmp_path / "store"
    result = runner.invoke(app, ["import", str(output), "--store", str(store_dir)])
    assert result.exit_code == 0, result.output
    assert (store_dir / "story" / f"{STORY_ID}.yaml").exists()


def test_import_fails_on_invalid_bundle(tmp_path: Path) -> None:
    bad_bundle = tmp_path / "bad.pmdf.tar.gz"
    with tarfile.open(bad_bundle, "w:gz") as tar:
        info = tarfile.TarInfo(name="manifest.json")
        content = b"{}"
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))

    store_dir = tmp_path / "store"
    result = runner.invoke(app, ["import", str(bad_bundle), "--store", str(store_dir)])
    assert result.exit_code == 1


def test_convert_to_csv(tmp_path: Path) -> None:
    entities_dir = tmp_path / "entities"
    save_entity(_story(), entities_dir)
    output = tmp_path / "stories.csv"
    result = runner.invoke(
        app,
        ["convert", str(entities_dir), str(output), "--to", "csv", "--kind", "story"],
    )
    assert result.exit_code == 0, result.output
    assert output.exists()
    assert "title" in output.read_text(encoding="utf-8")


def test_migrate_command_updates_version(tmp_path: Path) -> None:
    entity_file = tmp_path / "story.yaml"
    entity_file.write_text(
        "pmdf_version: '1.0.0'\nkind: story\nid: story-x\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        ["migrate", str(entity_file), "--from", "1.0.0", "--to", "1.1.0"],
    )
    assert result.exit_code == 0, result.output
    updated = entity_file.read_text(encoding="utf-8")
    assert "1.1.0" in updated
    assert "x_migrated" in updated


def test_migrate_command_fails_on_undefined_path(tmp_path: Path) -> None:
    entity_file = tmp_path / "story.yaml"
    entity_file.write_text("pmdf_version: '1.0.0'\nkind: story\nid: story-x\n", encoding="utf-8")
    result = runner.invoke(
        app,
        ["migrate", str(entity_file), "--from", "1.0.0", "--to", "9.9.9"],
    )
    assert result.exit_code == 1
