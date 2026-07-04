"""E2-8: CSV/Markdown変換出力のテスト。"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from pmdf.convert.csv_ import roadmap_item_to_csv, story_to_csv
from pmdf.convert.markdown import decision_to_markdown, report_to_markdown
from pmdf.models import Decision, Provenance, Report, RoadmapItem, Story
from pmdf.models.decision import Option, RejectedReason
from pmdf.models.story import Priority


def _provenance() -> Provenance:
    return Provenance(created_by="user:tester", updated_at=datetime(2026, 6, 1, tzinfo=UTC))


def _story(story_id: str, title: str, score: float) -> Story:
    return Story(
        pmdf_version="1.0.0",
        kind="story",
        id=story_id,
        provenance=_provenance(),
        title=title,
        as_a="a",
        i_want="b",
        so_that="c",
        acceptance_criteria=["AC1"],
        priority=Priority(method="RICE", score=score),
        status="ready",
    )


def _roadmap_item(item_id: str, theme: str) -> RoadmapItem:
    return RoadmapItem(
        pmdf_version="1.0.0",
        kind="roadmap_item",
        id=item_id,
        provenance=_provenance(),
        theme=theme,
        period="2026-Q3",
        status="planned",
        objective="obj-01JZX0KKKK01BBBBCCCCDDDDEF",
    )


def _decision() -> Decision:
    return Decision(
        pmdf_version="1.0.0",
        kind="decision",
        id="dec-01JZX3DDDD01BBBBCCCCDDDDEF",
        provenance=_provenance(),
        background="背景の説明",
        options=[Option(name="案A", description="説明A"), Option(name="案B")],
        chosen_option="案A",
        rationale="根拠の説明",
        rejected_reasons=[RejectedReason(option="案B", reason="コストが高いため")],
        autonomy_level="L1",
    )


def _report() -> Report:
    return Report(
        pmdf_version="1.0.0",
        kind="report",
        id="report-01JZX7RPRP01BBBBCCCCDDDABC",
        provenance=_provenance(),
        period="2026-Q3",
        health_assessment="yellow",
        decisions_needed=["A案の可否判断"],
        summary="概ね順調。",
    )


def test_story_to_csv_round_trips_with_csv_module() -> None:
    stories = [
        _story("story-01JZXSASSA01BBBBCCCCDDDDEE", "ストーリー1", 2240.0),
        _story("story-01JZXSBSSB01BBBBCCCCDDDDEE", "ストーリー2", 1500.0),
    ]
    csv_text = story_to_csv(stories)
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    assert len(rows) == 2
    assert rows[0]["title"] == "ストーリー1"
    assert rows[0]["priority.score"] == "2240.0"
    assert rows[1]["title"] == "ストーリー2"
    fieldnames = reader.fieldnames or ()
    assert "id" in fieldnames
    assert "status" in fieldnames


def test_roadmap_item_to_csv_round_trips_with_csv_module() -> None:
    items = [
        _roadmap_item("roadmap-01JZX1RRRR01BBBBCCCCDDDDEF", "テーマ1"),
        _roadmap_item("roadmap-01JZX1RRRR02BBBBCCCCDDDDEF", "テーマ2"),
    ]
    csv_text = roadmap_item_to_csv(items)
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)
    assert len(rows) == 2
    assert rows[0]["theme"] == "テーマ1"
    assert rows[1]["theme"] == "テーマ2"
    fieldnames = reader.fieldnames or ()
    assert "period" in fieldnames
    assert "status" in fieldnames


def test_decision_to_markdown_contains_expected_headings() -> None:
    markdown = decision_to_markdown(_decision())
    assert "# 背景" in markdown or "## 背景" in markdown
    assert "選択肢" in markdown
    assert "採用案" in markdown
    assert "却下理由" in markdown
    assert "案A" in markdown
    assert "コストが高いため" in markdown


def test_report_to_markdown_contains_period_and_decisions_needed() -> None:
    markdown = report_to_markdown(_report())
    assert "2026-Q3" in markdown
    assert "A案の可否判断" in markdown
    assert "概ね順調。" in markdown
