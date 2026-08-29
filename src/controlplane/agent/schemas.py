"""Structured I/O for the orchestrating agent.

`FixProposal.file_edits` is where scope gets enforced twice: the sandbox
layer blocks any path outside the repo root, and
agent/grounding.py separately checks the agent only touched files it was
actually supposed to (PROJECT.md Section 127's "scope creep" mitigation)
-- specifically, never the test file itself, since rewriting a test to
accept a bug isn't a fix.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FileEdit(BaseModel):
    file_path: str = Field(description="Path relative to the repo root, e.g. 'mathutils.py'.")
    new_content: str = Field(description="The complete new content of the file.")


class FixProposal(BaseModel):
    diagnosis: str = Field(description="What's actually wrong, based on the test failure output given.")
    file_edits: list[FileEdit] = Field(description="The files to change to fix it. Never the test file itself.")


class PullRequestDescription(BaseModel):
    title: str
    summary_of_changes: str
    why: str = Field(description="Why this change fixes the diagnosed issue.")
