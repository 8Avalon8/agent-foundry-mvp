# Project Status — Agent Builder MVP

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
- Added conditional Decision Graph visibility with `visible_when`.
- Added interactive CLI stage flow and saved session resume.
- Added AgentSpec before/after Impact Preview diff.
- Added staged Agent Design Card with high-risk unconfirmed defaults.
- Hardened AgentSpec safety defaults: high-risk actions compile to `ask` / `deny` unless explicitly confirmed.
- Stabilized generated agent file set, including `prespec_session.json` and `agent_design_card.md`.
- Added review-agent feedback labels -> `rule_patch_proposal.md` loop.
- Added writing-agent topic selection -> `style_rule_patch.md` loop.
- Added serializable Runtime Permission Engine checks and approval requests.
- Added tests for the MVP path.
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

python3 -m agent_foundry.cli feedback ./workspace/agents/svn-reviewer/runs/dry_run_xxx \
  --label F001=accepted

python3 -m agent_foundry.cli writing-feedback ./workspace/agents/wechat-ai-writer/runs/dry_run_xxx \
  --topic 1 \
  --style-feedback "标题更克制一点"
```

## Important design choice

The LLM proposes and explains. Deterministic code still compiles and enforces:

- AgentSpec schema
- tool_policy
- human_feedback
- memory approval
- output artifacts
- project file generation
- dry-run feedback loops

## Acceptance Matrix

| Scenario | Command | Expected evidence |
| --- | --- | --- |
| Unit tests | `python3 -m unittest discover -s tests -v` | All tests pass. |
| Mock review board | `python3 -m agent_foundry.cli board "我想做一个 SVN Review Agent" --llm-provider mock --stage feedback_protocol --format cli` | Dynamic question and impact preview render. |
| Review agent E2E | `python3 -m agent_foundry.cli new "我想做一个 SVN Review Agent，帮我审查 diff" --llm-provider mock --accept-recommended --dry-run --output ./workspace` | `review_report.md`, `findings.json`, `test_suggestions.md`, `feedback_requests.json`, `rule_patch_proposal.md`. |
| Writing agent E2E | `python3 -m agent_foundry.cli new "我想做一个微信公众号写作 Agent，帮我把素材变成文章" --llm-provider mock --accept-recommended --dry-run --output ./workspace` | `topic_options.md`, `outline.md`, `article.md`, `publish_package.json`, `style_rule_patch.md`. |
| Safety | Inspect generated `agent.yaml` and `permission_checks.json` | No silent high-risk `allow`; memory updates require approval. |
| Conversation Builder | `python3 -m agent_foundry.cli chat-build "我想做一个 SVN Review Agent，帮我审查 diff" --llm-provider mock --reply "都按推荐" --format a2ui-json --output ./workspace` | Natural-language goal/reply produce Agent files, dry run, and renderable A2UI tree. |
| Conversation Runtime | `python3 -m agent_foundry.cli serve-conversation --llm-provider mock --output ./workspace/conversation_api` | Web/A2UI clients can call `/conversation/start` and `/conversation/respond`. |
| Web Builder | `python3 -m agent_foundry.cli serve-web --llm-provider mock --output ./workspace/web_builder` | Built-in Web UI renders A2UI, sends action events, visibly updates right-panel state, and produces Agent files plus dry run. |

Last verified on 2026-05-01: unit tests passed; mock board, review-agent E2E, writing-agent E2E, UI demo E2E, Conversation Builder, Conversation Runtime, Web Builder smoke, Playwright right-panel interaction, and generated permission checks passed.

## Next

T0-T16 plus the Conversation Orchestrator / Runtime API and built-in Web Builder are implemented for the MVP boundary. Remaining future work is real A2UI SDK integration, real SVN commands, real publishing, hosted deployment, and long-running background operation.

## Tests

```bash
python3 -m unittest discover -s tests -v
```
