# 终极 TaskTodo：Agent Builder MVP 收束任务

## 任务目标

把 Agent Foundry 收束成一个可长任务执行的 Agent Builder MVP：

```text
用户自然语言需求
  -> Pre-Spec 决策面板
  -> 用户阶段式确认和自然语言补充
  -> Agent Design Card
  -> AgentSpec v0.1
  -> 工程文件
  -> dry run
  -> finding / draft 反馈
  -> Rule Patch / Style Patch 候选
```

最终标准：

1. 输入“我想做一个 SVN Review Agent，帮我审查 diff”后，系统能完整跑通从意图识别到 dry run 和 feedback 标签的链路。
2. 输入一条公众号素材后，writing-agent 能产出选题、大纲、初稿、发布包和 style patch 候选。
3. 所有敏感动作都通过 `allow` / `ask` / `deny` 权限策略控制。
4. 长期记忆和规则更新只生成 patch proposal，不静默写入。
5. mock provider 路径不依赖网络，OpenAI provider 路径支持 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`AGENT_FOUNDRY_OPENAI_MODEL`。

## 执行前必读路径

仓库根路径：`/Users/liuwenjia/GitProjects/agent_foundry_mvp`。除非特别说明，本文所有路径都相对这个根目录。

- `AGENTS.md`：仓库级工作规则、命令、文档维护约定。
- `README.md`：当前可运行命令和 OpenAI / mock provider 使用方式。
- `PROJECT_STATUS.md`：当前已交付能力快照。
- `docs/index.md`：文档入口和 source of truth 导航。
- `docs/product_principles.md`：产品定位、UX 原则、安全边界。
- `docs/architecture.md`：总体链路和模块职责。
- `docs/prespec_decision_board.md`：PreSpecSession、DecisionQuestion、DecisionBoard、组件协议和阶段图。
- `docs/agentspec_runtime.md`：AgentSpec、Compiler、Runtime、权限、反馈和记忆策略。
- `docs/example_agents.md`：SVN Review Agent 和微信公众号写作 Agent 的验收口径。
- `docs/roadmap.md`：milestone、iteration 和下一步建议。
- `docs/ultimate_task_todo.md`：本长任务清单。

## 代码路径总览

- `agent_foundry/cli.py`：命令入口；长任务需要增强 `new`、`board`、`update-session`、`dry-run` 的交互和输出。
- `agent_foundry/builder/models.py`：PreSpecSession、DecisionQuestion、DecisionBoard、AgentDesignCard 等核心数据模型。
- `agent_foundry/builder/intent_parser.py`：offline intent parser。
- `agent_foundry/builder/llm_intent_parser.py`：LLM intent parser。
- `agent_foundry/builder/llm_design.py`：LLM 设计草案。
- `agent_foundry/builder/llm_decision_updater.py`：自然语言决策更新。
- `agent_foundry/builder/llm_builder.py`：LLM builder 聚合入口。
- `agent_foundry/builder/presets.py`：agent type presets。
- `agent_foundry/builder/decision_graph.py`：阶段顺序、问题模板和可见性条件。
- `agent_foundry/builder/decision_board.py`：board 构建、渲染、session 保存和 stage 推进。
- `agent_foundry/builder/impact_preview.py`：影响预览，需升级为 before/after diff。
- `agent_foundry/builder/agentspec_compiler.py`：PreSpecSession -> AgentSpec。
- `agent_foundry/builder/file_generator.py`：AgentSpec -> 工程文件。
- `agent_foundry/llm/provider.py`：provider 抽象和 provider factory。
- `agent_foundry/llm/mock_provider.py`：确定性 mock provider。
- `agent_foundry/llm/openai_provider.py`：OpenAI Responses provider。
- `agent_foundry/llm/schemas.py`：LLM 结构化输出 schema。
- `agent_foundry/runtime/dry_run.py`：deterministic / LLM dry run。
- `agent_foundry/runtime/llm_dry_run.py`：LLM dry run 辅助路径。
- `agent_foundry/runtime/permission_engine.py`：权限检查。
- `agent_foundry/runtime/feedback_engine.py`：反馈请求生成。
- `agent_foundry/runtime/memory_engine.py`：memory / rule patch proposal。
- `agent_foundry/schemas/agentspec.schema.json`：AgentSpec schema。
- `agent_foundry/schemas/decision_board.schema.json`：DecisionBoard schema。
- `agent_foundry/schemas/decision_question.schema.json`：DecisionQuestion schema。
- `agent_foundry/schemas/prespec_session.schema.json`：PreSpecSession schema。
- `tests/test_llm_upgrade.py`：当前测试入口；长任务应继续从这里扩展或拆分新测试。
- `examples/svn_review/sample_diff.diff`：review-agent 示例输入。
- `examples/wechat_writer/sample_material.txt`：writing-agent 示例输入。
- `agents/.gitkeep`：生成 agent 的仓库占位目录。
- `generated_examples_llm/`：历史生成样例，只读参考，默认不要继续污染。
- `scripts/publish_to_github.sh`：发布脚本，长任务通常不用动。

