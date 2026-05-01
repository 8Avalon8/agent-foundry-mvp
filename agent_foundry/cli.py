from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_foundry.builder.agentspec_compiler import compile_agentspec
from agent_foundry.builder.decision_board import (
    advance_stage,
    apply_preset,
    apply_recommended_defaults,
    build_decision_board,
    create_session,
    generate_design_card,
    load_session,
    render_board_cli,
    render_board_html,
    render_board_markdown,
    save_session,
)
from agent_foundry.builder.decision_graph import get_stage_order
from agent_foundry.builder.file_generator import generate_agent_files
from agent_foundry.builder.llm_builder import apply_natural_language_update, create_session_with_llm
from agent_foundry.llm import LLMProviderError, provider_from_name
from agent_foundry.runtime.dry_run import dry_run


def _add_llm_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--llm-provider",
        choices=["offline", "mock", "openai"],
        default="offline",
        help="LLM provider for intent/design/dry-run. `offline` keeps deterministic template mode.",
    )
    parser.add_argument("--llm", action="store_true", help="Shortcut for --llm-provider openai unless provider is explicitly set.")
    parser.add_argument("--model", help="Optional provider model override, e.g. gpt-5.5")


def _resolve_provider(args: argparse.Namespace):
    provider_name = getattr(args, "llm_provider", "offline")
    if getattr(args, "llm", False) and provider_name == "offline":
        provider_name = "openai"
    try:
        return provider_from_name(provider_name, model=getattr(args, "model", None))
    except LLMProviderError as exc:
        raise SystemExit(f"LLM provider error: {exc}") from exc


def _create_session_for_args(args: argparse.Namespace):
    provider = _resolve_provider(args)
    if provider is not None:
        session = create_session_with_llm(args.goal, provider=provider, explicit_type=getattr(args, "agent_type", None))
        if getattr(args, "preset", None):
            apply_preset(session, args.preset)
        return session, provider
    session = create_session(args.goal, explicit_type=getattr(args, "agent_type", None))
    apply_preset(session, getattr(args, "preset", None))
    return session, None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-foundry",
        description="Pre-Spec decision-board driven Agent Builder MVP with optional LLM Builder Brain",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Create a new Agent through Pre-Spec decisions")
    p_new.add_argument("goal", nargs="?", help="Natural language goal, e.g. '我想做一个 SVN Review Agent'")
    p_new.add_argument("--type", dest="agent_type", help="Optional explicit agent type, e.g. review-agent")
    p_new.add_argument("--name", dest="agent_name", help="Agent folder/name override")
    p_new.add_argument("--output", type=Path, default=Path("."), help="Output root directory")
    p_new.add_argument("--preset", help="Preset id. If omitted, recommended preset is used.")
    p_new.add_argument("--accept-recommended", action="store_true", help="Accept recommended defaults for all questions without prompting")
    p_new.add_argument("--interactive", action="store_true", help="Prompt for decisions stage by stage")
    p_new.add_argument("--html-board", action="store_true", help="Generate design_board.html next to session files")
    p_new.add_argument("--dry-run", action="store_true", help="Run a dry run after generating agent files")
    p_new.add_argument("--apply-instruction", help="Natural-language configuration override, e.g. '可以读项目，但不能自动写文件'")
    p_new.add_argument("--session", type=Path, help="Resume from a saved PreSpecSession instead of creating a new one")
    _add_llm_args(p_new)

    p_board = sub.add_parser("board", help="Render a Pre-Spec decision board without generating files")
    p_board.add_argument("goal")
    p_board.add_argument("--type", dest="agent_type")
    p_board.add_argument("--preset")
    p_board.add_argument("--stage", help="Optional stage id, e.g. tool_permissions or feedback_protocol")
    p_board.add_argument("--format", choices=["cli", "markdown", "html", "json"], default="cli")
    p_board.add_argument("--output", type=Path, help="Output file for html/json/markdown")
    _add_llm_args(p_board)

    p_compile = sub.add_parser("compile-session", help="Compile a saved PreSpecSession into AgentSpec and files")
    p_compile.add_argument("session", type=Path)
    p_compile.add_argument("--name", dest="agent_name")
    p_compile.add_argument("--output", type=Path, default=Path("."))

    p_dry = sub.add_parser("dry-run", help="Run dry-run for an existing generated agent")
    p_dry.add_argument("agent_dir", type=Path)
    p_dry.add_argument("--sample", type=Path, help="Sample diff/material path")
    p_dry.add_argument("--output", type=Path, help="Dry-run output directory")
    _add_llm_args(p_dry)

    p_update = sub.add_parser("update-session", help="Apply a natural-language instruction to a saved PreSpecSession")
    p_update.add_argument("session", type=Path)
    p_update.add_argument("instruction", help="Natural language change, e.g. '可以读文件，但写文件前必须问我'")
    p_update.add_argument("--output", type=Path, help="Optional output session path. Defaults to overwrite input session.")
    _add_llm_args(p_update)

    return parser


