from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agent_foundry.builder.decision_board import advance_stage, build_decision_board
from agent_foundry.builder.models import DecisionQuestion, PreSpecSession
from agent_foundry.renderers.component_catalog import ACTION_TYPES


JSONDict = Dict[str, Any]


@dataclass
class ActionResult:
    status: str
    action: str
    message: str = ""
    session_id: str = ""
    payload: JSONDict = field(default_factory=dict)
    errors: List[JSONDict] = field(default_factory=list)

    def to_dict(self) -> JSONDict:
        return {
            "status": self.status,
            "action": self.action,
            "message": self.message,
            "session_id": self.session_id,
            "payload": self.payload,
            "errors": self.errors,
        }


def apply_action_event(session: PreSpecSession, event: JSONDict) -> ActionResult:
    action = str(event.get("action", ""))
    payload = event.get("payload") or {}
    if action not in ACTION_TYPES:
        return _rejected(session, action, "unsupported_action", f"Unsupported action: {action}")
    if event.get("session_id") and event["session_id"] != session.id:
        return _rejected(session, action, "session_mismatch", "Action event session_id does not match current session.")
    if action == "select_option":
        return _select_option(session, payload)
    if action == "update_text":
        return _update_text(session, payload)
    if action == "confirm_stage":
        return _confirm_stage(session, payload)
    if action == "save_draft":
        session.metadata["last_saved_action"] = action
        return _accepted(session, action, "Session draft saved.", {"session": session.to_dict()})
    if action == "show_impact":
        board = _board_for_read(session)
        return _accepted(session, action, "Impact preview rendered.", {"impact_preview": [item.to_dict() for item in board.impact_preview]})
    if action == "request_approval":
        return ActionResult(
            status="requires_approval",
            action=action,
            session_id=session.id,
            message="Approval is required before applying this action.",
            payload={"approval_request": {"action": payload.get("requested_action"), "reason": payload.get("reason", ""), "payload": payload}},
        )
    return _rejected(session, action, "unsupported_action", f"Unsupported action: {action}")


def _select_option(session: PreSpecSession, payload: JSONDict) -> ActionResult:
    action = "select_option"
    question = _visible_question(session, payload.get("question_id"))
    if question is None:
        return _rejected(session, action, "unknown_question", "Question is not visible in the current board.")
    if question.input_type == "text_input":
        return _rejected(session, action, "wrong_action", "Use update_text for text input questions.")
    value = payload.get("value")
    selected = value if isinstance(value, list) else [value]
    option_ids = {option.id for option in question.options}
    invalid = [item for item in selected if item not in option_ids]
    if invalid:
        return _rejected(session, action, "invalid_option", f"Invalid option for {question.id}: {invalid}")
    if question.input_type == "single_choice" and len(selected) != 1:
        return _rejected(session, action, "invalid_cardinality", "Single choice questions require exactly one value.")
    inputs = dict(payload.get("inputs") or {})
    missing = _missing_required_inputs(question, selected, inputs)
    if missing:
        return _rejected(session, action, "missing_required_input", f"Missing required input: {', '.join(missing)}")
    applied_value = selected if question.input_type == "multi_choice" else selected[0]
    _apply_decision_with_inputs(session, question, applied_value, inputs)
    return _accepted(session, action, "Decision applied.", {"question_id": question.id, "value": applied_value, "session": session.to_dict()})


def _update_text(session: PreSpecSession, payload: JSONDict) -> ActionResult:
    action = "update_text"
    question = _visible_question(session, payload.get("question_id"))
    if question is None:
        return _rejected(session, action, "unknown_question", "Question is not visible in the current board.")
    value = payload.get("value")
    if not isinstance(value, str) or (question.required and not value.strip()):
        return _rejected(session, action, "invalid_text", "Text value is required.")
    session.apply_decision(question.id, value, source="user_selected")
    return _accepted(session, action, "Text decision applied.", {"question_id": question.id, "value": value, "session": session.to_dict()})


def _confirm_stage(session: PreSpecSession, payload: JSONDict) -> ActionResult:
    action = "confirm_stage"
    stage = payload.get("stage") or session.current_stage
    if stage != session.current_stage:
        return _rejected(session, action, "stage_mismatch", "Confirm stage event does not match current stage.")
    board = _board_for_read(session)
    missing = [question.id for question in board.questions if question.required and question.id not in session.decisions]
    if missing:
        return _rejected(session, action, "missing_required_decisions", f"Missing required decisions: {', '.join(missing)}")
    confirmed = set(session.metadata.get("confirmed_stages", []))
    confirmed.add(session.current_stage)
    session.metadata["confirmed_stages"] = sorted(confirmed)
    advanced = advance_stage(session)
    message = "Stage confirmed and advanced." if advanced else "Final stage confirmed."
    return _accepted(session, action, message, {"advanced": advanced, "session": session.to_dict()})


def _visible_question(session: PreSpecSession, question_id: Any) -> Optional[DecisionQuestion]:
    if not question_id:
        return None
    board = _board_for_read(session)
    for question in board.questions:
        if question.id == question_id:
            return question
    return None


def _board_for_read(session: PreSpecSession):
    return build_decision_board(PreSpecSession.from_dict(session.to_dict()))


def _missing_required_inputs(question: DecisionQuestion, selected: List[Any], inputs: JSONDict) -> List[str]:
    missing: List[str] = []
    for option in question.options:
        if option.id not in selected or not option.requires_input:
            continue
        input_id = option.requires_input.get("id")
        if input_id and not inputs.get(input_id):
            missing.append(input_id)
    return missing


def _apply_decision_with_inputs(session: PreSpecSession, question: DecisionQuestion, value: Any, inputs: JSONDict) -> None:
    session.apply_decision(question.id, value, source="user_selected", inputs=inputs)
    for input_id, input_value in inputs.items():
        session.apply_decision(input_id, input_value, source="user_selected")


def _accepted(session: PreSpecSession, action: str, message: str, payload: JSONDict) -> ActionResult:
    return ActionResult(status="accepted", action=action, message=message, session_id=session.id, payload=payload)


def _rejected(session: PreSpecSession, action: str, code: str, message: str) -> ActionResult:
    return ActionResult(status="rejected", action=action, message=message, session_id=session.id, errors=[{"code": code, "message": message}])