## 生成物路径约束

默认不要提交以下路径的运行输出：

- `workspace/`
- `generated_agents/`
- `.agent_foundry_sessions/`
- `agents/*/runs/`
- `__pycache__/`
- `.pytest_cache/`
- `.env`

如需保留验收样例，优先放入：

- `examples/svn_review/`
- `examples/wechat_writer/`
- `docs/`
- `tests/fixtures/`，如果新增 fixture 目录。

## TaskTodo

### T0：环境和 provider 收束

路径：

- `.env.example`
- `README.md`
- `agent_foundry/llm/provider.py`
- `agent_foundry/llm/openai_provider.py`
- `tests/test_llm_upgrade.py`

任务：

1. 确认 OpenAI provider 支持 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`AGENT_FOUNDRY_OPENAI_MODEL`。
2. 确认没有显式 `--model` 时环境模型生效。
3. 用 fake OpenAI client 测试 base URL 传参，不依赖真实网络。
4. 保持 mock provider 全路径可测。

验收：

```bash
python3 -m unittest discover -s tests -v
python3 -m agent_foundry.cli board "我想做一个 SVN Review Agent" --llm-provider mock --stage feedback_protocol --format cli
```

### T1：协议模型和 schema 对齐

路径：

- `docs/prespec_decision_board.md`
- `agent_foundry/builder/models.py`
- `agent_foundry/schemas/prespec_session.schema.json`
- `agent_foundry/schemas/decision_question.schema.json`
- `agent_foundry/schemas/decision_board.schema.json`
- `tests/test_llm_upgrade.py`

任务：

1. 对齐 `DecisionQuestion.type` / `input_type` 命名，保留兼容读写。
2. 为 `required`、`recommended`、`recommendation_reason`、`risk_level`、`requires_input`、`affects` 补 schema 约束。
3. 明确 `PreSpecSession.unresolved` 的生成和清除规则。
4. 补充 session round-trip 测试。

验收：

1. schema 能表达文档里的问题模板。
2. session 保存再读取后，决策和补充输入不丢失。

### T2：Decision Graph 条件分支

路径：

- `agent_foundry/builder/decision_graph.py`
- `agent_foundry/builder/decision_board.py`
- `agent_foundry/builder/models.py`
- `tests/test_decision_graph.py`

任务：

1. 实现 `visible_when` 条件判断。
2. 当 `run_tests=deny` 时不追问测试白名单。
3. 当 `publish_policy=never_publish` 时不显示发布审批细节。
4. 当 `patch_policy=deny` 时不追问 patch 写入策略。
5. 为 review-agent 和 writing-agent 各补条件分支测试。

验收：

1. Stage 问题会随已选决策变化。
2. 不显示与已拒绝能力相关的后续问题。

### T3：CLI 交互式 Decision Board

路径：

- `agent_foundry/cli.py`
- `agent_foundry/builder/decision_board.py`
- `agent_foundry/builder/models.py`
- `tests/test_cli_interactive.py`

任务：

1. 增强 `new --interactive` 的输入解析。
2. 支持 `question=value`、序号选择、多选逗号分隔。
3. 支持 `requires_input` 的补充输入。
4. 支持每阶段确认后保存 session。
5. 支持从 saved session 继续。

验收：

1. CLI 能完成 review-agent 至少 3 个阶段的交互选择。
2. 生成的 session 中包含用户选择和自然语言补充。

### T4：Impact Preview 升级为 diff

路径：

- `agent_foundry/builder/impact_preview.py`
- `agent_foundry/builder/agentspec_compiler.py`
- `agent_foundry/builder/decision_board.py`
- `docs/prespec_decision_board.md`
- `tests/test_impact_preview.py`

任务：

1. 用当前 session 编译前后候选 AgentSpec。
2. 生成字段级 before/after diff。
3. 覆盖 `tool_policy`、`human_feedback`、`memory`、`output.artifacts`。
4. CLI / Markdown renderer 显示 diff-style preview。

验收：

```diff
tool_policy:
  shell.run_tests:
-   permission: deny
+   permission: ask
```

