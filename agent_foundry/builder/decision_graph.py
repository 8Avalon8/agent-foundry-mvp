from __future__ import annotations

from typing import Dict, List, Optional
from .models import AgentSummary, DecisionOption, DecisionQuestion, DecisionStage
from .presets import get_presets


STAGE_ORDER = [
    "foundation",
    "autonomy",
    "tool_permissions",
    "feedback_protocol",
    "memory_policy",
    "output_and_dry_run",
]


def get_stage_order(agent_type: str) -> List[str]:
    return STAGE_ORDER


def next_stage(current_stage: str) -> Optional[str]:
    try:
        idx = STAGE_ORDER.index(current_stage)
    except ValueError:
        return STAGE_ORDER[0]
    if idx + 1 < len(STAGE_ORDER):
        return STAGE_ORDER[idx + 1]
    return None


def previous_stage(current_stage: str) -> Optional[str]:
    try:
        idx = STAGE_ORDER.index(current_stage)
    except ValueError:
        return None
    if idx > 0:
        return STAGE_ORDER[idx - 1]
    return None


def get_agent_summary(agent_type: str, user_goal: str) -> AgentSummary:
    if agent_type == "review-agent":
        title = "SVN Review Agent" if "svn" in user_goal.lower() else "Review Agent"
        return AgentSummary(
            title=title,
            agent_type=agent_type,
            risk_level="medium",
            summary=[
                "读取 diff / 审查对象",
                "结合上下文生成分级 Review 报告",
                "支持用户对每条 finding 标记采纳、误报或太小",
                "通过审批后的 Rule Patch 沉淀项目规则",
            ],
        )
    if agent_type == "writing-agent":
        title = "AI 公众号写作助手" if "公众号" in user_goal else "Writing Agent"
        return AgentSummary(
            title=title,
            agent_type=agent_type,
            risk_level="medium",
            summary=[
                "收集碎片素材并聚类成选题",
                "生成选题、大纲、初稿和发布包",
                "发布前必须显式确认",
                "通过审批后的 Style Patch 学习写作风格",
            ],
        )
    return AgentSummary(
        title=agent_type.replace("-", " ").title(),
        agent_type=agent_type,
        risk_level="medium",
        summary=["从自然语言需求生成 Agent 蓝图", "通过 Pre-Spec 决策面板确认关键设计"],
    )


def get_questions(agent_type: str, stage: str) -> List[DecisionQuestion]:
    if agent_type == "review-agent":
        return _review_questions(stage)
    if agent_type == "writing-agent":
        return _writing_questions(stage)
    return _generic_questions(stage)


def get_stages(agent_type: str) -> List[DecisionStage]:
    return [
        DecisionStage(
            id=stage_id,
            title=_stage_title(stage_id),
            description=_stage_description(stage_id),
            questions=get_questions(agent_type, stage_id),
        )
        for stage_id in STAGE_ORDER
    ]


def _stage_title(stage_id: str) -> str:
    return {
        "foundation": "基础目标确认",
        "autonomy": "自治程度确认",
        "tool_permissions": "工具与权限确认",
        "feedback_protocol": "人类反馈机制确认",
        "memory_policy": "记忆与进化机制确认",
        "output_and_dry_run": "输出格式与 Dry Run",
    }[stage_id]


def _stage_description(stage_id: str) -> str:
    return {
        "foundation": "确认 Agent 是什么、服务什么目标、主要输入输出是什么。",
        "autonomy": "确认 Agent 可以自动推进到什么程度，以及什么时候必须暂停问人。",
        "tool_permissions": "确认工具权限的 allow / ask / deny 边界。",
        "feedback_protocol": "确认 Agent 用选择、报告、diff、标签还是对话来接收反馈。",
        "memory_policy": "确认哪些反馈可以沉淀，哪些规则更新必须审批。",
        "output_and_dry_run": "确认输出产物，并在生成正式工程前模拟一次运行。",
    }[stage_id]


