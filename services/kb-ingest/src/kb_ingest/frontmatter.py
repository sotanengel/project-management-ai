"""KBコーパスMarkdownファイルのYAML front-matter解析・スキーマ検証。

`kb/corpus/<domain>/<slug>.md` は先頭にYAML front-matter
(`---` ... `---`)を持ち、続けて独自著作の本文(Markdown)を記述する
規約とする(E6-1)。本モジュールはこのfront-matterの解析と
pydanticによるスキーマ検証を提供する。
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

#: PdM本体ドメインの例(FR-KB-01)。
PDM_DOMAINS: tuple[str, ...] = (
    "vision_strategy",
    "discovery",
    "roadmap",
    "backlog_prioritization",
    "metrics",
    "experimentation",
    "release",
    "stakeholder",
)

#: PM隣接ドメイン(PMBOK第8版準拠教科書の独自要約、原文複製は禁止)。
PM_ADJACENT_DOMAINS: tuple[str, ...] = ("project_management",)

#: 既知のdomain値全体(PdM本体 + PM隣接)。
KNOWN_DOMAINS: tuple[str, ...] = PDM_DOMAINS + PM_ADJACENT_DOMAINS

#: 既知のframework値の例(必須ではないため未知の値も許容する設計とはせず、
#: 拡張しやすいよう緩めのバリデーションに留める。値自体は自由記述文字列)。
KNOWN_FRAMEWORKS: tuple[str, ...] = (
    "rice",
    "wsjf",
    "kano",
    "aarrr",
    "north_star_metric",
    "jtbd",
    "okr",
    "evm",
    "wbs",
)

#: 既知のpm_principle値の例(PMBOK第8版の独自要約としての原則名。
#: 逐語引用ではなく本プロジェクト独自の分類ラベル)。
KNOWN_PM_PRINCIPLES: tuple[str, ...] = (
    "focus_on_value",
    "tailoring",
    "stewardship",
    "collaboration",
    "stakeholder_engagement",
    "adaptability",
    "quality",
    "complexity",
    "risk_response",
    "systems_thinking",
    "leadership",
)


class CorpusFrontMatter(BaseModel):
    """`kb/corpus/**/*.md` のfront-matter必須・任意フィールドのスキーマ。

    必須: domain, title, source, license。
    任意: framework, pm_principle(いずれもNone許容)。
    """

    model_config = ConfigDict(extra="forbid")

    domain: str = Field(description="コーパスの分野(例: discovery, project_management)")
    title: str = Field(description="ファイルのタイトル")
    source: str = Field(description="出典種別(例: original)")
    license: str = Field(description="ライセンス種別(例: internal)")
    framework: str | None = Field(default=None, description="関連フレームワーク名")
    pm_principle: str | None = Field(default=None, description="関連PM原則ラベル")

    @field_validator("domain")
    @classmethod
    def _validate_domain(cls, value: str) -> str:
        if value not in KNOWN_DOMAINS:
            raise ValueError(f"未知のdomain値です: {value!r}(既知の値: {', '.join(KNOWN_DOMAINS)})")
        return value

    def is_pm_adjacent(self) -> bool:
        """PM隣接ドメイン(project_management等)かどうかを返す。"""
        return self.domain in PM_ADJACENT_DOMAINS


def parse_markdown_text(text: str) -> tuple[dict, str]:
    """Markdownテキストを front-matter(dict) と本文(str) に分割する。

    先頭が `---` で始まらない、または閉じの `---` が無い場合は
    `ValueError` を送出する。
    """
    stripped = text.lstrip("﻿")
    if not stripped.startswith("---"):
        raise ValueError("front-matterが見つかりません(先頭が '---' ではありません)")

    lines = stripped.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("front-matterの開始行 '---' が不正です")

    end_index = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_index = i
            break
    if end_index is None:
        raise ValueError("front-matterの終端 '---' が見つかりません")

    front_matter_text = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :])
    front_matter = yaml.safe_load(front_matter_text) or {}
    if not isinstance(front_matter, dict):
        raise ValueError("front-matterはYAMLマッピング(dict)である必要があります")
    return front_matter, body


def parse_markdown_file(path: Path) -> tuple[dict, str]:
    """Markdownファイルを読み込み front-matter(dict) と本文(str) を返す。"""
    text = path.read_text(encoding="utf-8")
    return parse_markdown_text(text)


__all__ = [
    "KNOWN_DOMAINS",
    "KNOWN_FRAMEWORKS",
    "KNOWN_PM_PRINCIPLES",
    "PDM_DOMAINS",
    "PM_ADJACENT_DOMAINS",
    "CorpusFrontMatter",
    "parse_markdown_file",
    "parse_markdown_text",
]
