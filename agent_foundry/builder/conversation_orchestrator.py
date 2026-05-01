from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_foundry.llm.provider import LLMProvider

from .agentspec_compiler import compile_agentspec
from .decision_board import (
    advance_stage,
    apply_recommended_defaults,
    build_decision_board,
    create_session,
    generate_design_card,
    save_session,
)
from .file_generator import generate_agent_files
from .llm_builder import apply_natural_language_update, create_session_with_llm
from .models import DecisionQuestion, PreSpecSession
from .presets import get_recommended_preset
from agent_foundry.renderers.a2ui_renderer import board_to_a2ui_tree
from agent_foundry.renderers.action_protocol import apply_action_event
from agent_foundry.runtime.dry_run import dry_run


JSONDict = Dict[str, Any]


@dataclass
class ConversationResult:
    status: str
    message: str
    session: PreSpecSession
    next_question: Optional[DecisionQuestion] = None
    events: List[JSONDict] = field(default_factory=list)
    applied_updates: List[JSONDict] = field(default_factory=list)
    a2ui_tree: Optional[JSONDict] = None
    agent_dir: Optional[Path] = None
    run_dir: Optional[Path] = None

    def to_dict(self) -> JSONDict:
        a2ui_tree = self.a2ui_tree if self.a2ui_tree is not None else conversation_a2ui_tree(self.session)
        return {
            "status": self.status,
            "assistant_message": self.message,
            "message": self.message,
            "session_id": self.session.id,
            "session": self.session.to_dict(),
            "next_question": self.next_question.to_dict() if self.next_question else None,
            "a2ui_tree": a2ui_tree,
            "events": self.events,
            "applied_updates": self.applied_updates,
            "agent_spec_summary": agent_spec_summary(self.session) if self.status in {"completed", "ready_to_build"} else None,
            "agent_dir": str(self.agent_dir) if self.agent_dir else None,
            "run_dir": str(self.run_dir) if self.run_dir else None,
        }


def start_conversation(user_goal: str, provider: Optional[LLMProvider] = None, explicit_type: Optional[str] = None) -> ConversationResult:
    if provider is not None:
        session = create_session_with_llm(user_goal, provider=provider, explicit_type=explicit_type, apply_recommended_preset=False)
    else:
        session = create_session(user_goal, explicit_type=explicit_type)
    session.metadata["conversation_mode"] = True
    if not session.selected_preset:
        try:
            session.selected_preset = get_recommended_preset(session.inferred_agent_type).id
        except Exception:
            pass
    return _asking_result(session, "我先理解了目标，接下来需要确认一个关键问题。")


def handle_user_reply(
    session: PreSpecSession,
    reply: str,
    *,
    provider: Optional[LLMProvider] = None,
    output_root: Optional[Path] = None,
    agent_name: Optional[str] = None,
    run_dry_run: bool = True,
) -> ConversationResult:
    session.metadata["conversation_mode"] = True
    session.metadata.setdefault("conversation_turns", []).append({"role": "user", "content": reply})
    events: List[JSONDict] = []
    applied_updates: List[JSONDict] = []

    if _accepts_all_recommended(reply):
        before = set(session.decisions)
        apply_recommended_defaults(session, include_all_stages=True)
        applied_updates.extend({"question_id": key, "source": "recommended_accepted"} for key in sorted(set(session.decisions) - before))
    else:
        question = next_question(session)
        if question is not None:
            event = event_from_natural_reply(session, question, reply)
            if event is not None:
                result = apply_action_event(session, event)
                events.append(result.to_dict())
                if result.status != "accepted":
                    return ConversationResult(
                        status="needs_clarification",
                        message=result.message,
                        session=session,
                        next_question=question,
                        events=events,
                    )
        if provider is not None:
            update = apply_natural_language_update(session, provider, reply)
            applied_updates = list(update.get("applied", []))

    _advance_past_completed_stages(session)
    question = next_question(session)
    if question is not None:
        return ConversationResult(
            status="asking",
            message=_question_prompt(question),
            session=session,
            next_question=question,
            events=events,
            applied_updates=applied_updates,
        )
    if output_root is None:
        return ConversationResult(
            status="ready_to_build",
            message="关键决策已经足够明确，可以编译 AgentSpec 并生成 dry run。",
            session=session,
            events=events,
            applied_updates=applied_updates,
        )
    agent_dir, run_dir = build_agent_from_conversation(session, output_root, agent_name=agent_name, run_dry_run=run_dry_run, provider=provider)
    return ConversationResult(
        status="completed",
        message="关键决策已确认，AgentSpec、Agent 工程和 dry run 已生成。",
        session=session,
        events=events,
        applied_updates=applied_updates,
        agent_dir=agent_dir,
        run_dir=run_dir,
    )


def handle_action_event(
    session: PreSpecSession,
    event: JSONDict,
    *,
    output_root: Optional[Path] = None,
    agent_name: Optional[str] = None,
    run_dry_run: bool = True,
    provider: Optional[LLMProvider] = None,
) -> ConversationResult:
    session.metadata["conversation_mode"] = True
    result = apply_action_event(session, event)
    if result.status == "rejected":
        return ConversationResult(
            status="needs_clarification",
            message=result.message,
            session=session,
            next_question=next_question(session),
            events=[result.to_dict()],
        )
    if result.status == "requires_approval":
        return ConversationResult(
            status="requires_approval",
            message=result.message,
            session=session,
            next_question=next_question(session),
            events=[result.to_dict()],
        )
    _advance_past_completed_stages(session)
    question = next_question(session)
    if question is not None:
        return ConversationResult(
            status="asking",
            message=_question_prompt(question),
            session=session,
            next_question=question,
            events=[result.to_dict()],
        )
    if output_root is None:
        return ConversationResult(
            status="ready_to_build",
            message="关键决策已经足够明确，可以编译 AgentSpec 并生成 dry run。",
            session=session,
            events=[result.to_dict()],
        )
    agent_dir, run_dir = build_agent_from_conversation(session, output_root, agent_name=agent_name, run_dry_run=run_dry_run, provider=provider)
    return ConversationResult(
        status="completed",
        message="关键决策已确认，AgentSpec、Agent 工程和 dry run 已生成。",
        session=session,
        events=[result.to_dict()],
        agent_dir=agent_dir,
        run_dir=run_dir,
    )


