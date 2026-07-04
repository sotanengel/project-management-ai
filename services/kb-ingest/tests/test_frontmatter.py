"""kb_ingest.frontmatter のスキーマ検証・Markdown解析のテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest
from kb_ingest.frontmatter import (
    KNOWN_DOMAINS,
    CorpusFrontMatter,
    parse_markdown_file,
    parse_markdown_text,
)
from pydantic import ValidationError


def test_parse_markdown_text_splits_frontmatter_and_body() -> None:
    text = """---
domain: discovery
framework: jtbd
pm_principle: null
title: サンプルタイトル
source: original
license: internal
---
本文がここに入る。
複数行。
"""
    front_matter, body = parse_markdown_text(text)
    assert front_matter["domain"] == "discovery"
    assert front_matter["framework"] == "jtbd"
    assert front_matter["title"] == "サンプルタイトル"
    assert "本文がここに入る。" in body


def test_parse_markdown_file(tmp_path: Path) -> None:
    md_path = tmp_path / "sample.md"
    md_path.write_text(
        "---\ndomain: metrics\ntitle: t\nsource: original\nlicense: internal\n---\n本文\n",
        encoding="utf-8",
    )
    front_matter, body = parse_markdown_file(md_path)
    assert front_matter["domain"] == "metrics"
    assert body.strip() == "本文"


def test_parse_markdown_text_without_frontmatter_raises() -> None:
    with pytest.raises(ValueError):
        parse_markdown_text("front-matterが無い本文だけのファイル")


def test_corpus_frontmatter_valid_minimal() -> None:
    fm = CorpusFrontMatter.model_validate(
        {
            "domain": "discovery",
            "title": "タイトル",
            "source": "original",
            "license": "internal",
        }
    )
    assert fm.domain == "discovery"
    assert fm.framework is None
    assert fm.pm_principle is None


def test_corpus_frontmatter_valid_full() -> None:
    fm = CorpusFrontMatter.model_validate(
        {
            "domain": "backlog_prioritization",
            "framework": "rice",
            "pm_principle": None,
            "title": "RICEスコアの考え方",
            "source": "original",
            "license": "internal",
        }
    )
    assert fm.framework == "rice"


@pytest.mark.parametrize("missing_field", ["domain", "title", "source", "license"])
def test_corpus_frontmatter_missing_required_field_raises(missing_field: str) -> None:
    data = {
        "domain": "discovery",
        "title": "t",
        "source": "original",
        "license": "internal",
    }
    del data[missing_field]
    with pytest.raises(ValidationError):
        CorpusFrontMatter.model_validate(data)


def test_corpus_frontmatter_rejects_unknown_domain() -> None:
    with pytest.raises(ValidationError):
        CorpusFrontMatter.model_validate(
            {
                "domain": "unknown_domain_xyz",
                "title": "t",
                "source": "original",
                "license": "internal",
            }
        )


def test_known_domains_include_pm_adjacent() -> None:
    assert "project_management" in KNOWN_DOMAINS
    assert "discovery" in KNOWN_DOMAINS
