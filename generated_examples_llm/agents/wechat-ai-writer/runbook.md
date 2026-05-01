# Runbook: wechat-ai-writer

## 标准流程

1. 收集素材：手动输入、指定笔记、链接或摘要。
2. 聚类素材，生成 3-5 个选题方向。
3. 等待用户选择或调整方向。
4. 生成大纲，并标注文章意图、读者收益和示例。
5. 写初稿，并自检是否空泛、营销腔或缺少真实实践。
6. 根据反馈修改，生成发布包。
7. 提出 style_rule_patch.md，等待审批后写入 style_rules.md。

## 人类检查点

- `topic_selection`: {'mode': 'choice', 'options_count': '3-5'}
- `outline_review`: {'mode': 'structured_comment'}
- `draft_review`: {'mode': 'report_plus_chat'}
- `before_publish`: {'mode': 'explicit_approval', 'required_phrase': '确认发布'}
- `style_rule_update`: {'mode': 'diff_review', 'requires_approval': True}
