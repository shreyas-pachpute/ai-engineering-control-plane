"""Scope-integrity check -- deterministic, not LLM-judged.

PROJECT.md Section 127: "Scope creep: the agent modifies files outside
what the task actually required -- mitigated by... requiring the diff
review to flag unexpected file changes." The sandbox layer already blocks
any path outside the repo root; this catches the narrower, task-specific
case of the agent editing the test file itself to make it pass, which is
in-bounds for the sandbox but not a legitimate fix.
"""

from __future__ import annotations

from controlplane.agent.schemas import FixProposal


def validate_fix_scope(proposal: FixProposal, editable_files: set[str], forbidden_files: set[str]) -> list[str]:
    violations: list[str] = []

    if not proposal.file_edits:
        violations.append("Fix proposal contains no file edits at all.")

    for edit in proposal.file_edits:
        if edit.file_path in forbidden_files:
            violations.append(
                f"Fix proposal edits {edit.file_path!r}, which is the test file itself -- "
                "rewriting a test to accept a bug isn't a fix."
            )
        elif edit.file_path not in editable_files:
            violations.append(
                f"Fix proposal edits {edit.file_path!r}, which isn't a known file in this task's scope."
            )

    return violations
