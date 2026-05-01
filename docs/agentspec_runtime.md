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
    - read_svn_status
    - parse_diff_files
    - read_files
    - search_code
    - generate_review_report
    - collect_human_feedback
    - propose_rule_patch
    - apply_memory_patch
tool_policy:
  svn.diff:
    permission: allow
    risk: low
  svn.status:
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

Research Agent 输出约定：

```yaml
agent:
  type: research-agent
tools:
  required_capabilities:
    - search_public_web
    - read_public_pages
    - extract_evidence
    - generate_markdown
    - export_structured_sources
tool_policy:
  web.search:
    permission: allow
    scope: public_web
    risk: low_to_medium
  web.fetch_public:
    permission: allow
    scope: public_web
    risk: low_to_medium
  browser.login:
    permission: deny
    risk: high
  captcha.solve:
    permission: deny
    risk: high
  forms.submit:
    permission: deny
    risk: high
output:
  artifacts:
    - report.md
    - sources.json
    - research_plan.md
    - feedback_requests.json
```

`sources.json` 必须保留 `source_url`、`source_title`、`retrieved_at`、`evidence_snippet`、`source_type`、`confidence` 和 `inference_note`，用于复核报告里的事实来源。

真实 Research run 的输出比 dry run 更重。除上述核心产物外，真实运行必须额外生成：

```text
evidence_matrix.json
run_log.json
raw_notes/
```

- `evidence_matrix.json`：把每个报告结论映射到 `sources.json` 中的来源、证据片段、置信度和推断说明。
- `run_log.json`：记录检索词、抓取时间、权限决策、失败原因、跳过原因和人工确认点。
- `raw_notes/`：保存从公开页面抽取后的网页笔记或引用摘要，不默认保存整页内容。

当前 MVP 只实现 deterministic / LLM dry run。真实网页抓取、真实 Research run 和长期后台运行仍是后续范围。

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
prespec_session.json
agent_design_card.md
examples/
```

当前生成器保证上述稳定文件集都会落盘；`tool_policy.yaml`、`human_feedback.yaml`、`memory_policy.yaml`、`eval_rubric.yaml` 均来自同一个 `AgentSpec`，不得与 `agent.yaml` 中对应字段分叉。

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
  research-agent/
    agent.yaml
    system_prompt.md
    runbook.md
    tool_policy.yaml
    human_feedback.yaml
    memory_policy.yaml
    eval_rubric.yaml
    output_schema.json
    examples/
      sample_input.txt
      sample_report.md
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

第一版支持 deterministic dry run 和 LLM dry run。Review / Writing / Research Agent 都会生成声明的 dry run 产物；Research dry run 不执行真实网页访问，只模拟研究计划、报告、来源字段和反馈请求。

v0.2 新增 SVN Review Runtime。它只服务 `review-agent`，入口是：

```bash
python3 -m agent_foundry.cli review-svn ./path/to/svn-working-copy \
  --agent ./workspace/agents/svn-reviewer \
  --output ./workspace/runs \
  --llm-provider mock
```

运行目录必须包含：

```text
review_report.md
findings.json
feedback_requests.json
test_suggestions.md
rule_patch_proposal.md
run_log.json
permission_checks.json
context_snapshot.json
pending_approvals.json
approval_log.jsonl
run_state.json
```

Runtime 约束：

- 只允许 registry 中声明的工具，LLM 不能发明新工具。
- SVN 层只调用 `svn info`、`svn diff`、`svn status`，并使用 list args、`cwd`、`timeout` 和 captured output。
- 文件上下文只能来自 SVN working copy 内部，并记录 byte count 和 truncation metadata。
- 不修改源码，不写 patch 到 working copy，不执行 `svn commit`。
- 测试建议只写入 `test_suggestions.md`；当 `shell.run_tests.permission == ask` 时，只写 pending approval。
- `learned_rules.md` 会被加载进 review prompt，并记录到 `run_log.json` / `context_snapshot.json`。

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

Runtime 的权限判断输出必须稳定可序列化：

- `status=allowed`：可继续执行。
- `status=requires_approval`：必须暂停，输出 approval request。
- `status=denied`：直接拒绝并记录原因。

approval request 支持动作：`approve_once`、`reject`、`show_impact`、`add_to_whitelist`。其中 `add_to_whitelist` 只生成策略补丁请求，不会静默改白名单。

审批请求示例：

```yaml
approval_request:
  id: approval_001
  type: approval
  tool: shell.run_tests
  risk: medium
  payload:
    command: "npm test"
  reason: "运行测试可以验证本次变更是否引入回归"
  status: pending
  options:
    - approve_once
    - reject
    - show_impact
    - add_to_whitelist
```

每个真实 run 目录还会保存：

```text
run_state.json
pending_approvals.json
approval_log.jsonl
```

审批相关 CLI：

```bash
agent-foundry approvals ./workspace/runs/review_svn_xxx
agent-foundry approve ./workspace/runs/review_svn_xxx approval_shell_run_tests --decision reject
agent-foundry resume ./workspace/runs/review_svn_xxx
```

`resume` 当前只做安全幂等恢复：没有 pending approval 时输出 `no pending approvals`；已 rejected 的 approval 不会执行对应步骤；已 approve_once 的 approval 只记录一次性批准，不重跑已经完成的步骤。

## UI Action Event

Pre-Spec UI 不直接改 AgentSpec，也不绕过权限。它只能把用户操作作为 action event 回放到
`PreSpecSession`，再由 compiler / permission engine 重新计算后续状态。

事件 schema 位于 `agent_foundry/schemas/action_event.schema.json`。当前支持：

- `select_option`
- `update_text`
- `confirm_stage`
- `save_draft`
- `show_impact`
- `request_approval`

非法 action 返回 `rejected`，不会污染 session；需要审批的 action 返回 `requires_approval`。

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
- Review Runtime 的 `learned_rules.md` 只能通过显式 `memory-apply` 更新。
- `memory-apply` 追加写入 `learned_rules.md` 和 `memory_log.jsonl`，不会覆盖既有规则。
- `memory-reject` 追加写入 `rejected_rule_patches.jsonl`。
- 权限策略变更必须经过审批。
- 不允许记忆 credentials、secrets 或无关隐私内容。

记忆相关 CLI：

```bash
agent-foundry memory-review ./workspace/runs/review_svn_xxx
agent-foundry memory-apply ./workspace/agents/svn-reviewer ./workspace/runs/review_svn_xxx --patch rule_patch_proposal.md
agent-foundry memory-reject ./workspace/agents/svn-reviewer ./workspace/runs/review_svn_xxx --reason "too broad"
```
