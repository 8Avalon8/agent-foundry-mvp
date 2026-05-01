from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Literal
import re

Permission = Literal["allow", "ask", "deny"]
PermissionStatus = Literal["allowed", "requires_approval", "denied"]
ApprovalAction = Literal["approve_once", "reject", "show_impact", "add_to_whitelist"]


@dataclass
class PermissionDecision:
    permission: Permission
    status: PermissionStatus
    tool: str
    risk: str
    reason: str
    payload: Dict[str, Any]
    approval_request: Dict[str, Any] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def check_permission(agent_spec: Dict[str, Any], tool: str, payload: Dict[str, Any] | None = None) -> PermissionDecision:
    policy = agent_spec.get("tool_policy", {}).get(tool, {"permission": "ask", "risk": "medium"})
    permission = policy.get("permission", "ask")
    risk = policy.get("risk", "medium")
    reason = f"Tool `{tool}` is configured as `{permission}` with risk `{risk}`."
    payload = payload or {}
    approval = None
    status: PermissionStatus = "allowed"
    if permission == "ask":
        status = "requires_approval"
        approval = {
            "id": f"approval_{_slug(tool)}",
            "type": "approval",
            "action": tool,
            "tool": tool,
            "risk": risk,
            "payload": payload,
            "reason": reason,
            "options": ["approve_once", "reject", "show_impact", "add_to_whitelist"],
            "impact": {
                "policy_path": f"tool_policy.{tool}.permission",
                "current_permission": permission,
                "risk": risk,
            },
        }
    elif permission == "deny":
        status = "denied"
        reason = f"Tool `{tool}` is denied by tool_policy with risk `{risk}`."
    return PermissionDecision(permission=permission, status=status, tool=tool, risk=risk, reason=reason, payload=payload, approval_request=approval)


def resolve_approval(decision: PermissionDecision, action: ApprovalAction) -> Dict[str, Any]:
    if decision.status != "requires_approval":
        return {"status": decision.status, "tool": decision.tool, "reason": decision.reason}
    if action == "approve_once":
        return {"status": "approved_once", "tool": decision.tool, "permission": "allow", "scope": "single_action"}
    if action == "reject":
        return {"status": "rejected", "tool": decision.tool, "permission": "deny", "reason": "User rejected approval request."}
    if action == "show_impact":
        return {"status": "impact", "tool": decision.tool, "impact": decision.approval_request.get("impact") if decision.approval_request else {}}
    if action == "add_to_whitelist":
        return {
            "status": "policy_patch_required",
            "tool": decision.tool,
            "permission": "ask",
            "reason": "Adding to a whitelist requires an explicit policy patch approval.",
            "patch": {"tool": decision.tool, "payload": decision.payload},
        }
    raise ValueError(f"Unsupported approval action: {action}")


def permission_checks_for_spec(agent_spec: Dict[str, Any]) -> Dict[str, Any]:
    checks = [check_permission(agent_spec, tool).to_dict() for tool in sorted(agent_spec.get("tool_policy", {}))]
    return {"type": "permission_checks", "checks": checks}


def _slug(tool: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", tool).strip("_").lower() or "tool"
