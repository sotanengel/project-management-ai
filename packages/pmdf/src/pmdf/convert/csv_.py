"""story/roadmap_itemのCSV変換出力(FR-EX-06)。

モジュール名は`csv`標準ライブラリとの衝突を避けるため`csv_`とする。
"""

from __future__ import annotations

import csv
import io

from pmdf.models import RoadmapItem, Story


def story_to_csv(stories: list[Story]) -> str:
    """storyのリストをCSV文字列に変換する。"""
    buffer = io.StringIO()
    fieldnames = [
        "id",
        "title",
        "as_a",
        "status",
        "priority.method",
        "priority.score",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for story in stories:
        writer.writerow(
            {
                "id": story.id,
                "title": story.title,
                "as_a": story.as_a,
                "status": story.status,
                "priority.method": story.priority.method,
                "priority.score": story.priority.score,
            }
        )
    return buffer.getvalue()


def roadmap_item_to_csv(items: list[RoadmapItem]) -> str:
    """roadmap_itemのリストをCSV文字列に変換する。"""
    buffer = io.StringIO()
    fieldnames = ["id", "theme", "period", "status", "objective"]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for item in items:
        writer.writerow(
            {
                "id": item.id,
                "theme": item.theme,
                "period": item.period,
                "status": item.status,
                "objective": item.objective,
            }
        )
    return buffer.getvalue()


__all__ = ["roadmap_item_to_csv", "story_to_csv"]