### T5：Agent Design Card 阶段化

路径：

- `agent_foundry/builder/decision_board.py`
- `agent_foundry/builder/models.py`
- `agent_foundry/cli.py`
- `tests/test_design_card.py`

任务：

1. 每阶段结束生成确认卡。
2. 已确认项按阶段分组。
3. 未确认项明确列出。
4. 高风险默认值必须标注“尚未确认”。

验收：

1. design card 能让用户一眼看到已确认和待确认。
2. 不把未确认高风险项写成已批准。

### T6：AgentSpec 编译安全默认值

路径：

- `agent_foundry/builder/agentspec_compiler.py`
- `agent_foundry/schemas/agentspec.schema.json`
- `tests/test_agentspec_compiler.py`

任务：

1. 未确认的写文件、运行 shell、外部发布、长期记忆更新默认 `ask` 或 `deny`。
2. `svn.commit` / 外部发布默认 `deny`。
3. 所有权限必须带 `risk`。
4. 所有 memory update 必须带 `requires_approval`。

验收：

1. 没有用户确认时，不会出现高风险 `allow`。
2. 生成 AgentSpec 能通过 schema 校验。

### T7：工程文件生成稳定化

路径：

- `agent_foundry/builder/file_generator.py`
- `agent_foundry/builder/agentspec_compiler.py`
- `tests/test_file_generator.py`

任务：

1. 确保所有 agent 都生成稳定文件集。
2. `system_prompt.md` 明确权限边界和反馈规则。
3. `runbook.md` 明确运行步骤和暂停点。
4. `tool_policy.yaml`、`human_feedback.yaml`、`memory_policy.yaml` 与 `agent.yaml` 一致。

验收：

生成目录必须包含：

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

### T8：Review Agent feedback 闭环

路径：

- `agent_foundry/runtime/dry_run.py`
- `agent_foundry/runtime/feedback_engine.py`
- `agent_foundry/runtime/memory_engine.py`
- `agent_foundry/cli.py`
- `examples/svn_review/sample_diff.diff`
- `tests/test_review_feedback_loop.py`

任务：

1. dry run 输出 findings。
2. 将 findings 转成 feedback requests。
3. 支持用户提交 labels：`accepted`、`false_positive`、`too_minor`、`duplicate`、`needs_more_evidence`。
4. 根据 labels 生成 `rule_patch_proposal.md`。
5. patch proposal 明确需要审批。

验收：

1. review-agent 从 diff 到 feedback 到 rule patch 能端到端跑通。
2. 不自动写入 learned rules。

### T9：Writing Agent 选题和 style patch 闭环

路径：

- `agent_foundry/runtime/dry_run.py`
- `agent_foundry/runtime/feedback_engine.py`
- `agent_foundry/runtime/memory_engine.py`
- `examples/wechat_writer/sample_material.txt`
- `tests/test_writing_feedback_loop.py`

任务：

1. 输出 3-5 个选题。
2. 支持用户选择方向。
3. 输出大纲、初稿、发布包。
4. 根据用户反馈生成 `style_rule_patch.md`。
5. 发布相关动作始终需要显式确认。

验收：

1. writing-agent 能跑通素材 -> 发布包。
2. style patch 只作为候选，不自动写入。

### T10：Runtime Permission Engine 可执行化

路径：

- `agent_foundry/runtime/permission_engine.py`
- `agent_foundry/runtime/dry_run.py`
- `agent_foundry/cli.py`
- `tests/test_permission_engine.py`

任务：

1. 标准化 approval request。
2. 支持 `approve_once`、`reject`、`show_impact`、`add_to_whitelist`。
3. `deny` 直接拒绝并记录原因。
4. `ask` 暂停并输出审批请求。

验收：

1. 权限结果稳定可序列化。
2. Runtime 不绕过 `tool_policy`。

### T11：文档同步和验收矩阵

路径：

- `docs/index.md`
- `docs/product_principles.md`
- `docs/architecture.md`
- `docs/prespec_decision_board.md`
- `docs/agentspec_runtime.md`
- `docs/example_agents.md`
- `docs/roadmap.md`
- `docs/ultimate_task_todo.md`
- `AGENTS.md`
- `README.md`
- `PROJECT_STATUS.md`

任务：

1. 每完成一个功能 milestone，同步更新“当前状态”和“下一步”。
2. 不把目标形态写成已实现。
3. 为 MVP 增加验收矩阵，列出命令、输入、输出路径和预期结果。

验收：

