# Codex Handoff Protocol

Codex Handoff 是 Codex 与 Agent Foundry 服务之间的固定协议。

当前目标不是让 Codex 直接生成 AgentSpec，而是让 Codex 启动或连接服务，把用户目标交给服务，然后让用户在 Web/A2UI 面板完成设计选择。

## Endpoints

### POST /codex/start-design

输入：

```json
{
  "user_goal": "我想做一个 SVN Review Agent，帮我审查 diff",
  "agent_type": "optional",
  "agent_name": "optional"
}
```

输出包含：

```json
{
  "session_id": "session_xxx",
  "status": "asking",
  "assistant_message": "string",
  "web_url": "http://127.0.0.1:8765/design/session_xxx",
  "a2ui_tree": {},
  "next_codex_instruction": "请让用户打开 web_url 并完成决策。"
}
```

### GET /codex/session/{session_id}

返回当前设计状态、缺失问题、Web URL 和完成后的产物路径。

状态值：

- `asking`
- `awaiting_confirmation`
- `ready_to_build`
- `completed`

### POST /codex/continue

输入：

```json
{
  "session_id": "session_xxx"
}
```

如果设计还没完成，返回当前 Web URL 和缺失问题。

如果状态是 `ready_to_build`，服务会生成 Agent Design Card、AgentSpec 和 Agent 工程文件。

如果已经完成，直接返回已有产物路径。

## Boundary

Codex Handoff 只覆盖设计闭环：

```text
自然语言需求
  -> Codex handoff
  -> Web/A2UI 决策面板
  -> Agent Design Card
  -> AgentSpec
  -> Codex 继续实现
```

它不执行真实 SVN commit，不自动运行任意 shell，不真实发布公众号，也不静默合并长期记忆。
