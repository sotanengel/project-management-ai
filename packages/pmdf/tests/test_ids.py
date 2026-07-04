"""E2-5: ULID採番のテスト。

`generate_id(kind)` が `<kind_prefix>-<26文字ULID>` 形式の文字列を返し、
E2-1のIDパターンに合致すること、短時間に大量生成してもソート順が単調増加
すること(モノトニック性)を確認する。
"""

from __future__ import annotations

import re
import threading

import pytest
from pmdf.ids import KIND_TO_PREFIX, generate_id
from pmdf.models.common import ID_PATTERN

ALL_KINDS = [
    "product",
    "stakeholder",
    "persona",
    "objective",
    "metric",
    "roadmap_item",
    "story",
    "experiment",
    "decision",
    "release",
    "risk",
    "initiative",
    "report",
    "approval",
]


def test_kind_to_prefix_covers_all_14_kinds() -> None:
    assert set(KIND_TO_PREFIX.keys()) == set(ALL_KINDS)


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_generate_id_matches_schema_pattern(kind: str) -> None:
    generated = generate_id(kind)
    prefix = KIND_TO_PREFIX[kind]
    assert generated.startswith(f"{prefix}-")
    assert re.match(ID_PATTERN, generated), f"{generated!r} がIDパターンに一致しません"
    suffix = generated.split("-", 1)[1]
    assert len(suffix) == 26


def test_generate_id_unknown_kind_raises() -> None:
    with pytest.raises(KeyError):
        generate_id("not_a_kind")


def test_generate_id_is_monotonically_increasing_within_same_kind() -> None:
    ids = [generate_id("story") for _ in range(200)]
    suffixes = [i.split("-", 1)[1] for i in ids]
    assert suffixes == sorted(suffixes), "短時間大量生成でソート順が単調増加していません"
    assert len(set(ids)) == len(ids), "生成されたIDに重複があります"


def test_generate_id_is_monotonic_across_threads() -> None:
    generated: list[str] = []
    lock = threading.Lock()

    def worker() -> None:
        local_id = generate_id("story")
        with lock:
            generated.append(local_id)

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(set(generated)) == len(generated), "並行生成時にIDが重複しました"
