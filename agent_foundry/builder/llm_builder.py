from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from agent_foundry.llm.provider import BaseLLMProvider, json_dumps
from .decision_graph import required_question_ids
from .intent_parser import ParsedIntent, parse_intent
from .models import DecisionQuestion, PreSpecSession
from .presets import find_preset

AGENT_TYPES = [
    "writing-agent",
    "review-agent",
    "coding-agent",
    "research-agent",
    "automation-agent",
    "monitor-agent",
    "hybrid-agent",
]

INTENT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["user_goal", "domain", "likely_agent_type", "risk_level", "requires_tools", "possible_side_effects", "confidence", "rationale"],
    "properties": {
        "user_goal": {"type": "string"},
        "domain": {"type": "string"},
        "likely_agent_type": {"type": "string", "enum": AGENT_TYPES},
        "risk_level": {"type": "string"},
        "requires_tools": {"type": "array", "items": {"type": "string"}},
        "possible_side_effects": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string"},
        "rationale": {"type": "string"},
    },
}

DESIGN_BRIEF_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "risk_level", "summary", "recommended_preset_id", "recommended_preset_reason", "dynamic_questions", "notes"],
    "properties": {
        "title": {"type": "string"},
        "risk_level": {"type": "string"},
        "summary": {"type": "array", "items": {"type": "string"}},
        "recommended_preset_id": {"type": "string"},
        "recommended_preset_reason": {"type": "string"},
        "dynamic_questions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "stage", "title", "input_type", "recommended", "recommendation_reason", "risk_level", "options", "affects"],
                "properties": {
                    "id": {"type": "string"},
                    "stage": {"type": "string"},
                    "title": {"type": "string"},
                    "input_type": {"type": "string", "enum": ["single_choice", "multi_choice", "text_input"]},
                    "recommended": {"type": "string"},
                    "recommendation_reason": {"type": "string"},
                    "risk_level": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["id", "label", "tradeoff"],
                            "properties": {
                                "id": {"type": "string"},
                                "label": {"type": "string"},
                                "tradeoff": {"type": "string"},
                            },
                        },
                    },
                    "affects": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "notes": {"type": "array", "items": {"type": "string"}},
    },
}

SESSION_PATCH_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["decisions", "summary"],
    "properties": {
        "summary": {"type": "string"},
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["question_id", "value_json", "reason"],
                "properties": {
                    "question_id": {"type": "string"},
                    "value_json": {"type": "string"},
                    "reason": {"type": "string"},
                },
            },
        },
    },
}

INTENT_SYSTEM_PROMPT = """你是 Agent Foundry 的 Agent Builder Brain。把用户的一句话 Agent 需求解析成结构化意图。只输出符合 JSON Schema 的对象。风险评估要考虑文件写入、shell、外部发布、长期记忆和工具副作用。"""

DESIGN_SYSTEM_PROMPT = """你是 Agent Foundry 的 Pre-Spec 设计师。为用户需求生成一个可交互决策面板草案。先给专业草案，不要追问开放式长问题。推荐一个已有 preset id，并补充 0-3 个高价值动态问题。敏感动作默认 ask/deny。只输出符合 JSON Schema 的对象。"""

PATCH_SYSTEM_PROMPT = """你是 Agent Foundry 的自然语言决策更新器。把用户补充偏好转成 PreSpecSession 的结构化决策。只更新用户明确表达的字段。高风险动作优先 ask/deny。value_json 必须是合法 JSON 字符串。"""


def parse_intent_with_llm(provider: BaseLLMProvider, user_goal: str, explicit_type: Optional[str] = None) -> ParsedIntent:
    prompt = f"USER_GOAL:\n{user_goal}\n\nEXPLICIT_AGENT_TYPE:\n{explicit_type or ''}\n"
    try:
        raw = provider.complete_json(
            system_prompt=INTENT_SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=INTENT_SCHEMA,
            schema_name="agent_intent",
            temperature=0.1,
        )
        agent_type = explicit_type or raw.get("likely_agent_type") or "automation-agent"
        if agent_type == "hybrid-agent" or agent_type not in AGENT_TYPES:
            agent_type = "automation-agent"
        return ParsedIntent(
            user_goal=raw.get("user_goal") or user_goal,
            domain=raw.get("domain", "automation"),
            likely_agent_type=agent_type,
            risk_level=raw.get("risk_level", "medium"),
            requires_tools=list(raw.get("requires_tools", [])),
            possible_side_effects=list(raw.get("possible_side_effects", [])),
            confidence=raw.get("confidence", "medium"),
        )
    except Exception:
        return parse_intent(user_goal, explicit_type=explicit_type)


