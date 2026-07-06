"""E9-5: security-scan ワークフロー定義の検証。"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/security-scan.yml")


def test_security_scan_workflow_has_triggers() -> None:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert "schedule" in data["on"]
    assert "workflow_dispatch" in data["on"]
    job_names = set(data["jobs"])
    assert {"pinact", "zizmor", "trivy", "dependency-audit"}.issubset(job_names)
