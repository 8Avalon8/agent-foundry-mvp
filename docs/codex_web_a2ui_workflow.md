# Codex Web/A2UI Workflow

这是当前项目主线：Agent Design Surface MVP。

## 1. Codex 启动服务

```bash
python -m agent_foundry.cli serve-web \
  --llm-provider mock \
  --host 127.0.0.1 \
  --port 8765 \
  --output ./workspace/design_surface
```

也可以让 CLI 自动探测服务并启动：

```bash
python -m agent_foundry.cli codex-design "我想做一个 SVN Review Agent，帮我审查 diff" \
  --llm-provider mock \
  --host 127.0.0.1 \
  --port 8765 \
  --output ./workspace/design_surface \
  --open-web
```

## 2. Codex 提交用户需求

Codex 调用：

```text
POST /codex/start-design
```

服务返回 `session_id`、`assistant_message`、`a2ui_tree` 和 session 专属 `web_url`。

## 3. 用户在 Web/A2UI 上选择

用户打开：

```text
http://127.0.0.1:8765/design/session_xxx
```

页面会直接加载当前 session 的 A2UI 决策面板。

当前聚焦两个 demo agent：

- SVN Review Agent
- 微信公众号写作 Agent

面板包含 summary、preset、decision cards、推荐理由、风险提示、影响字段、Impact Preview 和确认按钮。

## 4. Codex 检查状态

```bash
python -m agent_foundry.cli codex-status session_xxx \
  --host 127.0.0.1 \
  --port 8765
```

或者直接调用：

```text
GET /codex/session/session_xxx
```

## 5. 完成后继续

```bash
python -m agent_foundry.cli codex-continue session_xxx \
  --host 127.0.0.1 \
  --port 8765
```

完成后返回：

- Agent Design Card 路径
- AgentSpec 路径
- agent_dir
- summary
- next_codex_instruction

Codex 之后读取 AgentSpec，再按用户要求生成 demo、实现计划或下一步工程改动。

## 6. 当前边界

这不是完整 Agent Harness。

当前不会做：

- 真实 `svn diff` runtime 主线
- 真实 shell 测试自动执行
- 真实 patch apply
- 真实 SVN commit
- 真实公众号发布
- 飞书 API
- memory apply / learned_rules 自动合并

所有高风险动作仍必须通过 `tool_policy` 和 `human_feedback` 进入 ask 或 deny。
