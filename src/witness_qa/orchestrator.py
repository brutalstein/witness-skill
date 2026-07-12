from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from .adapters.base import Adapter
from .errors import ReasoningError
from .models import (
    ActionResult,
    AdapterAction,
    Observation,
    OverallStatus,
    Persona,
    ProjectProfile,
    SessionStep,
)
from .reasoning.base import ReasoningEngine
from .reporting import ReportWriter


class Orchestrator:
    """Adapter-agnostic owner of the act -> observe -> reason -> decide loop."""

    def __init__(
        self,
        *,
        adapter: Adapter,
        reasoner: ReasoningEngine,
        output_dir: Path,
        max_turns: int = 20,
        report_formats: list[str] | None = None,
        seed: int = 0,
        max_cost_usd: float | None = None,
    ) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        self.adapter = adapter
        self.reasoner = reasoner
        self.output_dir = output_dir
        self.max_turns = max_turns
        self.seed = seed
        if max_cost_usd is not None and max_cost_usd < 0:
            raise ValueError("max_cost_usd must be non-negative")
        self.max_cost_usd = max_cost_usd
        self.reporter = ReportWriter(output_dir, report_formats)

    def run(self, *, profile: ProjectProfile, persona: Persona):
        started_at = datetime.now(UTC)
        steps: list[SessionStep] = []
        infrastructure_errors: list[str] = []
        handle = None
        status = OverallStatus.INCONCLUSIVE
        action: AdapterAction | None = None
        action_result: ActionResult | None = None
        previous_action = "initial_observation"
        budget_exceeded = False

        try:
            try:
                handle = self.adapter.start(profile)
                observation = self.adapter.observe(handle)
            except Exception as exc:
                infrastructure_errors.append(f"Adapter start/initial observation failed: {exc}")
                observation = Observation(
                    adapter=self.adapter.name,
                    summary="Witness could not start or observe the target",
                    text=str(exc),
                    errors=[str(exc)],
                )
                return self.reporter.write(
                    profile=profile,
                    persona=persona,
                    steps=steps,
                    overall_status=OverallStatus.INCONCLUSIVE,
                    adapter=self.adapter.name,
                    provider=self.reasoner.provider_name,
                    model=self.reasoner.model,
                    started_at=started_at,
                    infrastructure_errors=infrastructure_errors,
                    usage=getattr(self.reasoner, "usage", None),
                    seed=self.seed,
                    budget_exceeded=False,
                    max_cost_usd=self.max_cost_usd,
                )

            for turn in range(1, self.max_turns + 1):
                try:
                    decision = self.reasoner.decide(
                        profile=profile,
                        persona=persona,
                        adapter_name=self.adapter.name,
                        allowed_actions=self.adapter.supported_actions,
                        history=steps,
                        observation=observation,
                        previous_action=previous_action,
                    )
                except ReasoningError as exc:
                    infrastructure_errors.append(str(exc))
                    status = OverallStatus.INCONCLUSIVE
                    break

                step = SessionStep(
                    turn=turn,
                    action=action,
                    action_result=action_result,
                    observation=observation,
                    decision=decision,
                )
                steps.append(step)
                usage = getattr(self.reasoner, "usage", None)
                if (
                    self.max_cost_usd is not None
                    and usage is not None
                    and usage.cost_estimate_available
                    and usage.estimated_cost_usd > self.max_cost_usd
                ):
                    budget_exceeded = True
                    infrastructure_errors.append(
                        "Cost budget exceeded after turn "
                        f"{turn}: ${usage.estimated_cost_usd:.6f} > ${self.max_cost_usd:.6f}. "
                        "Witness preserved all evidence and stopped before the next action."
                    )
                    status = OverallStatus.INCONCLUSIVE
                    break
                next_action = decision.next_action
                if next_action.is_terminal:
                    if next_action.kind.value == "goal_reached":
                        status = OverallStatus.GOAL_REACHED
                    elif next_action.kind.value == "goal_blocked":
                        status = OverallStatus.GOAL_BLOCKED
                    else:
                        status = OverallStatus.INCONCLUSIVE
                    break

                if next_action.kind.value not in self.adapter.supported_actions:
                    infrastructure_errors.append(
                        f"Reasoning engine requested unsupported {self.adapter.name} action: {next_action.kind.value}"
                    )
                    status = OverallStatus.INCONCLUSIVE
                    break

                action = next_action
                action_result = self.adapter.act(handle, action)
                if action_result.infrastructure_error:
                    infrastructure_errors.append(action_result.infrastructure_error)
                try:
                    observation = self.adapter.observe(handle)
                except Exception as exc:
                    infrastructure_errors.append(f"Observation after action failed: {exc}")
                    status = OverallStatus.INCONCLUSIVE
                    break
                previous_action = action.human_summary()
            else:
                status = OverallStatus.INCONCLUSIVE

            if status is OverallStatus.GOAL_REACHED and any(
                step.decision.judgment.value == "mismatch" for step in steps
            ):
                status = OverallStatus.MIXED
        finally:
            if handle is not None:
                try:
                    self.adapter.stop(handle)
                except Exception as exc:
                    infrastructure_errors.append(f"Adapter teardown failed: {exc}")

        return self.reporter.write(
            profile=profile,
            persona=persona,
            steps=steps,
            overall_status=status,
            adapter=self.adapter.name,
            provider=self.reasoner.provider_name,
            model=self.reasoner.model,
            started_at=started_at,
            infrastructure_errors=infrastructure_errors,
            usage=getattr(self.reasoner, "usage", None),
            seed=self.seed,
            budget_exceeded=budget_exceeded,
            max_cost_usd=self.max_cost_usd,
        )
