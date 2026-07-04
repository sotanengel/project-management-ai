"""kb/corpus/ 配下の全Markdownファイルのfront-matterメタデータ検証。

E6-1の受け入れ条件:
- kb/corpus/ 配下の全Markdownファイルがfront-matterの必須フィールド
  (domain, title, source, license)を持つことをスキーマ検証する。
- PdM本体ドメイン最低10件、PM隣接ドメイン(project_management)最低5件の
  サンプルファイルが存在する。
- CORPUS_LICENSE_CHECKLIST.md が存在し、原文複製禁止・商標不使用の
  項目を含む。
- 全サンプルファイルの本文に「PMBOK」「PMP」などの商標文字列が
  製品名的な用法で使われていない。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kb_ingest.frontmatter import CorpusFrontMatter, parse_markdown_file
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = REPO_ROOT / "kb" / "corpus"
CHECKLIST_PATH = REPO_ROOT / "kb" / "CORPUS_LICENSE_CHECKLIST.md"

PM_ADJACENT_DOMAIN = "project_management"

#: コーパス本文中で製品名的用法として使用してはならない商標文字列。
FORBIDDEN_TRADEMARK_TERMS = ["PMBOK", "PMP"]


def _all_corpus_files() -> list[Path]:
    assert CORPUS_DIR.is_dir(), f"{CORPUS_DIR} が存在しません"
    return sorted(CORPUS_DIR.rglob("*.md"))


def test_corpus_dir_exists() -> None:
    assert CORPUS_DIR.is_dir()


def test_all_corpus_files_have_valid_frontmatter() -> None:
    files = _all_corpus_files()
    assert files, "kb/corpus/ 配下にMarkdownファイルが1件もありません"
    for path in files:
        front_matter, _body = parse_markdown_file(path)
        # pydanticスキーマ検証(必須フィールド欠如やdomain不正値は例外を送出する)
        CorpusFrontMatter.model_validate(front_matter)


def test_frontmatter_rejects_missing_required_fields() -> None:
    with pytest.raises(ValidationError):
        CorpusFrontMatter.model_validate(
            {
                "domain": "discovery",
                # title, source, license が欠落
            }
        )


def test_frontmatter_rejects_unknown_domain() -> None:
    with pytest.raises(ValidationError):
        CorpusFrontMatter.model_validate(
            {
                "domain": "not_a_real_domain",
                "title": "テスト",
                "source": "original",
                "license": "internal",
            }
        )


def test_pdm_domain_has_at_least_10_files() -> None:
    files = _all_corpus_files()
    pdm_files = [p for p in files if parse_markdown_file(p)[0].get("domain") != PM_ADJACENT_DOMAIN]
    assert len(pdm_files) >= 10, f"PdM本体ドメインのファイルが10件未満です({len(pdm_files)}件)"


def test_pm_adjacent_domain_has_at_least_5_files() -> None:
    files = _all_corpus_files()
    pm_files = [p for p in files if parse_markdown_file(p)[0].get("domain") == PM_ADJACENT_DOMAIN]
    assert len(pm_files) >= 5, f"PM隣接ドメインのファイルが5件未満です({len(pm_files)}件)"


def test_license_checklist_exists_and_has_required_items() -> None:
    assert CHECKLIST_PATH.is_file(), f"{CHECKLIST_PATH} が存在しません"
    text = CHECKLIST_PATH.read_text(encoding="utf-8")
    assert "原文" in text
    assert "商標" in text
    assert "ライセンス" in text or "出典" in text


@pytest.mark.parametrize("path", _all_corpus_files() or [None])
def test_no_trademark_terms_in_body(path: Path | None) -> None:
    if path is None:
        pytest.skip("kb/corpus/ にファイルがありません")
    _front_matter, body = parse_markdown_file(path)
    for term in FORBIDDEN_TRADEMARK_TERMS:
        assert term not in body, f"{path} の本文に商標文字列 '{term}' が含まれています"
