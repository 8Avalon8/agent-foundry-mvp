from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import yaml


def dump_yaml(data: Dict[str, Any]) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, indent=2)


def generate_agent_files(
    agent_spec: Dict[str, Any],
    output_root: Path,
    prespec_session: Dict[str, Any] | None = None,
    design_card_markdown: str | None = None,
) -> Path:
    agent_name = agent_spec["agent"]["name"]
    agent_dir = output_root / "agents" / agent_name
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "examples").mkdir(exist_ok=True)
    (agent_dir / "logs").mkdir(exist_ok=True)
    (agent_dir / "runs").mkdir(exist_ok=True)

    (agent_dir / "agent.yaml").write_text(dump_yaml(agent_spec), encoding="utf-8")
    (agent_dir / "tool_policy.yaml").write_text(dump_yaml(agent_spec.get("tool_policy", {})), encoding="utf-8")
    (agent_dir / "human_feedback.yaml").write_text(dump_yaml(agent_spec.get("human_feedback", {})), encoding="utf-8")
    (agent_dir / "memory_policy.yaml").write_text(dump_yaml(agent_spec.get("memory", {})), encoding="utf-8")
    (agent_dir / "eval_rubric.yaml").write_text(dump_yaml(agent_spec.get("eval", {})), encoding="utf-8")
    (agent_dir / "output_schema.json").write_text(json.dumps(_output_schema(agent_spec), ensure_ascii=False, indent=2), encoding="utf-8")
    (agent_dir / "system_prompt.md").write_text(_system_prompt(agent_spec), encoding="utf-8")
    (agent_dir / "runbook.md").write_text(_runbook(agent_spec), encoding="utf-8")
    (agent_dir / "prespec_session.json").write_text(
        json.dumps(prespec_session or {"source": agent_spec.get("source", {})}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (agent_dir / "agent_design_card.md").write_text(design_card_markdown or _design_card_placeholder(agent_spec), encoding="utf-8")

    if agent_spec["agent"]["type"] == "review-agent":
        (agent_dir / "learned_rules.md").write_text(_initial_review_rules(agent_spec), encoding="utf-8")
        (agent_dir / "examples" / "sample_input.diff").write_text(_sample_diff(), encoding="utf-8")
        (agent_dir / "examples" / "sample_review_report.md").write_text(_sample_review_report(), encoding="utf-8")
    elif agent_spec["agent"]["type"] == "writing-agent":
        (agent_dir / "style_rules.md").write_text(_initial_style_rules(agent_spec), encoding="utf-8")
        (agent_dir / "examples" / "sample_material.txt").write_text("今天发现 AI 做 code review 最有价值的不是找 bug，而是逼我显式化规则。\n", encoding="utf-8")
        (agent_dir / "examples" / "sample_publish_package.md").write_text(_sample_publish_package(), encoding="utf-8")
    else:
        (agent_dir / "examples" / "sample_input.txt").write_text(agent_spec.get("source", {}).get("user_goal", "sample task"), encoding="utf-8")

    return agent_dir


def _system_prompt(spec: Dict[str, Any]) -> str:
    agent = spec["agent"]
    lines = [
        f"# System Prompt: {agent['name']}",
        "",
        f"你是 `{agent['name']}`，类型为 `{agent['type']}`。",
        "",
        "## 目标",
        "",
        spec.get("goal", {}).get("primary", "完成用户指定任务。"),
        "",
        "## 工作原则",
        "",
        "1. 先完成低风险、可逆、只读的动作。",
        "2. 遇到写文件、运行命令、发布、提交、修改长期规则等动作时，必须遵守 tool_policy。",
        "3. 所有重要结论都应给出证据、置信度和下一步建议。",
        "4. 不静默改变长期记忆；只提出可审查的 Rule Patch / Style Patch。",
        "5. 当不确定性较高时，优先给出推荐方案并请求用户确认。",
        "",
        "## 自治边界",
        "",
        f"- 自治等级：`{spec.get('autonomy', {}).get('level', 'L2')}`",
        f"- 默认行为：`{spec.get('autonomy', {}).get('default_behavior', 'auto_low_risk_ask_high_risk')}`",
        "",
        "## 工具策略摘要",
        "",
    ]
    for tool, policy in spec.get("tool_policy", {}).items():
        lines.append(f"- `{tool}`: permission=`{policy.get('permission')}`, risk=`{policy.get('risk', '')}`")
    lines.extend(
        [
            "",
            "## 权限和反馈边界",
            "",
            "- `allow` 只能用于低风险或用户明确确认过的自动动作。",
            "- `ask` 必须暂停并生成审批请求，不能自行继续执行。",
            "- `deny` 必须直接拒绝并说明原因。",
            "- Rule Patch / Style Patch 只能作为候选补丁，等待用户审批。",
            "",
            "## 反馈规则",
            "",
        ]
    )
    for key, value in spec.get("human_feedback", {}).items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## 输出要求", ""])
    for artifact in spec.get("output", {}).get("artifacts", []):
        lines.append(f"- {artifact}")
    return "\n".join(lines) + "\n"


def _runbook(spec: Dict[str, Any]) -> str:
    t = spec["agent"]["type"]
    if t == "review-agent":
        steps = [
            "收集输入：SVN diff、相关源码、项目规则、历史反馈。",
            "根据 tool_policy 决定上下文读取范围。",
            "从变更中提取风险点：逻辑、空值、边界、回归、测试影响、可维护性。",
            "为每条 finding 提供位置、证据、风险等级、置信度和建议。",
            "生成 review_report.md、findings.json、test_suggestions.md。",
            "用户对 finding 打标签：accepted / false_positive / too_minor / duplicate / needs_more_evidence。",
            "根据反馈提出 rule_patch_proposal.md，等待审批后写入 learned_rules.md。",
        ]
    elif t == "writing-agent":
        steps = [
            "收集素材：手动输入、指定笔记、链接或摘要。",
            "聚类素材，生成 3-5 个选题方向。",
            "等待用户选择或调整方向。",
            "生成大纲，并标注文章意图、读者收益和示例。",
            "写初稿，并自检是否空泛、营销腔或缺少真实实践。",
            "根据反馈修改，生成发布包。",
            "提出 style_rule_patch.md，等待审批后写入 style_rules.md。",
        ]
    else:
        steps = ["理解用户任务", "生成计划", "执行低风险步骤", "关键动作前确认", "输出结果和反馈请求"]
    lines = [f"# Runbook: {spec['agent']['name']}", "", "## 标准流程", ""]
    lines.extend([f"{i}. {s}" for i, s in enumerate(steps, start=1)])
    lines.extend(["", "## 暂停点", ""])
    for tool, policy in spec.get("tool_policy", {}).items():
        if policy.get("permission") == "ask":
            lines.append(f"- `{tool}`: 暂停并请求审批，风险 `{policy.get('risk')}`。")
        elif policy.get("permission") == "deny":
            lines.append(f"- `{tool}`: 禁止执行，风险 `{policy.get('risk')}`。")
    lines.extend(["", "## 人类检查点", ""])
    for key, value in spec.get("human_feedback", {}).items():
        lines.append(f"- `{key}`: {value}")
    return "\n".join(lines) + "\n"


def _design_card_placeholder(spec: Dict[str, Any]) -> str:
    source = spec.get("source", {})
    return "\n".join(
        [
            f"# Agent Design Card: {spec['agent']['name']}",
            "",
            "## 已确认",
            "",
            f"- Agent 类型：{spec['agent']['type']}",
            f"- 用户目标：{source.get('user_goal', '')}",
            "",
            "## 待确认",
            "",
            "- 运行时使用前请复核 tool_policy、human_feedback 和 memory_policy。",
            "",
        ]
    )


def _output_schema(spec: Dict[str, Any]) -> Dict[str, Any]:
    if spec["agent"]["type"] == "review-agent":
        return {
            "type": "object",
            "required": ["summary", "findings", "test_suggestions"],
            "properties": {
                "summary": {"type": "string"},
                "findings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "severity", "title", "evidence", "recommendation", "confidence"],
                        "properties": {
                            "id": {"type": "string"},
                            "severity": {"enum": ["high", "medium", "low"]},
                            "title": {"type": "string"},
                            "evidence": {"type": "array", "items": {"type": "string"}},
                            "recommendation": {"type": "string"},
                            "confidence": {"type": "number"},
                        },
                    },
                },
                "test_suggestions": {"type": "array", "items": {"type": "string"}},
            },
        }
    if spec["agent"]["type"] == "writing-agent":
        return {
            "type": "object",
            "required": ["topics", "outline", "draft", "publish_package"],
            "properties": {
                "topics": {"type": "array", "items": {"type": "string"}},
                "outline": {"type": "array", "items": {"type": "string"}},
                "draft": {"type": "string"},
                "publish_package": {"type": "object"},
            },
        }
    return {"type": "object"}


