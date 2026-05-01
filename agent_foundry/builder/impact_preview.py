from __future__ import annotations

from typing import Any, Dict, List
from .models import ImpactItem, PreSpecSession


def build_impact_preview(session: PreSpecSession) -> List[ImpactItem]:
    if session.inferred_agent_type == "review-agent":
        items = _review_impact(session)
    elif session.inferred_agent_type == "writing-agent":
        items = _writing_impact(session)
    else:
        items = _generic_impact(session)
    _append_dynamic_question_impacts(session, items)
    return items


def _append_dynamic_question_impacts(session: PreSpecSession, items: List[ImpactItem]) -> None:
    for question in session.metadata.get("llm_dynamic_questions", []):
        qid = question.get("id")
        if not qid or qid not in session.decisions:
            continue
        value = session.decisions[qid].value
        for path in question.get("affects", []):
            if not any(item.path == path and item.value == value for item in items):
                items.append(
                    ImpactItem(
                        path=path,
                        value=value,
                        reason=f"LLM-generated decision: {question.get('title', qid)}",
                        risk_level=question.get("risk_level", "low"),
                    )
                )


def _review_impact(session: PreSpecSession) -> List[ImpactItem]:
    items: List[ImpactItem] = []
    context = session.get_value("context_scope")
    if context:
        if context == "diff_only":
            items.append(ImpactItem("tool_policy.fs.read.scope", "changed_files_only", "只读取 diff 涉及文件。"))
            items.append(ImpactItem("tool_policy.code.search.permission", "deny", "禁止跨项目搜索。"))
        elif context == "same_directory":
            items.append(ImpactItem("tool_policy.fs.read.scope", "same_directory", "允许读取同目录相关文件。"))
            items.append(ImpactItem("tool_policy.code.search.scope", "same_directory", "搜索范围限制在同目录。"))
        elif context == "project_search":
            items.append(ImpactItem("tool_policy.fs.read.scope", "current_project", "允许读取当前项目内相关文件。", "low_to_medium"))
            items.append(ImpactItem("tool_policy.code.search.permission", "allow", "允许搜索相关调用。", "low_to_medium"))
        elif context == "custom":
            scope = session.get_inputs("context_scope").get("context_custom_scope", "custom_scope")
            items.append(ImpactItem("tool_policy.fs.read.scope", scope, "使用用户自定义范围。", "medium"))

    tests = session.get_value("run_tests")
    if tests:
        mapping = {"deny": "deny", "ask": "ask", "allow_whitelist": "allow"}
        items.append(ImpactItem("tool_policy.shell.run_tests.permission", mapping.get(tests, tests), "测试命令权限。", "medium"))
        if tests == "allow_whitelist":
            whitelist = session.get_inputs("run_tests").get("test_command_whitelist", [])
            items.append(ImpactItem("tool_policy.shell.run_tests.allowed_commands", whitelist, "只自动运行白名单命令。", "medium"))
        if tests == "ask":
            items.append(ImpactItem("human_feedback.before_run_tests.mode", "approval", "运行测试前展示审批卡。", "medium"))

    patch = session.get_value("patch_policy")
    if patch:
        if patch == "deny":
            items.append(ImpactItem("tool_policy.fs.write_patch.permission", "deny", "禁止生成 patch 文件。", "low"))
        elif patch == "suggestion_only":
            items.append(ImpactItem("output.artifacts", ["review_report.md", "findings.json", "test_suggestions.md"], "只输出建议，不写 patch。"))
            items.append(ImpactItem("tool_policy.fs.write_patch.permission", "deny", "MVP 不写 patch。"))
        elif patch == "write_patch_ask":
            items.append(ImpactItem("tool_policy.fs.write_patch.permission", "ask", "生成 patch 文件前确认。", "medium_high"))
        elif patch == "modify_workspace_ask":
            items.append(ImpactItem("tool_policy.fs.modify_source.permission", "ask", "修改源码前展示 diff 并确认。", "high"))

    modify = session.get_value("source_modify_policy")
    if modify:
        items.append(ImpactItem("tool_policy.fs.modify_source.permission", {"deny": "deny", "ask": "ask", "allow_sandbox_only": "ask"}.get(modify, modify), "源码修改策略。", "high"))

    feedback = session.get_value("finding_feedback")
    if feedback:
        items.append(ImpactItem("human_feedback.finding_feedback.mode", feedback, "Review 结果反馈方式。"))

    memory = session.get_value("memory_policy")
    if memory:
        requires = memory in ["approved_rule_patch", "auto_low_risk_memory"]
        items.append(ImpactItem("memory.update_policy", memory, "长期记忆更新策略。", "medium"))
        items.append(ImpactItem("rule_patch.requires_approval", requires, "规则更新审批要求。", "medium"))

    output = session.get_value("output_format")
    if output:
        artifacts = {
            "markdown_report": ["review_report.md", "findings.json", "test_suggestions.md", "rule_patch_proposal.md"],
            "markdown_plus_json": ["review_report.md", "findings.json", "test_suggestions.md", "rule_patch_proposal.md"],
            "html_and_markdown": ["review_report.md", "findings.json", "review_report.html", "test_suggestions.md", "rule_patch_proposal.md"],
        }.get(output, ["review_report.md"])
        items.append(ImpactItem("output.artifacts", artifacts, "最终产物。"))

    return items


