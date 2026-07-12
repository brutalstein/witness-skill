from __future__ import annotations

import io
import json
import time
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import witness_qa.host_session as host_module
from witness_qa.errors import ConfigurationError, ReasoningError, WitnessError
from witness_qa.host_session import HostSessionClient, HostSessionRuntime, resolve_state_path
from witness_qa.models import (
    ActionResult,
    Confidence,
    Observation,
    OverallStatus,
    Persona,
    ProjectProfile,
    ProjectType,
)


def _decision(kind: str, *, judgment: str = "match", **action: object) -> dict:
    return {
        "expectation": "The target should respond correctly.",
        "action_taken": "current state",
        "observation_summary": "The state is visible.",
        "judgment": judgment,
        "confidence": "high",
        "reasoning": "Evidence supports this decision.",
        "hypothesis_if_mismatch": "",
        "severity": "none" if judgment == "match" else "high",
        "suggested_investigation": "",
        "visual_assessment": "Readable",
        "next_action": {"kind": kind, **action},
    }


class FakeAdapter:
    name = "fake"
    supported_actions = ("run_command",)

    def __init__(self) -> None:
        self.handle = object()
        self.observe_count = 0
        self.raise_on_start = False
        self.raise_on_observe = False
        self.raise_on_stop = False
        self.actions = []

    def start(self, profile):
        if self.raise_on_start:
            raise RuntimeError("start failed")
        return self.handle

    def observe(self, handle):
        if self.raise_on_observe:
            raise RuntimeError("observe failed")
        self.observe_count += 1
        return Observation(
            adapter=self.name,
            summary=f"observation {self.observe_count}",
            text="visible state",
            screenshot_path="screenshots/current.png",
            structured_path="logs/current.json",
        )

    def act(self, handle, action):
        self.actions.append(action)
        return ActionResult(success=True, summary=action.human_summary())

    def stop(self, handle):
        if self.raise_on_stop:
            raise RuntimeError("stop failed")


def _spec(tmp_path: Path, *, max_turns: int = 4) -> dict:
    profile = ProjectProfile(
        target=str(tmp_path),
        project_root=str(tmp_path),
        project_type=ProjectType.CLI,
        entry_point="echo ready",
        confidence=Confidence.HIGH,
    )
    persona = Persona(name="Tester", goal="Exercise the target")
    return {
        "output_dir": str(tmp_path / "out"),
        "profile": profile.model_dump(mode="json"),
        "persona": persona.model_dump(mode="json"),
        "max_turns": max_turns,
        "report_formats": ["markdown", "json"],
        "idle_timeout": 10,
    }


def _runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, max_turns: int = 4):
    adapter = FakeAdapter()
    monkeypatch.setattr(host_module, "create_adapter", lambda *args, **kwargs: adapter)
    runtime = HostSessionRuntime(_spec(tmp_path, max_turns=max_turns))
    return runtime, adapter


def test_runtime_start_request_submit_and_finish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, adapter = _runtime(tmp_path, monkeypatch)
    runtime.start()
    request = runtime.request_payload()
    assert request["turn"] == 1
    assert request["provider"] == "codex-host"
    assert request["screenshot_path"].endswith("screenshots/current.png")
    assert request["structured_path"].endswith("logs/current.json")

    next_request = runtime.submit(_decision("run_command", command="echo hello"), expected_turn=1)
    assert next_request["turn"] == 2
    assert adapter.actions[0].command == "echo hello"

    terminal = runtime.submit(_decision("goal_reached"), expected_turn=2)
    assert terminal["terminal"] is True
    assert terminal["result"]["overall_status"] == "goal_reached"
    assert runtime.finalized is True
    assert runtime.status == "finished"

    finished_again = runtime.finish(OverallStatus.INCONCLUSIVE)
    assert finished_again["terminal"] is True
    assert runtime.shutdown_requested is True


