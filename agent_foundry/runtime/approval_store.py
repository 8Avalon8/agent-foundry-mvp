from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


SUPPORTED_DECISIONS = {"approve_once", "reject", "show_impact", "add_to_whitelist"}


def normalize_approval_request(request: Dict[str, Any]) -> Dict[str, Any]:
    tool = request.get("tool") or request.get("action") or "unknown"
    return {
        "id": request.get("id") or f"approval_{str(tool).replace('.', '_')}",
        "type": request.get("type", "approval"),
        "tool": tool,
        "risk": request.get("risk", "medium"),
        "reason": request.get("reason", ""),
        "payload": request.get("payload", {}),
        "options": request.get("options", sorted(SUPPORTED_DECISIONS)),
        "created_at": request.get("created_at") or _now(),
        "status": request.get("status", "pending"),
        "decision": request.get("decision", ""),
        "impact": request.get("impact", {}),
    }


def load_pending_approvals(run_dir: Path) -> List[Dict[str, Any]]:
    path = run_dir / "pending_approvals.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("approvals", [])


def save_pending_approvals(run_dir: Path, approvals: List[Dict[str, Any]]) -> None:
    (run_dir / "pending_approvals.json").write_text(json.dumps(approvals, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_approval_log(run_dir: Path) -> None:
    path = run_dir / "approval_log.jsonl"
    if not path.exists():
        path.write_text("", encoding="utf-8")


def add_pending_approval(run_dir: Path, request: Dict[str, Any]) -> Dict[str, Any]:
    approval = normalize_approval_request(request)
    approvals = load_pending_approvals(run_dir)
    by_id = {item.get("id"): item for item in approvals}
    by_id[approval["id"]] = approval
    save_pending_approvals(run_dir, list(by_id.values()))
    ensure_approval_log(run_dir)
    return approval


def record_approval_decision(run_dir: Path, approval_id: str, decision: str) -> Dict[str, Any]:
    if decision not in SUPPORTED_DECISIONS:
        raise ValueError(f"Unsupported approval decision: {decision}")
    approvals = load_pending_approvals(run_dir)
    found = None
    for item in approvals:
        if item.get("id") == approval_id:
            found = item
            if decision in {"approve_once", "reject"}:
                item["status"] = "approved_once" if decision == "approve_once" else "rejected"
            item["decision"] = decision
            item["decided_at"] = _now()
            break
    if found is None:
        raise KeyError(f"Approval not found: {approval_id}")
    save_pending_approvals(run_dir, approvals)
    entry = {"approval_id": approval_id, "decision": decision, "recorded_at": _now(), "tool": found.get("tool")}
    with (run_dir / "approval_log.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def pending_count(run_dir: Path) -> int:
    return sum(1 for item in load_pending_approvals(run_dir) if item.get("status") == "pending")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
