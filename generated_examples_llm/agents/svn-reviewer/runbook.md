# Runbook: svn-reviewer

## 标准流程

1. 收集输入：SVN diff、相关源码、项目规则、历史反馈。
2. 根据 tool_policy 决定上下文读取范围。
3. 从变更中提取风险点：逻辑、空值、边界、回归、测试影响、可维护性。
4. 为每条 finding 提供位置、证据、风险等级、置信度和建议。
5. 生成 review_report.md、findings.json、test_suggestions.md。
6. 用户对 finding 打标签：accepted / false_positive / too_minor / duplicate / needs_more_evidence。
7. 根据反馈提出 rule_patch_proposal.md，等待审批后写入 learned_rules.md。

## 人类检查点

- `finding_feedback`: {'mode': 'inline_labels', 'options': ['accepted', 'false_positive', 'too_minor', 'duplicate', 'needs_more_evidence']}
- `before_run_tests`: {'mode': 'approval', 'show_command': True, 'when': 'tool_policy.shell.run_tests.permission == ask'}
- `before_sensitive_action`: {'mode': 'risk_card_with_reason'}
- `rule_update`: {'mode': 'diff_review', 'requires_approval': True}
