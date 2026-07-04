"""接頭辞付きULID採番。

`generate_id(kind)` は `<kind_prefix>-<26文字ULID>` 形式の文字列を返す。
ULIDは時刻順ソート可能なため、組織間衝突を避けるため単調(monotonic)生成
(同一プロセス内で同一ミリ秒に複数生成しても辞書順で単調増加する)を行う。
"""

from __future__ import annotations

import threading

from ulid import ULID

#: `kind` enum値とULID接頭辞の対応。E2-1のIDパターン
#: (`^[a-z]+-[0-9A-HJKMNP-TV-Z]{26}$`)に適合する接頭辞を用いる。
KIND_TO_PREFIX: dict[str, str] = {
    "product": "prod",
    "stakeholder": "stakeholder",
    "persona": "persona",
    "objective": "obj",
    "metric": "metric",
    "roadmap_item": "roadmap",
    "story": "story",
    "experiment": "experiment",
    "decision": "dec",
    "release": "release",
    "risk": "risk",
    "initiative": "initiative",
    "report": "report",
    "approval": "approval",
}

_MAX_ULID_INT = (1 << 128) - 1
_lock = threading.Lock()
_last_ulid: ULID | None = None


def _next_monotonic_ulid() -> ULID:
    """単調増加なULIDを生成する(スレッドセーフ)。

    同一ミリ秒内、あるいはシステムクロックの逆行時でも、直前に生成した
    ULIDより辞書順で必ず大きい値を返す(直前の値+1)。
    """
    global _last_ulid
    with _lock:
        candidate = ULID()
        if _last_ulid is not None and int.from_bytes(candidate.bytes, "big") <= int.from_bytes(
            _last_ulid.bytes, "big"
        ):
            next_int = int.from_bytes(_last_ulid.bytes, "big") + 1
            if next_int > _MAX_ULID_INT:
                raise OverflowError("ULIDの採番上限に達しました")
            candidate = ULID.from_bytes(next_int.to_bytes(16, "big"))
        _last_ulid = candidate
        return candidate


def generate_id(kind: str) -> str:
    """`kind` に対応する接頭辞付きULID文字列を生成する。

    Raises:
        KeyError: 未知の`kind`が指定された場合。
    """
    if kind not in KIND_TO_PREFIX:
        raise KeyError(f"未知のkindです: {kind!r}")
    prefix = KIND_TO_PREFIX[kind]
    ulid_value = _next_monotonic_ulid()
    return f"{prefix}-{ulid_value}"


__all__ = ["KIND_TO_PREFIX", "generate_id"]
