from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from .provider import BaseLLMProvider, LLMProviderError


class OpenAIProvider(BaseLLMProvider):
    """OpenAI Responses API provider.

    Configuration:
      - OPENAI_API_KEY must be set unless the SDK is configured externally.
      - AGENT_FOUNDRY_OPENAI_MODEL can override the default model.
    """

    name = "openai"

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None) -> None:
        self.model = model or os.environ.get("AGENT_FOUNDRY_OPENAI_MODEL") or "gpt-5.5"
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise LLMProviderError("OpenAI provider requires the `openai` package. Install with: pip install openai") from exc
        if not self.api_key:
            raise LLMProviderError("OPENAI_API_KEY is not set. Use --llm-provider mock for local testing.")
        self.client = OpenAI(api_key=self.api_key)

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
        schema_name: str,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "schema": schema,
                        "strict": True,
                    }
                },
                temperature=temperature,
            )
            return json.loads(_extract_responses_text(response))
        except AttributeError:
            return self._complete_json_chat(system_prompt, user_prompt, schema, schema_name, temperature)
        except Exception as exc:
            try:
                response = self.client.responses.create(
                    model=self.model,
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": schema_name,
                            "schema": schema,
                            "strict": False,
                        }
                    },
                    temperature=temperature,
                )
                return json.loads(_extract_responses_text(response))
            except Exception:
                raise LLMProviderError(f"OpenAI structured JSON call failed: {exc}") from exc

    def _complete_json_chat(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
        schema_name: str,
        temperature: float,
    ) -> Dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": schema, "strict": True},
            },
            temperature=temperature,
        )
        text = response.choices[0].message.content or "{}"
        return json.loads(text)


def _extract_responses_text(response: Any) -> str:
    if hasattr(response, "output_text") and response.output_text:
        return str(response.output_text)
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            if getattr(content, "type", None) == "output_text":
                return str(getattr(content, "text", ""))
    if isinstance(response, dict):
        for item in response.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return str(content.get("text", ""))
    raise LLMProviderError("Could not extract output_text from OpenAI response")

# ---- Compatibility for the newer Agent Builder Brain interface ----
def _af_openai_generate_json(self, *, system: str, user: str, schema: Dict[str, Any], schema_name: str) -> Dict[str, Any]:
    return self.complete_json(system_prompt=system, user_prompt=user, schema=schema, schema_name=schema_name)

OpenAIProvider.generate_json = _af_openai_generate_json
OpenAIResponsesProvider = OpenAIProvider
