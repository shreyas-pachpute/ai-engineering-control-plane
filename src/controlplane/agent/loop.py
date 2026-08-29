"""The orchestrating agent: a bounded investigate -> fix -> validate loop.

PROJECT.md Section 86: "the sequence of steps cannot be known in advance
and genuinely depends on what's discovered" -- how many fix attempts are
needed, and whether the second attempt's diagnosis differs from the
first's, depends entirely on what the test output says each time. Bounded
to `config.max_fix_attempts` LLM calls, same cost discipline as the rest
of this portfolio.

Every read, write, and command below goes through `sandbox`, never a bare
filesystem or subprocess call -- see sandbox/policy.py.
"""

from __future__ import annotations

from dataclasses import dataclass

from controlplane.agent.grounding import validate_fix_scope
from controlplane.agent.prompts import PR_SYSTEM_INSTRUCTION, SYSTEM_INSTRUCTION, fix_prompt, pr_description_prompt
from controlplane.agent.schemas import FixProposal, PullRequestDescription
from controlplane.config import Config
from controlplane.llm import LLMClient
from controlplane.sandbox.policy import CommandResult, Sandbox

EDITABLE_FILES = {"mathutils.py"}
FORBIDDEN_FILES = {"test_mathutils.py"}
TEST_COMMAND = ["pytest", "test_mathutils.py", "-v"]


@dataclass
class TaskOutcome:
    completed: bool
    attempts_used: int
    final_test_output: str
    diagnosis: str | None
    scope_violations: list[str]
    pr: PullRequestDescription | None
    commit_result: CommandResult | None


def run_fix_task(config: Config, client: LLMClient, sandbox: Sandbox) -> TaskOutcome:
    source_files = {f: sandbox.read_file(f) for f in EDITABLE_FILES}

    diagnosis: str | None = None
    scope_violations: list[str] = []
    test_output = ""
    completed = False
    attempts_used = 0

    for attempt in range(1, config.max_fix_attempts + 1):
        attempts_used = attempt
        test_result = sandbox.run_command(TEST_COMMAND)
        test_output = test_result.stdout + test_result.stderr
        if test_result.succeeded:
            completed = True
            break

        proposal: FixProposal = client.generate_structured(
            SYSTEM_INSTRUCTION, fix_prompt(source_files, test_output, attempt), FixProposal
        )
        diagnosis = proposal.diagnosis
        violations = validate_fix_scope(proposal, EDITABLE_FILES, FORBIDDEN_FILES)
        scope_violations.extend(violations)
        if violations:
            break  # never apply an out-of-scope edit; report the failure honestly

        for edit in proposal.file_edits:
            sandbox.write_file(edit.file_path, edit.new_content)
            source_files[edit.file_path] = edit.new_content
    else:
        # Attempts exhausted after applying a fix on the final iteration --
        # one last (free, deterministic) test run to capture whether it landed.
        test_result = sandbox.run_command(TEST_COMMAND)
        test_output = test_result.stdout + test_result.stderr
        completed = test_result.succeeded

    commit_result = None
    pr = None
    if completed:
        sandbox.run_command(["git", "add", "."])
        commit_result = sandbox.run_command(["git", "commit", "-m", f"Fix: {diagnosis or 'resolve failing tests'}"])
        diff_result = sandbox.run_command(["git", "diff", "HEAD~1", "HEAD"])
        pr = client.generate_structured(
            PR_SYSTEM_INSTRUCTION, pr_description_prompt(diagnosis or "", diff_result.stdout), PullRequestDescription
        )

    return TaskOutcome(
        completed=completed,
        attempts_used=attempts_used,
        final_test_output=test_output,
        diagnosis=diagnosis,
        scope_violations=scope_violations,
        pr=pr,
        commit_result=commit_result,
    )
