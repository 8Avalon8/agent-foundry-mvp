# Agent Foundry 文档入口

这个目录是 Agent Foundry MVP 的规划和实现导航。后续做功能、调整架构或拆任务时，优先从这里确认边界。

## 阅读顺序

1. [产品定位与 UX 原则](product_principles.md)
   - 解释这个项目为什么是 Agent 蓝图生成器，而不是 prompt 生成器。
   - 定义自然语言、交互式决策面板、AgentSpec 和人类反馈之间的产品关系。

2. [总体架构](architecture.md)
   - 描述从用户自然语言到 Runtime Harness 的完整链路。
   - 说明 Intent Parser、Agent Type Classifier、Draft Design、PreSpecSession、Compiler 和 Runtime 的职责边界。

3. [Pre-Spec 决策面板协议](prespec_decision_board.md)
   - 定义 PreSpecSession、DecisionQuestion、DecisionBoard、PresetProfile、ImpactPreview 和 AgentDesignCard。
   - 说明分阶段确认、组件 catalog、Decision Board JSON 和 CLI / Web / A2UI 渲染关系。

4. [AgentSpec、Compiler 与 Runtime](agentspec_runtime.md)
   - 定义 AgentSpec v0.1 顶层结构。
   - 说明工程文件生成、权限引擎、人类反馈引擎和记忆进化机制。

5. [首批示例 Agent](example_agents.md)
   - 定义 SVN Review Agent 和微信公众号写作 Agent 的 MVP 能力、输出和验收标准。

6. [实施路线图](roadmap.md)
   - 把计划拆成 Milestone、Iteration、近期开发顺序和 MVP 成功标准。

## 当前项目状态

当前代码已经覆盖第一条核心链路的大部分骨架：

```text
自然语言需求
  -> Intent Parser / LLM Intent Parser
  -> Pre-Spec Decision Board
  -> PreSpecSession
  -> Agent Design Card
  -> AgentSpec v0.1
  -> Agent 工程文件
  -> Deterministic or LLM Dry Run
```

可用命令见根目录 [README.md](../README.md)。规划文档描述的是目标形态和下一步收束方向；实现时以当前代码为准，低风险迭代，优先保持 mock provider 路径可测。

## Source of Truth

- 产品目标和 UX 原则：`docs/product_principles.md`
- 模块职责和链路：`docs/architecture.md`
- Pre-Spec 协议和交互面板：`docs/prespec_decision_board.md`
- AgentSpec / Compiler / Runtime：`docs/agentspec_runtime.md`
- 示例 Agent 验收：`docs/example_agents.md`
- 迭代路线：`docs/roadmap.md`

