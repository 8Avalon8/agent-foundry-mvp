from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .provider import BaseLLMProvider
from agent_foundry.builder.intent_parser import parse_intent


class MockLLMProvider(BaseLLMProvider):
    """Deterministic local provider for tests and offline demos."""

    name = "mock"

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or "mock-local"

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
        schema_name: str,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        if schema_name == "agent_intent":
            return self._intent(user_prompt)
        if schema_name == "agent_design_brief":
            return self._design_brief(user_prompt)
        if schema_name == "session_decision_patch":
            return self._session_patch(user_prompt)
        if schema_name == "review_dry_run":
            return self._review_dry_run(user_prompt)
        if schema_name == "writing_dry_run":
            return self._writing_dry_run(user_prompt)
        if schema_name == "research_dry_run":
            return self._research_dry_run(user_prompt)
        return _minimal_json_for_schema(schema)

    def _intent(self, prompt: str) -> Dict[str, Any]:
        goal = _extract_after(prompt, "USER_GOAL:") or prompt
        parsed = parse_intent(goal)
        data = parsed.to_dict()
        data["rationale"] = "Mock LLM 根据关键词和任务风险生成结构化意图。"
        return data

    def _design_brief(self, prompt: str) -> Dict[str, Any]:
        goal = _extract_after(prompt, "USER_GOAL:") or prompt
        parsed = parse_intent(goal)
        if parsed.likely_agent_type == "writing-agent":
            return {
                "title": "AI 公众号写作助手",
                "risk_level": "medium",
                "summary": [
                    "把碎片素材整理为选题池",
                    "先生成 3-5 个方向供用户选择，再生成大纲和初稿",
                    "发布动作必须显式确认",
                    "写作风格通过 Style Patch 审批后沉淀",
                ],
                "recommended_preset_id": "continuous_writer",
                "recommended_preset_reason": "用户想持续输出内容，低打扰半自动比纯手动更合适。",
                "dynamic_questions": [
                    {
                        "id": "tone_guardrail",
                        "stage": "feedback_protocol",
                        "title": "文章语气要避免哪些问题？",
                        "input_type": "multi_choice",
                        "recommended": "marketing_tone,empty_grandstanding",
                        "recommendation_reason": "写作型 Agent 很容易变成营销腔，提前设定护栏能减少后续修改。",
                        "risk_level": "low",
                        "options": [
                            {"id": "marketing_tone", "label": "避免营销腔", "tradeoff": "标题会更克制"},
                            {"id": "empty_grandstanding", "label": "避免空泛上价值", "tradeoff": "内容更贴近实践"},
                            {"id": "too_tutorial", "label": "避免过度入门教程", "tradeoff": "更适合程序员读者"},
                        ],
                        "affects": ["style_rules.tone_guardrail", "human_feedback.draft_review"],
                    }
                ],
                "notes": ["Mock 设计简报；真实 LLM 会根据用户上下文生成更贴合的动态问题。"],
            }
        if parsed.likely_agent_type == "review-agent":
            return {
                "title": "SVN Review Agent",
                "risk_level": "medium",
                "summary": [
                    "读取 SVN diff 并结合项目上下文生成分级 Review 报告",
                    "默认不自动修改代码，也不自动 commit",
                    "运行测试、写 patch、更新规则前通过审批卡暂停",
                    "用户对 finding 打标签后，Agent 生成 Rule Patch 候选",
                ],
                "recommended_preset_id": "controlled_semi_auto",
                "recommended_preset_reason": "代码审查需要上下文和一定自动化，但写入和命令执行要保留人工确认。",
                "dynamic_questions": [
                    {
                        "id": "evidence_style",
                        "stage": "feedback_protocol",
                        "title": "Review 报告需要多强的证据要求？",
                        "input_type": "single_choice",
                        "recommended": "line_and_reason",
                        "recommendation_reason": "明确证据要求能降低误报和主观建议。",
                        "risk_level": "low",
                        "options": [
                            {"id": "summary_only", "label": "只要摘要", "tradeoff": "阅读轻，但难复核"},
                            {"id": "line_and_reason", "label": "代码位置 + 原因", "tradeoff": "推荐，兼顾可读和可复核"},
                            {"id": "line_reason_fix", "label": "位置 + 原因 + 修复方向", "tradeoff": "信息最多，但报告更长"},
                        ],
                        "affects": ["output.findings.evidence_style", "eval.actionability"],
                    }
                ],
                "notes": ["Mock 设计简报；真实 LLM 会根据代码库、流程和用户偏好提出更多定制问题。"],
            }
        return {
            "title": parsed.likely_agent_type.replace("-", " ").title(),
            "risk_level": parsed.risk_level,
            "summary": ["根据自然语言目标生成 Agent 草案", "保留权限审批和结构化反馈"],
            "recommended_preset_id": "dry_run_first",
            "recommended_preset_reason": "通用执行任务应先 dry run 再执行。",
            "dynamic_questions": [],
            "notes": [],
        }

    def _session_patch(self, prompt: str) -> Dict[str, Any]:
        instruction = _extract_after(prompt, "USER_INSTRUCTION:") or prompt
        decisions = []
        lowered = instruction.lower()
        if (("不能" in instruction or "不要" in instruction or "禁止" in instruction) and ("写" in instruction or "修改" in instruction or "改文件" in instruction)):
            decisions.append({"question_id": "source_modify_policy", "value_json": json.dumps("deny", ensure_ascii=False), "reason": "用户要求不能/不要写入或修改。"})
            decisions.append({"question_id": "patch_policy", "value_json": json.dumps("suggestion_only", ensure_ascii=False), "reason": "保留建议输出，不直接写入。"})
        if "patch" in lowered and ("确认" in instruction or "问" in instruction):
            decisions.append({"question_id": "patch_policy", "value_json": json.dumps("write_patch_ask", ensure_ascii=False), "reason": "用户允许 patch，但要求确认。"})
        if "读" in instruction or "读取" in instruction:
            decisions.append({"question_id": "context_scope", "value_json": json.dumps("project_search", ensure_ascii=False), "reason": "用户允许读取上下文。"})
        if "测试" in instruction or "test" in lowered:
            decisions.append({"question_id": "run_tests", "value_json": json.dumps("ask", ensure_ascii=False), "reason": "用户提到测试，默认运行前询问。"})
        if "营销" in instruction:
            decisions.append({"question_id": "tone_guardrail", "value_json": json.dumps(["marketing_tone", "empty_grandstanding"], ensure_ascii=False), "reason": "用户强调避免营销腔。"})
        return {"decisions": decisions, "summary": "Mock LLM 已把自然语言补充转成结构化决策。"}

    def _review_dry_run(self, prompt: str) -> Dict[str, Any]:
        return {
            "report_markdown": "# LLM Dry Run Review Report\n\n## Summary\n\n这是由 Mock LLM 生成的 review dry run。它展示了 LLM Provider 接入后的产物形态。\n\n## Findings\n\n### F001 [medium] 示例风险：边界检查可能不足\n\n- 证据：mock 根据 diff 文本生成\n- 建议：补充边界输入测试，并确认上游保证。\n",
            "findings": [
                {
                    "id": "F001",
                    "severity": "medium",
                    "title": "示例风险：边界检查可能不足",
                    "evidence": ["mock evidence from diff"],
                    "recommendation": "补充边界输入测试，并确认上游保证。",
                    "confidence": 0.62,
                    "feedback_options": ["accepted", "false_positive", "too_minor", "duplicate", "needs_more_evidence"],
                }
            ],
            "test_suggestions": ["补充与 diff 分支相关的回归测试。"],
            "rule_patch_markdown": "# Rule Patch Proposal\n\n```diff\n+ Mock: 当边界检查缺失时，要求补充上游保证或测试证据。\n```\n",
        }

    def _writing_dry_run(self, prompt: str) -> Dict[str, Any]:
        return {
            "topic_options": [
                "我为什么想做一个可进化的 Agent Builder",
                "从 SVN Review 到公众号写作：Agent Harness 的复用方式",
                "受控半自动，可能是个人 AI 工作流的正确起点",
            ],
            "outline": ["开头：痛点", "主体：Pre-Spec 决策面板", "主体：权限与反馈", "结尾：如何逐步升级"],
            "article_markdown": "# 受控半自动，可能是个人 AI 工作流的正确起点\n\nMock LLM 生成的文章片段：真正有价值的 Agent 不是一次性帮你完成所有事，而是把你的反馈变成可审查、可积累的规则。\n",
            "publish_package": {
                "summary": "一篇关于 Agent Builder、权限边界和人类反馈机制的实践文章。",
                "cover_prompt": "A clean diagram of a human supervising an evolving AI agent workflow, minimal technical style.",
                "checklist": ["标题不过度营销", "有真实例子", "发布前人工确认"],
            },
            "style_rule_patch_markdown": "# Style Rule Patch Proposal\n\n```diff\n+ 写 Agent 工程文章时，优先用真实工作流问题切入，再抽象成架构原则。\n```\n",
        }

    def _research_dry_run(self, prompt: str) -> Dict[str, Any]:
        return {
            "report_markdown": "# Mock Research Report\n\n## Summary\n\n这是由 Mock LLM 生成的 research dry run。它验证带来源字段的报告、研究计划和反馈请求是否能稳定落盘。\n\n## Source Contract\n\n每条结论都保留 source_url、source_title、retrieved_at、evidence_snippet、source_type、confidence 和 inference_note。\n",
            "research_plan": [
                "确认比较对象和维度。",
                "优先读取官方公开页面和价格入口。",
                "记录证据片段和不确定性。",
            ],
            "sources": [
                {
                    "source_url": "https://example.com/notion",
                    "source_title": "Notion public page placeholder",
                    "retrieved_at": "2026-05-01",
                    "evidence_snippet": "Mock evidence snippet.",
                    "source_type": "official_public_page_placeholder",
                    "confidence": 0.5,
                    "inference_note": "Mock provider does not access live web.",
                }
            ],
            "feedback_requests": [
                {
                    "id": "RQ001",
                    "question": "来源字段是否足够可复核？",
                    "options": ["accepted", "needs_more_evidence", "weak_source"],
                }
            ],
        }