1. 新 agent 能从 `AGENTS.md` 和 `docs/index.md` 找到正确入口。
2. README 命令可复制运行。

### T12：端到端验收

路径：

- 全部 `agent_foundry/`
- `tests/`
- `examples/`
- `docs/`
- `README.md`

任务：

1. 运行全部单测。
2. mock provider 跑通 review-agent 创建和 dry run。
3. mock provider 跑通 writing-agent 创建和 dry run。
4. mock provider 跑通 research-agent 创建和 dry run。
5. OpenAI provider 至少完成配置初始化测试。
6. 检查 git 状态，确认没有提交生成物。

验收命令：

```bash
python3 -m unittest discover -s tests -v
python3 -m agent_foundry.cli board "我想做一个 SVN Review Agent" --llm-provider mock --stage feedback_protocol --format cli
python3 -m agent_foundry.cli new "我想做一个 SVN Review Agent，帮我审查 diff" --llm-provider mock --accept-recommended --dry-run --output ./workspace
python3 -m agent_foundry.cli new "我想做一个微信公众号写作 Agent，帮我把素材变成文章" --llm-provider mock --accept-recommended --dry-run --output ./workspace
python3 -m agent_foundry.cli new "我想做一个竞品研究 Agent，比较 Notion、飞书多维表格、Airtable" --type research-agent --llm-provider mock --accept-recommended --dry-run --output ./workspace
git status --short --branch
```

最终输出：

- SVN Review Agent：`review_report.md`、`findings.json`、`test_suggestions.md`、`feedback_requests.json`、`rule_patch_proposal.md`。
- Writing Agent：`topic_options.md`、`topic_options.json`、`topic_selection_request.json`、`outline.md`、`article.md`、`publish_package.json`、`style_rule_patch.md`。
- Research Agent dry run：`report.md`、`sources.json`、`research_plan.md`、`feedback_requests.json`。
- Research Agent real run 协议：额外生成 `evidence_matrix.json`、`run_log.json` 和 `raw_notes/`；真实网页抓取仍在后续范围。
- 文档：source of truth 与当前实现状态一致。
- 权限：高风险动作没有静默 `allow`。

## 当前实现状态

- T0-T10 已完成代码收束，并由单测覆盖 provider、schema、Decision Graph、CLI interactive、Impact Preview、Design Card、AgentSpec 安全默认值、文件生成、review feedback、writing feedback 和 Permission Engine。
- T11 文档同步范围：`README.md`、`PROJECT_STATUS.md`、`docs/index.md`、`docs/roadmap.md`、`docs/prespec_decision_board.md`、`docs/agentspec_runtime.md` 与本文件保持 source of truth 一致。
- T12 已于 2026-05-01 通过端到端验收：61 条单测通过，mock board / review dry run / writing dry run / research dry run 通过，`permission_checks.json` 中没有 high / critical 静默 `allow`，`workspace/` 仅作为 ignored 生成物存在。
- T13-T16 已落地到第二阶段 MVP 边界：Web renderer、A2UI-compatible renderer、component catalog / action protocol、UI E2E demo。真实托管 Web UI runtime 和真实 A2UI runtime 集成仍在后续范围。

### T13：Web Renderer

路径：

- `agent_foundry/builder/decision_board.py`
- `agent_foundry/builder/models.py`
- `agent_foundry/schemas/decision_board.schema.json`
- `docs/prespec_decision_board.md`
- `docs/agentspec_runtime.md`
- `tests/test_web_renderer.py`
- 后续可新增：`agent_foundry/renderers/web_renderer.py`

任务：

1. 定义 Decision Board 到 Web view model 的稳定转换层。
2. 支持 `AgentSummaryCard`、`PresetCardGroup`、`DecisionCard`、`ImpactPreview`、`StageProgress`、`ConfirmBar`。
3. 保证 Web renderer 只渲染声明式结构，不执行任意 agent 代码。
4. 输出可被前端或静态预览消费的 JSON / HTML。
5. 为 review-agent 和 writing-agent 各准备一个 renderer fixture。

验收：

1. 同一个 `DecisionBoard` 能稳定渲染为 CLI、Markdown、HTML / Web view model。
2. Web 输出中包含推荐理由、风险等级、影响预览和确认动作。
3. Web renderer 不改变 `PreSpecSession`，只产生展示结构。

### T14：A2UI-compatible Renderer

路径：

- `agent_foundry/builder/models.py`
- `agent_foundry/builder/decision_board.py`
- `agent_foundry/schemas/decision_board.schema.json`
- `docs/prespec_decision_board.md`
- `docs/architecture.md`
- `tests/test_a2ui_renderer.py`
- 后续可新增：`agent_foundry/renderers/a2ui_renderer.py`

