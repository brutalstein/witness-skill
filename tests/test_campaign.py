from pathlib import Path

from witness_qa.adapters.cli import CLIAdapter
from witness_qa.campaign import CampaignRunner
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
from witness_qa.reasoning.base import ReasoningEngine


class DoneReasoner(ReasoningEngine):
    provider_name = "test"
    model = "done"

    def decide(self, **kwargs):
        return ReasoningDecision(
            expectation="Usable CLI",
            action_taken="initial_observation",
            observation_summary="Terminal is ready",
            judgment=Judgment.MATCH,
            confidence=Confidence.HIGH,
            reasoning="Ready",
            hypothesis_if_mismatch="",
            severity=Severity.NONE,
            next_action=AdapterAction(kind=ActionKind.GOAL_REACHED, reason="done"),
        )


def test_campaign_runs_multiple_personas(tmp_path: Path) -> None:
    profile = ProjectProfile(
        target=str(tmp_path),
        project_root=str(tmp_path),
        project_type=ProjectType.CLI,
        confidence=Confidence.HIGH,
    )
    runner = CampaignRunner(
        output_dir=tmp_path / "out",
        adapter_factory=lambda output, persona: CLIAdapter(output),
        reasoner_factory=lambda output: DoneReasoner(),
        max_turns=2,
    )
    result = runner.run(
        profile=profile,
        personas=[Persona(name="One", goal="help"), Persona(name="Two", goal="help")],
    )
    assert len(result.sessions) == 2
    assert Path(result.report_path).is_file()


class CostlyReasoner(DoneReasoner):
    model = "costly"

    def decide(self, **kwargs):
        self.usage.requests += 1
        self.usage.input_tokens += 100
        self.usage.output_tokens += 20
        self.usage.cost_estimate_available = True
        self.usage.estimated_cost_usd = 0.75
        return super().decide(**kwargs)


def test_campaign_stops_and_preserves_results_when_budget_is_exceeded(tmp_path: Path) -> None:
    profile = ProjectProfile(
        target=str(tmp_path),
        project_root=str(tmp_path),
        project_type=ProjectType.CLI,
        confidence=Confidence.HIGH,
    )
    runner = CampaignRunner(
        output_dir=tmp_path / "budget-out",
        adapter_factory=lambda output, persona: CLIAdapter(output),
        reasoner_factory=lambda output: CostlyReasoner(),
        max_turns=2,
        max_cost_usd=0.50,
    )
    result = runner.run(
        profile=profile,
        personas=[Persona(name="One", goal="help"), Persona(name="Two", goal="help")],
    )

    assert result.budget_exceeded is True
    assert result.max_cost_usd == 0.50
    assert result.estimated_cost_usd == 0.75
    assert len(result.sessions) == 1
    assert result.sessions[0].budget_exceeded is True
    assert (
        Path(result.report_path).read_text(encoding="utf-8").find("**Budget exceeded:** True") >= 0
    )
