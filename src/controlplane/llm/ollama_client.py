"""Ollama backend -- a small local model for live verification without
depending on the shared free-tier quota.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel, ValidationError

from controlplane.config import Config


class OllamaUnavailable(Exception):
    """Raised when the local Ollama server can't be reached at all."""


class OllamaClient:
    def __init__(self, config: Config):
        self._config = config
        self.call_count = 0
        self.prompt_tokens = 0
        self.output_tokens = 0

    def generate_structured(self, system_instruction, user_prompt, response_model: type[BaseModel]):
        schema = response_model.model_json_schema()
        last_error: Exception | None = None

        for attempt in range(self._config.max_retries):
            try:
                response = httpx.post(
                    f"{self._config.ollama_base_url}/api/generate",
                    json={
                        "model": self._config.ollama_model,
                        "system": system_instruction,
                        "prompt": user_prompt,
                        "stream": False,
                        "format": schema,
                        "options": {"temperature": 0.2},
                    },
                    timeout=self._config.ollama_timeout_seconds,
                )
                response.raise_for_status()
                data = response.json()
                if "error" in data:
                    raise RuntimeError(f"Ollama error: {data['error']}")

                self.call_count += 1
                self.prompt_tokens += data.get("prompt_eval_count", 0) or 0
                self.output_tokens += data.get("eval_count", 0) or 0

                return response_model.model_validate_json(data["response"])
            except httpx.ConnectError as exc:
                raise OllamaUnavailable(
                    f"Could not reach Ollama at {self._config.ollama_base_url}. "
                    "Is it running? Try `ollama serve` or start the Ollama app."
                ) from exc
            except (ValidationError, ValueError, KeyError) as exc:
                last_error = exc
                if attempt == self._config.max_retries - 1:
                    raise

        raise last_error  # pragma: no cover
