# Codex Goal: Agent Foundry v0.2 Runnable Harness MVP

## Mission

Upgrade the current repository `8Avalon8/agent-foundry-mvp` from an **Agent Builder + dry-run MVP** into a **v0.2 Runnable Harness MVP**.

The project already knows how to design an agent:

```text
Natural language goal
→ LLM/offline intent parser
→ Pre-Spec Decision Board
→ PreSpecSession
→ Agent Design Card
→ AgentSpec v0.1
→ generated agent files
→ deterministic / LLM dry run
```

This goal is to make the first generated agent type, `review-agent`, actually useful in a real controlled workflow.

The new target flow is:

```text
Generated review-agent
→ real SVN working copy
→ read svn diff
→ parse changed files
→ read bounded file context
→ load learned_rules.md
→ run review analysis
→ write review outputs
→ collect finding feedback
→ propose rule patch
→ user explicitly applies or rejects patch
→ learned_rules.md is updated only after explicit approval
→ next review run loads learned_rules.md
```

The final result should prove that Agent Foundry is no longer only a blueprint generator. It should become a minimal, controlled, runnable harness for SVN review.

---

## Current Repository Context

The repository already contains these capabilities and they must continue to work:

- Offline deterministic Agent Builder.
- LLM Provider abstraction.
- Mock LLM Provider.
- OpenAI Provider.
- LLM-backed intent parsing.
- LLM-backed Pre-Spec design brief.
- LLM-generated dynamic decision questions.
- Natural-language session update command.
- Review / writing / research dry runs.
- Conditional Decision Graph visibility.
- Interactive CLI stage flow and saved session resume.
- AgentSpec before/after impact preview diff.
- Staged Agent Design Card.
- AgentSpec safety defaults.
- Generated agent file set.
- Review feedback label → `rule_patch_proposal.md` candidate.
- Writing feedback → `style_rule_patch.md` candidate.
- Runtime Permission Engine checks and approval requests.
- Conversation Builder.
- Conversation Runtime API.
- Built-in Web Builder.
- A2UI-compatible renderer.

Do not break existing commands:

```bash
python3 -m agent_foundry.cli board "我想做一个 SVN Review Agent" --format cli
python3 -m agent_foundry.cli new "我想做一个 SVN Review Agent，帮我审查 diff" --llm-provider mock --accept-recommended --dry-run --output ./workspace
python3 -m agent_foundry.cli chat-build "我想做一个 SVN Review Agent，帮我审查 diff" --llm-provider mock --reply "都按推荐" --format a2ui-json --output ./workspace
python3 -m agent_foundry.cli dry-run ./workspace/agents/svn-reviewer --llm-provider mock
python3 -m agent_foundry.cli feedback ./workspace/agents/svn-reviewer/runs/dry_run_xxx --label F001=accepted
python3 -m agent_foundry.cli writing-feedback ./workspace/agents/wechat-ai-writer/runs/dry_run_xxx --topic 1 --style-feedback "标题更克制一点"
python3 -m agent_foundry.cli serve-conversation --llm-provider mock --output ./workspace/conversation_api
python3 -m agent_foundry.cli serve-web --llm-provider mock --output ./workspace/web_builder
```

---

## Non-Goals

Do not implement these in this goal:

- Real WeChat publishing.
- Feishu API integration.
- Full frontend rewrite.
- Full official A2UI SDK integration.
- Long-running daemon.
- Multi-agent collaboration.
- Automatic SVN commit.
- Automatic source-code modification.
- Arbitrary shell execution.
- Complex database persistence.
- Cloud deployment.
- Large unrelated architecture rewrite.

Focus only on making `review-agent` runnable against a real or fixture SVN working copy under strict permission control.

---

## Safety Principles

The implementation must preserve these rules:

1. The LLM may propose, summarize, and analyze, but it must not bypass `tool_policy`.
2. Sensitive actions must be controlled by `allow / ask / deny`.
3. `svn.commit` must remain `deny` by default.
4. Automatic source-code modification must remain disabled by default.
5. Running tests must require approval unless explicitly whitelisted and confirmed.
6. Long-term memory updates must never be silent.
7. `learned_rules.md` may only be updated by an explicit `memory-apply` command.
8. Subprocess calls must never use `shell=True`.
9. Runtime logs must not dump unbounded source code or secrets.
10. All errors should be explicit and understandable.

