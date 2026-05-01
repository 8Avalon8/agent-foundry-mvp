from __future__ import annotations

from typing import Optional

from agent_foundry.llm.provider import BaseLLMProvider, LLMError
from agent_foundry.llm.schemas import INTENT_SCHEMA
from .intent_parser import ParsedIntent, parse_intent


SYSTEM_PROMPT = """You are Agent Foundry's intent parser.
Convert a user's natural-language request into a conservative structured Agent intent.
Prefer review-agent for code review/diff/SVN/Git review tasks.
Prefer writing-agent for article, blog, WeChat official account, story, or content workflow tasks.
Never grant high-risk actions directly. Only identify likely tools and side effects.
Return only data that matches the schema.
"""


def parse_intent_with_llm(user_goal: str, provider: BaseLLMProvider, explicit_type: Optional[str] = None) -> ParsedIntent:
    if explicit_type:
        base = parse_intent(user_goal, explicit_type=explicit_type)
        return base
    try:
        data = provider.complete_json(
            task="parse_intent",
            system=SYSTEM_PROMPT,
            user=user_goal,
            schema=INTENT_SCHEMA,
            temperature=0.1,
        )
        return ParsedIntent(
            user_goal=data.get("user_goal", user_goal),
            domain=data.get("domain", "automation"),
            likely_agent_type=data.get("likely_agent_type", "automation-agent"),
            risk_level=data.get("risk_level", "medium"),
            requires_tools=list(data.get("requires_tools", [])),
            possible_side_effects=list(data.get("possible_side_effects", [])),
            confidence=data.get("confidence", "medium"),
        )
    except LLMError:
        # Keep the builder usable even if the LLM is unavailable.
        return parse_intent(user_goal, explicit_type=explicit_type)
