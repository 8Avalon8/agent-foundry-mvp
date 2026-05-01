# AgentSpec、Compiler 与 Runtime

## AgentSpec v0.1

用户完成 Pre-Spec 后，系统才生成正式 AgentSpec。AgentSpec 的职责是把用户确认过的设计变成可加载、可审查、可运行的 Agent 蓝图。

顶层结构：

```yaml
agent:
goal:
lifecycle:
autonomy:
inputs:
tools:
tool_policy:
human_feedback:
memory:
output:
eval:
```

SVN Review Agent 示例：

```yaml
agent:
  name: svn-reviewer
  version: 0.1.0
  type: review-agent
  description: "辅助用户审查 SVN diff 的受控半自动 Agent"
goal:
  primary: "审查 SVN diff，发现潜在问题并生成 review 报告"
  secondary:
    - "降低人工 review 成本"
    - "沉淀项目审查规则"
    - "减少重复误报"
lifecycle:
  mode: on_demand
  trigger:
    - manual
    - svn_diff_available
autonomy:
  level: L2
  max_iterations_without_user: 3
  default_behavior: auto_low_risk_ask_high_risk
inputs:
  required:
    - svn_diff
  optional:
    - related_source_files
    - project_rules
    - previous_feedback
tools:
  required_capabilities:
    - read_svn_diff
    - read_files
    - search_code
    - generate_markdown
    - ask_user
    - propose_rule_patch
tool_policy:
  svn.diff:
    permission: allow
    risk: low
  fs.read:
    permission: allow
    scope: current_project
    risk: low
  shell.run_tests:
    permission: ask
    risk: medium
  fs.write_patch:
    permission: ask
    risk: medium
  svn.commit:
    permission: deny
    risk: critical
human_feedback:
  finding_feedback:
    mode: inline_label
    options:
      - accepted
      - false_positive
      - too_minor
      - duplicate
      - needs_more_evidence
  before_sensitive_action:
    mode: approval
  rule_update:
    mode: diff_review
    requires_approval: true
memory:
  short_term:
    - current_diff
    - current_review_context
  long_term_candidates:
    - accepted_patterns
    - false_positive_patterns
    - project_rules
  update_requires_approval: true
output:
  artifacts:
    - review_report.md
    - findings.json
    - test_suggestions.md
    - rule_patch_proposal.md
eval:
  metrics:
    - finding_acceptance_rate
    - false_positive_rate
    - actionable_suggestion_rate
    - user_revision_count
```

## Compiler

Compiler 的职责是把 AgentSpec 编译成工程文件。

输入：

```text
AgentSpec YAML / dict
```

输出：

```text
agent.yaml
system_prompt.md
runbook.md
tool_policy.yaml
human_feedback.yaml
memory_policy.yaml
eval_rubric.yaml
output_schema.json
examples/
```

完成标准：

1. `PreSpecSession -> AgentSpec` 可重复生成。
2. 必填字段完整。
3. 未确认项不会静默填充高风险默认值。
4. 所有 `allow` / `ask` / `deny` 权限清晰。
5. 生成文件可读、可加载、可 dry run。

安全默认值约定：

- 未由用户明确确认的运行测试、写文件、外部发布和长期记忆更新，必须编译为 `ask` 或 `deny`。
- `svn.commit` 和外部发布默认 `deny`；只有用户显式确认发布策略后，发布动作才可进入 `ask`。
- `tool_policy` 每个条目都必须包含 `permission` 和 `risk`。
- `memory.update_requires_approval` 必须为 `true`，Rule Patch / Style Patch 只能作为候选补丁等待审批。

## 工程目录结构

目标形态：

```text
agents/
  svn-reviewer/
    agent.yaml
    system_prompt.md
    runbook.md
    tool_policy.yaml
    human_feedback.yaml
    memory_policy.yaml
    eval_rubric.yaml
    output_schema.json
    prespec_session.json
    agent_design_card.md
    examples/
      sample_input.diff
      sample_review_report.md
    runs/
    learned_rules.md
  wechat-ai-writer/
    agent.yaml
    system_prompt.md
    runbook.md
    tool_policy.yaml
    human_feedback.yaml
    memory_policy.yaml
    eval_rubric.yaml
    output_schema.json
    examples/
    style_rules.md
    runs/
```

## Runtime Harness

初期 Runtime 不需要复杂。MVP 只需要：

1. 读取 AgentSpec。
2. 加载工具权限。
3. 执行 runbook 或 dry run。
4. 遇到 `ask` 权限时暂停。
5. 等待用户确认。
6. 生成输出产物。
7. 记录用户反馈。
8. 生成 rule patch 建议。

第一版可以先支持 deterministic dry run 和 LLM dry run，不急着接真实 SVN、真实 shell 或后台服务。

## Permission Engine

输入示例：

```yaml
tool: shell.run_tests
command: "npm test"
```

检查：

```yaml
tool_policy.shell.run_tests.permission
```

结果：

- `allow`：直接执行。
- `ask`：生成审批请求。
- `deny`：拒绝执行。

审批请求示例：

```yaml
approval_request:
  id: approval_001
  action: shell.run_tests
  risk: medium
  command: "npm test"
  reason: "运行测试可以验证本次变更是否引入回归"
  options:
    - approve
    - reject
    - approve_once
    - add_to_whitelist
```

## Human Feedback Engine

Human Feedback Engine 负责把 Agent 的问题转成标准反馈组件。

review finding 示例：

```yaml
feedback_request:
  type: finding_feedback
  finding_id: F003
  title: "可能存在空指针风险"
  evidence:
    - "FooService.java:123"
  options:
    - accepted
    - false_positive
    - too_minor
    - duplicate
    - needs_more_evidence
```

## Memory Engine

Memory Engine 负责把反馈转成候选规则更新，而不是直接写入长期规则。

输入：

```yaml
finding_id: F003
feedback: false_positive
reason: "这个字段在上游一定会初始化"
```

输出：

```yaml
rule_patch_proposal:
  target: learned_rules.md
  patch:
    - add: "在 FooService.createContext 之后，BarContext.user 可视为非空。"
  requires_approval: true
```

原则：

- 任何长期规则更新都必须经过审批。
- 权限策略变更必须经过审批。
- 不允许记忆 credentials、secrets 或无关隐私内容。