def _initial_review_rules(spec: Dict[str, Any]) -> str:
    return """# Learned Rules

这个文件保存经过用户审批后合并的项目审查规则。

## 默认规则

- 只有当建议具备明确证据和可执行改进方向时，才作为 finding 输出。
- 风格问题默认降级，除非它影响业务理解、接口误用风险或维护成本。
- 每次新增规则必须通过 rule_patch_proposal.md 审批。
"""


def _initial_style_rules(spec: Dict[str, Any]) -> str:
    return """# Style Rules

这个文件保存经过用户审批后合并的写作风格规则。

## 默认规则

- 避免营销腔和夸张标题。
- 优先使用真实实践案例，而不是空泛观点。
- 允许保留适度不确定性，体现工程思考过程。
- 每次新增风格规则必须通过 style_rule_patch.md 审批。
"""


def _sample_diff() -> str:
    return """Index: src/UserProfileService.java
===================================================================
--- src/UserProfileService.java    (revision 123)
+++ src/UserProfileService.java    (working copy)
@@ -10,10 +10,12 @@
 public class UserProfileService {
     public String displayName(User user) {
-        if (user == null) {
-            return "Guest";
-        }
+        // assume user always exists
         return user.getName().trim();
     }
 
     public void update(Request request) {
-        validate(request);
+        // validation removed for performance
         repository.save(request);
     }
 }
"""


def _sample_review_report() -> str:
    return """# Sample Review Report

## Summary

本次变更移除了空值保护和请求校验，存在中高风险。

## Findings

- F001 高风险：`displayName` 移除了 `user == null` 保护，但仍直接调用 `user.getName().trim()`。
- F002 中风险：`update` 移除了 `validate(request)`，可能导致非法请求落库。
"""


def _sample_publish_package() -> str:
    return """# Sample Publish Package

## 标题备选

1. 我开始把 AI 当成 Code Reviewer，而不是搜索引擎
2. AI Review 真正有价值的地方：逼我显式化规则
3. 一个程序员如何训练更懂项目的 AI 助手

## 大纲

1. 为什么 AI Review 不只是找 bug
2. 它如何暴露隐性工程规则
3. 如何把反馈沉淀成下一次更好的审查
"""
