# Pre-Spec 决策面板协议

## 目标

Pre-Spec 阶段位于 AgentSpec 之前。它负责把“我想做一个什么 Agent”变成可确认、可修改、可审查的设计决策。

第一版优先做自定义 JSON 协议，然后再渲染成 CLI / Markdown / Web / A2UI-compatible UI。

当前实现以 `DecisionBoard` 为 source of truth。CLI / Markdown / HTML / Web view model 都只消费
`DecisionBoard`，渲染层不能修改 `PreSpecSession`。

## 页面结构

一个标准 Decision Board 页面包括：

1. Agent Summary Card
2. Preset Combination Cards
3. Required Decision Cards
4. Optional Advanced Settings
5. Impact Preview
6. Stage Progress
7. Confirm Bar

## 组件 Catalog

初期组件：

- `AgentSummaryCard`
- `PresetCardGroup`
- `DecisionCard`
- `ChoiceGroup`
- `MultiChoiceGroup`
- `TextInputWithHint`
- `PermissionMatrix`
- `RiskBadge`
- `RecommendationBadge`
- `ExplainDrawer`
- `ImpactPreview`
- `ImpactDiff`
- `StageProgress`
- `ConfirmBar`
- `DryRunPreview`
- `AgentDesignCard`

`AgentDesignCard` 当前按阶段分组展示“已确认”和“待确认”。`medium_high`、`high`、`critical` 风险的问题如果只是采用推荐默认值，会继续显示为“尚未确认”，直到用户通过交互选择或自然语言指令明确确认。

## Renderer Targets

### Web Renderer

`agent_foundry.renderers.web_renderer` 将 `DecisionBoard` 转成声明式 Web view model：

- `AgentSummaryCard`
- `PresetCardGroup`
- `StageProgress`
- `DecisionCard`
- `ImpactPreview`
- `ConfirmBar`

Web view model 包含组件 `type`、`id`、`props`、`state_key` 和可触发的 action 元数据。它可以通过
`agent-foundry board ... --format web-json` 输出 JSON，也可以通过 `--format web-html` 输出静态 HTML 预览。

约束：

- Web renderer 不执行任意 Agent 代码。
- Web renderer 不改变 `PreSpecSession` 或 `DecisionBoard`。
- 推荐理由、风险等级、影响预览和确认动作必须保留在输出中。

### A2UI-compatible Renderer

`agent_foundry.renderers.a2ui_renderer` 将同一个 `DecisionBoard` 映射成 A2UI-compatible component tree。
`DecisionBoard` 仍然是业务 source of truth，A2UI 只是渲染目标。

当前组件映射：

- `AgentSummaryCard`
- `PresetCardGroup`
- `StageProgress`
- `DecisionCard`
- `ChoiceGroup`
- `MultiChoiceGroup`
- `TextInputWithHint`
- `ImpactDiff`
- `ConfirmBar`

A2UI 输出包含：

- component `type` / `id` / `props`。
- `state_key` 与 `on_change` action payload。
- `risk_level`、`recommendation`、`requires_input`、`affects`。
- session-scoped `action_payload_schema`。

可以通过 `agent-foundry board ... --format a2ui-json` 导出。

## Action Protocol

UI 层通过 action event 回传用户操作，后端将事件应用到 `PreSpecSession`：

```json
{
  "action": "select_option",
  "session_id": "session_xxx",
  "payload": {
    "question_id": "run_tests",
    "value": "ask"
  }
}
```

当前 action：

- `select_option`
- `update_text`
- `confirm_stage`
- `save_draft`
- `show_impact`
- `request_approval`

协议约束：

- 非法选项、缺少 required input、stage 不匹配会返回 `rejected`，不会污染 session。
- `show_impact` 和 `request_approval` 是只读事件，不改变 session。
- `confirm_stage` 只有当前阶段必填问题都已回答时才会推进阶段。
- CLI 可用 `agent-foundry apply-action <session.json> '<event-json>'` 回放事件。

## Conversation Orchestrator

`agent_foundry.builder.conversation_orchestrator` 把 Pre-Spec 决策面板包装成自然语言多轮体验：

```text
用户一句话
  -> 创建 PreSpecSession / DecisionBoard
  -> 选择下一条最重要的可见必填问题
  -> 接收自然语言回答
  -> 转成 action event / session patch
  -> 更新 board 和 impact preview
  -> 无未决问题后自动 compile + dry run
```

当前 CLI：

