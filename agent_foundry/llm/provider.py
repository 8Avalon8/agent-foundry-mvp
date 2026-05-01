from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

JSONDict = Dict[str, Any]


class LLMProviderError(RuntimeError):
    pass


LLMError = LLMProviderError


@dataclass
class LLMConfig:
    provider: str = "mock"
    model: Optional[str] = None
    temperature: float = 0.2
    timeout_seconds: int = 60
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class LLMProvider(Protocol):
    name: str
    model: str

    def generate_json(self, *, system: str, user: str, schema: JSONDict, schema_name: str) -> JSONDict: ...

    def complete_json(self, **kwargs: Any) -> JSONDict: ...


class BaseLLMProvider:
    name: str = "base"
    model: str = ""

    def generate_json(self, *, system: str, user: str, schema: JSONDict, schema_name: str) -> JSONDict:
        raise NotImplementedError

    def complete_json(self, **kwargs: Any) -> JSONDict:
        system = kwargs.get("system") or kwargs.get("system_prompt") or ""
        user = kwargs.get("user") or kwargs.get("user_prompt") or ""
        schema = kwargs.get("schema") or {}
        schema_name = kwargs.get("schema_name") or kwargs.get("task") or "json_response"
        return self.generate_json(system=system, user=user, schema=schema, schema_name=schema_name)


def get_provider(config: LLMConfig) -> LLMProvider:
    _load_dotenv_if_present()
    provider_name = (config.provider or "mock").lower()
    if provider_name in {"offline", "none"}:
        raise LLMProviderError("offline provider is represented by None; use provider_from_name for optional providers")
    if provider_name in {"mock", "offline-mock", "test"}:
        from .mock_provider import MockLLMProvider
        return MockLLMProvider(model=config.model)
    if provider_name == "openai":
        from .openai_provider import OpenAIProvider
        try:
            return OpenAIProvider(model=config.model, api_key=config.api_key, base_url=config.base_url)  # old-compatible provider
        except TypeError:
            from .openai_provider import OpenAIResponsesProvider
            return OpenAIResponsesProvider(
                model=config.model,
                api_key=config.api_key,
                base_url=config.base_url,
                temperature=config.temperature,
                timeout_seconds=config.timeout_seconds,
            )
    raise LLMProviderError(f"Unknown LLM provider: {config.provider}")


def provider_from_name(name: str | None, model: Optional[str] = None) -> Optional[LLMProvider]:
    provider_name = (name or "offline").lower()
    if provider_name in {"offline", "none", "rule", "rules"}:
        return None
    return get_provider(LLMConfig(provider=provider_name, model=model))


def get_llm_provider(provider: str = "mock", model: Optional[str] = None) -> LLMProvider:
    return get_provider(LLMConfig(provider=provider, model=model or "gpt-5.5"))


def json_dumps(data: Any) -> str:
    import json
    return json.dumps(data, ensure_ascii=False, indent=2)


def _load_dotenv_if_present(start: Optional[Path] = None) -> Optional[Path]:
    dotenv = _find_dotenv(start or Path.cwd())
    if dotenv is None:
        return None
    for raw_line in dotenv.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        elif " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        os.environ.setdefault(key, value)
    return dotenv


def _find_dotenv(start: Path) -> Optional[Path]:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for directory in [current, *current.parents]:
        candidate = directory / ".env"
        if candidate.exists() and candidate.is_file():
            return candidate
    return None
