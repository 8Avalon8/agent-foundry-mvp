from __future__ import annotations

from typing import Any, Dict, List


COMPONENT_CATALOG: List[Dict[str, Any]] = [
    {"type": "AgentSummaryCard", "events": []},
    {"type": "PresetCardGroup", "events": ["select_option"]},
    {"type": "DecisionCard", "events": ["select_option", "update_text", "show_impact"]},
    {"type": "ChoiceGroup", "events": ["select_option"]},
    {"type": "MultiChoiceGroup", "events": ["select_option"]},
    {"type": "TextInputWithHint", "events": ["update_text"]},
    {"type": "ImpactPreview", "events": ["show_impact"]},
    {"type": "ImpactDiff", "events": ["show_impact"]},
    {"type": "StageProgress", "events": []},
    {"type": "ConfirmBar", "events": ["use_recommended", "confirm_stage", "save_draft"]},
]


ACTION_TYPES = [
    "select_option",
    "update_text",
    "confirm_stage",
    "use_recommended",
    "save_draft",
    "show_impact",
    "request_approval",
]


def catalog_as_dict() -> Dict[str, Any]:
    return {
        "schema": "agent_foundry.component_catalog.v0.1",
        "components": COMPONENT_CATALOG,
        "actions": ACTION_TYPES,
    }