def test_runtime_handles_start_failure_and_teardown_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, adapter = _runtime(tmp_path, monkeypatch)
    adapter.raise_on_start = True
    runtime.start()
    assert runtime.finalized
    assert runtime.result is not None
    assert runtime.result.overall_status is OverallStatus.INCONCLUSIVE
    assert "start failed" in runtime.result.infrastructure_errors[0]

    runtime, adapter = _runtime(tmp_path / "second", monkeypatch)
    runtime.start()
    adapter.raise_on_stop = True
    runtime.finish()
    assert any("teardown failed" in item for item in runtime.result.infrastructure_errors)


def test_runtime_validates_turn_schema_supported_actions_and_max_turns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, _ = _runtime(tmp_path, monkeypatch)
    runtime.start()
    with pytest.raises(WitnessError, match="Stale host decision"):
        runtime.submit(_decision("goal_reached"), expected_turn=2)
    with pytest.raises(ReasoningError, match="does not match"):
        runtime.submit({"next_action": {"kind": "goal_reached"}}, expected_turn=1)

    response = runtime.submit(_decision("click", target="Save"), expected_turn=1)
    assert response["terminal"] is True
    assert "unsupported" in response["result"]["infrastructure_errors"][0]

    limited, adapter = _runtime(tmp_path / "limited", monkeypatch, max_turns=1)
    limited.start()
    response = limited.submit(_decision("run_command", command="echo x"), expected_turn=1)
    assert response["terminal"] is True
    assert adapter.actions == []
    assert "max_turns=1" in response["result"]["infrastructure_errors"][0]


def test_runtime_observation_failure_and_mixed_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, adapter = _runtime(tmp_path, monkeypatch)
    runtime.start()
    adapter.raise_on_observe = True
    response = runtime.submit(_decision("run_command", command="echo x"), expected_turn=1)
    assert response["terminal"] is True
    assert "Observation after action failed" in response["result"]["infrastructure_errors"][0]

    runtime, _ = _runtime(tmp_path / "mixed", monkeypatch)
    runtime.start()
    terminal = runtime.submit(_decision("goal_reached", judgment="mismatch"), expected_turn=1)
    assert terminal["result"]["overall_status"] == "mixed"


def test_runtime_idle_and_missing_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, _ = _runtime(tmp_path, monkeypatch)
    runtime.observation = None
    with pytest.raises(WitnessError, match="no observation"):
        runtime.request_payload()
    runtime.last_activity = time.monotonic() - 20
    assert runtime.idle_expired() is True


def test_client_resolves_state_and_handles_success_and_http_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "out"
    state = output / ".witness" / "session.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"port": 1234, "token": "abc"}), encoding="utf-8")
    client = HostSessionClient(output)
    assert client.state_path == state.resolve()
    assert resolve_state_path(state) == state.resolve()

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"ok": true, "status": "active"}'

    monkeypatch.setattr(host_module.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    assert client.health()["status"] == "active"
    assert client.current()["ok"] is True
    assert client.submit({"x": 1}, expected_turn=3)["ok"] is True
    assert client.status()["ok"] is True
    assert client.finish()["ok"] is True

    error = urllib.error.HTTPError(
        client.base_url,
        403,
        "Forbidden",
        hdrs=None,
        fp=io.BytesIO(b'{"ok": false, "error": "Unauthorized"}'),
    )
    monkeypatch.setattr(host_module.urllib.request, "urlopen", MagicMock(side_effect=error))
    with pytest.raises(WitnessError, match="HTTP 403"):
        client.health()

    monkeypatch.setattr(
        host_module.urllib.request, "urlopen", MagicMock(side_effect=OSError("down"))
    )
    with pytest.raises(WitnessError, match="Could not contact"):
        client.health()


def test_client_rejects_invalid_state_and_non_ok_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not-json", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Could not read"):
        HostSessionClient(bad)

    state = tmp_path / "state.json"
    state.write_text(json.dumps({"port": 1234, "token": "abc"}), encoding="utf-8")
    client = HostSessionClient(state)

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"ok": false, "error": "bad decision"}'

    monkeypatch.setattr(host_module.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    with pytest.raises(WitnessError, match="bad decision"):
        client.current()
