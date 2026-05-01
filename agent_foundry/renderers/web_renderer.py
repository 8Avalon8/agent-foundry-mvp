from __future__ import annotations

import json
from html import escape
from typing import Any, Dict, List

from agent_foundry.builder.decision_graph import get_stage_order
from agent_foundry.builder.impact_preview import impact_preview_as_diff
from agent_foundry.builder.models import DecisionBoard


JSONDict = Dict[str, Any]


def board_to_web_view_model(board: DecisionBoard) -> JSONDict:
    """Convert a DecisionBoard into a declarative, side-effect-free Web model."""
    data = board.to_dict()
    agent_type = data["summary"]["agent_type"]
    return {
        "renderer": {"name": "agent_foundry_web", "version": "0.1"},
        "surface_type": "agent_design_board_web",
        "session_id": data["session_id"],
        "stage": data["stage"],
        "title": data["title"],
        "state": {"decisions": data["decisions"]},
        "components": [
            _summary_component(data),
            _preset_component(data),
            _stage_progress_component(data, agent_type),
            *[_decision_component(question) for question in data["questions"]],
            _impact_component(data),
            _confirm_component(data),
        ],
    }


def render_web_html(board: DecisionBoard) -> str:
    model = board_to_web_view_model(board)
    body = "\n".join(_render_component(component) for component in model["components"])
    payload = escape(json.dumps(model, ensure_ascii=False, indent=2))
    title = escape(str(model["title"]))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>{title}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f7f8fb; color: #18212f; }}
  main {{ max-width: 1120px; margin: 0 auto; padding: 24px; }}
  section {{ background: #fff; border: 1px solid #dfe4ec; border-radius: 8px; padding: 16px; margin: 12px 0; }}
  h1, h2, h3 {{ margin: 0 0 8px; }}
  .muted {{ color: #5f6b7a; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
  .item {{ border: 1px solid #dfe4ec; border-radius: 8px; padding: 12px; }}
  .recommended {{ border-color: #26845d; }}
  .risk {{ display: inline-block; padding: 2px 8px; border-radius: 999px; background: #fff3cd; font-size: 12px; }}
  .choice {{ display: grid; grid-template-columns: 20px 1fr; gap: 8px; padding: 8px; border-top: 1px solid #edf0f5; }}
  pre {{ white-space: pre-wrap; background: #101826; color: #eef2f7; border-radius: 8px; padding: 12px; overflow: auto; }}
  button {{ border: 1px solid #1f2937; background: #1f2937; color: white; border-radius: 6px; padding: 8px 12px; }}
</style>
</head>
<body>
<main>
{body}
<script type="application/json" id="agent-foundry-web-model">{payload}</script>
</main>
</body>
</html>"""


def _summary_component(data: JSONDict) -> JSONDict:
    return {
        "type": "AgentSummaryCard",
        "id": "agent_summary",
        "props": data["summary"],
    }


def _preset_component(data: JSONDict) -> JSONDict:
    return {
        "type": "PresetCardGroup",
        "id": "preset_cards",
        "props": {"presets": data["presets"], "recommended_ids": [p["id"] for p in data["presets"] if p.get("recommended")]},
    }


def _stage_progress_component(data: JSONDict, agent_type: str) -> JSONDict:
    stages = get_stage_order(agent_type)
    return {
        "type": "StageProgress",
        "id": "stage_progress",
        "props": {
            "current_stage": data["stage"],
            "stages": [{"id": stage, "status": _stage_status(stage, data["stage"], stages)} for stage in stages],
        },
    }


def _decision_component(question: JSONDict) -> JSONDict:
    return {
        "type": "DecisionCard",
        "id": f"decision_{question['id']}",
        "state_key": question["id"],
        "props": {
            "question": question,
            "risk_level": question.get("risk_level", "low"),
            "recommendation": {
                "value": question.get("recommended"),
                "reason": question.get("recommendation_reason", ""),
            },
            "input": _input_component(question),
            "requires_input": [option.get("requires_input") for option in question.get("options", []) if option.get("requires_input")],
            "affects": question.get("affects", []),
        },
        "events": _question_events(question),
    }


def _input_component(question: JSONDict) -> JSONDict:
    input_type = question["input_type"]
    if input_type == "multi_choice":
        component_type = "MultiChoiceGroup"
    elif input_type == "text_input":
        component_type = "TextInputWithHint"
    else:
        component_type = "ChoiceGroup"
    return {
        "type": component_type,
        "state_key": question["id"],
        "props": {
            "options": question.get("options", []),
            "placeholder": question.get("placeholder", ""),
            "recommended": question.get("recommended"),
        },
    }


def _question_events(question: JSONDict) -> List[JSONDict]:
    action = "update_text" if question["input_type"] == "text_input" else "select_option"
    return [
        {
            "action": action,
            "payload_schema": {
                "question_id": question["id"],
                "value_type": "array" if question["input_type"] == "multi_choice" else "string",
            },
        },
        {"action": "show_impact", "payload_schema": {"question_id": question["id"]}},
    ]


def _impact_component(data: JSONDict) -> JSONDict:
    return {
        "type": "ImpactPreview",
        "id": "impact_preview",
        "props": {
            "items": data["impact_preview"],
            "diff_text": impact_preview_as_diff(board_items(data)),
        },
    }


def _confirm_component(data: JSONDict) -> JSONDict:
    return {
        "type": "ConfirmBar",
        "id": "confirm_bar",
        "props": {
            "actions": [{"id": action, "label": _action_label(action)} for action in data["next_actions"]],
            "stage": data["stage"],
        },
        "events": [{"action": action, "payload_schema": {"session_id": data["session_id"], "stage": data["stage"]}} for action in data["next_actions"]],
    }


def board_items(data: JSONDict) -> List[Any]:
    from agent_foundry.builder.models import ImpactItem

    return [ImpactItem(**item) for item in data.get("impact_preview", [])]


def _render_component(component: JSONDict) -> str:
    ctype = component["type"]
    props = component.get("props", {})
    if ctype == "AgentSummaryCard":
        summary = "".join(f"<li>{escape(str(item))}</li>" for item in props.get("summary", []))
        return f"<section><h1>{escape(props['title'])}</h1><p class='muted'>{escape(props['agent_type'])} | {escape(props['risk_level'])}</p><ul>{summary}</ul></section>"
    if ctype == "PresetCardGroup":
        cards = []
        for preset in props.get("presets", []):
            cls = "item recommended" if preset.get("recommended") else "item"
            cards.append(f"<article class='{cls}'><h3>{escape(preset['title'])}</h3><p>{escape(preset['description'])}</p></article>")
        return f"<section><h2>推荐组合</h2><div class='grid'>{''.join(cards)}</div></section>"
    if ctype == "StageProgress":
        stages = " / ".join(f"{escape(stage['id'])}:{escape(stage['status'])}" for stage in props["stages"])
        return f"<section><h2>阶段</h2><p>{stages}</p></section>"
    if ctype == "DecisionCard":
        question = props["question"]
        choices = "".join(_render_choice(question, option) for option in question.get("options", []))
        if not choices:
            choices = f"<div class='choice'><span></span><span>{escape(question.get('placeholder', '请输入内容'))}</span></div>"
        reason = escape(str(props.get("recommendation", {}).get("reason", "")))
        return f"<section><h2>{escape(question['title'])} <span class='risk'>{escape(props['risk_level'])}</span></h2><p class='muted'>{reason}</p>{choices}</section>"
    if ctype == "ImpactPreview":
        return f"<section><h2>Impact Preview</h2><pre>{escape(props.get('diff_text', ''))}</pre></section>"
    if ctype == "ConfirmBar":
        buttons = "".join(f"<button data-action='{escape(action['id'])}'>{escape(action['label'])}</button> " for action in props["actions"])
        return f"<section><h2>确认</h2>{buttons}</section>"
    return f"<section><pre>{escape(json.dumps(component, ensure_ascii=False, indent=2))}</pre></section>"


def _render_choice(question: JSONDict, option: JSONDict) -> str:
    recommended = question.get("recommended")
    checked = option.get("id") == recommended or (isinstance(recommended, list) and option.get("id") in recommended)
    marker = "x" if checked else " "
    tradeoff = f"<br><small>{escape(option.get('tradeoff', ''))}</small>" if option.get("tradeoff") else ""
    return f"<label class='choice'><span>[{marker}]</span><span>{escape(option['label'])}{tradeoff}</span></label>"


def _stage_status(stage: str, current_stage: str, stages: List[str]) -> str:
    current_index = stages.index(current_stage) if current_stage in stages else 0
    stage_index = stages.index(stage) if stage in stages else 0
    if stage_index < current_index:
        return "completed"
    if stage_index == current_index:
        return "current"
    return "pending"


def _action_label(action: str) -> str:
    return {
        "use_recommended": "采用推荐",
        "confirm_stage": "确认本阶段",
        "save_draft": "保存草稿",
    }.get(action, action)