def create_session_with_llm(
    user_goal: str,
    *,
    provider: BaseLLMProvider,
    explicit_type: Optional[str] = None,
    apply_recommended_preset: bool = True,
) -> PreSpecSession:
    parsed = parse_intent_with_llm(provider, user_goal, explicit_type=explicit_type)
    session = PreSpecSession(user_goal=user_goal, inferred_agent_type=parsed.likely_agent_type)
    session.metadata["builder_mode"] = "llm"
    session.metadata["parsed_intent"] = parsed.to_dict()
    session.metadata["llm_provider"] = getattr(provider, "name", provider.__class__.__name__)
    session.unresolved = required_question_ids(parsed.likely_agent_type)
    enrich_session_design_with_llm(session, provider, apply_recommended_preset=apply_recommended_preset)
    return session


def enrich_session_design_with_llm(session: PreSpecSession, provider: BaseLLMProvider, *, apply_recommended_preset: bool = True) -> None:
    prompt = f"USER_GOAL:\n{session.user_goal}\n\nAGENT_TYPE:\n{session.inferred_agent_type}\n\nPARSED_INTENT:\n{json_dumps(session.metadata.get('parsed_intent', {}))}\n"
    try:
        design = provider.complete_json(
            system_prompt=DESIGN_SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=DESIGN_BRIEF_SCHEMA,
            schema_name="agent_design_brief",
            temperature=0.2,
        )
    except Exception as exc:
        session.metadata["llm_design_error"] = str(exc)
        return
    dynamic_questions = [_normalize_dynamic_question(q) for q in design.get("dynamic_questions", [])]
    session.metadata["llm_design"] = {
        "title": design.get("title", ""),
        "risk_level": design.get("risk_level", "medium"),
        "summary": design.get("summary", []),
        "recommended_preset_id": design.get("recommended_preset_id", ""),
        "recommended_preset_reason": design.get("recommended_preset_reason", ""),
        "notes": design.get("notes", []),
    }
    session.metadata["llm_dynamic_questions"] = dynamic_questions
    for q in dynamic_questions:
        if q.get("required", True) and q.get("id") not in session.unresolved:
            session.unresolved.append(q["id"])
    if apply_recommended_preset:
        try:
            preset = find_preset(session.inferred_agent_type, design.get("recommended_preset_id", ""))
            session.selected_preset = preset.id
            for key, value in preset.decisions.items():
                if key not in session.decisions:
                    session.apply_decision(key, value, source="llm_recommended_preset", confidence="medium")
        except Exception:
            pass


def apply_natural_language_update(session: PreSpecSession, provider: BaseLLMProvider, instruction: str) -> Dict[str, Any]:
    prompt = f"USER_INSTRUCTION:\n{instruction}\n\nCURRENT_SESSION:\n{json_dumps(session.to_dict())}\n\nKNOWN_DYNAMIC_QUESTIONS:\n{json_dumps(session.metadata.get('llm_dynamic_questions', []))}\n"
    patch = provider.complete_json(
        system_prompt=PATCH_SYSTEM_PROMPT,
        user_prompt=prompt,
        schema=SESSION_PATCH_SCHEMA,
        schema_name="session_decision_patch",
        temperature=0.1,
    )
    applied: List[Dict[str, Any]] = []
    for item in patch.get("decisions", []):
        qid = item.get("question_id")
        if not qid:
            continue
        try:
            value = json.loads(item.get("value_json", "null"))
        except json.JSONDecodeError:
            value = item.get("value_json")
        session.apply_decision(qid, value, source="llm_interpreted_user_instruction", note=item.get("reason", ""))
        applied.append({"question_id": qid, "value": value, "reason": item.get("reason", "")})
    session.metadata.setdefault("llm_updates", []).append({"instruction": instruction, "summary": patch.get("summary", ""), "applied": applied})
    return {"summary": patch.get("summary", ""), "applied": applied}


def dynamic_questions_for_stage(session: PreSpecSession, stage: str) -> List[DecisionQuestion]:
    return [DecisionQuestion.from_dict(raw) for raw in session.metadata.get("llm_dynamic_questions", []) if raw.get("stage") == stage]


def _normalize_dynamic_question(raw: Dict[str, Any]) -> Dict[str, Any]:
    input_type = raw.get("input_type", "single_choice")
    recommended_raw = str(raw.get("recommended", ""))
    recommended_ids = {x.strip() for x in recommended_raw.split(",") if x.strip()}
    rec_value: Any = list(recommended_ids) if input_type == "multi_choice" else recommended_raw
    options = []
    for opt in raw.get("options", []):
        oid = str(opt.get("id", "option"))
        options.append({
            "id": oid,
            "label": str(opt.get("label", oid)),
            "tradeoff": str(opt.get("tradeoff", "")),
            "recommended": oid in recommended_ids,
        })
    return {
        "id": str(raw.get("id", "llm_question")),
        "stage": str(raw.get("stage", "foundation")),
        "title": str(raw.get("title", "LLM generated decision")),
        "input_type": input_type,
        "required": True,
        "recommended": rec_value,
        "recommendation_reason": str(raw.get("recommendation_reason", "")),
        "risk_level": str(raw.get("risk_level", "low")),
        "options": options,
        "affects": list(raw.get("affects", [])),
        "help_text": "LLM-generated Pre-Spec question.",
    }
