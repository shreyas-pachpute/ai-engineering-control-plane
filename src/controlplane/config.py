"""Central configuration.

PROJECT.md Section 21 (MVP): "a hard-coded permission-enforcement layer
blocking anything beyond read/edit/commit within its assigned branch."
`sandbox_root` is the one and only directory this entire codebase is ever
allowed to touch -- everything in sandbox/policy.py is enforced relative
to it, and it lives inside this project's own folder, not anywhere near a
real system.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Config:
    gemini_api_key: str | None
    llm_provider: str = os.environ.get("LLM_PROVIDER", "gemini")
    gemini_model: str = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
    ollama_model: str = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
    ollama_base_url: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    sandbox_root: Path = PROJECT_ROOT / "sandbox_workspace" / "toy_repo"
    runs_dir: Path = PROJECT_ROOT / "runs"

    # Hard-coded permission policy (PROJECT.md Section 8: "a hard-coded
    # policy, not something the model self-polices").
    allowed_executables: tuple[str, ...] = ("pytest", "python", "git")
    allowed_git_subcommands: tuple[str, ...] = ("status", "diff", "add", "commit", "checkout", "branch", "log")
    command_timeout_seconds: float = 30.0

    max_fix_attempts: int = 2

    max_retries: int = 5
    initial_backoff_seconds: float = 2.0
    ollama_timeout_seconds: float = 120.0


def load_config() -> Config:
    provider = os.environ.get("LLM_PROVIDER", "gemini")
    api_key = os.environ.get("GEMINI_API_KEY")
    if provider == "gemini" and not api_key:
        raise RuntimeError("GEMINI_API_KEY not set. Add it to .env in the project root.")
    return Config(gemini_api_key=api_key)
