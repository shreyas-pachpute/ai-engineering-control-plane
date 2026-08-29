"""Renders a task run to JSON (the full audit trail -- PROJECT.md Section
18: "the primary way an engineering manager or security reviewer can
answer 'what did this agent actually do'") and Markdown.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from controlplane.agent.loop import TaskOutcome
from controlplane.sandbox.policy import AuditLog


def trace_to_dict(run_id: str, outcome: TaskOutcome, audit_log: AuditLog, llm_call_count: int) -> dict:
    return {
        "run_id": run_id,
        "completed": outcome.completed,
        "attempts_used": outcome.attempts_used,
        "diagnosis": outcome.diagnosis,
        "scope_violations": outcome.scope_violations,
        "final_test_output": outcome.final_test_output,
        "pr": outcome.pr.model_dump(mode="json") if outcome.pr else None,
        "commit": dataclasses.asdict(outcome.commit_result) if outcome.commit_result else None,
        "audit_log": [dataclasses.asdict(e) for e in audit_log.entries],
        "blocked_action_count": len(audit_log.blocked_entries),
        "llm_call_count": llm_call_count,
    }


def render_markdown(run_id: str, outcome: TaskOutcome, audit_log: AuditLog) -> str:
    lines = [
        f"# Engineering Task Run — {run_id}",
        "",
        f"**Completed:** {outcome.completed}  |  **Attempts:** {outcome.attempts_used}",
        f"**Scope violations:** {outcome.scope_violations or 'none'}",
        f"**Blocked actions (audit log):** {len(audit_log.blocked_entries)}",
        "",
        "## Diagnosis",
        outcome.diagnosis or "_(none recorded)_",
        "",
        "## Final Test Output",
        "```",
        outcome.final_test_output,
        "```",
    ]

    if outcome.pr:
        lines += [
            "",
            "## Pull Request (for human review — never auto-merged)",
            f"**{outcome.pr.title}**",
            outcome.pr.summary_of_changes,
            f"_Why: {outcome.pr.why}_",
        ]

    if audit_log.blocked_entries:
        lines += ["", "## Blocked Actions"]
        for e in audit_log.blocked_entries:
            lines.append(f"- [{e.timestamp}] {e.action_type}: {e.detail} — {e.reason}")

    lines += ["", "## Full Audit Log"]
    for e in audit_log.entries:
        status = "OK" if e.allowed else "BLOCKED"
        lines.append(f"- [{e.timestamp}] {status} {e.action_type}: {e.detail}")

    return "\n".join(lines)


def save_run(run_id: str, outcome: TaskOutcome, audit_log: AuditLog, llm_call_count: int, runs_dir: Path) -> Path:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "trace.json").write_text(
        json.dumps(trace_to_dict(run_id, outcome, audit_log, llm_call_count), indent=2), encoding="utf-8"
    )
    (run_dir / "report.md").write_text(render_markdown(run_id, outcome, audit_log), encoding="utf-8")
    return run_dir
