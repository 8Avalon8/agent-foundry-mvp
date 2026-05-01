from __future__ import annotations

import json
from typing import Any, Dict, Optional

from agent_foundry.llm.provider import BaseLLMProvider, LLMError
from agent_foundry.llm.schemas import DESIGN_BRIEF_SCHEMA
from .models import DecisionBoard, PreSpecSession


SYSTEM_PROMPT = """You are the Agent Builder architect.
Given a user goal and the current deterministic decision board, produce a concise design brief.
Your job is to improve UX before AgentSpec generation: summarize the design, recommend one preset, list high-value questions, and flag risk notes.
Do not invent capabilities that are not represented in the board. Do not recommend automatic external publishing, code commit, or silent long-term memory updates.
Return only JSON matching the schema.
"""


def generate_design_brief(session: PreSpecSession, board: DecisionBoard, provider: BaseLLMProvider) -> Dict[str, Any]:
    payload = {
        "user_goal": session.user_goal,
        "inferred_agent_type": session.inferred_agent_type,
        "current_stage": session.current_stage,
        "selected_preset": session.selected_preset,
        "presets": [p.to_dict() for p in board.presets],
        "questions": [q.to_dict() for q in board.questions],
        "current_decisions": {k: v.to_dict() for k, v in session.decisions.items()},
    }
    try:
        return provider.complete_json(
            task="design_brief",
            system=SYSTEM_PROMPT,
            user=json.dumps(payload, ensure_ascii=False, indent=2),
            schema=DESIGN_BRIEF_SCHEMA,
            temperature=0.2,
        )
    except LLMError:
        return {
            "title": board.title,
            "recommended_preset": session.selected_preset or "",
            "summary": board.summary.summary,
            "recommended_reason": "LLM 不可用，使用确定性模板推荐。",
            "high_value_questions": [q.id for q in board.questions],
            "risk_notes": [],
        }


def attach_design_brief_to_session(session: PreSpecSession, brief: Dict[str, Any], provider_name: Optional[str] = None) -> None:
    session.metadata["llm_design_brief"] = brief
    if brief.get("recommended_preset"):
        session.metadata["llm_recommended_preset"] = brief.get("recommended_preset")
    if brief.get("recommended_reason"):
        session.metadata["llm_recommendation_message"] = brief.get("recommended_reason")
    if provider_name:
        session.metadata["llm_provider"] = provider_name
