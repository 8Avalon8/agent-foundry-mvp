# UI Demo Fixtures

This directory documents the second-phase UI demo entry point. Generated demo outputs are written to `workspace/ui_demo` by default so they stay out of Git.

```bash
python3 -m agent_foundry.cli ui-demo --output ./workspace/ui_demo
```

The command generates two deterministic scenarios:

- `review_agent`: natural-language goal -> DecisionBoard -> action events -> PreSpecSession -> AgentSpec -> dry run.
- `writing_agent`: material/writing goal -> DecisionBoard -> action events -> PreSpecSession -> AgentSpec -> dry run.

Each scenario writes:

- `events.json`
- `final_session.json`
- `agent_spec.json`
- `final_web_view_model.json`
- `final_a2ui_tree.json`
- generated Agent files under `agents/`
- dry run outputs under `runs/dry_run_demo/`
