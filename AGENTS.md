# AGENTS.md

本文件约束 `/Users/liuwenjia/GitProjects/agent_foundry_mvp` 及其子目录内的工作。

## 基本规则

- 永远使用中文回复。
- 先读当前 checkout 的真实文件，再下结论；不要只根据旧记忆或文件名猜测。
- 默认不要提交代码；用户明确要求提交时，再做 focused commit。
- 修改前先看 `git status --short --branch`，避免混入无关改动。
- 不要提交本地运行生成物、workspace 输出、`.env`、缓存目录或 `__pycache__`。

## 项目定位

这是一个 Python CLI 版 Agent Builder / Agent 蓝图生成器 MVP。核心链路是：

```text
自然语言需求 -> Intent Parser / LLM Intent Parser -> Pre-Spec Decision Board
-> PreSpecSession -> Agent Design Card -> AgentSpec v0.1 -> Agent 工程文件
-> Deterministic or LLM Dry Run
```

重要设计边界：

- LLM 负责意图理解、设计草案、动态问题、自然语言决策更新和 dry run 内容生成。
- 确定性代码负责 AgentSpec 编译、权限策略、工程文件生成和高风险动作边界。
- 高风险动作必须通过 `tool_policy` / `human_feedback` 进入 ask 或 deny；不要让 LLM 自行放行。
- Agent 不静默学习；只能生成 `rule_patch_proposal.md` 或 `style_rule_patch.md` 供用户审批。

## 目录入口

- `agent_foundry/cli.py`：CLI 入口，包含 `new`、`board`、`compile-session`、`dry-run`、`update-session`。
- `agent_foundry/builder/`：Pre-Spec session、决策板、preset、AgentSpec 编译、文件生成和 LLM builder。
- `agent_foundry/llm/`：LLM provider 抽象、mock provider、OpenAI provider 和结构化 schema。
- `agent_foundry/runtime/`：dry run、反馈、记忆和权限运行时。
- `agent_foundry/schemas/`：AgentSpec、DecisionBoard、PreSpecSession 等 JSON schema。
- `tests/`：当前测试以 `unittest` 为主。
- `docs/index.md`：文档入口和 source of truth 导航。
- `docs/product_principles.md`：产品定位与 UX 原则。
- `docs/architecture.md`：总体架构和模块职责。
- `docs/prespec_decision_board.md`：Pre-Spec 决策面板协议和分阶段决策图。
- `docs/agentspec_runtime.md`：AgentSpec、Compiler、Runtime、权限和反馈机制。
- `docs/example_agents.md`：SVN Review Agent 与微信公众号写作 Agent 的 MVP 验收。
- `docs/roadmap.md`：实施路线图、milestones 和下一步建议。
- `docs/ultimate_task_todo.md`：长任务执行清单，包含路径、任务拆分和验收命令。

## 常用命令

安装基础依赖：

```bash
python3 -m pip install -e .
```

安装 OpenAI provider 依赖：

```bash
python3 -m pip install -e '.[openai]'
```

运行测试：

```bash
python3 -m unittest discover -s tests -v
```

离线决策板：

```bash
python3 -m agent_foundry.cli board "我想做一个 SVN Review Agent" --format cli
```

Mock LLM 决策板：

```bash
python3 -m agent_foundry.cli board "我想做一个 SVN Review Agent" --llm-provider mock --stage feedback_protocol --format cli
```

Mock LLM 创建并 dry run：

```bash
python3 -m agent_foundry.cli new "我想做一个 SVN Review Agent，帮我审查 diff" --llm-provider mock --accept-recommended --dry-run --output ./workspace
```

自然语言更新 session：

```bash
python3 -m agent_foundry.cli update-session ./workspace/.agent_foundry_sessions/session_xxx.json "可以读项目上下文，但不能自动写文件；生成 patch 必须让我确认" --llm-provider mock
```

## 编码约定

- Python 目标版本为 3.10+。
- 继续使用标准库 `dataclasses`、`pathlib`、类型标注和小函数拆分的现有风格。
- JSON / YAML 读写要保留 UTF-8，并在面向用户或样例输出时用 `ensure_ascii=False`。
- Provider 相关逻辑要保持 `offline` / `mock` / `openai` 三种路径清晰可测。
- 低风险验证优先用 `mock` provider，不依赖网络或 API key。
- 涉及 OpenAI provider 时，不要硬编码 API key；使用 `OPENAI_API_KEY` 和可选 `AGENT_FOUNDRY_OPENAI_MODEL`。

## 文档维护约定

- 做产品、协议、Compiler、Runtime 或示例 Agent 方向的实质变化时，同步检查 `docs/index.md` 指向的分类文档。
- `docs/product_principles.md` 是产品体验和安全边界的 source of truth。
- `docs/prespec_decision_board.md` 是 PreSpecSession、DecisionQuestion、DecisionBoard、PresetProfile 和组件协议的 source of truth。
- `docs/agentspec_runtime.md` 是 AgentSpec v0.1、Compiler 输出、Permission Engine、Human Feedback Engine 和 Memory Engine 的 source of truth。
- `docs/roadmap.md` 是 milestone、iteration 和下一步开发顺序的 source of truth。
- `docs/ultimate_task_todo.md` 是执行长任务时的 TaskTodo source of truth。
- 不要把尚未实现的规划写成“已经支持”；文档里要区分当前状态、目标形态和下一步。

## 生成物与测试注意事项

- `workspace/`、`generated_agents/`、`.agent_foundry_sessions/` 是生成输出，默认不要提交。
- dry run 会在 agent 目录下生成 `runs/dry_run_*`，默认不要提交，除非用户明确要求保留样例。
- 新增行为优先补 `tests/` 下的 `unittest` 覆盖，尤其是 LLM mock 路径、AgentSpec 编译和 dry run 输出。
- 若变更 CLI 参数或输出结构，同步检查 `README.md`、`PROJECT_STATUS.md` 和 `docs/design_overview.md` 是否需要更新。
