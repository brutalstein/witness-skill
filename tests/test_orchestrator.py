from __future__ import annotations

from pathlib import Path

from witness_qa.adapters.cli import CLIAdapter
from witness_qa.models import (
    ActionKind,
    AdapterAction,
    Confidence,
    Judgment,
    Persona,
    ProjectProfile,
    ProjectType,
    ReasoningDecision,
    Severity,
)
from witness_qa.orchestrator import Orchestrator
from witness_qa.reasoning.base import ReasoningEngine


class DeterministicReasoner(ReasoningEngine):
    provider_name = "test"
    model = "deterministic"

    def decide(self, *, history, observation, previous_action, **kwargs):
        if not history:
            return ReasoningDecision(
                expectation="The CLI should expose usable help output.",
                action_taken="initial_observation",
                observation_summary="A terminal is ready.",
                judgment=Judgment.MATCH,
                confidence=Confidence.HIGH,
                reasoning="The target is ready for a first command.",
                hypothesis_if_mismatch="",
                severity=Severity.NONE,
                next_action=AdapterAction(
                    kind=ActionKind.RUN_COMMAND,
                    command="python -c \"print('usage: demo')\"",
                    reason="Inspect the primary help surface.",
                ),
            )
        return ReasoningDecision(
            expectation="Help text should be visible.",
            action_taken=previous_action,
            observation_summary="The terminal shows usage: demo.",
            judgment=Judgment.MATCH,
            confidence=Confidence.HIGH,
            reasoning="The command completed and exposed clear usage text.",
            hypothesis_if_mismatch="",
            severity=Severity.NONE,
            next_action=AdapterAction(
                kind=ActionKind.GOAL_REACHED, reason="The goal is observable."
            ),
        )


def test_orchestrator_writes_contract_and_report(tmp_path: Path) -> None:
    profile = ProjectProfile(
        target=str(tmp_path),
        project_root=str(tmp_path),
        project_type=ProjectType.CLI,
        entry_point="python --help",
        confidence=Confidence.HIGH,
    )
    result = Orchestrator(
        adapter=CLIAdapter(tmp_path / "out"),
        reasoner=DeterministicReasoner(),
        output_dir=tmp_path / "out",
        max_turns=4,
    ).run(profile=profile, persona=Persona(name="Tester", goal="See help"))
    assert result.overall_status.value == "goal_reached"
    assert Path(result.report_path).is_file()
    assert Path(result.trace_path).is_file()
    assert (tmp_path / "out" / "result.json").is_file()
