"""E8-5: テキスト匿名化(FR-SL-04)。

完全な匿名化保証は困難(正規表現ベースの限界あり)。
実運用データ利用時は人手レビューを推奨する。
"""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"\b0\d{1,4}[-\s]?\d{1,4}[-\s]?\d{3,4}\b")
# 株式会社等 + 固有名、または @ 付き組織名
_ORG_RE = re.compile(
    r"(?:株式会社|有限会社|合同会社|Inc\.|Corp\.|Ltd\.)\s*[\w\u3040-\u30ff\u4e00-\u9fff]+"
)
# 日本語氏名ヒューリスティック(姓+名 2〜4文字×2)
_JA_NAME_RE = re.compile(r"[\u4e00-\u9fff]{2,4}\s*[\u4e00-\u9fff]{2,4}")

_MASK = "[REDACTED]"


def anonymize_text(text: str) -> str:
    """固有名詞・連絡先をマスクする(ベストエフォート)。"""
    result = _EMAIL_RE.sub(_MASK, text)
    result = _PHONE_RE.sub(_MASK, result)
    result = _ORG_RE.sub(_MASK, result)
    result = _JA_NAME_RE.sub(_MASK, result)
    return result
