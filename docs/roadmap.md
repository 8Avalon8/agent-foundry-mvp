# 实施路线图

## MVP 成功标准

当用户输入：

```text
我想做一个 SVN Review Agent，帮我审查 diff。
```

系统应该完成：

1. 自动识别为 `review-agent`。
2. 推荐“受控半自动”配置。
3. 显示 4-6 个关键决策问题。
4. 每个问题有推荐选项和原因。
5. 支持用户选择和补充。
6. 生成 Agent Design Card。
7. 生成 AgentSpec YAML。
8. 生成工程文件。
9. 执行一次 dry run。
10. 输出 review 报告和 feedback 标签。

## Milestones

### Milestone 0：项目骨架

目标：建立基础工程结构。

产物：

```text
agent_foundry/
  builder/
  runtime/
  schemas/
agents/
examples/
README.md
CLI 入口
```

完成标准：

1. 有基本目录。
2. 有 README。
3. 有 schema 草案。
4. 有 CLI 入口占位。

当前状态：已完成。

### Milestone 1：PreSpec 数据协议

目标：定义核心协议。

产物：

- `PreSpecSession`
- `DecisionQuestion`
- `DecisionStage`
- `DecisionBoard`
- `PresetProfile`
- `ImpactPreview`
- `schemas/prespec_session.schema.json`
- `schemas/decision_question.schema.json`
- `schemas/decision_board.schema.json`

完成标准：

1. 能用 JSON/YAML 表达一组问题。
2. 能记录用户选择。
3. 能区分 resolved / unresolved。
4. 能生成 impact preview。
5. 能进入下一阶段。

当前状态：代码已有基础模型和 schema，后续要继续收紧协议字段和组件表达。

### Milestone 2：Preset Registry

目标：给不同 Agent 类型定义默认推荐组合。

产物：

- `review-agent`
- `writing-agent`
- `coding-agent`
- `research-agent`
- `automation-agent`
- `monitor-agent`

完成标准：

用户输入：

```text
我想做一个 SVN Review Agent
```

系统能推荐：

```text
review-agent + controlled_semi_auto
```

当前状态：已有 Python preset 逻辑；后续可以决定是否外置为 YAML registry。

### Milestone 3：Decision Graph

目标：实现分阶段问题流。

阶段：

- `foundation`
- `autonomy`
- `tool_permissions`
- `feedback_protocol`
- `memory_policy`
- `output_and_dry_run`

完成标准：

1. 确认 Stage 1 后，才进入 Stage 2。
2. 选择“会发布到外部平台”后，才显示发布审批问题。
3. 选择“不运行 shell”后，不再追问 shell 白名单。

当前状态：已有阶段顺序和部分可见性逻辑；后续要补条件分支和更多 Agent 类型。

### Milestone 4：Decision Board Renderer

目标：先做 CLI / Markdown renderer，不急着做 Web UI。

完成标准：

1. 能显示推荐组合。
2. 能显示问题。
3. 能显示推荐理由。
4. 能接受用户选择。
5. 能更新 PreSpecSession。

当前状态：已有 CLI / Markdown / HTML / JSON 输出；后续要增强交互输入体验。

### Milestone 5：Impact Preview

目标：根据用户选择生成 AgentSpec 影响预览。

示例：

```diff
tool_policy:
  shell.run_tests:
-   permission: deny
+   permission: ask
```

完成标准：

1. 用户每做一个选择，能看到受影响字段。
2. 支持 `tool_policy`。
3. 支持 `human_feedback`。
4. 支持 `memory_policy`。
5. 支持 `output artifacts`。

当前状态：已有基础影响预览；后续要补 diff-style preview。

### Milestone 6：Agent Design Card

目标：每个阶段完成后生成确认卡。

完成标准：

1. 能总结已确认决策。
2. 能列出未确认项。
3. 用户可以确认进入下一阶段。

当前状态：已有 design card 生成；后续要按阶段增强内容质量。

### Milestone 7：AgentSpec Compiler

目标：把 PreSpecSession 编译成 AgentSpec v0.1。

完成标准：

1. `PreSpecSession -> AgentSpec`。
2. 必填字段完整。
3. 未确认项不会静默填充高风险默认值。
4. 所有 `ask` / `deny` / `allow` 权限清晰。

当前状态：已有基础编译器；后续要围绕风险默认值和未确认项补测试。

### Milestone 8：工程文件生成器

目标：把 AgentSpec 编译成文件夹。

产物：

