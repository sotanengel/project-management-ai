"""E9-5: security-scan ワークフロー定義の検証。"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/security-scan.yml")


def test_security_scan_workflow_has_triggers() -> None:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = data.get(True) or data.get("on")
    assert triggers is not None
    assert "schedule" in triggers
    assert "workflow_dispatch" in triggers
    job_names = set(data["jobs"])
    assert {"pinact", "zizmor", "trivy", "dependency-audit"}.issubset(job_names)
