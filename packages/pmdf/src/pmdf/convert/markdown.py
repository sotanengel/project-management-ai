"""decision/reportのMarkdown変換出力(FR-EX-06)。"""

from __future__ import annotations

from pmdf.models import Decision, Report


def decision_to_markdown(decision: Decision) -> str:
    """decisionを背景/選択肢/採用案/却下理由のMarkdown見出し構造で出力する。"""
    lines: list[str] = [f"# Decision: {decision.id}", ""]

    lines += ["## 背景", "", decision.background, ""]

    lines.append("## 選択肢")
    lines.append("")
    for option in decision.options:
        line = f"- **{option.name}**"
        if option.description:
            line += f": {option.description}"
        lines.append(line)
    lines.append("")

    lines += ["## 採用案", "", decision.chosen_option, ""]
    lines += ["## 根拠", "", decision.rationale, ""]

    lines.append("## 却下理由")
    lines.append("")
    for rejected in decision.rejected_reasons:
        lines.append(f"- {rejected.option}: {rejected.reason}")
    lines.append("")

    lines += [f"自律レベル: {decision.autonomy_level}", ""]

    return "\n".join(lines)


def report_to_markdown(report: Report) -> str:
    """reportを期間/健全性評価/要判断事項のMarkdown構造で出力する。"""
    health_labels = {"green": "順調", "yellow": "要注意", "red": "危険"}
    lines: list[str] = [
        f"# Report: {report.id}",
        "",
        f"- 期間: {report.period}",
        f"- 健全性評価: {report.health_assessment}"
        f" ({health_labels.get(report.health_assessment, report.health_assessment)})",
        "",
        "## 要判断事項",
        "",
    ]
    for item in report.decisions_needed:
        lines.append(f"- {item}")
    lines.append("")

    if report.summary:
        lines += ["## サマリ", "", report.summary, ""]

    return "\n".join(lines)


__all__ = ["decision_to_markdown", "report_to_markdown"]
