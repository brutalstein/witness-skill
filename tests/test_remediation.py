from pathlib import Path

import pytest

from witness_qa.models import (
    Confidence,
    Finding,
    OverallStatus,
    ProjectProfile,
    ProjectType,
    SessionMetadata,
    SessionResult,
    Severity,
)
from witness_qa.remediation import RemediationError, RemediationRunner


def _result(path: Path, project: Path) -> Path:
    result = SessionResult(
        overall_status=OverallStatus.GOAL_BLOCKED,
        personas_run=["tester"],
        findings=[
            Finding(
                persona="tester",
                severity=Severity.HIGH,
                summary="Greeting is wrong",
                expectation="Hello",
                observation="Bye",
                evidence_path="",
                reasoning="Mismatch",
                hypothesis="Wrong constant",
                turn=1,
            )
        ],
        report_path="report.md",
        trace_path="trace.json",
        profile=ProjectProfile(
            target=str(project),
            project_root=str(project),
            project_type=ProjectType.CLI,
            confidence=Confidence.HIGH,
        ),
        metadata=SessionMetadata(
            adapter="cli",
            provider="test",
            model="test",
            project_type=ProjectType.CLI,
            project_confidence=Confidence.HIGH,
            started_at="2026-01-01T00:00:00Z",
            finished_at="2026-01-01T00:00:01Z",
            duration_seconds=1,
            turns=1,
        ),
    )
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return path


def test_patch_remediation_isolated_and_verified(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text('print("Bye")\n', encoding="utf-8")
    result = _result(tmp_path / "result.json", project)
    patch = tmp_path / "fix.patch"
    patch.write_text(
        '--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-print("Bye")\n+print("Hello")\n',
        encoding="utf-8",
    )
    outcome = RemediationRunner(result_path=result, output_dir=tmp_path / "fix").run(
        patch_file=patch, verification_commands=["python app.py"]
    )
    assert outcome.verified
    assert not outcome.applied_to_source
    assert (project / "app.py").read_text(encoding="utf-8") == 'print("Bye")\n'
    assert (outcome.workspace / "app.py").read_text(encoding="utf-8") == 'print("Hello")\n'
    assert "app.py" in outcome.changed_files


def test_agent_remediation_can_apply_only_after_verification(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "value.txt").write_text("bad\n", encoding="utf-8")
    result = _result(tmp_path / "result.json", project)
    fixer = tmp_path / "fixer.py"
    fixer.write_text(
        "from pathlib import Path\nimport json\nPath('value.txt').write_text('good\\n')\nprint(json.dumps({'summary':'fixed','verification_commands':['grep -q good value.txt']}))\n",
        encoding="utf-8",
    )
    outcome = RemediationRunner(result_path=result, output_dir=tmp_path / "fix").run(
        agent_command=f"python {fixer}", apply_to_source=True
    )
    assert outcome.verified
    assert outcome.applied_to_source
    assert (project / "value.txt").read_text(encoding="utf-8") == "good\n"


def test_remediation_refuses_escaping_patch(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text("x\n", encoding="utf-8")
    result = _result(tmp_path / "result.json", project)
    patch = tmp_path / "bad.patch"
    patch.write_text("--- a/app.py\n+++ ../../escape.py\n@@ -1 +1 @@\n-x\n+y\n", encoding="utf-8")
    with pytest.raises(RemediationError):
        RemediationRunner(result_path=result, output_dir=tmp_path / "fix").run(patch_file=patch)
