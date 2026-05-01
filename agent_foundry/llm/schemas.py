from __future__ import annotations

from typing import Any, Dict

JSONDict = Dict[str, Any]

INTENT_SCHEMA: JSONDict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "user_goal": {"type": "string"},
        "domain": {"type": "string"},
        "likely_agent_type": {"type": "string", "enum": ["writing-agent", "review-agent", "coding-agent", "research-agent", "automation-agent", "monitor-agent", "hybrid-agent"]},
        "risk_level": {"type": "string"},
        "requires_tools": {"type": "array", "items": {"type": "string"}},
        "possible_side_effects": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "rationale": {"type": "string"},
    },
    "required": ["user_goal", "domain", "likely_agent_type", "risk_level", "requires_tools", "possible_side_effects", "confidence", "rationale"],
}

DECISION_VALUE_SCHEMA: JSONDict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "question_id": {"type": "string"},
        "value_json": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["question_id", "value_json", "reason"],
}

QUESTION_OPTION_SCHEMA: JSONDict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "id": {"type": "string"},
        "label": {"type": "string"},
        "description": {"type": "string"},
        "recommended": {"type": "boolean"},
        "tradeoff": {"type": "string"},
        "requires_input_id": {"type": "string"},
        "requires_input_type": {"type": "string"},
        "requires_input_placeholder": {"type": "string"},
        "risk_level": {"type": "string"},
    },
    "required": ["id", "label", "description", "recommended", "tradeoff", "requires_input_id", "requires_input_type", "requires_input_placeholder", "risk_level"],
}

ADDITIONAL_QUESTION_SCHEMA: JSONDict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "id": {"type": "string"},
        "title": {"type": "string"},
        "input_type": {"type": "string", "enum": ["single_choice", "multi_choice", "text_input", "path_input", "number_input", "toggle", "permission_matrix", "ranked_choice", "approval", "diff_review", "checklist"]},
        "stage": {"type": "string", "enum": ["foundation", "autonomy", "tool_permissions", "feedback_protocol", "memory_policy", "output_and_dry_run"]},
        "required": {"type": "boolean"},
        "recommended_json": {"type": "string"},
        "recommendation_reason": {"type": "string"},
        "risk_level": {"type": "string"},
        "help_text": {"type": "string"},
        "placeholder": {"type": "string"},
        "options": {"type": "array", "items": QUESTION_OPTION_SCHEMA},
        "affects": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["id", "title", "input_type", "stage", "required", "recommended_json", "recommendation_reason", "risk_level", "help_text", "placeholder", "options", "affects"],
}

DESIGN_DRAFT_SCHEMA: JSONDict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "agent_title": {"type": "string"},
        "agent_type": {"type": "string"},
        "risk_level": {"type": "string"},
        "summary_points": {"type": "array", "items": {"type": "string"}},
        "recommended_preset": {"type": "string"},
        "recommendation_message": {"type": "string"},
        "recommended_decisions": {"type": "array", "items": DECISION_VALUE_SCHEMA},
        "additional_questions": {"type": "array", "items": ADDITIONAL_QUESTION_SCHEMA},
        "open_issues": {"type": "array", "items": {"type": "string"}},
        "spec_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["agent_title", "agent_type", "risk_level", "summary_points", "recommended_preset", "recommendation_message", "recommended_decisions", "additional_questions", "open_issues", "spec_notes"],
}

DECISION_PATCH_SCHEMA: JSONDict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "decision_updates": {"type": "array", "items": DECISION_VALUE_SCHEMA},
        "additional_questions": {"type": "array", "items": ADDITIONAL_QUESTION_SCHEMA},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "decision_updates", "additional_questions", "warnings"],
}
