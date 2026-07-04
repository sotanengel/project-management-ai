"""pmdf-store層(Git永続化)のテスト(E3-2)。

1操作=1コミット、任意版取得、履歴取得、並行書き込みの直列化・
ロックタイムアウトを検証する。
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from api_server.pmdf_store.lock import LockTimeoutError
from api_server.pmdf_store.store import PmdfStore

from tests.factories import make_story


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    repo_path = tmp_path / "pmdf-repo"
    PmdfStore.init(repo_path)
    return repo_path


def test_init_creates_git_repository(store_path: Path) -> None:
    assert (store_path / ".git").exists()


def test_create_writes_file_and_creates_one_commit(store_path: Path) -> None:
    store = PmdfStore(store_path)
    story = make_story(id="story-01HAAAAAAAAAAAAAAAAAAAAAAA")

    store.create(story, actor="user:alice")

    saved_path = store_path / "story" / f"{story.id}.yaml"
    assert saved_path.exists()

    history = store.history("story", story.id)
    assert len(history) == 1
    assert "alice" in history[0].author


def test_update_creates_additional_commit(store_path: Path) -> None:
    store = PmdfStore(store_path)
    story = make_story(id="story-01HBBBBBBBBBBBBBBBBBBBBBBB", title="v1")
    store.create(story, actor="user:alice")

    updated = story.model_copy(update={"title": "v2"})
    store.update(updated, actor="agent:pm-bot@v1")

    history = store.history("story", story.id)
    assert len(history) == 2
    assert "pm-bot" in history[0].author  # 最新が先頭


def test_get_returns_latest_by_default(store_path: Path) -> None:
    store = PmdfStore(store_path)
    story = make_story(id="story-01HCCCCCCCCCCCCCCCCCCCCCCC", title="v1")
    store.create(story, actor="user:alice")
    updated = story.model_copy(update={"title": "v2"})
    store.update(updated, actor="user:alice")

    fetched = store.get("story", story.id)
    assert fetched.title == "v2"  # type: ignore[attr-defined]


def test_get_with_ref_returns_past_version(store_path: Path) -> None:
    store = PmdfStore(store_path)
    story = make_story(id="story-01HDDDDDDDDDDDDDDDDDDDDDDD", title="v1")
    store.create(story, actor="user:alice")
    first_commit = store.history("story", story.id)[0].commit_hash

    updated = story.model_copy(update={"title": "v2"})
    store.update(updated, actor="user:alice")

    past = store.get("story", story.id, ref=first_commit)
    assert past.title == "v1"  # type: ignore[attr-defined]

    latest = store.get("story", story.id)
    assert latest.title == "v2"  # type: ignore[attr-defined]


def test_history_round_trip_matches_content_at_each_version(store_path: Path) -> None:
    store = PmdfStore(store_path)
    story = make_story(id="story-01HEEEEEEEEEEEEEEEEEEEEEEE", title="v1")
    store.create(story, actor="user:alice")
    for i in range(2, 5):
        updated = story.model_copy(update={"title": f"v{i}"})
        story = updated
        store.update(updated, actor="user:alice")

    history = store.history("story", story.id)
    assert len(history) == 4

    # 履歴は新しい順。各版のcommit_hashで復元し、期待するtitleと一致するか確認する。
    expected_titles_oldest_first = ["v1", "v2", "v3", "v4"]
    commits_oldest_first = list(reversed([h.commit_hash for h in history]))
    for commit_hash, expected_title in zip(
        commits_oldest_first, expected_titles_oldest_first, strict=True
    ):
        restored = store.get("story", story.id, ref=commit_hash)
        assert restored.title == expected_title  # type: ignore[attr-defined]


def test_concurrent_writes_are_serialized_and_commit_count_matches(store_path: Path) -> None:
    store = PmdfStore(store_path)
    n_threads = 8
    errors: list[Exception] = []

    from pmdf.ids import generate_id

    def _create_one(i: int) -> None:
        try:
            story = make_story(id=generate_id("story"))
            store.create(story, actor=f"user:worker{i}")
        except Exception as exc:  # pragma: no cover - captured for assertion
            errors.append(exc)

    threads = [threading.Thread(target=_create_one, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors

    repo = store.repo
    commit_count = sum(1 for _ in repo.iter_commits())
    assert commit_count == n_threads


def test_lock_timeout_raises_lock_timeout_error(store_path: Path, monkeypatch) -> None:
    from api_server.pmdf_store import lock as lock_module

    store = PmdfStore(store_path, lock_timeout_seconds=0.2)
    story = make_story(id="story-01HGGGGGGGGGGGGGGGGGGGGGGG")

    held_lock = lock_module.FileLock(str(store_path / ".pmdf.lock"))
    held_lock.acquire()
    try:
        with pytest.raises(LockTimeoutError):
            store.create(story, actor="user:alice")
    finally:
        held_lock.release()


def test_delete_is_not_provided(store_path: Path) -> None:
    store = PmdfStore(store_path)
    assert not hasattr(store, "delete")


def test_list_all_returns_all_entities_of_kind(store_path: Path) -> None:
    store = PmdfStore(store_path)
    story1 = make_story(id="story-01HHHHHHHHHHHHHHHHHHHHHHHH", title="one")
    story2 = make_story(id="story-01HJJJJJJJJJJJJJJJJJJJJJJJ", title="two")
    store.create(story1, actor="user:alice")
    store.create(story2, actor="user:alice")

    results = store.list_all("story")

    assert {e.id for e in results} == {story1.id, story2.id}


def test_list_all_returns_empty_list_when_kind_dir_missing(store_path: Path) -> None:
    store = PmdfStore(store_path)
    assert store.list_all("story") == []


def test_save_all_writes_multiple_entities_in_one_commit(store_path: Path) -> None:
    store = PmdfStore(store_path)
    baseline = make_story(id="story-01HPPPPPPPPPPPPPPPPPPPPPPP", title="baseline")
    store.create(baseline, actor="user:alice")

    story1 = make_story(id="story-01HKKKKKKKKKKKKKKKKKKKKKKK", title="one")
    story2 = make_story(id="story-01HMMMMMMMMMMMMMMMMMMMMMMM", title="two")

    store.save_all([story1, story2], actor="user:bulk", message="bundle apply: 2 entities")

    assert (store_path / "story" / f"{story1.id}.yaml").exists()
    assert (store_path / "story" / f"{story2.id}.yaml").exists()
    commit_count = sum(1 for _ in store.repo.iter_commits())
    assert commit_count == 2


def test_save_all_with_empty_list_creates_no_additional_commit(store_path: Path) -> None:
    store = PmdfStore(store_path)
    story = make_story(id="story-01HNNNNNNNNNNNNNNNNNNNNNNN")
    store.create(story, actor="user:alice")

    store.save_all([], actor="user:bulk", message="no-op")

    commit_count = sum(1 for _ in store.repo.iter_commits())
    assert commit_count == 1