def _review_questions(stage: str) -> List[DecisionQuestion]:
    if stage == "foundation":
        return [
            DecisionQuestion(
                id="review_focus",
                title="Review 重点是什么？",
                input_type="multi_choice",
                stage=stage,
                recommended=["bug_risk", "maintainability", "test_impact"],
                recommendation_reason="初期建议优先关注可执行的问题：潜在 bug、可维护性风险和测试影响。",
                options=[
                    DecisionOption("bug_risk", "潜在 bug / 逻辑风险", recommended=True),
                    DecisionOption("maintainability", "可维护性和架构风险", recommended=True),
                    DecisionOption("test_impact", "测试影响和回归风险", recommended=True),
                    DecisionOption("style", "风格和命名问题"),
                    DecisionOption("security", "安全风险"),
                ],
                affects=["runbook.review_scope", "eval.metrics"],
            ),
            DecisionQuestion(
                id="lifecycle",
                title="这个 Agent 是按需运行，还是长期监控？",
                input_type="single_choice",
                stage=stage,
                recommended="on_demand",
                recommendation_reason="SVN Review 第一版更适合按需运行，方便你观察误报率和权限边界。",
                options=[
                    DecisionOption("on_demand", "按需运行", recommended=True),
                    DecisionOption("scheduled", "定时扫描"),
                    DecisionOption("triggered_by_diff", "检测到 diff 后触发"),
                ],
                affects=["lifecycle.mode", "trigger"],
            ),
        ]
    if stage == "autonomy":
        return [
            DecisionQuestion(
                id="autonomy_level",
                title="自治程度应该设为哪一档？",
                input_type="single_choice",
                stage=stage,
                recommended="L2",
                recommendation_reason="受控半自动能自动做低风险分析，但遇到测试、写入和规则更新时暂停确认。",
                options=[
                    DecisionOption("L0", "L0 手动辅助：只回答问题"),
                    DecisionOption("L1", "L1 草稿自动：自动生成报告，不执行动作"),
                    DecisionOption("L2", "L2 受控半自动：低风险自动，高风险询问", recommended=True),
                    DecisionOption("L3", "L3 沙箱自治：沙箱中可多步执行，高风险询问"),
                    DecisionOption("L4", "L4 高自治：长期主动行动，不建议 MVP"),
                ],
                affects=["autonomy.level", "interruption_policy"],
                risk_level="medium",
            ),
            DecisionQuestion(
                id="max_iterations_without_user",
                title="Agent 最多连续自循环几轮后必须汇报？",
                input_type="single_choice",
                stage=stage,
                recommended="3",
                recommendation_reason="3 轮足够完成读取、分析、自检，同时避免长时间无反馈。",
                options=[
                    DecisionOption("1", "1 轮：非常保守"),
                    DecisionOption("3", "3 轮：推荐", recommended=True),
                    DecisionOption("5", "5 轮：更高自治"),
                ],
                affects=["autonomy.max_iterations_without_user"],
            ),
        ]
    if stage == "tool_permissions":
        return [
            DecisionQuestion(
                id="context_scope",
                title="Agent 可以读取多大范围的上下文？",
                input_type="single_choice",
                stage=stage,
                recommended="project_search",
                recommendation_reason="代码审查通常需要跨文件理解调用关系；限制在当前项目内可以兼顾质量和边界。",
                options=[
                    DecisionOption("diff_only", "只读取 diff 文件", tradeoff="最安全，但容易缺上下文"),
                    DecisionOption("same_directory", "读取同目录相关文件", tradeoff="适合小改动"),
                    DecisionOption("project_search", "允许在当前项目内搜索相关调用", recommended=True, tradeoff="审查质量更高，但读取范围更大"),
                    DecisionOption("custom", "自定义范围", requires_input={"id": "context_custom_scope", "type": "path_input", "placeholder": "例如：src/gameplay/**, config/**/*.json"}),
                ],
                affects=["tool_policy.fs.read.scope", "tool_policy.code.search"],
                risk_level="low_to_medium",
            ),
            DecisionQuestion(
                id="run_tests",
                title="是否允许运行测试命令？",
                input_type="single_choice",
                stage=stage,
                recommended="ask",
                recommendation_reason="测试能提高 review 可信度，但命令执行存在成本和副作用，初期建议每次询问。",
                options=[
                    DecisionOption("deny", "不运行测试", tradeoff="最安全，但可信度较低"),
                    DecisionOption("ask", "每次运行前询问", recommended=True, tradeoff="安全和质量比较平衡"),
                    DecisionOption("allow_whitelist", "自动运行白名单命令", tradeoff="效率更高，但需要维护白名单", requires_input={"id": "test_command_whitelist", "type": "text_input", "placeholder": "例如：npm test, pytest tests/unit"}),
                ],
                affects=["tool_policy.shell.run_tests", "human_feedback.before_run_tests"],
                risk_level="medium",
            ),
            DecisionQuestion(
                id="patch_policy",
                title="是否允许生成 patch？",
                input_type="single_choice",
                stage=stage,
                recommended="suggestion_only",
                recommendation_reason="第一版先生成修复建议，不直接写入 patch，可以降低误修风险。",
                options=[
                    DecisionOption("deny", "不生成 patch，只做 review"),
                    DecisionOption("suggestion_only", "只生成修复建议", recommended=True),
                    DecisionOption("write_patch_ask", "可以生成 patch 文件，但写入前确认"),
                    DecisionOption("modify_workspace_ask", "可以修改工作区文件，但必须确认"),
                ],
                affects=["tool_policy.fs.write_patch", "tool_policy.fs.modify_source"],
                risk_level="medium_high",
            ),
            DecisionQuestion(
                id="source_modify_policy",
                title="是否允许直接修改源码？",
                input_type="single_choice",
                stage=stage,
                recommended="ask",
                recommendation_reason="即使生成 patch，也应该保留源码修改审批点。",
                options=[
                    DecisionOption("deny", "禁止修改源码"),
                    DecisionOption("ask", "修改前展示 diff 并询问", recommended=True),
                    DecisionOption("allow_sandbox_only", "只允许在沙箱中修改"),
                ],
                affects=["tool_policy.fs.modify_source"],
                risk_level="high",
            ),
        ]
    if stage == "feedback_protocol":
        return [
            DecisionQuestion(
                id="finding_feedback",
                title="Review 结果应该如何收集反馈？",
                input_type="single_choice",
                stage=stage,
                recommended="inline_labels",
                recommendation_reason="逐条 finding 打标签最适合沉淀误报和采纳规则。",
                options=[
                    DecisionOption("inline_labels", "逐条标签：采纳 / 误报 / 太小 / 重复 / 需要证据", recommended=True),
                    DecisionOption("free_chat", "自由对话反馈"),
                    DecisionOption("report_comment", "整份报告批注"),
                ],
                affects=["human_feedback.finding_feedback"],
            ),
            DecisionQuestion(
                id="approval_style",
                title="敏感动作审批时应该怎么展示？",
                input_type="single_choice",
                stage=stage,
                recommended="risk_card_with_reason",
                recommendation_reason="审批卡应展示动作、风险、原因和影响，避免用户盲批。",
                options=[
                    DecisionOption("minimal", "只显示动作和同意/拒绝"),
                    DecisionOption("risk_card_with_reason", "显示风险卡、推荐理由和影响", recommended=True),
                    DecisionOption("diff_first", "优先展示 diff，再审批"),
                ],
                affects=["human_feedback.before_sensitive_action"],
            ),
        ]
    if stage == "memory_policy":
        return [
            DecisionQuestion(
                id="memory_policy",
                title="Agent 如何沉淀经验？",
                input_type="single_choice",
                stage=stage,
                recommended="approved_rule_patch",
                recommendation_reason="让 Agent 提出规则补丁、由你确认后合并，既能进化又不失控。",
                options=[
                    DecisionOption("no_long_term", "不使用长期记忆"),
                    DecisionOption("approved_rule_patch", "生成 Rule Patch，经审批后写入", recommended=True),
                    DecisionOption("auto_low_risk_memory", "低风险规则自动写入，高风险审批"),
                ],
                affects=["memory.update_policy", "rule_patch.requires_approval"],
                risk_level="medium",
            ),
            DecisionQuestion(
                id="memory_scope",
                title="哪些内容允许进入长期记忆？",
                input_type="multi_choice",
                stage=stage,
                recommended=["accepted_patterns", "false_positive_patterns", "project_rules"],
                recommendation_reason="Review Agent 最有价值的长期记忆是采纳模式、误报模式和项目规则。",
                options=[
                    DecisionOption("accepted_patterns", "被采纳的问题模式", recommended=True),
                    DecisionOption("false_positive_patterns", "重复误报模式", recommended=True),
                    DecisionOption("project_rules", "项目专属审查规则", recommended=True),
                    DecisionOption("user_global_preferences", "用户全局偏好"),
                ],
                affects=["memory.long_term_candidates"],
            ),
        ]
    if stage == "output_and_dry_run":
        return [
            DecisionQuestion(
                id="output_format",
                title="最终输出形式是什么？",
                input_type="single_choice",
                stage=stage,
                recommended="markdown_report",
                recommendation_reason="Markdown 报告最容易落地，也方便后续接 HTML / JSON。",
                options=[
                    DecisionOption("markdown_report", "Markdown Review 报告", recommended=True),
                    DecisionOption("markdown_plus_json", "Markdown + findings.json"),
                    DecisionOption("html_and_markdown", "HTML 交互报告 + Markdown"),
                ],
                affects=["output.artifacts"],
            ),
            DecisionQuestion(
                id="dry_run_enabled",
                title="生成 AgentSpec 前是否先跑 dry run？",
                input_type="single_choice",
                stage=stage,
                recommended="yes",
                recommendation_reason="Dry run 能在正式生成前暴露输出格式和反馈流程是否符合预期。",
                options=[
                    DecisionOption("yes", "是，使用示例 diff 模拟", recommended=True),
                    DecisionOption("no", "否，直接生成"),
                ],
                affects=["dry_run.enabled"],
            ),
        ]
    return []


