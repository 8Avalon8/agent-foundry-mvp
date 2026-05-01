# 首批示例 Agent

## 示例一：SVN Review Agent

SVN Review Agent 是最适合做 MVP 的 Agent。

原因：

1. 输入明确：`svn diff` 或用户提供的 diff 文本。
2. 输出明确：review report。
3. 反馈明确：采纳、误报、太小、重复、证据不足。
4. 权限容易控制：读、测、写、commit。
5. 适合验证 rule patch 机制。

### MVP 能力

第一版不需要真的接 SVN，可以先用用户提供的 diff 文本。

能力：

1. 读取用户提供的 diff。
2. 生成 review 报告。
3. 每条 finding 有风险等级、证据、建议和置信度。
4. 用户可以标记每条 finding。
5. 根据反馈生成 `rule_patch_proposal.md` 候选，不自动写入 `learned_rules.md`。

### 输出产物

```text
review_report.md
findings.json
test_suggestions.md
optional_patch.diff
rule_patch_proposal.md
feedback_requests.json
```

### 推荐默认配置

```yaml
agent_type: review-agent
selected_preset: controlled_semi_auto
autonomy:
  level: L2
tool_policy:
  svn.diff:
    permission: allow
  fs.read:
    permission: allow
    scope: current_project
  code.search:
    permission: allow
    scope: current_project
  shell.run_tests:
    permission: ask
  fs.write_patch:
    permission: deny
  fs.modify_source:
    permission: ask
  svn.commit:
    permission: deny
human_feedback:
  finding_feedback:
    mode: inline_label
    options:
      - accepted
      - false_positive
      - too_minor
      - duplicate
      - needs_more_evidence
memory:
  update_requires_approval: true
output:
  artifacts:
    - review_report.md
    - findings.json
    - test_suggestions.md
    - rule_patch_proposal.md
```

### Dry Run 验收

输入一段模拟 diff 后，系统应输出：

1. 发现的问题。
2. 风险等级。
3. 代码证据。
4. 建议测试点。
5. 用户可打标签的 finding 列表。
6. 候选 rule patch，且明确需要审批。

### 后续增强

1. 自动调用 `svn diff`。
2. 搜索相关源码。
3. 运行测试。
4. 生成 patch。
5. 接入项目规则库。
6. 统计误报率和采纳率。

## 示例二：微信公众号写作 Agent

微信公众号写作 Agent 用于验证创作型 Agent、风格记忆、选题反馈和发布包输出。

原因：

1. 可以验证创作型 Agent。
2. 可以验证风格记忆。
3. 可以验证选择式反馈。
4. 可以验证发布包输出。
5. 可以验证长期低打扰提醒机制。

### MVP 能力

1. 用户输入一条素材。
2. Agent 生成 3-5 个选题。
3. 用户选择一个方向。
4. Agent 生成大纲。
5. 用户反馈。
6. Agent 生成初稿。
7. 输出发布包。
8. 提出风格规则更新建议。

### 输出产物

```text
article.md
topic_options.md
outline.md
summary.md
cover_prompt.md
publish_checklist.md
style_rule_patch.md
```

### 推荐默认配置

```yaml
agent_type: writing-agent
selected_preset: continuous_writer
autonomy:
  level: L2
tool_policy:
  read_notes:
    permission: ask_or_allow
  write_draft:
    permission: ask
  external_publish:
    permission: deny
human_feedback:
  topic_selection:
    mode: choice
    options_count: 3-5
  outline_review:
    mode: structured_comment
  draft_review:
    mode: report_plus_chat
  before_publish:
    mode: explicit_approval
    required_phrase: "确认发布"
  style_rule_update:
    mode: diff_review
    requires_explicit_approval: true
memory:
  long_term_candidates:
    - writing_style_preferences
    - repeated_revision_patterns
  update_requires_approval: true
output:
  artifacts:
    - article.md
    - title_options.md
    - summary.md
    - cover_prompt.md
    - publish_checklist.md
    - style_rule_patch.md
```

### Dry Run 验收

输入素材：

```text
AI review 最有价值的不是找 bug，而是逼我显式化规则。
```

系统应输出：

1. 选题建议。
2. 推荐标题。
3. 大纲。
4. 初稿片段。
5. 发布包预览。
6. 候选 style rule patch，且明确需要审批。

### 后续增强

1. 读取本地 Markdown 笔记。
2. 管理选题池。
3. 每周推荐选题。
4. 生成 HTML 预览。
5. 接入飞书。
6. 接入公众号发布前检查。
