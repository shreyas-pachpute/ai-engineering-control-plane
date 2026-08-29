"""The permission-enforcement layer -- the actual point of this project.

PROJECT.md Section 133: "the permission-enforcement layer is implemented
as ordinary, independently-tested software that does not rely on the
model's cooperation -- if the model attempts a disallowed action, the
enforcement layer blocks it at the system level, not by asking the model
nicely." Every file read, file write, and shell command the agent issues
goes through this module; nothing in agent/ ever calls `open()` or
`subprocess` directly.

Scope, honestly stated: this is a path- and command-allowlist enforcement
layer, not OS-level container isolation (gVisor/Firecracker-class
sandboxing, per PROJECT.md Section 19, is named there as a scaling
decision beyond this MVP, not something this build claims to provide).
What it does guarantee, for real: no path outside `sandbox_root` can be
read or written, and only a small fixed set of commands can run at all --
`git push`, `fetch`, `remote`, `clone` are not merely discouraged, they
are not in the allowlist, so a network-capable git operation cannot
execute regardless of what an agent (or a prompt injection embedded in
repository content) asks for.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from controlplane.config import Config


class SandboxViolation(Exception):
    """Raised when an action is blocked by the permission-enforcement layer."""


@dataclass(frozen=True)
class AuditEntry:
    timestamp: str
    action_type: str  # "read", "write", "command"
    detail: str
    allowed: bool
    reason: str | None = None


@dataclass
class AuditLog:
    entries: list[AuditEntry] = field(default_factory=list)

    def record(self, action_type: str, detail: str, allowed: bool, reason: str | None = None) -> None:
        self.entries.append(
            AuditEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                action_type=action_type,
                detail=detail,
                allowed=allowed,
                reason=reason,
            )
        )

    @property
    def blocked_entries(self) -> list[AuditEntry]:
        return [e for e in self.entries if not e.allowed]


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0


class Sandbox:
    """Every method here either performs the requested action and records
    it, or raises SandboxViolation and records the block -- there is no
    third path where a disallowed action silently no-ops or partially
    succeeds."""

    def __init__(self, config: Config, audit_log: AuditLog):
        self._config = config
        self._root = config.sandbox_root.resolve()
        self._audit = audit_log

    def _resolve_within_root(self, relative_path: str) -> Path:
        raw = Path(relative_path)
        if raw.is_absolute() or ".." in raw.parts:
            self._audit.record("path_check", relative_path, False, "absolute path or '..' traversal rejected")
            raise SandboxViolation(
                f"Path {relative_path!r} is absolute or contains '..' -- rejected before resolution, "
                "the same defense-in-depth discipline used for untrusted paths elsewhere in this portfolio."
            )
        candidate = (self._root / raw).resolve()
        try:
            candidate.relative_to(self._root)
        except ValueError:
            self._audit.record("path_check", relative_path, False, "resolved path escapes sandbox root")
            raise SandboxViolation(f"Path {relative_path!r} resolves outside the sandbox root {self._root}.")
        return candidate

    def read_file(self, relative_path: str) -> str:
        path = self._resolve_within_root(relative_path)
        if not path.exists() or not path.is_file():
            self._audit.record("read", relative_path, False, "file does not exist")
            raise SandboxViolation(f"{relative_path!r} does not exist in the sandbox.")
        content = path.read_text(encoding="utf-8")
        self._audit.record("read", relative_path, True)
        return content

    def write_file(self, relative_path: str, content: str) -> None:
        path = self._resolve_within_root(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self._audit.record("write", relative_path, True)

    def run_command(self, command: list[str]) -> CommandResult:
        detail = " ".join(command)
        if not command:
            self._audit.record("command", detail, False, "empty command")
            raise SandboxViolation("Empty command.")

        executable = command[0]
        if executable not in self._config.allowed_executables:
            self._audit.record("command", detail, False, f"executable {executable!r} not in allowlist")
            raise SandboxViolation(
                f"Executable {executable!r} is not allowed. Allowed: {self._config.allowed_executables}"
            )

        if executable == "git":
            subcommand = command[1] if len(command) > 1 else None
            if subcommand not in self._config.allowed_git_subcommands:
                self._audit.record("command", detail, False, f"git subcommand {subcommand!r} not in allowlist")
                raise SandboxViolation(
                    f"git subcommand {subcommand!r} is not allowed. "
                    f"Allowed: {self._config.allowed_git_subcommands} -- push/fetch/remote/clone are "
                    "deliberately absent, not merely blocked by a separate check."
                )

        # `pytest`/`python` resolved as bare names via subprocess.run are
        # unreliable across platforms -- they depend on the parent
        # process's PATH already including the right venv/Scripts
        # directory, which isn't guaranteed just because *this* process
        # is running under that interpreter. `[sys.executable, "-m", ...]`
        # is the portable, recommended invocation regardless of PATH
        # state; policy checks above still apply to the original,
        # unmodified command.
        actual_command = command
        if executable == "pytest":
            actual_command = [sys.executable, "-m", "pytest", *command[1:]]
        elif executable == "python":
            actual_command = [sys.executable, *command[1:]]

        try:
            result = subprocess.run(
                actual_command,
                cwd=self._root,
                timeout=self._config.command_timeout_seconds,
                capture_output=True,
                text=True,
            )
        except subprocess.TimeoutExpired as exc:
            self._audit.record("command", detail, False, "timed out")
            raise SandboxViolation(
                f"Command {command} timed out after {self._config.command_timeout_seconds}s."
            ) from exc
        except OSError as exc:
            self._audit.record("command", detail, False, f"execution error: {exc}")
            raise SandboxViolation(f"Command {command} failed to execute: {exc}") from exc

        self._audit.record("command", detail, True)
        return CommandResult(command=command, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