def _writing_questions(stage: str) -> List[DecisionQuestion]:
    if stage == "foundation":
        return [
            DecisionQuestion(
                id="writing_focus",
                title="文章主要偏向哪些方向？",
                input_type="multi_choice",
                stage=stage,
                recommended=["engineering_thinking", "ai_usage", "personal_practice"],
                recommendation_reason="你的目标是分享 AI 技巧和心得，工程化思考 + 实践案例会更有辨识度。",
                options=[
                    DecisionOption("engineering_thinking", "工程化思考", recommended=True),
                    DecisionOption("ai_usage", "AI 使用技巧", recommended=True),
                    DecisionOption("personal_practice", "个人实践心得", recommended=True),
                    DecisionOption("beginner_tutorial", "入门教程"),
                    DecisionOption("hot_topic_commentary", "热点评论"),
                ],
                affects=["runbook.topic_strategy", "style_rules"],
            ),
            DecisionQuestion(
                id="lifecycle",
                title="它是按需写作，还是持续运营助手？",
                input_type="single_choice",
                stage=stage,
                recommended="continuous",
                recommendation_reason="你希望降低持续发文成本，因此建议作为持续写作助手。",
                options=[
                    DecisionOption("on_demand", "按需召唤"),
                    DecisionOption("continuous", "持续写作助手", recommended=True),
                    DecisionOption("operation_planner", "选题池 + 发文计划"),
                ],
                affects=["lifecycle.mode"],
            ),
        ]
    if stage == "autonomy":
        return [
            DecisionQuestion(
                id="autonomy_level",
                title="自治程度应该设为哪一档？",
                input_type="single_choice",
                stage=stage,
                recommended="L2",
                recommendation_reason="写作任务适合自动整理和产出草稿，但发布、风格规则更新仍需确认。",
                options=[
                    DecisionOption("L1", "只生成草稿，不主动提醒"),
                    DecisionOption("L2", "低打扰半自动：自动整理和推荐，关键节点确认", recommended=True),
                    DecisionOption("L3", "更主动：定期提醒和维护选题池"),
                ],
                affects=["autonomy.level", "interruption_policy"],
            ),
            DecisionQuestion(
                id="initiative_level",
                title="它应该多主动？",
                input_type="single_choice",
                stage=stage,
                recommended="weekly_suggestion",
                recommendation_reason="每周一次建议可以形成节奏，但不会频繁打扰。",
                options=[
                    DecisionOption("on_demand", "只在我召唤时工作"),
                    DecisionOption("weekly_suggestion", "每周推荐一次选题", recommended=True),
                    DecisionOption("topic_pool_threshold", "素材积累到一定数量时提醒"),
                ],
                affects=["lifecycle.trigger", "notification_policy"],
            ),
        ]
    if stage == "tool_permissions":
        return [
            DecisionQuestion(
                id="material_sources",
                title="素材可以来自哪里？",
                input_type="multi_choice",
                stage=stage,
                recommended=["manual_input", "markdown_notes"],
                recommendation_reason="第一版建议先用手动输入和本地 Markdown 笔记，后续再接飞书和公众号。",
                options=[
                    DecisionOption("manual_input", "手动输入", recommended=True),
                    DecisionOption("markdown_notes", "本地 Markdown 笔记目录", recommended=True, requires_input={"id": "notes_path", "type": "path_input", "placeholder": "例如：~/notes/ai"}),
                    DecisionOption("feishu_docs", "飞书文档"),
                    DecisionOption("web_links", "网页 / RSS / 链接"),
                    DecisionOption("chat_summaries", "聊天记录摘要"),
                ],
                affects=["tools.material_reader", "tool_policy.read_sources"],
            ),
            DecisionQuestion(
                id="publish_policy",
                title="是否允许发布到公众号？",
                input_type="single_choice",
                stage=stage,
                recommended="explicit_confirmation",
                recommendation_reason="发布是外部副作用，必须显式确认；MVP 可以先只生成发布包。",
                options=[
                    DecisionOption("never_publish", "不发布，只生成发布包"),
                    DecisionOption("explicit_confirmation", "发布前必须显式确认", recommended=True),
                    DecisionOption("draft_to_platform", "可同步草稿到平台，但发布前确认"),
                ],
                affects=["tool_policy.wechat.publish", "human_feedback.before_publish"],
                risk_level="critical",
            ),
        ]
    if stage == "feedback_protocol":
        return [
            DecisionQuestion(
                id="topic_feedback",
                title="选题阶段用什么反馈方式？",
                input_type="single_choice",
                stage=stage,
                recommended="choice",
                recommendation_reason="选题适合给 3-5 个方向让你快速选择。",
                options=[
                    DecisionOption("choice", "选择式：从 3-5 个选题中选", recommended=True),
                    DecisionOption("ranked_choice", "排序式：按优先级排序"),
                    DecisionOption("free_chat", "自由对话"),
                ],
                affects=["human_feedback.topic_selection"],
            ),
            DecisionQuestion(
                id="draft_feedback",
                title="初稿阶段用什么反馈方式？",
                input_type="single_choice",
                stage=stage,
                recommended="report_plus_chat",
                recommendation_reason="初稿需要看整体，也需要自然语言修改意见。",
                options=[
                    DecisionOption("structured_comment", "结构化评论：保留/删除/补例子/调语气"),
                    DecisionOption("report_plus_chat", "报告式 + 自由对话", recommended=True),
                    DecisionOption("inline_edit", "逐段批注"),
                ],
                affects=["human_feedback.draft_review"],
            ),
        ]
    if stage == "memory_policy":
        return [
            DecisionQuestion(
                id="style_memory_policy",
                title="写作风格如何学习？",
                input_type="single_choice",
                stage=stage,
                recommended="approved_style_patch",
                recommendation_reason="风格学习必须可审查，避免 Agent 悄悄变味。",
                options=[
                    DecisionOption("no_long_term", "不使用长期风格记忆"),
                    DecisionOption("approved_style_patch", "生成 Style Patch，经审批后写入", recommended=True),
                    DecisionOption("auto_low_risk_style", "低风险风格规则自动写入"),
                ],
                affects=["memory.style_rules", "style_patch.requires_approval"],
            ),
            DecisionQuestion(
                id="style_memory_scope",
                title="哪些风格偏好可以沉淀？",
                input_type="multi_choice",
                stage=stage,
                recommended=["tone", "title_preference", "article_structure"],
                recommendation_reason="最有价值的是语气、标题偏好和文章结构。",
                options=[
                    DecisionOption("tone", "语气：避免营销腔、保持真实", recommended=True),
                    DecisionOption("title_preference", "标题偏好", recommended=True),
                    DecisionOption("article_structure", "文章结构", recommended=True),
                    DecisionOption("example_style", "案例风格"),
                ],
                affects=["memory.long_term_candidates"],
            ),
        ]
    if stage == "output_and_dry_run":
        return [
            DecisionQuestion(
                id="output_package",
                title="最终发布包包含哪些内容？",
                input_type="multi_choice",
                stage=stage,
                recommended=["article_md", "title_options", "summary", "cover_prompt", "publish_checklist"],
                recommendation_reason="完整发布包能降低从初稿到发布的摩擦。",
                options=[
                    DecisionOption("article_md", "正文 Markdown", recommended=True),
                    DecisionOption("title_options", "标题备选", recommended=True),
                    DecisionOption("summary", "摘要", recommended=True),
                    DecisionOption("cover_prompt", "封面图 prompt", recommended=True),
                    DecisionOption("publish_checklist", "发布前 checklist", recommended=True),
                    DecisionOption("html_preview", "HTML 预览"),
                ],
                affects=["output.artifacts"],
            ),
            DecisionQuestion(
                id="dry_run_enabled",
                title="生成 AgentSpec 前是否先跑 dry run？",
                input_type="single_choice",
                stage=stage,
                recommended="yes",
                recommendation_reason="用一条示例素材模拟选题和大纲，能快速验证体验。",
                options=[DecisionOption("yes", "是", recommended=True), DecisionOption("no", "否")],
                affects=["dry_run.enabled"],
            ),
        ]
    return []


