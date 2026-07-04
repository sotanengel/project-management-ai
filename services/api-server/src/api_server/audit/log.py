"""追記専用監査ログ(JSONL + SHA-256ハッシュ連鎖)。

全ての書込系操作(PMDF CRUD、承認決定等)を`AuditRecord`として
`append_record`でJSONLファイルへ追記専用(オープンモード`"a"`)で
記録する。各レコードは直前レコードの`hash`を`prev_hash`として持ち、
`verify_chain`で先頭から連鎖を再計算することで改ざんを検知できる
(SEC-04)。

追記のみを提供し、既存行の書き換え・削除APIは意図的に用意しない。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


def _canonical_json(data: dict[str, Any]) -> str:
    """ハッシュ計算用に、キー順を固定した決定論的なJSON文字列を生成する。"""
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class AuditRecord(BaseModel):
    """監査ログ1レコード分の情報。"""

    timestamp: datetime
    actor: str
    action: str
    target_kind: str
    target_id: str
    detail: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str | None = None
    hash: str

    @classmethod
    def create(
        cls,
        *,
        actor: str,
        action: str,
        target_kind: str,
        target_id: str,
        detail: dict[str, Any] | None = None,
        prev_hash: str | None,
        timestamp: datetime | None = None,
    ) -> AuditRecord:
        """`hash`(prev_hash+他フィールドから算出するSHA-256)を含む新規レコードを生成する。"""
        ts = timestamp or datetime.now(UTC)
        payload = {
            "timestamp": ts.isoformat(),
            "actor": actor,
            "action": action,
            "target_kind": target_kind,
            "target_id": target_id,
            "detail": detail or {},
            "prev_hash": prev_hash,
        }
        digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
        return cls(
            timestamp=ts,
            actor=actor,
            action=action,
            target_kind=target_kind,
            target_id=target_id,
            detail=detail or {},
            prev_hash=prev_hash,
            hash=digest,
        )

    def recompute_hash(self) -> str:
        """現在のフィールド値から`hash`を再計算する(検証用)。"""
        payload = {
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "action": self.action,
            "target_kind": self.target_kind,
            "target_id": self.target_id,
            "detail": self.detail,
            "prev_hash": self.prev_hash,
        }
        return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def append_record(record: AuditRecord, log_path: Path) -> None:
    """`record`をJSONL形式で`log_path`へ追記する(追記専用、オープンモード`"a"`)。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = record.model_dump_json()
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def read_records(log_path: Path) -> list[AuditRecord]:
    """`log_path`から全レコードを順番に読み込む。ファイルが無ければ空リスト。"""
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(AuditRecord.model_validate(json.loads(line)))
    return records


def latest_hash(log_path: Path) -> str | None:
    """直近レコードの`hash`を返す(新規レコード作成時の`prev_hash`として利用)。"""
    records = read_records(log_path)
    if not records:
        return None
    return records[-1].hash


@dataclass(frozen=True)
class VerifyResult:
    """`verify_chain`の結果。"""

    ok: bool
    #: 改ざんが検出された場合の行番号(1始まり)。改ざんなしの場合は`None`。
    tampered_line: int | None


def verify_chain(log_path: Path) -> VerifyResult:
    """先頭から`prev_hash`の連鎖を検証し、不整合があれば該当行番号を報告する。

    各行について、(1)自身のフィールドから再計算した`hash`が記録された
    `hash`と一致するか、(2)`prev_hash`が直前レコードの`hash`と一致するか
    (先頭行は`prev_hash is None`であるべきか)を検証する。ファイルが
    存在しない・空の場合は改ざんなしとみなす。
    """
    if not log_path.exists():
        return VerifyResult(ok=True, tampered_line=None)

    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    prev_hash: str | None = None
    for index, line in enumerate(lines, start=1):
        record = AuditRecord.model_validate(json.loads(line))
        if record.prev_hash != prev_hash:
            return VerifyResult(ok=False, tampered_line=index)
        if record.recompute_hash() != record.hash:
            return VerifyResult(ok=False, tampered_line=index)
        prev_hash = record.hash

    return VerifyResult(ok=True, tampered_line=None)


__all__ = [
    "AuditRecord",
    "VerifyResult",
    "append_record",
    "latest_hash",
    "read_records",
    "verify_chain",
]