---

# Required Work

## 1. Add Minimal Capability Registry / Tool Registry

Add a minimal capability and tool registry to support review-agent execution.

Suggested files:

```text
agent_foundry/runtime/capability_registry.py
agent_foundry/runtime/tool_registry.py
```

At minimum, support these capabilities:

```text
read_svn_diff
read_svn_status
parse_diff_files
read_files
search_code
generate_review_report
collect_human_feedback
propose_rule_patch
apply_memory_patch
```

Each registered tool should declare:

```text
tool_id
capability
policy_key
risk
side_effect: true / false
description
```

Example shape:

```python
ToolDefinition(
    tool_id="svn.diff",
    capability="read_svn_diff",
    policy_key="svn.diff",
    risk="low",
    side_effect=False,
    description="Read svn diff from a working copy."
)
```

Acceptance criteria:

- A review-agent's `required_capabilities` can be mapped to available tools.
- Missing capability produces a clear error.
- The registry is deterministic and testable.
- The LLM cannot invent arbitrary tools outside the registry.

---

## 2. Add Real SVN Tool Layer

Add:

```text
agent_foundry/tools/svn_tools.py
```

Implement:

```python
find_svn_working_copy_root(path: Path) -> Path
run_svn_diff(repo_path: Path, paths: Optional[List[str]] = None) -> str
run_svn_status(repo_path: Path) -> str
parse_changed_files_from_diff(diff_text: str) -> List[str]
read_changed_file_context(repo_path: Path, changed_files: List[str], max_bytes_per_file: int = 20000) -> Dict[str, str]
```

Command constraints:

- Only allow explicit SVN commands needed by this goal:
  - `svn info`
  - `svn diff`
  - `svn status`
- Use `subprocess.run([...])` with list args.
- Do not use `shell=True`.
- Always set `cwd`.
- Always set `timeout`.
- Capture stdout and stderr.
- Return or raise structured errors.
- If the path is not an SVN working copy, fail clearly.

Context reading constraints:

- Only read files inside the SVN working copy root.
- Prevent path traversal.
- Bound file context with `max_bytes_per_file`.
- Return truncation metadata somewhere in the runtime output.
- Do not silently read unrelated files.

Tests should use fake subprocess / monkeypatch. They should not require a real SVN installation.

---

## 3. Add Real Review Runtime

Add:

```text
agent_foundry/runtime/review_runtime.py
```

Add CLI:

```bash
python3 -m agent_foundry.cli review-svn ./path/to/svn-working-copy \
  --agent ./workspace/agents/svn-reviewer \
  --output ./workspace/runs \
  --llm-provider mock
```

Installed-script form should also work:

```bash
agent-foundry review-svn ./path/to/svn-working-copy \
  --agent ./workspace/agents/svn-reviewer \
  --output ./workspace/runs \
  --llm-provider mock
```

Runtime steps:

1. Load `agent.yaml` from the generated agent directory.
2. Validate `agent.agent.type == review-agent`.
3. Load and enforce `tool_policy`.
4. Resolve required capabilities through the registry.
5. Check permission for `svn.diff`.
6. Run `svn diff` if allowed.
7. Parse changed files.
8. Check permission for `fs.read` and `code.search`.
9. Read bounded changed-file context.
10. Load `learned_rules.md` if it exists.
11. Run review analysis:
    - If an LLM provider is available, use structured JSON output.
    - If no LLM provider is available or the LLM path fails, use the existing heuristic analyzer.
12. Write all outputs to a new run directory:

```text
runs/review_svn_YYYYMMDD_HHMMSS/
  review_report.md
  findings.json
  feedback_requests.json
  test_suggestions.md
  rule_patch_proposal.md
  run_log.json
  permission_checks.json
  context_snapshot.json
  pending_approvals.json
  approval_log.jsonl
```

Important runtime constraints:

- Do not modify source files.
- Do not write patches into the working copy.
- Do not run `svn commit`.
- Do not run tests automatically.
- If test execution would be useful and `shell.run_tests.permission == ask`, create a pending approval instead of executing.
- If any tool is `deny`, do not execute it; record the denial.

---

## 4. Improve Permission Engine with Run State, Pending Approvals, and Resume