```bash
python3 -m agent_foundry.cli chat-build "我想做一个 SVN Review Agent，帮我审查 diff" \
  --llm-provider mock \
  --reply "都按推荐" \
  --output ./workspace
```

交互协议收束点：

- action event 必须带 `session_id`，否则拒绝。
- 自然语言回答先尽量映射到当前问题的 action event，再应用 LLM session patch。
- 信息足够明确后自动产出 AgentSpec、Agent 工程和 dry run。

`agent_foundry.runtime.conversation_runtime` 提供 Web / A2UI 客户端可调用的运行时 facade：

```text
GET /
  -> 内置 Web / A2UI Agent Builder

GET /health
  -> provider / model / output_root / OpenAI 配置状态

POST /conversation/start
  -> assistant_message + session_id + a2ui_tree

POST /conversation/respond
  -> assistant_message + updated a2ui_tree + status
```

`respond` 支持两类输入：

- `action_event`：用户在 A2UI 组件上的点击 / 输入。
- `natural_language_reply`：用户直接用自然语言补充偏好。

当 `status=completed` 时，响应体还会包含：

- `agent_dir`
- `run_dir`
- `agent_spec_summary`

内置网页入口：

```bash
python3 -m agent_foundry.cli serve-web \
  --host 127.0.0.1 \
  --port 8765 \
  --output ./workspace/web_builder
```

`serve-web` 默认使用 OpenAI provider；自动化验收和本地无 key 演示可以使用 `--llm-provider mock`。

## 分阶段决策图

### Stage 1：基础目标确认

目标：确认这个 Agent 到底是什么。

需要回答：

1. Agent 类型是什么。
2. 主要目标是什么。
3. 主要输入是什么。
4. 主要输出是什么。
5. 是一次性任务，还是长期助手。

输出示例：

```yaml
stage_1_result:
  agent_type: review-agent
  goal: "审查 SVN diff"
  input:
    - svn_diff
    - related_source_files
  output:
    - review_report
    - risk_list
    - test_suggestions
  lifecycle: on_demand
```

### Stage 2：自治程度确认

推荐自治等级：

- `L0` 手动辅助：Agent 只生成建议。
- `L1` 草稿自动：Agent 可自动生成草稿、报告、计划。
- `L2` 受控半自动：Agent 可自动执行低风险动作，中高风险动作前询问。
- `L3` 沙箱自治：Agent 可在沙箱中自动执行多步操作，高风险动作前询问。
- `L4` 高自治：Agent 可长期运行和主动行动，只适合成熟系统。

初期默认：

```yaml
autonomy:
  level: L2
  default_behavior: auto_low_risk_ask_high_risk
  max_iterations_without_user: 3
```

### Stage 3：工具和权限确认

目标：确认 Agent 可以使用哪些工具，以及每个工具的权限：

- `allow`：自动允许。
- `ask`：使用前询问。
- `deny`：禁止使用。

review-agent 示例：

```yaml
tool_policy:
  svn.diff:
    permission: allow
    risk: low
  fs.read:
    permission: allow
    scope: current_project
    risk: low
  code.search:
    permission: allow
    scope: current_project
    risk: low
  shell.run_tests:
    permission: ask
    allowed_commands: []
    risk: medium
  fs.write_patch:
    permission: ask
    risk: medium
  fs.modify_source:
    permission: ask
    risk: high
  svn.commit:
    permission: deny
    risk: critical
```

### Stage 4：人类反馈机制确认

反馈类型：

- `choice`
- `multi_choice`
- `approval`
- `report`
- `inline_label`
- `diff_review`
- `structured_comment`
- `free_chat`
- `dashboard`

review-agent 推荐：

```yaml
human_feedback:
  finding_feedback:
    mode: inline_label
    options:
      - accepted
      - false_positive
      - too_minor
      - duplicate
      - needs_more_evidence
  before_run_tests:
    mode: approval
    show_command: true
  before_write_patch:
    mode: diff_review
  before_rule_update:
    mode: diff_review
    requires_explicit_approval: true
```

writing-agent 推荐：

```yaml
human_feedback:
  topic_selection:
    mode: choice
    options_count: 3-5
  outline_review:
    mode: structured_comment
  draft_review:
    mode: report_plus_chat
  before_publish:
    mode: explicit_approval
    required_phrase: "确认发布"
  style_rule_update:
    mode: diff_review
    requires_explicit_approval: true
```

### Stage 5：记忆和进化机制确认

记忆层级：

