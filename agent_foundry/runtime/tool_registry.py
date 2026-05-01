from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class ToolDefinition:
    tool_id: str
    capability: str
    policy_key: str
    risk: str
    side_effect: bool
    description: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def default_tool_definitions() -> List[ToolDefinition]:
    return [
        ToolDefinition("svn.diff", "read_svn_diff", "svn.diff", "low", False, "Read svn diff from a working copy."),
        ToolDefinition("svn.status", "read_svn_status", "svn.status", "low", False, "Read svn status from a working copy."),
        ToolDefinition("diff.parse_files", "parse_diff_files", "diff.parse_files", "low", False, "Parse changed files from diff text."),
        ToolDefinition("fs.read", "read_files", "fs.read", "low_to_medium", False, "Read bounded file context inside a working copy."),
        ToolDefinition("code.search", "search_code", "code.search", "low_to_medium", False, "Search code context inside allowed scope."),
        ToolDefinition("review.report", "generate_review_report", "review.report", "low", False, "Generate a review report."),
        ToolDefinition("review.report", "generate_markdown", "review.report", "low", False, "Generate markdown output."),
        ToolDefinition("human.feedback", "collect_human_feedback", "human.feedback", "low", False, "Collect human feedback labels."),
        ToolDefinition("human.feedback", "ask_user", "human.feedback", "low", False, "Ask the user for structured feedback."),
        ToolDefinition("memory.propose_rule_patch", "propose_rule_patch", "memory.propose_rule_patch", "medium", False, "Propose a rule patch candidate."),
        ToolDefinition("memory.apply_patch", "apply_memory_patch", "memory.apply_patch", "medium", True, "Apply an approved memory patch."),
    ]


class ToolRegistry:
    def __init__(self, tools: Iterable[ToolDefinition] | None = None) -> None:
        self._tools_by_id: Dict[str, ToolDefinition] = {}
        self._tools_by_capability: Dict[str, ToolDefinition] = {}
        for tool in tools or default_tool_definitions():
            self.register(tool)

    def register(self, tool: ToolDefinition) -> None:
        self._tools_by_id[tool.tool_id] = tool
        self._tools_by_capability.setdefault(tool.capability, tool)

    def get_tool(self, tool_id: str) -> ToolDefinition:
        try:
            return self._tools_by_id[tool_id]
        except KeyError as exc:
            raise KeyError(f"Unknown tool: {tool_id}") from exc

    def get_for_capability(self, capability: str) -> ToolDefinition:
        try:
            return self._tools_by_capability[capability]
        except KeyError as exc:
            raise KeyError(f"Missing tool for capability: {capability}") from exc

    def to_dict(self) -> Dict[str, object]:
        return {"tools": [tool.to_dict() for tool in self._tools_by_id.values()]}


def default_tool_registry() -> ToolRegistry:
    return ToolRegistry()
