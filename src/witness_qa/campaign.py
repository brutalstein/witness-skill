from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .adapters.base import Adapter
from .models import CampaignResult, Persona, ProjectProfile, TestJourney
from .orchestrator import Orchestrator
from .reasoning.base import ReasoningEngine
from .reporting import CampaignReportWriter


class CampaignRunner:
    def __init__(
        self,
        *,
        output_dir: Path,
        adapter_factory: Callable[[Path, Persona], Adapter],
        reasoner_factory: Callable[[Path], ReasoningEngine],
        max_turns: int,
        report_formats: list[str] | None = None,
        seed: int = 0,
        max_cost_usd: float | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.adapter_factory = adapter_factory
        self.reasoner_factory = reasoner_factory
        self.max_turns = max_turns
        self.report_formats = report_formats
        self.seed = seed
        if max_cost_usd is not None and max_cost_usd < 0:
            raise ValueError("max_cost_usd must be non-negative")
        self.max_cost_usd = max_cost_usd

    def run(
        self,
        *,
        profile: ProjectProfile,
        personas: list[Persona],
        journeys: list[TestJourney] | None = None,
    ) -> CampaignResult:
        sessions = []
        selected_journeys = journeys or []
        combinations: list[tuple[Persona, TestJourney | None]] = []
        if selected_journeys:
            for persona in personas:
                for journey in selected_journeys:
                    combinations.append((persona, journey))
        else:
            combinations = [(persona, None) for persona in personas]
        spent = 0.0
        budget_exceeded = False
        for index, (persona, journey) in enumerate(combinations, start=1):
            remaining_budget = (
                max(0.0, self.max_cost_usd - spent) if self.max_cost_usd is not None else None
            )
            if remaining_budget is not None and remaining_budget <= 0:
                budget_exceeded = True
                break
            effective = persona.model_copy(deep=True)
            if journey:
                effective.goal = journey.goal
                if journey.success_criteria:
                    effective.success_criteria = journey.success_criteria
                effective.name = f"{persona.name} · {journey.name}"
            session_dir = self.output_dir / "sessions" / f"{index:03d}-{_slug(effective.name)}"
            adapter = self.adapter_factory(session_dir, effective)
            reasoner = self.reasoner_factory(session_dir)
            result = Orchestrator(
                adapter=adapter,
                reasoner=reasoner,
                output_dir=session_dir,
                max_turns=self.max_turns,
                report_formats=self.report_formats,
                seed=self.seed + index,
                max_cost_usd=remaining_budget,
            ).run(profile=profile.model_copy(deep=True), persona=effective)
            sessions.append(result)
            spent = round(spent + result.metadata.usage.estimated_cost_usd, 8)
            if result.budget_exceeded or (
                self.max_cost_usd is not None and spent > self.max_cost_usd
            ):
                budget_exceeded = True
                break
        return CampaignReportWriter(self.output_dir).write(
            sessions,
            max_cost_usd=self.max_cost_usd,
            budget_exceeded=budget_exceeded,
        )


def _slug(value: str) -> str:
    return (
        "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")[:70]
        or "session"
    )