1. `task_memory`：当前任务内临时记忆。
2. `project_memory`：当前项目规则。
3. `agent_memory`：当前 Agent 的长期偏好。
4. `user_memory`：用户全局偏好。
5. `forbidden_memory`：禁止记忆的内容。

策略示例：

```yaml
memory_policy:
  short_term:
    - current_task_goal
    - current_user_feedback
  long_term_candidates:
    - accepted_review_patterns
    - repeated_false_positives
    - writing_style_preferences
    - project_specific_rules
  requires_approval:
    - new_project_rule
    - style_rule_update
    - permission_policy_change
    - tool_scope_change
  forbidden:
    - credentials
    - secrets
    - unrelated_private_content
```

### Stage 6：输出格式和 dry run

常见输出类型：

- Markdown 报告
- JSON 结构化数据
- HTML 预览
- Patch 文件
- 发布包
- Checklist
- Dashboard
- 日志
- Rule Patch

SVN Review Agent 输出：

```yaml
output:
  artifacts:
    - review_report.md
    - findings.json
    - test_suggestions.md
    - optional_patch.diff
    - rule_patch_proposal.md
```

公众号 Agent 输出：

```yaml
output:
  artifacts:
    - article.md
    - title_options.md
    - summary.md
    - cover_prompt.md
    - publish_checklist.md
    - style_rule_patch.md
```

Research Agent 输出：

```yaml
output:
  artifacts:
    - report.md
    - sources.json
    - research_plan.md
    - feedback_requests.json
```

真实 Research run 还需要额外生成 `evidence_matrix.json`、`run_log.json` 和 `raw_notes/`，用于复核结论、追踪检索过程和保留抽取笔记。当前 MVP 只承诺 dry run 产物。

### Stage 7：AgentSpec 生成前 dry run

目标：在真正生成或最终确认 AgentSpec 前，模拟一次运行，让用户看到实际效果。

SVN Review Agent dry run 输入一段模拟 diff，输出：

1. 发现的问题。
2. 风险等级。
3. 证据。
4. 建议测试点。
5. 用户可打标签的 finding 列表。

公众号 Agent dry run 输入一条模拟素材，输出：

1. 选题建议。
2. 推荐标题。
3. 大纲。
4. 初稿片段。
5. 发布包预览。

Research Agent dry run 输入一条模拟调研需求，输出：

1. 调研计划。
2. 带来源字段的报告。
3. 结构化来源列表。
4. 待用户确认的问题。

## 数据模型

### PreSpecSession

```yaml
pre_spec_session:
  id: session_001
  user_goal: "做一个 SVN Review Agent"
  inferred_agent_type: review-agent
  current_stage: tool_permissions
  selected_preset: controlled_semi_auto
  decisions:
    context_scope:
      value: project_search
      source: user_selected
      confidence: high
    run_tests:
      value: ask
      source: recommended_accepted
      confidence: high
    output_format:
      value: markdown_report
      source: default
      confidence: medium
  unresolved:
    - patch_generation_policy
    - memory_update_policy
  impact_preview:
    tool_policy.fs.read.scope: project_search
    tool_policy.shell.run_tests.permission: ask
  generated:
    - agent_design_card
```

### DecisionQuestion

```yaml
decision_question:
  id: run_tests
  title: "是否允许运行测试命令？"
  type: single_choice
  input_type: single_choice
  stage: tool_permissions
  required: true
  recommended: ask
  recommendation_reason: "测试能提高 review 可信度，但命令执行存在成本和副作用。"
  risk_level: medium
  options:
    - id: deny
      label: "不运行测试"
      tradeoff: "最安全，但 review 可信度较低"
    - id: ask
      label: "每次运行前询问"
      recommended: true
      tradeoff: "安全和质量比较平衡"
    - id: allow_whitelist
      label: "自动运行白名单命令"
      tradeoff: "效率更高，但需要维护白名单"
      requires_input:
        id: test_command_whitelist
        type: text_input
        placeholder: "例如：npm test, pytest tests/unit"
  affects:
    - tool_policy.shell.run_tests
    - human_feedback.before_run_tests
```

实现约定：

- `input_type` 是当前 Python 模型和 JSON schema 的规范字段。
- `type` 是兼容旧文档和旧 renderer 的 wire-format 别名；读取时接受 `type`，写出时同时包含 `input_type` 和 `type`。
- `required: true` 的可见问题会进入 `PreSpecSession.unresolved`；当 `apply_decision()` 记录该问题答案后，对应 id 会从 `unresolved` 清除。
- 当决策图发生条件分支变化时，`unresolved` 应从当前可见的 required 问题重新生成，避免隐藏问题继续阻塞 session。
- `visible_when` 用来表达条件追问；MVP 支持 `{question, equals}`、`{question, in}`、`{question, contains}`、`all`、`any` 和 `not`。例如 `run_tests=deny` 时不显示测试白名单，`publish_policy=never_publish` 时不显示发布审批细节。

