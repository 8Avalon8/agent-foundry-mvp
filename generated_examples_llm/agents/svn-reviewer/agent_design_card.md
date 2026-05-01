# Agent Design Card: SVN Review Agent

## 推荐模式

当前采用 `controlled_semi_auto`，可在后续阶段继续细化权限、反馈和记忆策略。

LLM 推荐理由：代码审查需要上下文和一定自动化，但写入和命令执行要保留人工确认。

## 已确认

- 自治程度应该设为哪一档？：L2
- Agent 可以读取多大范围的上下文？：project_search
- 是否允许运行测试命令？：ask
- 是否允许生成 patch？：suggestion_only
- 是否允许直接修改源码？：ask
- 最终输出形式是什么？：markdown_report
- Review 结果应该如何收集反馈？：inline_labels
- Agent 如何沉淀经验？：approved_rule_patch
- Review 重点是什么？：['bug_risk', 'maintainability', 'test_impact']
- 这个 Agent 是按需运行，还是长期监控？：on_demand
- Agent 最多连续自循环几轮后必须汇报？：3
- 敏感动作审批时应该怎么展示？：risk_card_with_reason
- Review 报告需要多强的证据要求？：line_and_reason
- 哪些内容允许进入长期记忆？：['accepted_patterns', 'false_positive_patterns', 'project_rules']
- 生成 AgentSpec 前是否先跑 dry run？：yes

## 待确认

- 暂无

## 下一步

确认后可编译 AgentSpec，并生成 Agent 工程文件。
