# Agent Foundry MVP Design Overview

## 1. 产品目标

Agent Foundry 的目标不是生成一个 prompt，而是生成一套可控、可审查、可进化的 Agent 工程。

核心思路：

```text
Conversation 负责表达意图
Decision Surface 负责协商设计
AgentSpec 负责定义执行边界
Runtime Harness 负责运行和反馈
```

## 2. Pre-Spec 决策面板

Pre-Spec 阶段位于 AgentSpec 之前。它负责把“我想做一个什么 Agent”变成可确认的设计决策。

核心组件：

- AgentSummaryCard
- PresetCardGroup
- DecisionCard
- ChoiceGroup / MultiChoiceGroup
- TextInputWithHint
- PermissionMatrix
- RiskBadge
- RecommendationBadge
- ImpactPreview
- StageProgress
- ConfirmBar

## 3. 分阶段确认

阶段顺序：

1. foundation：基础目标确认
2. autonomy：自治程度确认
3. tool_permissions：工具和权限确认
4. feedback_protocol：人类反馈机制确认
5. memory_policy：记忆和进化机制确认
6. output_and_dry_run：输出格式和 dry run

## 4. AgentSpec v0.1

AgentSpec 的顶层结构：

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

## 5. 进化机制

Agent 不静默学习。它只能提出：

- rule_patch_proposal.md
- style_rule_patch.md

用户审批后才进入 learned_rules.md / style_rules.md。

## 6. A2UI 关系

本项目没有把业务协议绑定到 A2UI，而是先定义自己的 DecisionBoard JSON。

后续可以把 DecisionBoard 适配到 A2UI：

```text
DecisionBoard JSON -> A2UI declarative components -> Web / Mobile / Desktop renderers
```
