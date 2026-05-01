from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_foundry.builder.agentspec_compiler import compile_agentspec
from agent_foundry.builder.conversation_orchestrator import ConversationResult, handle_user_reply, next_question, start_conversation
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
from agent_foundry.runtime.memory_engine import ALLOWED_REVIEW_LABELS, propose_memory_patch, propose_style_patch
from agent_foundry.runtime.permission_engine import check_permission
from agent_foundry.runtime.dry_run import load_agent_spec
from agent_foundry.runtime.conversation_runtime import serve_conversation_api
from agent_foundry.runtime.approval_store import record_approval_decision
from agent_foundry.runtime.review_runtime import (
    list_approvals,
    memory_apply,
    memory_reject,
    memory_review,
    resume_review_run,
    run_review_svn,
)
from agent_foundry.renderers.a2ui_renderer import board_to_a2ui_tree
from agent_foundry.renderers.action_protocol import apply_action_event
from agent_foundry.renderers.web_renderer import board_to_web_view_model, render_web_html
from agent_foundry.renderers.ui_demo import build_ui_demo


def _add_llm_args(parser: argparse.ArgumentParser, *, default_provider: str = "offline") -> None:
    parser.add_argument(
        "--llm-provider",
        choices=["offline", "mock", "openai"],
        default=default_provider,
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
    p_board.add_argument(
        "--format",
        choices=["cli", "markdown", "html", "json", "web-json", "web-html", "a2ui-json"],
        default="cli",
    )
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

    p_feedback = sub.add_parser("feedback", help="Apply review finding labels to a dry-run directory")
    p_feedback.add_argument("run_dir", type=Path)
    p_feedback.add_argument("--label", action="append", default=[], help="Finding label in the form F001=accepted")
    p_feedback.add_argument("--reason", action="append", default=[], help="Optional reason in the form F001=explanation")

    p_writing_feedback = sub.add_parser("writing-feedback", help="Apply writing-agent topic/style feedback to a dry-run directory")
    p_writing_feedback.add_argument("run_dir", type=Path)
    p_writing_feedback.add_argument("--topic", required=True, help="Selected topic number or exact topic text")
    p_writing_feedback.add_argument("--style-feedback", default="", help="Natural-language style feedback to convert into a style patch candidate")

    p_permission = sub.add_parser("permission-check", help="Check one tool against a generated agent's tool_policy")
    p_permission.add_argument("agent_dir", type=Path)
    p_permission.add_argument("tool")
    p_permission.add_argument("--payload-json", default="{}", help="Optional JSON payload for the approval request")

    p_review_svn = sub.add_parser("review-svn", help="Run a generated review-agent against an SVN working copy")
    p_review_svn.add_argument("svn_working_copy", type=Path)
    p_review_svn.add_argument("--agent", required=True, type=Path, help="Generated review-agent directory")
    p_review_svn.add_argument("--output", type=Path, default=Path("workspace/runs"), help="Output root for review_svn runs")
    _add_llm_args(p_review_svn)

    p_approvals = sub.add_parser("approvals", help="List pending approvals for a run directory")
    p_approvals.add_argument("run_dir", type=Path)

    p_approve = sub.add_parser("approve", help="Record an approval decision for a run directory")
    p_approve.add_argument("run_dir", type=Path)
    p_approve.add_argument("approval_id")
    p_approve.add_argument("--decision", required=True, choices=["approve_once", "reject", "show_impact", "add_to_whitelist"])

    p_resume = sub.add_parser("resume", help="Resume a paused review run without re-running completed steps")
    p_resume.add_argument("run_dir", type=Path)

    p_memory_review = sub.add_parser("memory-review", help="Review a run's rule_patch_proposal.md")
    p_memory_review.add_argument("run_dir", type=Path)

    p_memory_apply = sub.add_parser("memory-apply", help="Explicitly apply a rule patch proposal to learned_rules.md")
    p_memory_apply.add_argument("agent_dir", type=Path)
    p_memory_apply.add_argument("run_dir", type=Path)
    p_memory_apply.add_argument("--patch", default="rule_patch_proposal.md")

    p_memory_reject = sub.add_parser("memory-reject", help="Reject a rule patch proposal and record the reason")
    p_memory_reject.add_argument("agent_dir", type=Path)
    p_memory_reject.add_argument("run_dir", type=Path)
    p_memory_reject.add_argument("--patch", default="rule_patch_proposal.md")
    p_memory_reject.add_argument("--reason", required=True)

    p_action = sub.add_parser("apply-action", help="Apply a UI action event to a saved PreSpecSession")
    p_action.add_argument("session", type=Path)
    p_action.add_argument("event_json", help="Action event JSON string")
    p_action.add_argument("--output", type=Path, help="Optional output session path. Defaults to overwrite input session.")

    p_ui_demo = sub.add_parser("ui-demo", help="Generate deterministic UI E2E demo outputs")
    p_ui_demo.add_argument("--output", type=Path, default=Path("workspace/ui_demo"), help="Output directory for demo fixtures")

    p_chat = sub.add_parser("chat-build", help="Build an Agent through natural-language multi-turn conversation")
    p_chat.add_argument("goal", nargs="?", help="Natural language goal. Omit when continuing with --session.")
    p_chat.add_argument("--session", type=Path, help="Resume an existing conversation PreSpecSession")
    p_chat.add_argument("--reply", action="append", default=[], help="User reply for this turn. Can be repeated for scripted multi-turn use.")
    p_chat.add_argument("--type", dest="agent_type", help="Optional explicit agent type for a new conversation")
    p_chat.add_argument("--name", dest="agent_name", help="Agent folder/name override when the conversation completes")
    p_chat.add_argument("--output", type=Path, default=Path("workspace"), help="Output root for session, generated Agent, and dry run")
    p_chat.add_argument("--format", choices=["json", "a2ui-json"], default="json", help="Response shape for this conversation turn")
    p_chat.add_argument("--no-dry-run", action="store_true", help="Compile the Agent without running dry run after decisions are complete")
    _add_llm_args(p_chat)

    p_serve = sub.add_parser("serve-conversation", help="Serve Conversation Runtime API for Web/A2UI clients")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.add_argument("--output", type=Path, default=Path("workspace/conversation_api"))
    p_serve.add_argument("--no-dry-run", action="store_true", help="Compile without dry run when a conversation completes")
    _add_llm_args(p_serve)

    p_serve_web = sub.add_parser("serve-web", help="Serve the built-in Web/A2UI Agent Builder")
    p_serve_web.add_argument("--host", default="127.0.0.1")
    p_serve_web.add_argument("--port", type=int, default=8765)
    p_serve_web.add_argument("--output", type=Path, default=Path("workspace/web_builder"))
    p_serve_web.add_argument("--no-dry-run", action="store_true", help="Compile without dry run when a conversation completes")
    _add_llm_args(p_serve_web, default_provider="openai")

    p_codex_design = sub.add_parser("codex-design", help="Start a Codex handoff design session through Web/A2UI")
    p_codex_design.add_argument("goal")
    p_codex_design.add_argument("--type", dest="agent_type")
    p_codex_design.add_argument("--name", dest="agent_name")
    p_codex_design.add_argument("--host", default="127.0.0.1")
    p_codex_design.add_argument("--port", type=int, default=8765)
    p_codex_design.add_argument("--output", type=Path, default=Path("workspace/design_surface"))
    p_codex_design.add_argument("--open-web", action="store_true")
    _add_llm_args(p_codex_design, default_provider="mock")

    p_codex_status = sub.add_parser("codex-status", help="Get Codex handoff session status")
    p_codex_status.add_argument("session_id")
    p_codex_status.add_argument("--host", default="127.0.0.1")
    p_codex_status.add_argument("--port", type=int, default=8765)

    p_codex_continue = sub.add_parser("codex-continue", help="Continue a completed design into Agent Design Card and AgentSpec")
    p_codex_continue.add_argument("session_id")
    p_codex_continue.add_argument("--host", default="127.0.0.1")
    p_codex_continue.add_argument("--port", type=int, default=8765)

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
    elif args.format == "web-json":
        text = json.dumps(board_to_web_view_model(board), ensure_ascii=False, indent=2)
    elif args.format == "web-html":
        text = render_web_html(board)
    elif args.format == "a2ui-json":
        text = json.dumps(board_to_a2ui_tree(board), ensure_ascii=False, indent=2)
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
    agent_dir = generate_agent_files(
        agent_spec,
        output_root,
        prespec_session=session.to_dict(),
        design_card_markdown=design_card.to_markdown(),
    )

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
    design_card = generate_design_card(session)
    agent_dir = generate_agent_files(
        spec,
        args.output,
        prespec_session=session.to_dict(),
        design_card_markdown=design_card.to_markdown(),
    )
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


def cmd_feedback(args: argparse.Namespace) -> int:
    findings_path = args.run_dir / "findings.json"
    if not findings_path.exists():
        raise SystemExit(f"findings.json not found: {findings_path}")
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    labels = _parse_key_value_args(args.label, "--label")
    reasons = _parse_key_value_args(args.reason, "--reason")
    findings_by_id = {finding.get("id"): finding for finding in findings}
    feedback_items = []
    for finding_id, label in labels.items():
        if label not in ALLOWED_REVIEW_LABELS:
            raise SystemExit(f"Unsupported label for {finding_id}: {label}")
        finding = findings_by_id.get(finding_id, {"id": finding_id, "title": finding_id})
        feedback_items.append(
            {
                "finding_id": finding_id,
                "title": finding.get("title", finding_id),
                "label": label,
                "reason": reasons.get(finding_id, ""),
            }
        )
    if not feedback_items:
        raise SystemExit("feedback requires at least one --label F001=accepted")
    (args.run_dir / "feedback_labels.json").write_text(json.dumps(feedback_items, ensure_ascii=False, indent=2), encoding="utf-8")
    patch = propose_memory_patch(feedback_items)
    (args.run_dir / "rule_patch_proposal.md").write_text(patch, encoding="utf-8")
    print(f"Saved feedback labels: {args.run_dir / 'feedback_labels.json'}")
    print(f"Updated rule patch proposal: {args.run_dir / 'rule_patch_proposal.md'}")
    return 0


def cmd_writing_feedback(args: argparse.Namespace) -> int:
    topics_path = args.run_dir / "topic_options.json"
    if not topics_path.exists():
        raise SystemExit(f"topic_options.json not found: {topics_path}")
    topics = json.loads(topics_path.read_text(encoding="utf-8"))
    selected_topic = _resolve_topic_selection(topics, args.topic)
    selected = {"topic": selected_topic, "style_feedback": args.style_feedback}
    (args.run_dir / "selected_topic.json").write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")
    patch = propose_style_patch(selected_topic, args.style_feedback)
    (args.run_dir / "style_rule_patch.md").write_text(patch, encoding="utf-8")
    print(f"Saved selected topic: {args.run_dir / 'selected_topic.json'}")
    print(f"Updated style patch proposal: {args.run_dir / 'style_rule_patch.md'}")
    return 0


def cmd_permission_check(args: argparse.Namespace) -> int:
    spec = load_agent_spec(args.agent_dir)
    try:
        payload = json.loads(args.payload_json)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--payload-json must be valid JSON: {exc}") from exc
    decision = check_permission(spec, args.tool, payload=payload)
    print(json.dumps(decision.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_review_svn(args: argparse.Namespace) -> int:
    provider = _resolve_provider(args)
    run_dir = run_review_svn(args.svn_working_copy, args.agent, args.output, provider=provider)
    print(f"Review SVN run output: {run_dir}")
    return 0


def cmd_approvals(args: argparse.Namespace) -> int:
    print(json.dumps(list_approvals(args.run_dir), ensure_ascii=False, indent=2))
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    try:
        entry = record_approval_decision(args.run_dir, args.approval_id, args.decision)
    except (KeyError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(entry, ensure_ascii=False, indent=2))
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    print(json.dumps(resume_review_run(args.run_dir), ensure_ascii=False, indent=2))
    return 0


def cmd_memory_review(args: argparse.Namespace) -> int:
    print(memory_review(args.run_dir))
    return 0


def cmd_memory_apply(args: argparse.Namespace) -> int:
    target = memory_apply(args.agent_dir, args.run_dir, args.patch)
    print(f"Updated learned rules: {target}")
    return 0


def cmd_memory_reject(args: argparse.Namespace) -> int:
    target = memory_reject(args.agent_dir, args.run_dir, args.patch, args.reason)
    print(f"Recorded rejected rule patch: {target}")
    return 0


def cmd_apply_action(args: argparse.Namespace) -> int:
    session = load_session(args.session)
    try:
        event = json.loads(args.event_json)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"event_json must be valid JSON: {exc}") from exc
    result = apply_action_event(session, event)
    if result.status == "accepted":
        save_session(session, args.output or args.session)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_ui_demo(args: argparse.Namespace) -> int:
    manifest = build_ui_demo(args.output)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


def cmd_chat_build(args: argparse.Namespace) -> int:
    provider = _resolve_provider(args)
    output_root: Path = args.output
    output_root.mkdir(parents=True, exist_ok=True)
    session_path = args.session
    if session_path:
        session = load_session(session_path)
        result = None
    else:
        if not args.goal:
            raise SystemExit("chat-build requires a goal unless --session is provided")
        result = start_conversation(args.goal, provider=provider, explicit_type=args.agent_type)
        session = result.session
        session_path = output_root / ".agent_foundry_sessions" / f"{session.id}.json"
        save_session(session, session_path)

    replies = list(args.reply)
    if not replies:
        if result is None:
            question = next_question(session)
            result = ConversationResult(
                status="asking" if question else "ready_to_build",
                message="继续确认下一项。" if question else "关键决策已经足够明确，可以生成 Agent。",
                session=session,
                next_question=question,
            )
        print(json.dumps(_conversation_output(result, session_path, args.format), ensure_ascii=False, indent=2))
        return 0

    for reply in replies:
        result = handle_user_reply(
            session,
            reply,
            provider=provider,
            output_root=output_root,
            agent_name=args.agent_name,
            run_dry_run=not args.no_dry_run,
        )
        session = result.session
        save_session(session, session_path)
    print(json.dumps(_conversation_output(result, session_path, args.format), ensure_ascii=False, indent=2))
    return 0


def _conversation_output(result, session_path: Path, output_format: str = "json") -> Dict[str, Any]:
    data = result.to_dict()
    data["session_path"] = str(session_path)
    if output_format == "a2ui-json":
        return {
            "status": data["status"],
            "assistant_message": data["assistant_message"],
            "session_id": data["session_id"],
            "session_path": data["session_path"],
            "a2ui_tree": data["a2ui_tree"],
            "next_question": data["next_question"],
            "events": data["events"],
            "applied_updates": data["applied_updates"],
            "agent_spec_summary": data["agent_spec_summary"],
            "agent_dir": data["agent_dir"],
            "run_dir": data["run_dir"],
        }
    return data


def cmd_serve_conversation(args: argparse.Namespace) -> int:
    provider_name = getattr(args, "llm_provider", "offline")
    if getattr(args, "llm", False) and provider_name == "offline":
        provider_name = "openai"
    serve_conversation_api(
        host=args.host,
        port=args.port,
        output_root=args.output,
        provider_name=provider_name,
        model=getattr(args, "model", None),
        run_dry_run=not args.no_dry_run,
    )
    return 0


def cmd_serve_web(args: argparse.Namespace) -> int:
    provider_name = getattr(args, "llm_provider", "openai")
    if getattr(args, "llm", False):
        provider_name = "openai"
    serve_conversation_api(
        host=args.host,
        port=args.port,
        output_root=args.output,
        provider_name=provider_name,
        model=getattr(args, "model", None),
        run_dry_run=not args.no_dry_run,
        serve_web=True,
    )
    return 0


def cmd_codex_design(args: argparse.Namespace) -> int:
    base = f"http://{args.host}:{args.port}"
    started_service = False
    if not _http_health_ok(base):
        provider_name = getattr(args, "llm_provider", "mock")
        if getattr(args, "llm", False):
            provider_name = "openai"
        cmd = [
            sys.executable,
            "-m",
            "agent_foundry.cli",
            "serve-web",
            "--llm-provider",
            provider_name,
            "--host",
            args.host,
            "--port",
            str(args.port),
            "--output",
            str(args.output),
        ]
        if getattr(args, "model", None):
            cmd.extend(["--model", args.model])
        subprocess.Popen(cmd, cwd=Path.cwd(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        started_service = True
        _wait_for_http_health(base)

    payload: Dict[str, Any] = {"user_goal": args.goal}
    if args.agent_type:
        payload["agent_type"] = args.agent_type
    if args.agent_name:
        payload["agent_name"] = args.agent_name
    result = _http_json("POST", base + "/codex/start-design", payload)
    result["service_started"] = started_service
    if args.open_web:
        try:
            webbrowser.open(result["web_url"])
        except Exception:
            pass
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_codex_status(args: argparse.Namespace) -> int:
    base = f"http://{args.host}:{args.port}"
    result = _http_json("GET", base + f"/codex/session/{args.session_id}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_codex_continue(args: argparse.Namespace) -> int:
    base = f"http://{args.host}:{args.port}"
    result = _http_json("POST", base + "/codex/continue", {"session_id": args.session_id})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _http_health_ok(base: str) -> bool:
    try:
        data = _http_json("GET", base + "/health")
        return data.get("status") in {"ok", "degraded"}
    except Exception:
        return False


def _wait_for_http_health(base: str) -> None:
    deadline = time.time() + 8
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            if _http_health_ok(base):
                return
        except Exception as exc:
            last_error = exc
        time.sleep(0.1)
    raise SystemExit(f"Codex design service did not start: {last_error or base}")


def _http_json(method: str, url: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise SystemExit(body) from exc


def _resolve_topic_selection(topics: List[str], raw: str) -> str:
    if raw.isdigit():
        index = int(raw) - 1
        if 0 <= index < len(topics):
            return topics[index]
        raise SystemExit(f"Topic index out of range: {raw}")
    if raw in topics:
        return raw
    raise SystemExit(f"Unknown topic selection: {raw}")


def _parse_key_value_args(items: List[str], flag: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"{flag} expects KEY=VALUE, got: {item}")
        key, value = item.split("=", 1)
        result[key.strip()] = value.strip()
    return result


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
    if args.command == "feedback":
        return cmd_feedback(args)
    if args.command == "writing-feedback":
        return cmd_writing_feedback(args)
    if args.command == "permission-check":
        return cmd_permission_check(args)
    if args.command == "review-svn":
        return cmd_review_svn(args)
    if args.command == "approvals":
        return cmd_approvals(args)
    if args.command == "approve":
        return cmd_approve(args)
    if args.command == "resume":
        return cmd_resume(args)
    if args.command == "memory-review":
        return cmd_memory_review(args)
    if args.command == "memory-apply":
        return cmd_memory_apply(args)
    if args.command == "memory-reject":
        return cmd_memory_reject(args)
    if args.command == "apply-action":
        return cmd_apply_action(args)
    if args.command == "ui-demo":
        return cmd_ui_demo(args)
    if args.command == "chat-build":
        return cmd_chat_build(args)
    if args.command == "serve-conversation":
        return cmd_serve_conversation(args)
    if args.command == "serve-web":
        return cmd_serve_web(args)
    if args.command == "codex-design":
        return cmd_codex_design(args)
    if args.command == "codex-status":
        return cmd_codex_status(args)
    if args.command == "codex-continue":
        return cmd_codex_continue(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
