from controlplane.agent.grounding import validate_fix_scope
from controlplane.agent.schemas import FileEdit, FixProposal


def _proposal(edits) -> FixProposal:
    return FixProposal(diagnosis="d", file_edits=edits)


def test_editing_the_editable_file_passes():
    proposal = _proposal([FileEdit(file_path="mathutils.py", new_content="...")])
    assert validate_fix_scope(proposal, {"mathutils.py"}, {"test_mathutils.py"}) == []


def test_editing_the_test_file_flagged():
    proposal = _proposal([FileEdit(file_path="test_mathutils.py", new_content="...")])
    violations = validate_fix_scope(proposal, {"mathutils.py"}, {"test_mathutils.py"})
    assert len(violations) == 1
    assert "test file itself" in violations[0]


def test_editing_an_unknown_file_flagged():
    proposal = _proposal([FileEdit(file_path="unrelated.py", new_content="...")])
    violations = validate_fix_scope(proposal, {"mathutils.py"}, {"test_mathutils.py"})
    assert len(violations) == 1
    assert "isn't a known file" in violations[0]


def test_no_edits_at_all_flagged():
    proposal = _proposal([])
    violations = validate_fix_scope(proposal, {"mathutils.py"}, {"test_mathutils.py"})
    assert any("no file edits" in v for v in violations)


def test_mixed_valid_and_invalid_edits_flags_only_the_invalid_one():
    proposal = _proposal([
        FileEdit(file_path="mathutils.py", new_content="..."),
        FileEdit(file_path="test_mathutils.py", new_content="..."),
    ])
    violations = validate_fix_scope(proposal, {"mathutils.py"}, {"test_mathutils.py"})
    assert len(violations) == 1
