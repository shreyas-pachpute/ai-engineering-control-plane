"""Gemini backend -- structured JSON output + quota-aware errors."""

from __future__ import annotations

import logging
import time
from typing import TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from controlplane.config import Config

logging.getLogger("google_genai.models").setLevel(logging.ERROR)

T = TypeVar("T", bound=BaseModel)


class DailyQuotaExhausted(Exception):
    """Raised when the free-tier per-day request quota is exhausted."""


def _is_daily_quota_error(exc: errors.APIError) -> bool:
    details = getattr(exc, "details", None) or {}
    error_body = details.get("error", details) if isinstance(details, dict) else {}
    for item in error_body.get("details", []) if isinstance(error_body, dict) else []:
        for violation in item.get("violations", []):
            if "PerDay" in str(violation.get("quotaId", "")):
                return True
    return "PerDay" in str(details)


class GeminiClient:
    def __init__(self, config: Config):
        self._config = config
        self._client = genai.Client(api_key=config.gemini_api_key)
        self.call_count = 0
        self.prompt_tokens = 0
        self.output_tokens = 0

    def generate_structured(
        self, system_instruction: str, user_prompt: str, response_model: type[T]
    ) -> T:
        backoff = self._config.initial_backoff_seconds
        last_error: Exception | None = None

        for attempt in range(self._config.max_retries):
            try:
                resp = self._client.models.generate_content(
                    model=self._config.gemini_model,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        response_mime_type="application/json",
                        response_schema=response_model,
                        temperature=0.2,
                    ),
                )
                usage = resp.usage_metadata
                self.call_count += 1
                self.prompt_tokens += getattr(usage, "prompt_token_count", 0) or 0
                self.output_tokens += getattr(usage, "candidates_token_count", 0) or 0
                if resp.parsed is None:
                    raise ValueError(f"Model did not return parseable JSON: {resp.text!r}")
                return resp.parsed
            except errors.APIError as exc:
                last_error = exc
                if getattr(exc, "code", None) == 429 and _is_daily_quota_error(exc):
                    raise DailyQuotaExhausted(
                        "Free-tier daily request quota exhausted for model "
                        f"'{self._config.gemini_model}'. Wait for the daily quota "
                        f"reset, switch GEMINI_MODEL, or set LLM_PROVIDER=ollama. "
                        f"Original error: {exc}"
                    ) from exc
                is_retryable = getattr(exc, "code", None) in (429, 500, 503)
                if not is_retryable or attempt == self._config.max_retries - 1:
                    raise
                time.sleep(backoff)
                backoff *= 2

        raise last_error  # pragma: no cover
