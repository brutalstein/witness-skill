from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ..models import ActionResult, AdapterAction, Observation, ProjectProfile


class Adapter(ABC):
    name: str
    supported_actions: tuple[str, ...]

    def __init__(self, output_dir: Path, **options: Any) -> None:
        self.output_dir = output_dir
        self.options = options

    @abstractmethod
    def start(self, project_profile: ProjectProfile) -> Any:
        """Boot or connect to the target and return an adapter-owned session handle."""

    @abstractmethod
    def act(self, session_handle: Any, action: AdapterAction) -> ActionResult:
        """Perform one atomic action."""

    @abstractmethod
    def observe(self, session_handle: Any) -> Observation:
        """Capture the externally observable state."""

    @abstractmethod
    def stop(self, session_handle: Any) -> None:
        """Tear down only resources created by this adapter."""