def cmd_board(args: argparse.Namespace) -> int:
    session, _provider = _create_session_for_args(args)
    if getattr(args, "stage", None):
        session.current_stage = args.stage
    board = build_decision_board(session)
    if args.format == "cli":
        text = render_board_cli(board)
    elif args.format == "markdown":
        text = render_board_markdown(board)
    elif args.format == "html":
        text = render_board_html(board)
    else:
        text = json.dumps(board.to_dict(), ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(text)
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    output_root: Path = args.output
    output_root.mkdir(parents=True, exist_ok=True)
    session_dir = output_root / ".agent_foundry_sessions"
    if args.session:
        session = load_session(args.session)
        provider = _resolve_provider(args)
        session_path = args.session
    else:
        if not args.goal:
            raise SystemExit("new requires a goal unless --session is provided")
        session, provider = _create_session_for_args(args)
        session_path = session_dir / f"{session.id}.json"

    if provider is not None and args.apply_instruction:
        result = apply_natural_language_update(session, provider, args.apply_instruction)
        print("LLM decision update:")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    # Always generate first board from current state.
    board = build_decision_board(session)
    print(render_board_cli(board))

    if args.interactive and not args.accept_recommended:
        _interactive_collect(session, session_path=session_path)
    else:
        apply_recommended_defaults(session, include_all_stages=True)

    save_session(session, session_path)

    if args.html_board:
        html = render_board_html(build_decision_board(session))
        (session_dir / f"{session.id}_design_board.html").write_text(html, encoding="utf-8")

    design_card = generate_design_card(session)
    design_card_path = session_dir / f"{session.id}_design_card.md"
    design_card_path.write_text(design_card.to_markdown(), encoding="utf-8")

    agent_spec = compile_agentspec(session, agent_name=args.agent_name)
    agent_dir = generate_agent_files(agent_spec, output_root)
    (agent_dir / "prespec_session.json").write_text(json.dumps(session.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (agent_dir / "agent_design_card.md").write_text(design_card.to_markdown(), encoding="utf-8")

    print(f"\nGenerated AgentSpec and files at: {agent_dir}")
    print(f"Saved PreSpecSession: {session_path}")
    print(f"Saved Agent Design Card: {design_card_path}")

    if args.dry_run or session.get_value("dry_run_enabled", "yes") == "yes":
        run_dir = dry_run(agent_dir, provider=provider)
        print(f"Dry run output: {run_dir}")

    return 0


def _interactive_collect(session, session_path: Optional[Path] = None) -> None:
    stages = get_stage_order(session.inferred_agent_type)
    try:
        start_idx = stages.index(session.current_stage)
    except ValueError:
        start_idx = 0
    for stage in stages[start_idx:]:
        session.current_stage = stage
        confirmed_stages = set(session.metadata.get("interactive_confirmed_stages", []))
        answered_by_stage = session.metadata.setdefault("interactive_answered_questions", {})
        answered_questions = set(answered_by_stage.get(stage, []))
        while True:
            board = build_decision_board(session)
            if stage in confirmed_stages:
                pending_questions = []
            else:
                pending_questions = [q for q in board.questions if q.id not in answered_questions]
            if not pending_questions:
                print(render_board_cli(board))
                break
            print(render_board_cli(board))
            for q in pending_questions:
                default = session.get_value(q.id, q.recommended)
                raw = input(f"{q.id} [{_format_default(default)}]: ").strip()
                value, source = _parse_interactive_value(q, raw, default)
                inputs = _collect_option_inputs(q, value, source, session)
                session.apply_decision(q.id, value, source=source, inputs=inputs)
                answered_questions.add(q.id)
                answered_questions.update(inputs.keys())
                answered_by_stage[stage] = sorted(answered_questions)
                if session_path:
                    save_session(session, session_path)
                break
        if stage not in confirmed_stages:
            confirmed_stages.add(stage)
            session.metadata["interactive_confirmed_stages"] = [item for item in stages if item in confirmed_stages]
        if session_path:
            save_session(session, session_path)
            _save_design_card_snapshot(session, session_path)
            print(f"Saved stage `{stage}` session: {session_path}")
        if stage != stages[-1]:
            cont = input("确认本阶段并进入下一阶段？[Y/n] ").strip().lower()
            if cont in ["n", "no"]:
                break
            advance_stage(session)
            if session_path:
                save_session(session, session_path)
                _save_design_card_snapshot(session, session_path)


def _format_default(default: Any) -> str:
    if isinstance(default, list):
        return ",".join(str(item) for item in default)
    return "" if default is None else str(default)


def _save_design_card_snapshot(session, session_path: Path) -> None:
    card_path = session_path.with_name(f"{session.id}_design_card.md")
    card_path.write_text(generate_design_card(session).to_markdown(), encoding="utf-8")


def _parse_interactive_value(q, raw: str, default: Any) -> tuple[Any, str]:
    if not raw:
        return default, "recommended_accepted"
    value_text = raw
    if "=" in value_text:
        maybe_id, maybe_value = value_text.split("=", 1)
        if maybe_id.strip() == q.id:
            value_text = maybe_value.strip()
    if q.input_type == "multi_choice":
        return [_parse_option_token(q, token) for token in _split_multi_value(value_text)], "user_selected"
    if q.options:
        return _parse_option_token(q, value_text), "user_selected"
    return value_text, "user_selected"


def _split_multi_value(raw: str) -> List[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _parse_option_token(q, token: str) -> str:
    if token.isdigit() and q.options:
        index = int(token) - 1
        if 0 <= index < len(q.options):
            return q.options[index].id
    normalized = token.strip().lower()
    for opt in q.options:
        if normalized in {opt.id.lower(), opt.label.lower()}:
            return opt.id
    return token.strip()


def _collect_option_inputs(q, value: Any, source: str, session) -> Dict[str, Any]:
    inputs: Dict[str, Any] = {}
    selected_values = value if isinstance(value, list) else [value]
    for opt in q.options:
        if opt.id in selected_values and opt.requires_input:
            placeholder = opt.requires_input.get("placeholder", "")
            supplemental = input(f"  {opt.requires_input['id']} ({placeholder}): ").strip()
            if supplemental:
                input_id = opt.requires_input["id"]
                inputs[input_id] = supplemental
                if input_id not in session.decisions:
                    session.apply_decision(input_id, supplemental, source=source)
    return inputs


def cmd_compile_session(args: argparse.Namespace) -> int:
    session = load_session(args.session)
    spec = compile_agentspec(session, agent_name=args.agent_name)
    agent_dir = generate_agent_files(spec, args.output)
    (agent_dir / "prespec_session.json").write_text(json.dumps(session.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated: {agent_dir}")
    return 0


def cmd_dry_run(args: argparse.Namespace) -> int:
    provider = _resolve_provider(args)
    run_dir = dry_run(args.agent_dir, sample_input=args.sample, output_dir=args.output, provider=provider)
    print(f"Dry run output: {run_dir}")
    return 0


def cmd_update_session(args: argparse.Namespace) -> int:
    provider = _resolve_provider(args)
    if provider is None:
        raise SystemExit("update-session requires --llm-provider mock or --llm-provider openai")
    session = load_session(args.session)
    result = apply_natural_language_update(session, provider, args.instruction)
    out = args.output or args.session
    save_session(session, out)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Saved updated session: {out}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "new":
        return cmd_new(args)
    if args.command == "board":
        return cmd_board(args)
    if args.command == "compile-session":
        return cmd_compile_session(args)
    if args.command == "dry-run":
        return cmd_dry_run(args)
    if args.command == "update-session":
        return cmd_update_session(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