### Impact Preview

Impact Preview 可以用两种方式呈现：

- 单点影响：展示当前决策会影响哪些 AgentSpec 路径。
- before/after diff：编译两个候选 `PreSpecSession`，对 `tool_policy`、`human_feedback`、`memory` 和 `output.artifacts` 做字段级比较。

diff-style 示例：

```diff
tool_policy.shell.run_tests:
- permission: deny
+ permission: ask
```

### 输入组件类型

需要支持：

- `single_choice`
- `multi_choice`
- `text_input`
- `path_input`
- `number_input`
- `toggle`
- `permission_matrix`
- `ranked_choice`
- `approval`
- `diff_review`
- `checklist`

## Preset 推荐组合

### Review Agent

`readonly_safe`：保守只读

- 只读 diff。
- 不运行命令。
- 不生成 patch。
- 只输出报告。

`controlled_semi_auto`：受控半自动，默认推荐

- 自动读取 diff 和相关源码。
- 测试命令运行前询问。
- 不自动修改代码。
- 输出结构化 review 报告。

`efficient_whitelist`：高效率模式

- 自动读取项目上下文。
- 自动运行白名单测试。
- 可生成 patch 文件，但写入前确认。

`sandbox_auto`：沙箱自治模式

- 在沙箱里自动运行测试和生成 patch。
- 高风险动作前确认。

### Writing Agent

`draft_assistant`：纯写作助手

- 只在用户召唤时工作。
- 根据用户输入生成文章。

`continuous_writer`：持续写作助手，默认推荐

- 收集素材。
- 聚类选题。
- 生成大纲和初稿。
- 发布前确认。

`operation_planner`：运营规划助手

- 管理选题池。
- 制定发文计划。
- 定期提醒。

`publish_assistant`：半自动发布助手

- 生成发布包。
- 检查格式。
- 发布前显式确认。

### Coding Agent

`plan_only`：计划模式，只分析，不改文件。

`patch_suggestion`：Patch 建议模式，生成修改建议或 patch，不直接写入。

`controlled_edit`：受控修改模式，可修改文件，每次修改前展示 diff。

`sandbox_auto`：沙箱自治模式，在隔离环境自动改、测、总结。

## Decision Board JSON 示例

```json
{
  "surface_type": "agent_design_board",
  "session_id": "session_001",
  "stage": "tool_permissions",
  "title": "SVN Review Agent 设计草案",
  "components": [
    {
      "type": "AgentSummaryCard",
      "props": {
        "title": "SVN Review Agent",
        "agent_type": "review-agent",
        "risk_level": "medium",
        "summary": [
          "读取 SVN diff",
          "结合项目上下文生成 review 报告",
          "支持用户标记误报和采纳",
          "可沉淀项目审查规则"
        ]
      }
    },
    {
      "type": "PresetCardGroup",
      "props": {
        "recommended": "controlled_semi_auto",
        "options": [
          {
            "id": "readonly_safe",
            "title": "保守只读",
            "description": "只分析，不运行命令，不改文件"
          },
          {
            "id": "controlled_semi_auto",
            "title": "受控半自动",
            "recommended": true,
            "description": "自动分析，关键动作前确认"
          }
        ]
      }
    },
    {
      "type": "DecisionCard",
      "props": {
        "id": "run_tests",
        "title": "是否允许运行测试命令？",
        "recommended": "ask",
        "recommendation_reason": "测试能提高 review 可信度，但命令执行存在成本和副作用。",
        "input_type": "single_choice",
        "options": [
          {
            "id": "deny",
            "label": "不运行测试"
          },
          {
            "id": "ask",
            "label": "每次运行前询问",
            "recommended": true
          },
          {
            "id": "allow_whitelist",
            "label": "自动运行白名单命令",
            "requires_input": true
          }
        ]
      }
    }
  ]
}
```

## 渲染策略

实现顺序：

1. 自定义 JSON 协议。
2. CLI renderer / Markdown renderer。
3. Web renderer。
4. A2UI-compatible renderer。
5. 自定义组件 catalog。

核心原则：业务协议属于 Agent Foundry，A2UI 是可选渲染目标，不是业务核心。
