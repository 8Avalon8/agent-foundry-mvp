from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from .tool_registry import ToolDefinition, ToolRegistry, default_tool_registry


class CapabilityResolutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class CapabilityResolution:
    capability: str
    tool: ToolDefinition

    def to_dict(self) -> Dict[str, object]:
        return {"capability": self.capability, "tool": self.tool.to_dict()}


class CapabilityRegistry:
    def __init__(self, tool_registry: ToolRegistry | None = None) -> None:
        self.tool_registry = tool_registry or default_tool_registry()

    def resolve(self, capability: str) -> CapabilityResolution:
        try:
            return CapabilityResolution(capability=capability, tool=self.tool_registry.get_for_capability(capability))
        except KeyError as exc:
            raise CapabilityResolutionError(str(exc)) from exc

    def resolve_all(self, capabilities: Iterable[str]) -> List[CapabilityResolution]:
        return [self.resolve(capability) for capability in capabilities]


def resolve_required_capabilities(agent_spec: Dict[str, object], registry: CapabilityRegistry | None = None) -> List[CapabilityResolution]:
    capabilities = agent_spec.get("tools", {}).get("required_capabilities", [])  # type: ignore[union-attr]
    if not isinstance(capabilities, list):
        raise CapabilityResolutionError("agent.tools.required_capabilities must be a list")
    return (registry or CapabilityRegistry()).resolve_all(str(item) for item in capabilities)
