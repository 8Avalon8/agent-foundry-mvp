# 总体架构

## 核心链路

Agent Foundry 的主链路是：

```text
用户自然语言需求
  -> Intent Parser：理解用户想做什么 Agent
  -> Agent Type Classifier：判断 Agent 类型
  -> Draft Design：生成初步设计草案
  -> Pre-Spec Decision Board：可交互决策面板
  -> PreSpecSession：保存用户选择和未确认项
  -> Conversation Orchestrator：自然语言多轮追问和 action event 回放
  -> Conversation Runtime API：每轮返回 assistant_message + A2UI tree
  -> Built-in Web Builder：渲染 A2UI 并回传 action event
  -> Agent Design Card：阶段性确认卡
  -> AgentSpec v0.1：正式 Agent 蓝图
  -> Compiler：编译成工程文件
  -> Runtime Harness：运行 Agent
  -> Human Feedback Loop：采集反馈
  -> Rule Patch / Memory Patch：提出进化建议
```

最关键的产品体验是：

```text
自然语言 -> 可交互决策面板 -> 自然语言多轮确认 -> AgentSpec
```

## 模块职责

### Intent Parser

目标：把用户一句自然语言需求转成初步意图。

输入示例：

```text
我想做一个帮我审查 SVN diff 的 Agent
```

输出目标：

```yaml
user_goal: "帮我审查 SVN diff"
domain: "code_review"
likely_agent_type: "review-agent"
risk_level: "medium"
requires_tools:
  - read_svn_diff
  - read_files
  - search_code
  - generate_report
possible_side_effects:
  - run_tests
  - write_patch
  - modify_files
```

MVP 做法：

- offline 模式可以先用规则式推断。
- LLM 模式输出结构化 JSON。
- 输出必须进入确定性校验和后续 Pre-Spec 决策，不直接生成最终权限。

### Agent Type Classifier

初期支持 7 类 Agent：

1. `writing-agent`：写作、公众号、博客、剧情创作、文案。
2. `review-agent`：SVN review、代码审查、文档审查、设定审查。
3. `coding-agent`：代码生成、重构、修复 bug、脚本开发。
4. `research-agent`：技术调研、资料整理、竞品分析。
5. `automation-agent`：批处理、文件整理、日常自动化。
6. `monitor-agent`：定时检查、提醒、日报、周报。
7. `hybrid-agent`：混合型，需要进一步拆分。

review-agent 默认推荐：

```yaml
default_autonomy: controlled_semi_auto
default_output: markdown_report
default_feedback: finding_labels
default_memory: approved_rule_patch
default_permissions:
  read: allow
  write: ask
  shell: ask
  external_publish: deny
```

writing-agent 默认推荐：

```yaml
default_autonomy: low_interrupt_semi_auto
default_output: publish_package
default_feedback: choice_then_chat
default_memory: style_rule_patch
default_permissions:
  read_notes: ask_or_allow
  write_draft: ask
  external_publish: deny
  publish: explicit_approval
```

### Draft Design

Draft Design 负责把意图、类型和 preset 组合成“专业草案”。它不要求用户先回答所有问题，而是先提出可确认的初始方案。

草案应该包含：

- Agent 类型和风险等级。
- 推荐 preset。
- 关键能力。
- 默认权限边界。
- 需要用户确认的少量问题。
- 推荐原因。

### Pre-Spec Decision Board

Pre-Spec Decision Board 是核心交互层。它把草案变成可交互、可分阶段确认的决策面板。

它的业务协议不绑定具体 UI 技术。渲染目标可以包括：

- CLI renderer
- Markdown renderer
- Web renderer
- A2UI-compatible renderer

核心协议见 [Pre-Spec 决策面板协议](prespec_decision_board.md)。

### PreSpecSession

PreSpecSession 是 Pre-Spec 流程的状态中心，负责记录：

- 用户目标。
- 推断的 Agent 类型。
- 当前阶段。
- 用户已确认的决策。
- 未确认项。
- 影响预览。
- 生成过的设计卡。

### AgentSpec v0.1

AgentSpec 是正式蓝图，只有用户完成 Pre-Spec 确认后才生成。它定义：

- Agent 基本信息。
- 目标和生命周期。
- 自治等级。
- 输入。
- 工具能力。
- 工具权限。
- 人类反馈机制。
- 记忆策略。
- 输出产物。
- 评估指标。

### Compiler

Compiler 把 AgentSpec 编译成工程文件：

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

### Runtime Harness

Runtime Harness 的 MVP 职责：

1. 读取 AgentSpec。
2. 加载工具权限。
3. 执行 runbook 或 dry run。
4. 遇到 `ask` 权限时暂停。
5. 等待用户确认。
6. 生成输出产物。
7. 记录用户反馈。
8. 生成 rule patch 建议。

Research Agent 的 dry run 只模拟研究计划、报告、来源字段和反馈请求；真实 Research run 需要额外生成 `evidence_matrix.json`、`run_log.json` 和 `raw_notes/`。真实网页抓取不在当前 MVP Runtime Harness 范围内。

## LLM 与确定性代码分工

LLM 负责：

- 意图理解。
- 设计草案生成。
- 动态问题生成。
- 自然语言决策更新。
- dry run 内容生成。

确定性代码负责：

- schema 校验。
- AgentSpec 编译。
- tool_policy allow / ask / deny。
- 工程目录生成。
- 高风险动作边界。
- Rule Patch / Style Patch 审批要求。

原则：LLM 可以提案和解释，但不能绕过权限策略。
