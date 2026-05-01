from __future__ import annotations

from typing import Any, Dict, List


def finding_feedback_request(finding: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "finding_feedback",
        "finding_id": finding.get("id"),
        "title": finding.get("title"),
        "severity": finding.get("severity"),
        "evidence": finding.get("evidence", []),
        "options": finding.get("feedback_options", ["accepted", "false_positive", "too_minor", "duplicate", "needs_more_evidence"]),
    }


def batch_feedback_requests(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [finding_feedback_request(f) for f in findings]