```text
agent.yaml
system_prompt.md
runbook.md
tool_policy.yaml
human_feedback.yaml
memory_policy.yaml
eval_rubric.yaml
output_schema.json
```

完成标准：

1. 文件结构稳定。
2. 每个文件可读。
3. 可被 Runtime 加载。

当前状态：已有基础生成器。

### Milestone 9：SVN Review Agent MVP

目标：验证第一条完整链路。

```text
自然语言需求
  -> PreSpec Decision Board
  -> 用户确认
  -> AgentSpec
  -> 工程文件
  -> dry run
```

完成标准：

1. 输入 diff。
2. 输出 `review_report.md`。
3. 输出 `findings.json`。
4. 用户能标记 finding。
5. 系统能生成 `rule_patch_proposal.md`。

当前状态：已支持 dry run 输出、`feedback_requests.json`、finding label CLI 和 `rule_patch_proposal.md` 候选生成；不会自动写入长期规则。

### Milestone 10：微信公众号写作 Agent MVP

目标：验证创作型 Agent。

完成标准：

1. 输入一条素材。
2. 输出选题列表。
3. 用户选择方向。
4. 输出大纲。
5. 输出初稿。
6. 输出发布包。
7. 生成 `style_rule_patch.md`。

当前状态：已支持 writing-agent dry run、3-5 个选题、选题选择、发布包和 `style_rule_patch.md` 候选生成；不会自动写入长期风格规则。

### Milestone 11：Research Agent MVP

目标：验证资料整理和竞品研究型 Agent。

完成标准：

1. 输入一条调研需求。
2. 输出 `research_plan.md`。
3. 输出 `report.md`。
4. 输出带来源字段的 `sources.json`。
5. 输出 `feedback_requests.json`。
6. 权限策略禁止登录、验证码、表单提交和外部发布。

当前状态：已支持 research-agent compile 和 dry run 产物；真实网页抓取尚未实现。真实 Research run 协议要求额外生成 `evidence_matrix.json`、`run_log.json` 和 `raw_notes/`，用于审计来源、运行轨迹和抽取笔记。

## 五个小迭代

### Iteration 1：协议和模型

目标：把 PreSpecSession / DecisionQuestion / AgentSpec 的数据结构定下来。

产物：

- `models.py`
- schema 草案
- 硬编码 SVN Review Agent Decision Board

### Iteration 2：CLI 决策面板

目标：让用户可以在命令行完成第一轮选择。

产物：

- `agent new "..."`
- 推荐组合展示
- 用户选择收集
- PreSpecSession 保存

### Iteration 3：AgentSpec 编译

目标：把 PreSpecSession 编译成 AgentSpec。

产物：

- `agentspec.yaml`
- Agent Design Card
- Impact Preview

### Iteration 4：工程文件生成

目标：生成完整 Agent 文件夹。

产物：

- `agent.yaml`
- `system_prompt.md`
- `runbook.md`
- `tool_policy.yaml`
- `human_feedback.yaml`
- `memory_policy.yaml`
- `eval_rubric.yaml`

### Iteration 5：SVN Review dry run

目标：用模拟 diff 跑一遍 review 流程。

产物：

- `review_report.md`
- `findings.json`
- `rule_patch_proposal.md`

## 下一步建议

当前 T0-T16 MVP 已进入验收收口；下一步优先做全量端到端命令验证和生成物检查。真实 Web UI runtime、真实 A2UI runtime、真实 SVN 调用、真实公众号发布和真实网页抓取仍在 MVP 边界外。

## 第一版暂不做

为了避免项目过大，第一版先不做：

1. 真正 Web UI。
2. 完整 A2UI 集成。
3. 真正接入微信公众号。
4. 真正自动调用 SVN。
5. 真正长期后台运行。
6. 真正多 Agent 协作。
7. 自动发布。
8. 自动提交代码。
9. 复杂数据库。
10. 复杂权限沙箱。

第一版只保证：

```text
自然语言需求
  -> 结构化决策面板
  -> 用户选择
  -> AgentSpec
  -> 工程文件
  -> dry run
```

Web / A2UI 并不是终局外的内容，当前已按 `docs/ultimate_task_todo.md` 中的 T13-T16 落地到协议和 demo 层：

- T13 Web Renderer：声明式 Web view model / static HTML。
- T14 A2UI-compatible Renderer：A2UI-compatible component tree。
- T15 Component Catalog / Action Protocol：可回放 action event。
- T16 UI E2E Demo：review/writing 两条 action event -> AgentSpec -> dry run demo。
