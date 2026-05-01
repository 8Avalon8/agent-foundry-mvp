from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from agent_foundry.builder.agentspec_compiler import compile_agentspec
from agent_foundry.builder.decision_board import build_decision_board, create_session, generate_design_card, save_session
from agent_foundry.builder.decision_graph import get_stage_order
from agent_foundry.builder.file_generator import generate_agent_files
from agent_foundry.builder.models import DecisionQuestion, PreSpecSession
from agent_foundry.renderers.a2ui_renderer import board_to_a2ui_tree
from agent_foundry.renderers.action_protocol import apply_action_event
from agent_foundry.renderers.web_renderer import board_to_web_view_model
from agent_foundry.runtime.dry_run import dry_run


JSONDict = Dict[str, Any]


DEMO_SCENARIOS = [
    {
        "id": "review_agent",
        "goal": "我想做一个 SVN Review Agent，帮我审查 diff",
        "agent_name": "svn-reviewer-ui-demo",
    },
    {
        "id": "writing_agent",
        "goal": "我想做一个微信公众号写作 Agent，帮我把素材变成文章",
        "agent_name": "wechat-ai-writer-ui-demo",
    },
]


def build_ui_demo(output_root: Path) -> JSONDict:
    output_root.mkdir(parents=True, exist_ok=True)
    scenarios = []
    for scenario in DEMO_SCENARIOS:
        scenarios.append(_build_scenario(output_root, scenario))
    manifest = {
        "schema": "agent_foundry.ui_demo.v0.1",
        "scenarios": scenarios,
    }
    (output_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _build_scenario(output_root: Path, scenario: JSONDict) -> JSONDict:
    scenario_dir = output_root / scenario["id"]
    scenario_dir.mkdir(parents=True, exist_ok=True)
    session = create_session(scenario["goal"])
    initial_board = build_decision_board(PreSpecSession.from_dict(session.to_dict()))
    events = _recommended_events(session)

    final_board = build_decision_board(PreSpecSession.from_dict(session.to_dict()))
    agent_spec = compile_agentspec(session, agent_name=scenario["agent_name"])
    design_card = generate_design_card(session)
    agent_dir = generate_agent_files(
        agent_spec,
        scenario_dir,
        prespec_session=session.to_dict(),
        design_card_markdown=design_card.to_markdown(),
    )
    run_dir = dry_run(agent_dir, output_dir=agent_dir / "runs" / "dry_run_demo")

    save_session(session, scenario_dir / "final_session.json")
    _write_json(scenario_dir / "events.json", events)
    _write_json(scenario_dir / "initial_web_view_model.json", board_to_web_view_model(initial_board))
    _write_json(scenario_dir / "final_web_view_model.json", board_to_web_view_model(final_board))
    _write_json(scenario_dir / "final_a2ui_tree.json", board_to_a2ui_tree(final_board))
    _write_json(scenario_dir / "agent_spec.json", agent_spec)

    return {
        "id": scenario["id"],
        "goal": scenario["goal"],
        "events": str((scenario_dir / "events.json").relative_to(output_root)),
        "final_session": str((scenario_dir / "final_session.json").relative_to(output_root)),
        "agent_spec": str((scenario_dir / "agent_spec.json").relative_to(output_root)),
        "web_view_model": str((scenario_dir / "final_web_view_model.json").relative_to(output_root)),
        "a2ui_tree": str((scenario_dir / "final_a2ui_tree.json").relative_to(output_root)),
        "agent_dir": str(agent_dir.relative_to(output_root)),
        "dry_run": str(run_dir.relative_to(output_root)),
    }


def _recommended_events(session: PreSpecSession) -> List[JSONDict]:
    events: List[JSONDict] = []
    for stage in get_stage_order(session.inferred_agent_type):
        session.current_stage = stage
        while True:
            board = build_decision_board(PreSpecSession.from_dict(session.to_dict()))
            pending = [question for question in board.questions if question.id not in session.decisions]
            if not pending:
                break
            question = pending[0]
            event = _event_for_question(session, question)
            events.append(event)
            result = apply_action_event(session, event)
            if result.status != "accepted":
                raise RuntimeError(f"Unable to apply generated event: {result.to_dict()}")
        confirm = {"action": "confirm_stage", "session_id": session.id, "payload": {"stage": stage}}
        events.append(confirm)
        result = apply_action_event(session, confirm)
        if result.status != "accepted":
            raise RuntimeError(f"Unable to confirm stage: {result.to_dict()}")
    return events


def _event_for_question(session: PreSpecSession, question: DecisionQuestion) -> JSONDict:
    value = _recommended_value(question)
    if question.input_type == "text_input":
        return {"action": "update_text", "session_id": session.id, "payload": {"question_id": question.id, "value": str(value)}}
    payload: JSONDict = {"question_id": question.id, "value": value}
    inputs = _inputs_for_value(question, value)
    if inputs:
        payload["inputs"] = inputs
    return {"action": "select_option", "session_id": session.id, "payload": payload}


def _recommended_value(question: DecisionQuestion) -> Any:
    if question.recommended is not None:
        return question.recommended
    if question.default is not None:
        return question.default
    recommended_options = [option.id for option in question.options if option.recommended]
    if question.input_type == "multi_choice":
        return recommended_options or [option.id for option in question.options[:1]]
    if recommended_options:
        return recommended_options[0]
    if question.options:
        return question.options[0].id
    return question.placeholder or "demo"


def _inputs_for_value(question: DecisionQuestion, value: Any) -> JSONDict:
    selected = value if isinstance(value, list) else [value]
    inputs: JSONDict = {}
    for option in question.options:
        if option.id not in selected or not option.requires_input:
            continue
        input_id = option.requires_input["id"]
        inputs[input_id] = _demo_input_value(input_id)
    return inputs


def _demo_input_value(input_id: str) -> str:
    return {
        "test_command_whitelist": "python3 -m unittest discover -s tests -v",
        "context_custom_scope": "agent_foundry/**, tests/**",
        "notes_path": "examples/wechat_writer/sample_material.txt",
    }.get(input_id, "demo")


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