def _extract_after(text: str, marker: str) -> str:
    if marker not in text:
        return ""
    return text.split(marker, 1)[1].strip().split("\n\n", 1)[0].strip()


def _minimal_json_for_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    props = schema.get("properties", {})
    result: Dict[str, Any] = {}
    for key, prop in props.items():
        t = prop.get("type")
        if t == "string":
            result[key] = ""
        elif t == "array":
            result[key] = []
        elif t == "object":
            result[key] = {}
        elif t == "number":
            result[key] = 0
        elif t == "boolean":
            result[key] = False
        else:
            result[key] = None
    return result

# ---- Compatibility for the newer Agent Builder Brain interface ----
def _af_mock_generate_json(self, *, system: str, user: str, schema: Dict[str, Any], schema_name: str) -> Dict[str, Any]:
    if schema_name == "agent_intent":
        return self._intent(user)
    if schema_name == "agent_design_draft":
        goal = _extract_after(user, "USER_GOAL:") or user
        parsed = parse_intent(goal)
        if parsed.likely_agent_type == "review-agent":
            return {
                "agent_title": "SVN Review Agent" if "svn" in goal.lower() else "Review Agent",
                "agent_type": "review-agent",
                "risk_level": "medium",
                "summary_points": [
                    "读取 diff 与相关上下文，生成分级 Review 报告。",
                    "低风险读取自动执行，测试、写入和规则更新前暂停确认。",
                    "用户可以对每条 finding 标记采纳、误报、太小或需要更多证据。",
                    "通过审批后的 Rule Patch 沉淀项目专属审查规则。",
                ],
                "recommended_preset": "controlled_semi_auto",
                "recommendation_message": "建议从受控半自动开始：质量优于只读模式，风险低于沙箱自治。",
                "recommended_decisions": [
                    {"question_id": "context_scope", "value_json": json.dumps("project_search"), "reason": "代码审查通常需要跨文件上下文。"},
                    {"question_id": "run_tests", "value_json": json.dumps("ask"), "reason": "测试有价值但存在副作用。"},
                    {"question_id": "patch_policy", "value_json": json.dumps("suggestion_only"), "reason": "第一版先降低误修风险。"},
                ],
                "additional_questions": [
                    {
                        "id": "review_evidence_style",
                        "title": "Review 报告中的证据粒度应该多细？",
                        "input_type": "single_choice",
                        "stage": "feedback_protocol",
                        "required": False,
                        "recommended_json": json.dumps("file_line_and_reason"),
                        "recommendation_reason": "带文件位置、原因和置信度的证据更利于判断是否采纳。",
                        "risk_level": "low",
                        "help_text": "由 LLM Builder Brain 动态补充的问题。",
                        "placeholder": "",
                        "options": [
                            {"id": "brief", "label": "只给简短结论", "description": "", "recommended": False, "tradeoff": "阅读快，但可验证性低", "requires_input_id": "", "requires_input_type": "", "requires_input_placeholder": "", "risk_level": "low"},
                            {"id": "file_line_and_reason", "label": "文件位置 + 原因 + 建议", "description": "", "recommended": True, "tradeoff": "平衡可读性和可验证性", "requires_input_id": "", "requires_input_type": "", "requires_input_placeholder": "", "risk_level": "low"},
                        ],
                        "affects": ["output.findings.evidence", "human_feedback.finding_feedback"],
                    }
                ],
                "open_issues": ["是否后续接入真实 svn diff 命令", "是否为测试命令建立白名单"],
                "spec_notes": ["LLM 只提出设计建议；权限由 tool_policy 强制执行。"],
            }
        if parsed.likely_agent_type == "writing-agent":
            return {
                "agent_title": "AI 公众号写作助手" if "公众号" in goal else "Writing Agent",
                "agent_type": "writing-agent",
                "risk_level": "medium",
                "summary_points": [
                    "把碎片素材整理成选题、大纲、初稿和发布包。",
                    "选题阶段用选择式反馈，初稿阶段用报告加自由修改。",
                    "发布前必须显式确认，不默认自动发布。",
                    "风格学习通过 Style Patch 审批后沉淀。",
                ],
                "recommended_preset": "continuous_writer",
                "recommendation_message": "建议使用持续写作助手模式：你只做方向选择和关键反馈。",
                "recommended_decisions": [
                    {"question_id": "publish_policy", "value_json": json.dumps("explicit_confirmation"), "reason": "公众号发布是外部副作用，必须显式确认。"},
                    {"question_id": "topic_feedback", "value_json": json.dumps("choice"), "reason": "选题适合低成本选择式反馈。"},
                ],
                "additional_questions": [],
                "open_issues": ["素材来源目录需要后续配置"],
                "spec_notes": ["发布权限默认 ask/deny，不静默发布。"],
            }
        return {"agent_title": parsed.likely_agent_type, "agent_type": parsed.likely_agent_type, "risk_level": "medium", "summary_points": ["根据用户目标生成 Agent 蓝图。"], "recommended_preset": "", "recommendation_message": "", "recommended_decisions": [], "additional_questions": [], "open_issues": [], "spec_notes": []}
    if schema_name == "decision_patch":
        instruction = user.lower()
        updates = []
        warnings = []
        if any(x in instruction for x in ["不能写", "不要写", "不写文件", "don't write", "no write"]):
            updates.append({"question_id": "source_modify_policy", "value_json": json.dumps("deny"), "reason": "用户要求不要自动写文件。"})
            updates.append({"question_id": "patch_policy", "value_json": json.dumps("suggestion_only"), "reason": "用户禁止写文件时，patch 退化为建议。"})
        if any(x in instruction for x in ["可以读", "允许读", "read files"]):
            updates.append({"question_id": "context_scope", "value_json": json.dumps("project_search"), "reason": "用户允许读取项目上下文。"})
        if any(x in instruction for x in ["生成 patch", "可以 patch", "patch 但", "patch but"]):
            updates.append({"question_id": "patch_policy", "value_json": json.dumps("write_patch_ask"), "reason": "用户希望允许 patch，但仍应确认。"})
        if any(x in instruction for x in ["测试", "test"]):
            updates.append({"question_id": "run_tests", "value_json": json.dumps("ask"), "reason": "测试命令先采用 ask 权限。"})
        if not updates:
            warnings.append("Mock provider did not infer a structured decision from this note.")
        return {"summary": "已将自然语言补充转换为候选决策更新。", "decision_updates": updates, "additional_questions": [], "warnings": warnings}
    return self.complete_json(system_prompt=system, user_prompt=user, schema=schema, schema_name=schema_name)

MockLLMProvider.generate_json = _af_mock_generate_json
