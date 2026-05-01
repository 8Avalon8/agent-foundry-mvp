from __future__ import annotations

from typing import Dict, List
from .models import PresetProfile


PRESETS: Dict[str, List[PresetProfile]] = {
    "review-agent": [
        PresetProfile(
            id="readonly_safe",
            title="保守只读",
            description="适合第一次试用：只读 diff，不运行命令，不生成 patch。",
            summary=[
                "只读取 diff 或用户提供的上下文",
                "不运行测试命令",
                "不写入文件",
                "输出 Markdown Review 报告",
            ],
            decisions={
                "autonomy_level": "L1",
                "context_scope": "diff_only",
                "run_tests": "deny",
                "patch_policy": "suggestion_only",
                "source_modify_policy": "deny",
                "output_format": "markdown_report",
                "finding_feedback": "inline_labels",
                "memory_policy": "approved_rule_patch",
            },
            risk_level="low",
        ),
        PresetProfile(
            id="controlled_semi_auto",
            title="受控半自动",
            description="推荐：自动分析低风险信息，测试/写入等关键动作前确认。",
            recommended=True,
            summary=[
                "自动读取 diff 和相关源码",
                "允许运行测试，但每次运行前询问",
                "默认不直接修改代码，只生成建议",
                "输出结构化 Review 报告",
                "用户可对每条 finding 标记采纳/误报/太小",
            ],
            decisions={
                "autonomy_level": "L2",
                "context_scope": "project_search",
                "run_tests": "ask",
                "patch_policy": "suggestion_only",
                "source_modify_policy": "ask",
                "output_format": "markdown_report",
                "finding_feedback": "inline_labels",
                "memory_policy": "approved_rule_patch",
            },
            risk_level="medium",
        ),
        PresetProfile(
            id="efficient_whitelist",
            title="高效率白名单",
            description="适合已有稳定测试命令的项目：自动运行白名单测试，其它动作确认。",
            summary=[
                "自动读取项目上下文",
                "自动运行白名单测试命令",
                "可生成 patch 文件，但写入前确认",
                "规则更新仍需审批",
            ],
            decisions={
                "autonomy_level": "L2",
                "context_scope": "project_search",
                "run_tests": "allow_whitelist",
                "patch_policy": "write_patch_ask",
                "source_modify_policy": "ask",
                "output_format": "markdown_plus_json",
                "finding_feedback": "inline_labels",
                "memory_policy": "approved_rule_patch",
            },
            risk_level="medium_high",
        ),
        PresetProfile(
            id="sandbox_auto",
            title="沙箱自治",
            description="适合隔离环境：在沙箱中自动运行测试和生成 patch，高风险动作前确认。",
            summary=[
                "在沙箱里自动运行多步分析",
                "自动生成 patch 草案",
                "提交代码和外部动作依然禁止",
                "适合后续成熟阶段，不建议第一版直接使用",
            ],
            decisions={
                "autonomy_level": "L3",
                "context_scope": "project_search",
                "run_tests": "allow_whitelist",
                "patch_policy": "write_patch_ask",
                "source_modify_policy": "ask",
                "output_format": "html_and_markdown",
                "finding_feedback": "inline_labels",
                "memory_policy": "approved_rule_patch",
            },
            risk_level="high",
        ),
    ],
    "writing-agent": [
        PresetProfile(
            id="pure_writer",
            title="纯写作助手",
            description="只在用户召唤时工作，根据输入素材生成文章。",
            summary=["手动输入素材", "生成选题/大纲/初稿", "不主动提醒", "不发布"],
            decisions={
                "autonomy_level": "L1",
                "writing_focus": ["ai_usage", "personal_practice"],
                "material_sources": ["manual_input"],
                "initiative_level": "on_demand",
                "publish_policy": "never_publish",
                "output_package": ["article_md", "title_options", "summary"],
                "topic_feedback": "choice",
                "draft_feedback": "report_plus_chat",
                "style_memory_policy": "approved_style_patch",
            },
            risk_level="low",
        ),
        PresetProfile(
            id="continuous_writer",
            title="持续写作助手",
            description="推荐：收集素材、聚类选题、生成初稿和发布包，发布前确认。",
            recommended=True,
            summary=[
                "支持碎片素材积累",
                "生成 3-5 个选题让用户选择",
                "生成大纲、初稿和发布包",
                "风格规则更新需审批",
            ],
            decisions={
                "autonomy_level": "L2",
                "writing_focus": ["engineering_thinking", "ai_usage", "personal_practice"],
                "material_sources": ["manual_input", "markdown_notes"],
                "initiative_level": "weekly_suggestion",
                "publish_policy": "explicit_confirmation",
                "output_package": ["article_md", "title_options", "summary", "cover_prompt", "publish_checklist"],
                "topic_feedback": "choice",
                "draft_feedback": "report_plus_chat",
                "style_memory_policy": "approved_style_patch",
            },
            risk_level="medium",
        ),
        PresetProfile(
            id="operation_planner",
            title="运营规划助手",
            description="偏长期运营：维护选题池、节奏和发布计划。",
            summary=["维护选题池", "制定发文计划", "定期提醒", "仍不自动发布"],
            decisions={
                "autonomy_level": "L2",
                "writing_focus": ["engineering_thinking", "ai_usage"],
                "material_sources": ["manual_input", "markdown_notes", "web_links"],
                "initiative_level": "topic_pool_threshold",
                "publish_policy": "explicit_confirmation",
                "output_package": ["article_md", "title_options", "summary", "cover_prompt", "publish_checklist", "html_preview"],
                "topic_feedback": "choice",
                "draft_feedback": "structured_comment",
                "style_memory_policy": "approved_style_patch",
            },
            risk_level="medium",
        ),
    ],
    "coding-agent": [
        PresetProfile(
            id="plan_only",
            title="计划模式",
            description="只分析和制定计划，不改文件。",
            recommended=True,
            summary=["读取代码", "输出计划", "不修改文件", "适合高风险仓库"],
            decisions={"autonomy_level": "L1", "source_modify_policy": "deny", "run_tests": "ask"},
            risk_level="low",
        ),
        PresetProfile(
            id="patch_suggestion",
            title="Patch 建议模式",
            description="生成 patch 草案，但应用前确认。",
            summary=["读取代码", "生成 patch", "写入前确认"],
            decisions={"autonomy_level": "L2", "source_modify_policy": "ask", "run_tests": "ask"},
            risk_level="medium",
        ),
    ],
    "research-agent": [
        PresetProfile(
            id="cited_report",
            title="引用报告模式",
            description="制定研究计划、收集资料、输出带来源的报告。",
            recommended=True,
            summary=["先列研究计划", "阶段性报告", "输出引用和不确定性"],
            decisions={"autonomy_level": "L2", "output_format": "markdown_report"},
            risk_level="medium",
        )
    ],
    "automation-agent": [
        PresetProfile(
            id="dry_run_first",
            title="先 dry-run 再执行",
            description="执行型任务先展示计划和变更，再请求确认。",
            recommended=True,
            summary=["先计划", "展示影响", "确认后执行", "输出日志"],
            decisions={"autonomy_level": "L2", "source_modify_policy": "ask"},
            risk_level="medium_high",
        )
    ],
    "monitor-agent": [
        PresetProfile(
            id="low_interrupt_monitor",
            title="低打扰监控",
            description="定时扫描，只在达到阈值时提醒。",
            recommended=True,
            summary=["定时扫描", "阈值提醒", "摘要报告", "用户反馈调整阈值"],
            decisions={"autonomy_level": "L2", "initiative_level": "threshold_based"},
            risk_level="medium",
        )
    ],
}


def get_presets(agent_type: str) -> List[PresetProfile]:
    return PRESETS.get(agent_type, PRESETS["automation-agent"])


def get_recommended_preset(agent_type: str) -> PresetProfile:
    presets = get_presets(agent_type)
    for preset in presets:
        if preset.recommended:
            return preset
    return presets[0]


def find_preset(agent_type: str, preset_id: str) -> PresetProfile:
    for preset in get_presets(agent_type):
        if preset.id == preset_id:
            return preset
    raise KeyError(f"Unknown preset '{preset_id}' for agent type '{agent_type}'")
