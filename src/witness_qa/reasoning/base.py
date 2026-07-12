from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import (
    Observation,
    Persona,
    ProjectProfile,
    ReasoningDecision,
    SessionStep,
    UsageMetrics,
)


class ReasoningEngine(ABC):
    provider_name: str
    model: str

    def __init__(self) -> None:
        self.usage = UsageMetrics()

    @abstractmethod
    def decide(
        self,
        *,
        profile: ProjectProfile,
        persona: Persona,
        adapter_name: str,
        allowed_actions: tuple[str, ...],
        history: list[SessionStep],
        observation: Observation,
        previous_action: str,
    ) -> ReasoningDecision:
        """Judge the current observation and choose one next action or stopping condition."""
