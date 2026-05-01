from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List
import re


@dataclass
class ParsedIntent:
    user_goal: str
    domain: str
    likely_agent_type: str
    risk_level: str
    requires_tools: List[str]
    possible_side_effects: List[str]
    confidence: str = "medium"

    def to_dict(self) -> Dict:
        return asdict(self)


KEYWORDS = {
    "review-agent": ["review", "审查", "代码审查", "svn", "diff", "code review", "cr", "检查", "评审"],
    "writing-agent": ["公众号", "写作", "文章", "博客", "文案", "选题", "初稿", "创作", "剧情", "故事"],
    "coding-agent": ["写代码", "重构", "bug", "修复", "开发", "实现", "coding", "代码生成"],
    "research-agent": ["调研", "研究", "资料", "竞品", "报告", "research", "方案比较"],
    "monitor-agent": ["监控", "提醒", "定时", "日报", "周报", "watch", "monitor"],
    "automation-agent": ["自动化", "批处理", "整理", "执行", "脚本", "workflow", "流程"],
}


def parse_intent(user_goal: str, explicit_type: str | None = None) -> ParsedIntent:
    goal_l = user_goal.lower()
    if explicit_type:
        agent_type = explicit_type
        confidence = "high"
    else:
        scores = {agent_type: 0 for agent_type in KEYWORDS}
        for agent_type, words in KEYWORDS.items():
            for word in words:
                if word.lower() in goal_l:
                    scores[agent_type] += 2 if len(word) > 3 else 1
        agent_type = max(scores, key=scores.get)
        if scores[agent_type] == 0:
            agent_type = "automation-agent"
            confidence = "low"
        else:
            confidence = "high" if scores[agent_type] >= 3 else "medium"

    domain, risk, tools, side_effects = _defaults_for(agent_type, user_goal)
    return ParsedIntent(
        user_goal=user_goal,
        domain=domain,
        likely_agent_type=agent_type,
        risk_level=risk,
        requires_tools=tools,
        possible_side_effects=side_effects,
        confidence=confidence,
    )


def _defaults_for(agent_type: str, goal: str):
    if agent_type == "review-agent":
        side_effects = ["run_tests", "write_patch", "modify_files"]
        if re.search(r"svn", goal, re.I):
            tools = ["read_svn_diff", "read_files", "search_code", "generate_markdown", "ask_user"]
        else:
            tools = ["read_diff", "read_files", "search_code", "generate_markdown", "ask_user"]
        return "code_review", "medium", tools, side_effects
    if agent_type == "writing-agent":
        return "writing", "medium", ["read_notes", "generate_markdown", "ask_user", "store_style_memory"], ["write_draft", "external_publish"]
    if agent_type == "coding-agent":
        return "coding", "high", ["read_files", "write_files", "run_tests", "generate_patch", "ask_user"], ["modify_files", "run_shell", "commit_code"]
    if agent_type == "research-agent":
        return "research", "medium", ["search_web_or_sources", "read_documents", "generate_report", "ask_user"], ["external_api_calls"]
    if agent_type == "monitor-agent":
        return "monitoring", "medium", ["schedule", "read_sources", "summarize", "notify_user"], ["send_notifications"]
    return "automation", "medium_high", ["read_files", "write_files", "run_commands", "ask_user"], ["modify_files", "run_shell"]
