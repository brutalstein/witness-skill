from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import ConfigurationError
from .models import AdapterAction


class TraceReplay:
    def __init__(self, trace_path: Path) -> None:
        try:
            self.data = json.loads(trace_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ConfigurationError(f"Could not read trace {trace_path}: {exc}") from exc
        self.steps = self.data.get("steps") or []

    def actions(self) -> list[AdapterAction]:
        actions: list[AdapterAction] = []
        for step in self.steps:
            action = step.get("decision", {}).get("next_action")
            if not action or action.get("kind") in {
                "goal_reached",
                "goal_blocked",
                "give_up_and_report",
            }:
                continue
            if action.get("text") == "[REDACTED]":
                raise ConfigurationError(
                    "Trace contains a redacted input action and cannot be replayed automatically. "
                    "Supply a secure fixture or replay only non-sensitive actions."
                )
            actions.append(AdapterAction.model_validate(action))
        return actions

    def summary(self) -> dict[str, Any]:
        manifest = self.data.get("manifest") or {}
        result = self.data.get("result") or {}
        return {
            "schema_version": self.data.get("schema_version"),
            "manifest": manifest,
            "overall_status": result.get("overall_status"),
            "step_count": len(self.steps),
            "replayable_action_count": sum(
                1
                for step in self.steps
                if step.get("decision", {}).get("next_action", {}).get("kind")
                not in {None, "goal_reached", "goal_blocked", "give_up_and_report"}
            ),
        }