def build_agent_from_conversation(
    session: PreSpecSession,
    output_root: Path,
    *,
    agent_name: Optional[str] = None,
    run_dry_run: bool = True,
    provider: Optional[LLMProvider] = None,
) -> tuple[Path, Optional[Path]]:
    output_root.mkdir(parents=True, exist_ok=True)
    session_dir = output_root / ".agent_foundry_sessions"
    save_session(session, session_dir / f"{session.id}.json")
    design_card = generate_design_card(session)
    (session_dir / f"{session.id}_design_card.md").write_text(design_card.to_markdown(), encoding="utf-8")
    spec = compile_agentspec(session, agent_name=agent_name)
    agent_dir = generate_agent_files(
        spec,
        output_root,
        prespec_session=session.to_dict(),
        design_card_markdown=design_card.to_markdown(),
    )
    run_dir = dry_run(agent_dir, provider=provider) if run_dry_run else None
    return agent_dir, run_dir


def conversation_a2ui_tree(session: PreSpecSession) -> JSONDict:
    return board_to_a2ui_tree(build_decision_board(PreSpecSession.from_dict(session.to_dict())))


def agent_spec_summary(session: PreSpecSession) -> JSONDict:
    spec = compile_agentspec(session)
    return {
        "agent": spec.get("agent", {}),
        "tool_policy": spec.get("tool_policy", {}),
        "human_feedback": spec.get("human_feedback", {}),
        "memory": spec.get("memory", {}),
        "output": spec.get("output", {}),
    }


def next_question(session: PreSpecSession) -> Optional[DecisionQuestion]:
    _advance_past_completed_stages(session)
    board = build_decision_board(session)
    for question in board.questions:
        if question.required and question.id not in session.decisions:
            return question
    return None


def event_from_natural_reply(session: PreSpecSession, question: DecisionQuestion, reply: str) -> Optional[JSONDict]:
    value = _value_from_reply(question, reply)
    if value is None:
        return None
    action = "update_text" if question.input_type == "text_input" else "select_option"
    payload: JSONDict = {"question_id": question.id, "value": value}
    inputs = _inputs_from_reply(question, value, reply)
    if inputs:
        payload["inputs"] = inputs
    return {"action": action, "session_id": session.id, "payload": payload}


def _asking_result(session: PreSpecSession, prefix: str) -> ConversationResult:
    question = next_question(session)
    if question is None:
        return ConversationResult(status="ready_to_build", message="关键决策已经足够明确，可以生成 Agent。", session=session)
    return ConversationResult(status="asking", message=f"{prefix}\n{_question_prompt(question)}", session=session, next_question=question)


def _question_prompt(question: DecisionQuestion) -> str:
    lines = [question.title]
    if question.recommendation_reason:
        lines.append(f"推荐：{question.recommended}。{question.recommendation_reason}")
    if question.options:
        lines.append("可选：" + " / ".join(f"{option.id}={option.label}" for option in question.options))
    return "\n".join(lines)


def _advance_past_completed_stages(session: PreSpecSession) -> None:
    while True:
        board = build_decision_board(session)
        missing = [question.id for question in board.questions if question.required and question.id not in session.decisions]
        if missing:
            return
        if not advance_stage(session):
            return


def _accepts_all_recommended(reply: str) -> bool:
    lowered = reply.strip().lower()
    return any(token in lowered for token in ["都按推荐", "全部按推荐", "按推荐", "accept recommended", "use recommended", "defaults"])


def _value_from_reply(question: DecisionQuestion, reply: str) -> Any:
    raw = reply.strip()
    if not raw:
        return question.recommended
    lowered = raw.lower()
    approval_phrases = {"推荐", "默认", "按推荐", "用推荐", "可以", "ok", "yes", "好的", "好", "行"}
    if lowered in approval_phrases or raw in approval_phrases:
        return question.recommended
    if question.input_type == "text_input":
        return raw
    if not question.options:
        return raw
    matches = []
    for option in question.options:
        haystacks = [option.id.lower(), option.label.lower()]
        if any(item and item in lowered for item in haystacks):
            matches.append(option.id)
    if not matches and raw.isdigit():
        index = int(raw) - 1
        if 0 <= index < len(question.options):
            matches.append(question.options[index].id)
    if question.input_type == "multi_choice":
        return matches or None
    return matches[0] if matches else None


def _inputs_from_reply(question: DecisionQuestion, value: Any, reply: str) -> JSONDict:
    selected = value if isinstance(value, list) else [value]
    inputs: JSONDict = {}
    for option in question.options:
        if option.id not in selected or not option.requires_input:
            continue
        input_id = option.requires_input.get("id")
        if not input_id:
            continue
        marker = f"{input_id}="
        if marker in reply:
            inputs[input_id] = reply.split(marker, 1)[1].strip()
        elif question.input_type == "text_input":
            inputs[input_id] = reply.strip()
        elif option.id in reply:
            inputs[input_id] = reply.strip()
    return inputs