任务：

1. 将 Agent Foundry 自定义 `DecisionBoard` 协议映射到 A2UI-compatible declarative component tree。
2. 保持业务协议独立：`DecisionBoard` 是 source of truth，A2UI 只是渲染目标。
3. 定义字段映射：component type、props、state key、action id、risk metadata、recommendation metadata。
4. 支持至少这些组件：`AgentSummaryCard`、`PresetCardGroup`、`DecisionCard`、`ChoiceGroup`、`MultiChoiceGroup`、`TextInputWithHint`、`ImpactDiff`、`ConfirmBar`。
5. 输出 action payload schema，供客户端把用户选择回传给 `PreSpecSession`。

验收：

1. review-agent 的 `tool_permissions` 阶段能导出 A2UI-compatible JSON。
2. A2UI 输出不能丢失推荐理由、risk level、requires_input 和 affects。
3. A2UI action payload 能被后端转换为 session decision patch。

### T15：Component Catalog / Action Protocol

路径：

- `docs/prespec_decision_board.md`
- `docs/agentspec_runtime.md`
- `agent_foundry/schemas/decision_board.schema.json`
- `agent_foundry/schemas/decision_question.schema.json`
- 后续可新增：`agent_foundry/schemas/action_event.schema.json`
- 后续可新增：`agent_foundry/renderers/component_catalog.py`
- 后续可新增：`tests/test_action_protocol.py`

任务：

1. 固化 Agent Builder UI 组件 catalog。
2. 定义组件输入 props、输出 events、state key、validation rules。
3. 定义 action protocol：`select_option`、`update_text`、`confirm_stage`、`save_draft`、`show_impact`、`request_approval`。
4. 定义事件回放规则：同一 action event 可重复应用或被安全拒绝。
5. 定义错误反馈：非法选项、缺少 required input、权限升级需要确认。

验收：

1. CLI、Web、A2UI 都使用同一套 action / event 语义。
2. action event 能更新 `PreSpecSession`，并重新生成 `ImpactPreview`。
3. 非法 action 不会污染 session。

### T16：UI E2E Demo

路径：

- `agent_foundry/cli.py`
- `agent_foundry/builder/decision_board.py`
- `agent_foundry/builder/agentspec_compiler.py`
- `agent_foundry/builder/file_generator.py`
- `agent_foundry/runtime/dry_run.py`
- `examples/svn_review/sample_diff.diff`
- `examples/wechat_writer/sample_material.txt`
- `examples/ui_demo/`
- `tests/test_ui_e2e.py`
- `docs/example_agents.md`
- `docs/ultimate_task_todo.md`

任务：

1. 准备 review-agent UI demo：自然语言 -> decision board -> action events -> session -> AgentSpec -> dry run。
2. 准备 writing-agent UI demo：素材 -> topic selection -> outline / draft -> publish package -> style patch。
3. 产出 demo fixtures，包含输入、交互事件、最终 session、AgentSpec 和输出产物。
4. 记录 demo 验收命令和输出路径。
5. 确认 Web / A2UI renderer 与 CLI 共享同一业务协议。

验收：

1. 两个示例 Agent 都能用 action events 走完主链路。
2. UI 层不绕过 `tool_policy`、`human_feedback`、`memory.update_requires_approval`。
3. demo 输出可作为回归测试 fixture。

验收命令：

```bash
python3 -m unittest tests.test_ui_e2e -v
python3 -m agent_foundry.cli ui-demo --output ./workspace/ui_demo
```

## 长任务执行建议

推荐执行顺序：

```text
T0 -> T1 -> T2 -> T3 -> T4 -> T6 -> T7 -> T8 -> T9 -> T10 -> T11 -> T12 -> T13 -> T14 -> T15 -> T16
```

第二阶段终局任务已落地到 MVP 协议 / demo 层：

- T13 Web Renderer。
- T14 A2UI-compatible Renderer。
- T15 Component Catalog / Action Protocol。
- T16 UI E2E Demo。

仍可暂缓到更后面：

- 真实 SVN 调用。
- 真实公众号发布。
- 长期后台运行。

每完成一个 Task，都应至少运行：

```bash
python3 -m unittest discover -s tests -v
git status --short --branch
```

如果任务改动了用户可见 CLI 或文档 source of truth，还要同步检查：

```text
README.md
PROJECT_STATUS.md
AGENTS.md
docs/index.md
docs/roadmap.md
```