def _generic_questions(stage: str) -> List[DecisionQuestion]:
    if stage == "foundation":
        return [
            DecisionQuestion(
                id="main_output",
                title="这个 Agent 最终应该交付什么？",
                input_type="single_choice",
                stage=stage,
                recommended="markdown_report",
                recommendation_reason="Markdown 产物最容易审查和迭代。",
                options=[
                    DecisionOption("markdown_report", "Markdown 报告", recommended=True),
                    DecisionOption("json_data", "JSON 结构化数据"),
                    DecisionOption("files_or_patch", "文件或 patch"),
                    DecisionOption("dashboard", "状态面板"),
                ],
                affects=["output.artifacts"],
            )
        ]
    if stage == "autonomy":
        return [
            DecisionQuestion(
                id="autonomy_level",
                title="自治程度应该设为哪一档？",
                input_type="single_choice",
                stage=stage,
                recommended="L2",
                recommendation_reason="MVP 推荐受控半自动。",
                options=[DecisionOption("L1", "草稿自动"), DecisionOption("L2", "受控半自动", recommended=True), DecisionOption("L3", "沙箱自治")],
                affects=["autonomy.level"],
            )
        ]
    return []


def required_question_ids(agent_type: str) -> List[str]:
    ids: List[str] = []
    for stage in get_stage_order(agent_type):
        for q in get_questions(agent_type, stage):
            if q.required:
                ids.append(q.id)
    return ids


def preset_decision_defaults(agent_type: str, preset_id: str) -> Dict:
    for preset in get_presets(agent_type):
        if preset.id == preset_id:
            return dict(preset.decisions)
    return {}