Add or extend:

```text
agent_foundry/runtime/run_state.py
agent_foundry/runtime/approval_store.py
agent_foundry/runtime/permission_engine.py
```

Each run directory should have:

```text
run_state.json
pending_approvals.json
approval_log.jsonl
```

Add CLI commands:

```bash
agent-foundry approvals ./workspace/runs/review_svn_xxx
agent-foundry approve ./workspace/runs/review_svn_xxx approval_id --decision approve_once
agent-foundry approve ./workspace/runs/review_svn_xxx approval_id --decision reject
agent-foundry resume ./workspace/runs/review_svn_xxx
```

For this goal, `resume` can be minimal:

- If there are no pending approvals, print `no pending approvals`.
- If an approval was rejected, record it and do not execute the step.
- If an approval was approved once, mark the step as approved.
- Do not re-run completed steps.
- Keep state deterministic and serializable.

Approval request format should include:

```text
id
type
tool
risk
reason
payload
options
created_at
status
```

Supported decisions:

```text
approve_once
reject
show_impact
add_to_whitelist
```

Acceptance criteria:

- `ask` never silently executes.
- `deny` always refuses and logs the reason.
- Approval decisions are appended to `approval_log.jsonl`.
- `resume` is safe and idempotent.

---

## 5. Implement Rule Patch Review / Apply / Reject

The current feedback flow can generate `rule_patch_proposal.md`. Add explicit memory commands.

Add CLI:

```bash
agent-foundry memory-review ./workspace/runs/review_svn_xxx
agent-foundry memory-apply ./workspace/agents/svn-reviewer ./workspace/runs/review_svn_xxx --patch rule_patch_proposal.md
agent-foundry memory-reject ./workspace/agents/svn-reviewer ./workspace/runs/review_svn_xxx --reason "too broad"
```

Behavior:

### `memory-review`

- Read `rule_patch_proposal.md` from the run directory.
- Print a clear summary.
- If missing or empty, fail clearly.

### `memory-apply`

- Require explicit user command.
- Append the proposed patch to:

```text
agent_dir/learned_rules.md
```

- Append metadata to:

```text
agent_dir/memory_log.jsonl
```

Each log entry should include:

```text
applied_at
source_run
patch_file
approval_required: true
approved_by_user: true
```

### `memory-reject`

- Append rejection metadata to:

```text
agent_dir/rejected_rule_patches.jsonl
```

Each rejection should include:

```text
rejected_at
source_run
reason
patch_file
```

Rules:

- Do not auto-apply patches after feedback.
- Do not let the LLM modify `learned_rules.md` directly.
- Do not overwrite existing learned rules.
- Preserve append-only history.

---

## 6. Make Review Runtime Use `learned_rules.md`

When `agent_dir/learned_rules.md` exists:

- Load it during `review-svn`.
- Include it in the LLM review prompt.
- Record it in `run_log.json`.
- Record it in `context_snapshot.json` under `loaded_memory_files`.

If using heuristic review:

- It is acceptable not to deeply apply every rule.
- Still record that learned rules were loaded.

`context_snapshot.json` should avoid dumping large source content. Prefer:

```json
{
  "changed_files": [...],
  "loaded_memory_files": [...],
  "file_context": {
    "src/foo.py": {
      "bytes": 1234,
      "truncated": false
    }
  }
}
```

---

## 7. CLI Enhancements

Add these commands to `agent_foundry/cli.py`:

```text
review-svn
approvals
approve
resume
memory-review
memory-apply
memory-reject
```

Requirements:

- Keep existing CLI commands intact.
- All path arguments should use `Path`.
- Help text should be clear.
- On failure, raise `SystemExit` with a useful message.
- New commands must work with `python3 -m agent_foundry.cli ...` and installed `agent-foundry ...`.

---

## 8. Tests

Add or update tests:

```text
tests/test_svn_tools.py
tests/test_review_runtime_svn.py
tests/test_run_state_approvals.py
tests/test_memory_apply.py
tests/test_capability_registry.py
```

Test coverage must include:

1. Fake `svn diff` returns diff text successfully.
2. Fake `svn status` works.
3. Changed files are parsed correctly from diff.
4. Non-SVN working copy gives a clear error.
5. SVN command timeout / stderr error path is handled.
6. `review-svn` generates a full run directory.
7. Run directory includes:

```text
review_report.md
findings.json
feedback_requests.json
test_suggestions.md
rule_patch_proposal.md
run_log.json
permission_checks.json
context_snapshot.json
pending_approvals.json
approval_log.jsonl
```

8. `ask` permission generates pending approval and does not execute.
9. `deny` permission refuses and logs reason.
10. `approve` writes `approval_log.jsonl`.
11. `resume` is idempotent.
12. `memory-review` displays patch summary.
13. `memory-apply` updates `learned_rules.md` and `memory_log.jsonl`.
14. `memory-reject` updates `rejected_rule_patches.jsonl`.
15. A second `review-svn` run loads `learned_rules.md` and records it in `run_log.json`.
16. Existing tests still pass.

Final test command:

```bash
python3 -m unittest discover -s tests -v
```

---

## 9. Documentation Updates

Update:

```text
README.md
PROJECT_STATUS.md
docs/roadmap.md
docs/agentspec_runtime.md
docs/example_agents.md
```

Documentation must say:

- v0.2 adds real SVN Review Runtime.
- `review-agent` can now read real `svn diff` from a working copy.
- Source modification is still not automatic.
- `svn commit` remains denied.
- Shell tests still require approval unless explicitly whitelisted.
- Rule patches require explicit `memory-apply`.
- `learned_rules.md` is loaded by subsequent review runs.
- Real WeChat / Feishu / publishing / long-running daemon are still future work.

Do not describe unimplemented features as completed.

---

# Required Acceptance Commands

After implementation, these commands should work.

## Run all tests

```bash
python3 -m unittest discover -s tests -v
```

## Generate a review-agent

```bash
python3 -m agent_foundry.cli new "我想做一个 SVN Review Agent，帮我审查 diff" \
  --llm-provider mock \
  --accept-recommended \
  --dry-run \
  --output ./workspace
```

## Run real or fixture SVN review

```bash
python3 -m agent_foundry.cli review-svn ./tests/fixtures/fake_svn_working_copy \
  --agent ./workspace/agents/svn-reviewer \
  --output ./workspace/runs \
  --llm-provider mock
```

## Inspect approvals

```bash
python3 -m agent_foundry.cli approvals ./workspace/runs/review_svn_xxx
```

## Reject a pending approval

```bash
python3 -m agent_foundry.cli approve ./workspace/runs/review_svn_xxx approval_shell_run_tests --decision reject
```

## Resume safely

```bash
python3 -m agent_foundry.cli resume ./workspace/runs/review_svn_xxx
```

## Submit finding feedback

```bash
python3 -m agent_foundry.cli feedback ./workspace/runs/review_svn_xxx \
  --label F001=accepted \
  --label F002=false_positive \
  --reason F002="该对象由上游工厂保证非空"
```

## Review memory patch

```bash
python3 -m agent_foundry.cli memory-review ./workspace/runs/review_svn_xxx
```

## Apply memory patch explicitly

```bash
python3 -m agent_foundry.cli memory-apply ./workspace/agents/svn-reviewer ./workspace/runs/review_svn_xxx \
  --patch rule_patch_proposal.md
```

## Run review again and verify learned rules are loaded

```bash
python3 -m agent_foundry.cli review-svn ./tests/fixtures/fake_svn_working_copy \
  --agent ./workspace/agents/svn-reviewer \
  --output ./workspace/runs \
  --llm-provider mock
```

The second run's `run_log.json` must show that `learned_rules.md` was loaded.

---

# Final Deliverable Format

When finished, provide a concise final report with:

1. Summary of what changed.
2. New files added.
3. Existing files modified.
4. New CLI commands.
5. Test result.
6. Example run directory path and generated artifacts.
7. Remaining limitations.

Do not claim that WeChat, Feishu, full A2UI SDK, real publishing, automatic source modification, or long-running daemon support has been implemented unless actually implemented.

---

# Success Definition

This goal is complete only when the repository has moved from:

```text
Can design an Agent and dry-run it
```

to:

```text
Can run a generated review-agent against a real or fixture SVN working copy,
produce review outputs,
collect feedback,
explicitly apply rule patches,
and load learned rules in the next review run.
```
