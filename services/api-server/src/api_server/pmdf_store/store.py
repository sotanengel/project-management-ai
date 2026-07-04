"""PMDFエンティティのCRUD操作をGitコミットとして永続化する`PmdfStore`。

1操作=1コミットとし、任意時点の版取得・履歴取得を可能にする。
Windows環境での同時書き込みに備え、書き込み系操作はプロセス内
(かつクロスプロセスの)ファイルロックで直列化する(`lock.py`)。

`delete` は提供しない(DR-06によりapproval/decisionは削除不可。
他エンティティも本層では論理削除相当の`status`フィールド更新を推奨し、
物理削除APIは用意しない)。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import git
from pmdf.io import entity_relative_path, load_entity, save_entity
from pmdf.models.common import PmdfBase

from api_server.pmdf_store.lock import DEFAULT_LOCK_TIMEOUT_SECONDS, repo_write_lock


@dataclass(frozen=True)
class CommitInfo:
    """1コミット分の履歴情報。"""

    commit_hash: str
    author: str
    committed_at: datetime
    message: str


def _git_actor_email(actor: str) -> str:
    """`user:<id>` / `agent:<name>` 形式のactor文字列からコミット用メールを組み立てる。

    実在するメールアドレスである必要はなく、コミットのauthor情報として
    識別可能であればよい(ローカルGitリポジトリ内の来歴記録用途)。
    """
    local_part = actor.replace("@", "_at_").replace(" ", "_")
    return f"{local_part}@pmdf.local"


class PmdfStore:
    """PMDFエンティティ用のGit永続化ストア。"""

    def __init__(self, repo_path: Path, lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS):
        self.repo_path = Path(repo_path)
        self.lock_timeout_seconds = lock_timeout_seconds
        self.repo = git.Repo(self.repo_path)

    @staticmethod
    def init(path: Path) -> None:
        """`path` に通常のGitリポジトリ(作業ツリー同梱、bare不可)を初期化する。"""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        git.Repo.init(path, bare=False)

    def _commit(self, entity: PmdfBase, actor: str, verb: str) -> None:
        with repo_write_lock(self.repo_path, timeout_seconds=self.lock_timeout_seconds):
            save_entity(entity, self.repo_path)
            relative_path = entity_relative_path(entity.kind, entity.id).as_posix()
            self.repo.index.add([relative_path])
            message = f"{verb}({entity.kind}): {entity.id} by {actor}"
            author = git.Actor(actor, _git_actor_email(actor))
            self.repo.index.commit(message, author=author, committer=author)

    def create(self, entity: PmdfBase, actor: str) -> PmdfBase:
        """エンティティをYAML書き込み+1コミットとして新規作成する。"""
        self._commit(entity, actor, "create")
        return entity

    def update(self, entity: PmdfBase, actor: str) -> PmdfBase:
        """エンティティをYAML書き込み+1コミットとして更新する。"""
        self._commit(entity, actor, "update")
        return entity

    def get(self, kind: str, id: str, ref: str | None = None) -> PmdfBase:
        """エンティティを取得する。`ref` 省略時はHEAD(作業ツリー上の最新)を返す。"""
        relative_path = entity_relative_path(kind, id)
        if ref is None:
            return load_entity(self.repo_path / relative_path)

        blob = self.repo.commit(ref).tree / relative_path.as_posix()
        text = blob.data_stream.read().decode("utf-8")
        return self._load_entity_from_text(text)

    @staticmethod
    def _load_entity_from_text(text: str) -> PmdfBase:
        from pmdf.io import yaml_to_dict
        from pmdf.models import KIND_TO_MODEL

        data = yaml_to_dict(text)
        kind = data.get("kind")
        if kind not in KIND_TO_MODEL:
            raise KeyError(f"未知のkindです: {kind!r}")
        model = KIND_TO_MODEL[kind]
        return model.model_validate(data)

    def history(self, kind: str, id: str) -> list[CommitInfo]:
        """対象ファイルの全コミット履歴を新しい順で返す。"""
        relative_path = entity_relative_path(kind, id).as_posix()
        commits = list(self.repo.iter_commits(paths=relative_path))
        return [
            CommitInfo(
                commit_hash=commit.hexsha,
                author=f"{commit.author.name} <{commit.author.email}>",
                committed_at=datetime.fromtimestamp(commit.committed_date, tz=UTC),
                message=str(commit.message).strip(),
            )
            for commit in commits
        ]


__all__ = ["CommitInfo", "PmdfStore"]
