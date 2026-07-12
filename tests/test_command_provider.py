from __future__ import annotations

import json
import sys
from pathlib import Path

from witness_qa.models import Confidence, Observation, Persona, ProjectProfile, ProjectType
from witness_qa.reasoning.providers import CommandReasoningEngine


def test_command_provider_uses_local_host_model_protocol(tmp_path: Path) -> None:
    script = tmp_path / "agent.py"
    decision = {
        "expectation": "The image should be visible.",
        "action_taken": "initial_observation",
        "observation_summary": "A visual frame is attached.",
        "judgment": "match",
        "confidence": "high",
        "reasoning": "The frame is available for review.",
        "hypothesis_if_mismatch": "",
        "severity": "none",
        "suggested_investigation": "",
        "visual_assessment": "The frame is non-empty.",
        "next_action": {"kind": "goal_reached", "reason": "Complete."},
    }
    script.write_text(
        "import json,sys\njson.load(sys.stdin)\nprint(" + repr(json.dumps(decision)) + ")\n",
        encoding="utf-8",
    )
    engine = CommandReasoningEngine(
        command=f"{sys.executable} {script}", model="local", output_dir=tmp_path
    )
    result = engine.decide(
        profile=ProjectProfile(
            target="x", project_type=ProjectType.GAME, confidence=Confidence.HIGH
        ),
        persona=Persona(name="Tester", goal="Review"),
        adapter_name="game",
        allowed_actions=("goal_reached",),
        history=[],
        observation=Observation(adapter="game", summary="frame"),
        previous_action="initial_observation",
    )
    assert result.next_action.kind.value == "goal_reached"
    assert engine.usage.requests == 1
