from datetime import UTC, datetime
from pathlib import Path

from witness_qa.models import (
    ActionKind,
    AdapterAction,
    Confidence,
    Judgment,
    Observation,
    OverallStatus,
    Persona,
    ProjectProfile,
    ProjectType,
    ReasoningDecision,
    SessionStep,
    Severity,
)
from witness_qa.reporting import ReportWriter


def test_report_includes_evidence_backed_finding(tmp_path: Path) -> None:
    screenshot = tmp_path / "screenshots" / "001.png"
    screenshot.parent.mkdir()
    screenshot.write_bytes(b"png")
    step = SessionStep(
        turn=1,
        action=None,
        action_result=None,
        observation=Observation(
            adapter="web", summary="page", screenshot_path="screenshots/001.png"
        ),
        decision=ReasoningDecision(
            expectation="A confirmation should appear.",
            action_taken="click: submit",
            observation_summary="An error is visible.",
            judgment=Judgment.MISMATCH,
            confidence=Confidence.HIGH,
            reasoning="The core flow is blocked.",
            hypothesis_if_mismatch="The submission handler may reject valid data.",
            severity=Severity.HIGH,
            next_action=AdapterAction(kind=ActionKind.GOAL_BLOCKED, reason="Cannot continue."),
        ),
    )
    result = ReportWriter(tmp_path).write(
        profile=ProjectProfile(
            target="x", project_type=ProjectType.WEB, confidence=Confidence.HIGH
        ),
        persona=Persona(name="New user", goal="Sign up"),
        steps=[step],
        overall_status=OverallStatus.GOAL_BLOCKED,
        adapter="web",
        provider="test",
        model="test",
        started_at=datetime.now(UTC),
        infrastructure_errors=[],
    )
    report = Path(result.report_path).read_text(encoding="utf-8")
    assert "[HIGH]" in report
    assert "screenshots/001.png" in report


def test_trace_redacts_typed_text(tmp_path: Path) -> None:
    step = SessionStep(
        turn=1,
        action=AdapterAction(kind=ActionKind.TYPE, target="Password", text="secret-value"),
        action_result=None,
        observation=Observation(adapter="web", summary="page"),
        decision=ReasoningDecision(
            expectation="Password accepted.",
            action_taken="type: Password",
            observation_summary="Password field is filled.",
            judgment=Judgment.MATCH,
            confidence=Confidence.HIGH,
            reasoning="The field accepted input.",
            hypothesis_if_mismatch="",
            severity=Severity.NONE,
            next_action=AdapterAction(kind=ActionKind.TYPE, target="Token", text="another-secret"),
        ),
    )
    result = ReportWriter(tmp_path).write(
        profile=ProjectProfile(
            target="x", project_type=ProjectType.WEB, confidence=Confidence.HIGH
        ),
        persona=Persona(name="New user", goal="Sign up"),
        steps=[step],
        overall_status=OverallStatus.INCONCLUSIVE,
        adapter="web",
        provider="test",
        model="test",
        started_at=datetime.now(UTC),
        infrastructure_errors=[],
    )
    trace = Path(result.trace_path).read_text(encoding="utf-8")
    assert "secret-value" not in trace
    assert "another-secret" not in trace
    assert trace.count("[REDACTED]") == 2
