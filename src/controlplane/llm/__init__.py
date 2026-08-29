"""Provider-agnostic LLM client selection."""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

from controlplane.config import Config
from controlplane.llm.gemini_client import DailyQuotaExhausted, GeminiClient
from controlplane.llm.ollama_client import OllamaClient, OllamaUnavailable

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    call_count: int
    prompt_tokens: int
    output_tokens: int

    def generate_structured(self, system_instruction: str, user_prompt: str, response_model: type[T]) -> T: ...


def build_llm_client(config: Config) -> LLMClient:
    if config.llm_provider == "ollama":
        return OllamaClient(config)
    return GeminiClient(config)


__all__ = ["build_llm_client", "LLMClient", "DailyQuotaExhausted", "OllamaUnavailable"]
