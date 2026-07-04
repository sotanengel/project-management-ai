"""KBコーパスMarkdown本文のチャンク分割(E6-2)。

見出し(`#`で始まる行)を優先的な分割点として使い、見出しが無い/
1見出しあたりの文字数が上限(既定500字)を超える場合は固定長
(オーバーラップ付き)でさらに分割する。各チャンクはfront-matter
メタデータ(domain/framework/pm_principle/title)を継承する。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: 既定のチャンク最大文字数。
DEFAULT_MAX_CHARS = 500

#: 固定長分割時のオーバーラップ文字数。
DEFAULT_OVERLAP = 50

_HEADING_RE = re.compile(r"^#{1,6}\s+.*$", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    """1チャンク分のテキストと継承メタデータ。"""

    text: str
    domain: str
    framework: str | None
    pm_principle: str | None
    title: str
    source_path: str
    chunk_index: int


def _split_by_heading(body: str) -> list[str]:
    """見出し行を区切りとして本文をセクションに分割する。

    見出しが1つも無い場合は本文全体を単一セクションとして返す。
    """
    positions = [m.start() for m in _HEADING_RE.finditer(body)]
    if not positions:
        return [body]

    sections: list[str] = []
    for i, start in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(body)
        sections.append(body[start:end])
    # 最初の見出しより前に本文がある場合は先頭セクションとして追加する。
    if positions[0] > 0:
        sections.insert(0, body[: positions[0]])
    return sections


def _split_fixed_length(text: str, max_chars: int, overlap: int) -> list[str]:
    """固定長(オーバーラップ付き)でテキストを分割する。"""
    if len(text) <= max_chars:
        return [text]

    parts: list[str] = []
    step = max(max_chars - overlap, 1)
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        parts.append(text[start:end])
        if end == len(text):
            break
        start += step
    return parts


def chunk_document(
    body: str,
    front_matter: dict,
    *,
    source_path: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[Chunk]:
    """Markdown本文をチャンク分割し、front-matterメタデータを継承する。

    見出し単位でまず分割し、各セクションが `max_chars` を超える場合は
    固定長(オーバーラップ `overlap` 文字)でさらに分割する。
    """
    if not body.strip():
        return []

    domain: str = front_matter.get("domain", "")
    framework: str | None = front_matter.get("framework")
    pm_principle: str | None = front_matter.get("pm_principle")
    title: str = front_matter.get("title", "")

    sections = _split_by_heading(body)
    texts: list[str] = []
    for section in sections:
        if not section.strip():
            continue
        texts.extend(_split_fixed_length(section, max_chars=max_chars, overlap=overlap))

    return [
        Chunk(
            text=text,
            domain=domain,
            framework=framework,
            pm_principle=pm_principle,
            title=title,
            source_path=source_path,
            chunk_index=i,
        )
        for i, text in enumerate(texts)
    ]


__all__ = ["DEFAULT_MAX_CHARS", "DEFAULT_OVERLAP", "Chunk", "chunk_document"]
