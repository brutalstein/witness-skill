from __future__ import annotations

import os
from pathlib import Path

import pytest

from witness_qa.errors import WitnessError
from witness_qa.host_session import HostSessionClient, launch_host_session
from witness_qa.models import Confidence, Persona, ProjectProfile, ProjectType


def _decision(kind: str, **action: object) -> dict:
    return {
        "expectation": "The CLI should behave as described.",
        "action_taken": "current state",
        "observation_summary": "The terminal state is observable.",
        "judgment": "match",
        "confidence": "high",
        "reasoning": "The visible terminal evidence supports the next action.",
        "hypothesis_if_mismatch": "",
        "severity": "none",
        "suggested_investigation": "",
        "visual_assessment": "The terminal screenshot is readable.",
        "next_action": {"kind": kind, **action},
    }


def test_native_host_session_runs_real_cli_adapter_without_model_api(tmp_path: Path) -> None:
    project = Path(__file__).parents[1] / "examples" / "friendly_cli"
    output = tmp_path / "native-session"
    profile = ProjectProfile(
        target=str(project),
        project_root=str(project),
        project_type=ProjectType.CLI,
        entry_point="python cli.py --help",
        confidence=Confidence.HIGH,
    )
    persona = Persona(name="CLI user", goal="Run the greeting in shout mode")
    spec = {
        "output_dir": str(output),
        "profile": profile.model_dump(mode="json"),
        "persona": persona.model_dump(mode="json"),
        "adapter_options": {"sandbox": "copy", "command_timeout": 10},
        "max_turns": 5,
        "report_formats": ["markdown", "json"],
        "seed": 0,
        "idle_timeout": 60,
    }
    state_path, _ = launch_host_session(spec, output, startup_timeout=20)
    client = HostSessionClient(state_path)

    request = client.current()
    assert request["provider"] == "codex-host"
    if os.name != "nt":
        assert state_path.stat().st_mode & 0o077 == 0
    assert Path(request["screenshot_path"]).is_file()
    assert request["schema"]["additionalProperties"] is False

    next_request = client.submit(
        _decision("run_command", command="python cli.py Ada --shout"), expected_turn=1
    )
    assert "HELLO, ADA!" in next_request["observation"]["text"]

    with pytest.raises(WitnessError, match="Stale host decision"):
        client.submit(_decision("goal_reached", reason="stale"), expected_turn=1)

    terminal = client.submit(
        _decision("goal_reached", reason="Greeting is correct"), expected_turn=2
    )
    assert terminal["terminal"] is True
    assert terminal["result"]["overall_status"] == "goal_reached"
    assert Path(terminal["result"]["report_path"]).is_file()
