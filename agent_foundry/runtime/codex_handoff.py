from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from agent_foundry.builder.agentspec_compiler import compile_agentspec
from agent_foundry.builder.conversation_orchestrator import (
    build_agent_from_conversation,
    conversation_a2ui_tree,
    next_question,
)
from agent_foundry.builder.decision_board import build_decision_board, refresh_visible_unresolved, save_session
from agent_foundry.builder.decision_graph import get_stage_order
from agent_foundry.builder.models import PreSpecSession
from agent_foundry.llm.provider import LLMProvider


JSONDict = Dict[str, Any]


def design_web_url(host: str, port: int, session_id: str) -> str:
    display_host = "127.0.0.1" if host in {"", "0.0.0.0", "::"} else host
    return f"http://{display_host}:{port}/design/{session_id}"


def session_artifact_paths(output_root: Path, session: PreSpecSession) -> JSONDict:
    artifacts = dict(session.metadata.get("codex_artifacts") or {})
    if artifacts:
        return artifacts
    agent_name = session.metadata.get("codex_agent_name")
    if not agent_name:
        try:
            agent_name = compile_agentspec(session).get("agent", {}).get("name")
        except Exception:
            agent_name = None
    session_dir = output_root / ".agent_foundry_sessions"
    agent_dir = output_root / "agents" / str(agent_name) if agent_name else None
    return {
        "agent_design_card_path": str(session_dir / f"{session.id}_design_card.md"),
        "agentspec_path": str(agent_dir / "agent.yaml") if agent_dir else None,
        "agent_dir": str(agent_dir) if agent_dir else None,
        "run_dir": None,
    }


def handoff_payload(
    session: PreSpecSession,
    *,
    output_root: Path,
    host: str,
    port: int,
    status_hint: Optional[str] = None,
    assistant_message: str = "",
    include_a2ui_tree: bool = True,
) -> JSONDict:
    status = resolve_status(session, output_root=output_root, status_hint=status_hint)
    board = build_decision_board(PreSpecSession.from_dict(session.to_dict()))
    missing = [question.id for question in board.questions if question.required and question.id not in session.decisions]
    all_missing = list(session.unresolved)
    paths = session_artifact_paths(output_root, session) if status == "completed" else {}
    payload: JSONDict = {
        "session_id": session.id,
        "status": status,
        "assistant_message": assistant_message or _message_for_status(status),
        "web_url": design_web_url(host, port, session.id),
        "current_stage": session.current_stage,
        "completed_stages": list(session.metadata.get("confirmed_stages", [])),
        "missing_required_questions": all_missing or missing,
        "agent_design_card_path": paths.get("agent_design_card_path"),
        "agentspec_path": paths.get("agentspec_path"),
        "agent_dir": paths.get("agent_dir"),
        "run_dir": paths.get("run_dir"),
        "summary": completed_summary(session) if status == "completed" else None,
        "next_codex_instruction": next_codex_instruction(status),
    }
    if include_a2ui_tree:
        payload["a2ui_tree"] = conversation_a2ui_tree(session)
    return payload


def resolve_status(session: PreSpecSession, *, output_root: Path, status_hint: Optional[str] = None) -> str:
    if status_hint == "completed" or _has_completed_artifacts(session, output_root):
        return "completed"
    if status_hint in {"asking", "awaiting_confirmation", "ready_to_build"}:
        return status_hint

    refresh_visible_unresolved(session)
    question = next_question(session)
    if question is not None:
        return "asking"
    board = build_decision_board(PreSpecSession.from_dict(session.to_dict()))
    if board.questions and session.current_stage not in set(session.metadata.get("confirmed_stages", [])):
        return "awaiting_confirmation"
    if not session.unresolved and _all_stages_confirmed(session):
        return "ready_to_build"
    return "asking"


def complete_design(
    session: PreSpecSession,
    *,
    output_root: Path,
    agent_name: Optional[str] = None,
    run_dry_run: bool = True,
    provider: Optional[LLMProvider] = None,
) -> JSONDict:
    if _has_completed_artifacts(session, output_root):
        return session_artifact_paths(output_root, session)
    agent_dir, run_dir = build_agent_from_conversation(
        session,
        output_root,
        agent_name=agent_name,
        run_dry_run=run_dry_run,
        provider=provider,
    )
    paths = {
        "agent_design_card_path": str(output_root / ".agent_foundry_sessions" / f"{session.id}_design_card.md"),
        "agentspec_path": str(agent_dir / "agent.yaml"),
        "agent_dir": str(agent_dir),
        "run_dir": str(run_dir) if run_dir else None,
    }
    session.metadata["codex_artifacts"] = paths
    if agent_name:
        session.metadata["codex_agent_name"] = agent_name
    save_session(session, output_root / ".agent_foundry_sessions" / f"{session.id}.json")
    return paths


def mark_completed_artifacts(
    session: PreSpecSession,
    *,
    output_root: Path,
    agent_dir: Optional[Path],
    run_dir: Optional[Path],
    agent_name: Optional[str] = None,
) -> None:
    if not agent_dir:
        return
    session.metadata["codex_artifacts"] = {
        "agent_design_card_path": str(output_root / ".agent_foundry_sessions" / f"{session.id}_design_card.md"),
        "agentspec_path": str(agent_dir / "agent.yaml"),
        "agent_dir": str(agent_dir),
        "run_dir": str(run_dir) if run_dir else None,
    }
    if agent_name:
        session.metadata["codex_agent_name"] = agent_name


def completed_summary(session: PreSpecSession) -> JSONDict:
    spec = compile_agentspec(session)
    ask_or_deny = {
        name: policy
        for name, policy in spec.get("tool_policy", {}).items()
        if policy.get("permission") in {"ask", "deny"}
    }
    return {
        "agent_name": spec.get("agent", {}).get("name", ""),
        "agent_type": spec.get("agent", {}).get("type", session.inferred_agent_type),
        "autonomy": spec.get("autonomy", {}).get("level", ""),
        "sensitive_actions": sorted(ask_or_deny),
        "human_feedback": spec.get("human_feedback", {}),
        "memory_policy": spec.get("memory", {}).get("update_policy", spec.get("memory", {}).get("mode", "")),
    }


def next_codex_instruction(status: str) -> str:
    return {
        "asking": "请让用户打开 web_url 并完成决策。",
        "awaiting_confirmation": "请让用户在 Web 面板确认当前阶段。",
        "ready_to_build": "决策已完成，请调用 /codex/continue 生成 Agent Design Card 和 AgentSpec。",
        "completed": "请读取 AgentSpec，然后按用户要求生成 demo 或实现计划。",
    }.get(status, "请检查 session 状态。")


def _message_for_status(status: str) -> str:
    return {
        "asking": "设计还在确认中。",
        "awaiting_confirmation": "当前阶段已选完，等待确认。",
        "ready_to_build": "关键设计已确认，可以生成 Agent Design Card 和 AgentSpec。",
        "completed": "Agent Design Complete。Codex 可以继续。",
    }.get(status, "Session 状态已更新。")


def _all_stages_confirmed(session: PreSpecSession) -> bool:
    confirmed = set(session.metadata.get("confirmed_stages", []))
    return set(get_stage_order(session.inferred_agent_type)).issubset(confirmed)


def _has_completed_artifacts(session: PreSpecSession, output_root: Path) -> bool:
    paths = session_artifact_paths(output_root, session)
    agentspec = paths.get("agentspec_path")
    card = paths.get("agent_design_card_path")
    return bool(agentspec and card and Path(agentspec).exists() and Path(card).exists())
