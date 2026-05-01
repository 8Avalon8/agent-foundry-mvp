from __future__ import annotations

from typing import Any, Dict, List

from agent_foundry.builder.decision_graph import get_stage_order
from agent_foundry.builder.impact_preview import impact_preview_as_diff
from agent_foundry.builder.models import DecisionBoard, ImpactItem


JSONDict = Dict[str, Any]


def board_to_a2ui_tree(board: DecisionBoard) -> JSONDict:
    """Map DecisionBoard to an A2UI-compatible declarative component tree."""
    data = board.to_dict()
    agent_type = data["summary"]["agent_type"]
    return {
        "schema": "a2ui.component_tree",
        "schema_version": "0.1",
        "source_protocol": "agent_foundry.decision_board.v0.1",
        "session_id": data["session_id"],
        "state": {
            "stage": data["stage"],
            "decisions": data["decisions"],
        },
        "root": {
            "type": "Stack",
            "id": "agent_foundry_board",
            "props": {"gap": "md"},
            "children": [
                _component("AgentSummaryCard", "agent_summary", data["summary"]),
                _component("PresetCardGroup", "preset_cards", {"presets": data["presets"]}),
                _component(
                    "StageProgress",
                    "stage_progress",
                    {"current": data["stage"], "stages": _stage_items(agent_type, data["stage"])},
                ),
                *[_decision_card(question) for question in data["questions"]],
                _impact_diff(data),
                _confirm_bar(data),
            ],
        },
        "action_payload_schema": action_payload_schema(data["session_id"]),
    }


def action_payload_schema(session_id: str | None = None) -> JSONDict:
    schema: JSONDict = {
        "type": "object",
        "required": ["action", "session_id", "payload"],
        "properties": {
            "action": {
                "enum": [
                    "select_option",
                    "update_text",
                    "use_recommended",
                    "confirm_stage",
                    "save_draft",
                    "show_impact",
                    "request_approval",
                ]
            },
            "session_id": {"type": "string"},
            "payload": {"type": "object"},
        },
        "additionalProperties": False,
    }
    if session_id:
        schema["properties"]["session_id"]["const"] = session_id
    return schema


def _component(component_type: str, component_id: str, props: JSONDict, children: List[JSONDict] | None = None) -> JSONDict:
    node = {
        "type": component_type,
        "id": component_id,
        "props": props,
    }
    if children is not None:
        node["children"] = children
    return node


def _decision_card(question: JSONDict) -> JSONDict:
    input_component = _question_input(question)
    return _component(
        "DecisionCard",
        f"decision_{question['id']}",
        {
            "question_id": question["id"],
            "title": question["title"],
            "risk_level": question.get("risk_level", "low"),
            "recommendation": {
                "value": question.get("recommended"),
                "reason": question.get("recommendation_reason", ""),
            },
            "requires_input": [option["requires_input"] for option in question.get("options", []) if option.get("requires_input")],
            "affects": question.get("affects", []),
        },
        children=[input_component],
    )


def _question_input(question: JSONDict) -> JSONDict:
    input_type = question["input_type"]
    if input_type == "multi_choice":
        component_type = "MultiChoiceGroup"
        action = "select_option"
    elif input_type == "text_input":
        component_type = "TextInputWithHint"
        action = "update_text"
    else:
        component_type = "ChoiceGroup"
        action = "select_option"
    return _component(
        component_type,
        f"input_{question['id']}",
        {
            "state_key": question["id"],
            "options": question.get("options", []),
            "placeholder": question.get("placeholder", ""),
            "recommended": question.get("recommended"),
            "validation": {"required": question.get("required", True), "input_type": input_type},
            "on_change": {
                "action": action,
                "payload": {"question_id": question["id"], "value": "$value"},
            },
        },
    )


def _impact_diff(data: JSONDict) -> JSONDict:
    items = [ImpactItem(**item) for item in data.get("impact_preview", [])]
    return _component(
        "ImpactDiff",
        "impact_diff",
        {
            "items": data.get("impact_preview", []),
            "diff_text": impact_preview_as_diff(items),
            "on_request_detail": {"action": "show_impact", "payload": {"stage": data["stage"]}},
        },
    )


def _confirm_bar(data: JSONDict) -> JSONDict:
    return _component(
        "ConfirmBar",
        "confirm_bar",
        {
            "stage": data["stage"],
            "actions": [
                {"id": action, "label": _action_label(action), "event": {"action": _event_action(action), "payload": {"stage": data["stage"]}}}
                for action in data["next_actions"]
            ],
        },
    )


def _stage_items(agent_type: str, current: str) -> List[JSONDict]:
    stages = get_stage_order(agent_type)
    current_index = stages.index(current) if current in stages else 0
    items = []
    for index, stage in enumerate(stages):
        if index < current_index:
            status = "completed"
        elif index == current_index:
            status = "current"
        else:
            status = "pending"
        items.append({"id": stage, "status": status})
    return items


def _event_action(action: str) -> str:
    if action == "confirm_stage":
        return "confirm_stage"
    if action == "save_draft":
        return "save_draft"
    return action


def _action_label(action: str) -> str:
    return {
        "use_recommended": "采用推荐",
        "confirm_stage": "确认本阶段",
        "save_draft": "保存草稿",
    }.get(action, action)