def _writing_impact(session: PreSpecSession) -> List[ImpactItem]:
    items: List[ImpactItem] = []
    material = session.get_value("material_sources")
    if material:
        items.append(ImpactItem("tools.material_sources", material, "素材读取来源。", "medium"))
        if "markdown_notes" in material:
            notes_path = session.get_inputs("material_sources").get("notes_path", "user_configured_notes_path")
            items.append(ImpactItem("tool_policy.fs.read.scope", notes_path, "读取指定笔记目录。", "medium"))
    publish = session.get_value("publish_policy")
    if publish:
        if publish == "never_publish":
            items.append(ImpactItem("tool_policy.wechat.publish.permission", "deny", "只生成发布包，不发布。", "low"))
        elif publish == "explicit_confirmation":
            items.append(ImpactItem("tool_policy.wechat.publish.permission", "ask", "发布前必须显式确认。", "critical"))
            items.append(ImpactItem("human_feedback.before_publish.required_phrase", "确认发布", "防止误发布。", "critical"))
        elif publish == "draft_to_platform":
            items.append(ImpactItem("tool_policy.wechat.create_draft.permission", "ask", "同步草稿前确认。", "high"))
            items.append(ImpactItem("tool_policy.wechat.publish.permission", "ask", "发布前必须确认。", "critical"))

    output = session.get_value("output_package")
    if output:
        mapping = {
            "article_md": "article.md",
            "title_options": "title_options.md",
            "summary": "summary.md",
            "cover_prompt": "cover_prompt.md",
            "publish_checklist": "publish_checklist.md",
            "html_preview": "article_preview.html",
        }
        artifacts = [mapping[x] for x in output if x in mapping]
        items.append(ImpactItem("output.artifacts", artifacts, "发布包产物。"))

    topic = session.get_value("topic_feedback")
    if topic:
        items.append(ImpactItem("human_feedback.topic_selection.mode", topic, "选题阶段反馈方式。"))
    draft = session.get_value("draft_feedback")
    if draft:
        items.append(ImpactItem("human_feedback.draft_review.mode", draft, "初稿反馈方式。"))
    style_memory = session.get_value("style_memory_policy")
    if style_memory:
        items.append(ImpactItem("memory.style_rules.update_policy", style_memory, "风格规则更新策略。", "medium"))
    return items


def _generic_impact(session: PreSpecSession) -> List[ImpactItem]:
    items = []
    for key, value in session.decisions.items():
        items.append(ImpactItem(f"decisions.{key}", value.value, "用户确认的设计决策。"))
    return items


def impact_preview_as_diff(items: List[ImpactItem]) -> str:
    if not items:
        return "# 暂无影响预览"
    lines = ["# Impact Preview", ""]
    for item in items:
        lines.append(f"+ {item.path}: {item.value!r}")
        if item.reason:
            lines.append(f"  # {item.reason}")
    return "\n".join(lines)


def impact_items_to_mapping(items: List[ImpactItem]) -> Dict[str, Any]:
    return {item.path: item.value for item in items}
