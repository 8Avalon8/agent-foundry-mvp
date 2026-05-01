# Project Status — LLM Upgrade

## Delivered

- Offline deterministic Agent Builder remains available.
- Added LLM Provider abstraction.
- Added Mock LLM Provider for local demos and tests.
- Added OpenAI Provider using structured JSON responses.
- OpenAI Provider now supports `OPENAI_BASE_URL` for OpenAI-compatible gateways.
- Added LLM-backed intent parsing.
- Added LLM-backed Pre-Spec design brief.
- Added LLM-generated dynamic decision questions.
- Added natural-language session update command.
- Added LLM dry run for review-agent and writing-agent.
- Added tests for the LLM upgrade path.
- Added long-task planning source of truth at `docs/ultimate_task_todo.md`.

## Key commands

```bash
python3 -m agent_foundry.cli board "我想做一个 SVN Review Agent" --format cli

python3 -m agent_foundry.cli board "我想做一个 SVN Review Agent" \
  --llm-provider mock \
  --stage feedback_protocol \
  --format cli

python3 -m agent_foundry.cli new "我想做一个 SVN Review Agent，帮我审查 diff" \
  --llm-provider mock \
  --accept-recommended \
  --dry-run \
  --output ./workspace

python3 -m agent_foundry.cli update-session ./workspace/.agent_foundry_sessions/session_xxx.json \
  "可以读项目上下文，但不能自动写文件；生成 patch 必须让我确认" \
  --llm-provider mock
```

## Important design choice

The LLM proposes and explains. Deterministic code still compiles and enforces:

- AgentSpec schema
- tool_policy
- human_feedback
- memory approval
- output artifacts
- project file generation

## Tests

```bash
python3 -m unittest discover -s tests -v
```
