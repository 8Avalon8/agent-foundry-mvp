from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List

from agent_foundry.llm.provider import BaseLLMProvider, LLMError
from agent_foundry.llm.schemas import DECISION_UPDATES_SCHEMA
from .decision_graph import get_questions, get_stage_order
from .models import PreSpecSession


SYSTEM_PROMPT = """You update an Agent Foundry PreSpecSession from a user's natural-language instruction.
Map the user's instruction to known question IDs only. Never create new question IDs.
If a user asks for a high-risk action, prefer ask/explicit_confirmation over allow.
Return only JSON matching the schema.
"""


@dataclass
class DecisionUpdateResult:
    updates: List[Dict[str, Any]]
    needs_user_confirmation: bool
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "updates": self.updates,
            "needs_user_confirmation": self.needs_user_confirmation,
            "summary": self.summary,
        }


def known_questions_payload(session: PreSpecSession) -> List[Dict[str, Any]]:
    questions = []
    for stage in get_stage_order(session.inferred_agent_type):
        for q in get_questions(session.inferred_agent_type, stage):
            questions.append(
                {
                    "id": q.id,
                    "title": q.title,
                    "input_type": q.input_type,
                    "stage": q.stage,
                    "recommended": q.recommended,
                    "options": [o.to_dict() for o in q.options],
                    "affects": q.affects,
                }
            )
    return questions


def propose_decision_updates(session: PreSpecSession, instruction: str, provider: BaseLLMProvider) -> DecisionUpdateResult:
    payload = {
        "user_goal": session.user_goal,
        "agent_type": session.inferred_agent_type,
        "current_decisions": {k: v.to_dict() for k, v in session.decisions.items()},
        "known_questions": known_questions_payload(session),
        "instruction": instruction,
    }
    try:
        data = provider.complete_json(
            task="decision_updates",
            system=SYSTEM_PROMPT,
            user=json.dumps(payload, ensure_ascii=False, indent=2),
            schema=DECISION_UPDATES_SCHEMA,
            temperature=0.1,
        )
    except LLMError:
        data = {"updates": [], "needs_user_confirmation": False, "summary": "LLM 不可用，未应用更新。"}
    valid_ids = {q["id"] for q in payload["known_questions"]}
    updates = [u for u in data.get("updates", []) if u.get("question_id") in valid_ids]
    return DecisionUpdateResult(
        updates=updates,
        needs_user_confirmation=bool(data.get("needs_user_confirmation", bool(updates))),
        summary=data.get("summary", ""),
    )


def apply_decision_updates(session: PreSpecSession, result: DecisionUpdateResult, source: str = "llm_user_instruction") -> None:
    for update in result.updates:
        session.apply_decision(
            update["question_id"],
            update.get("value"),
            source=source,
            confidence="medium",
            note=update.get("note", ""),
            inputs=update.get("inputs", {}) or {},
        )
    session.metadata.setdefault("llm_decision_updates", []).append(result.to_dict())
