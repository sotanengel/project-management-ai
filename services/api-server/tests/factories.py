"""テスト用のPMDFエンティティ生成ヘルパー(pmdf-store層以降のテストで共通利用)。"""

from __future__ import annotations

from datetime import UTC, datetime

from pmdf.models import Priority, Provenance, Story


def make_story(
    *,
    id: str = "story-01HZZZZZZZZZZZZZZZZZZZZZZZ",
    title: str = "サンプルストーリー",
    status: str = "draft",
    product: str | None = None,
    created_by: str = "user:tester",
) -> Story:
    return Story(
        pmdf_version="1.0.0",
        kind="story",
        id=id,
        provenance=Provenance(created_by=created_by, updated_at=datetime.now(UTC)),
        attachments=[],
        product=product,
        title=title,
        as_a="ユーザー",
        i_want="機能を使いたい",
        so_that="価値を得られる",
        acceptance_criteria=["条件1"],
        priority=Priority(method="RICE"),
        status=status,  # type: ignore[arg-type]
        links=None,
    )


__all__ = ["make_story"]
