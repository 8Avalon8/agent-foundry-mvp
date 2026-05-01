# Agent Design Card: AI 公众号写作助手

## 推荐模式

当前采用 `continuous_writer`，可在后续阶段继续细化权限、反馈和记忆策略。

LLM 推荐理由：用户想持续输出内容，低打扰半自动比纯手动更合适。

## 已确认

- 自治程度应该设为哪一档？：L2
- 文章主要偏向哪些方向？：['engineering_thinking', 'ai_usage', 'personal_practice']
- 素材可以来自哪里？：['manual_input', 'markdown_notes']
- 它应该多主动？：weekly_suggestion
- 是否允许发布到公众号？：explicit_confirmation
- 最终发布包包含哪些内容？：['article_md', 'title_options', 'summary', 'cover_prompt', 'publish_checklist']
- 选题阶段用什么反馈方式？：choice
- 初稿阶段用什么反馈方式？：report_plus_chat
- 写作风格如何学习？：approved_style_patch
- 它是按需写作，还是持续运营助手？：continuous
- 文章语气要避免哪些问题？：['empty_grandstanding', 'marketing_tone']
- 哪些风格偏好可以沉淀？：['tone', 'title_preference', 'article_structure']
- 生成 AgentSpec 前是否先跑 dry run？：yes

## 待确认

- 暂无

## 下一步

确认后可编译 AgentSpec，并生成 Agent 工程文件。
