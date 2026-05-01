from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Literal

Permission = Literal["allow", "ask", "deny"]


@dataclass
class PermissionDecision:
    permission: Permission
    tool: str
    risk: str
    reason: str
    approval_request: Dict[str, Any] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def check_permission(agent_spec: Dict[str, Any], tool: str, payload: Dict[str, Any] | None = None) -> PermissionDecision:
    policy = agent_spec.get("tool_policy", {}).get(tool, {"permission": "ask", "risk": "medium"})
    permission = policy.get("permission", "ask")
    risk = policy.get("risk", "medium")
    reason = f"Tool `{tool}` is configured as `{permission}` with risk `{risk}`."
    approval = None
    if permission == "ask":
        approval = {
            "type": "approval",
            "tool": tool,
            "risk": risk,
            "payload": payload or {},
            "reason": reason,
            "options": ["approve_once", "reject", "show_impact"],
        }
    return PermissionDecision(permission=permission, tool=tool, risk=risk, reason=reason, approval_request=approval)
