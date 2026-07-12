from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

import witness_qa.cli as cli_module
from witness_qa.cli import app
from witness_qa.errors import WitnessError

runner = CliRunner()


def _decision(kind: str = "goal_reached", **action: object) -> dict:
    return {
        "expectation": "The target should be usable.",
        "action_taken": "initial observation",
        "observation_summary": "The target is visible.",
        "judgment": "match",
        "confidence": "high",
        "reasoning": "The evidence is sufficient.",
        "hypothesis_if_mismatch": "",
        "severity": "none",
        "suggested_investigation": "",
        "visual_assessment": "Readable",
        "next_action": {"kind": kind, **action},
    }


def test_detect_plan_init_personas_and_adapters_commands(tmp_path: Path) -> None:
    project = tmp_path / "site"
    project.mkdir()
    (project / "index.html").write_text("<h1>Hi</h1>", encoding="utf-8")

    detected = runner.invoke(app, ["detect", str(project)])
    assert detected.exit_code == 0
    assert json.loads(detected.stdout)["project_type"] == "web"

    plan_path = tmp_path / "plan.md"
    planned = runner.invoke(app, ["plan", str(project), "--output", str(plan_path)])
    assert planned.exit_code == 0
    assert plan_path.is_file()
    assert json.loads(planned.stdout)["project_type"] == "web"

    config = tmp_path / "witness.yaml"
    initialized = runner.invoke(app, ["init", "--path", str(config)])
    assert initialized.exit_code == 0
    assert config.is_file()

    assert runner.invoke(app, ["personas"]).exit_code == 0
    assert runner.invoke(app, ["adapters"]).exit_code == 0

    missing = runner.invoke(app, ["detect", str(tmp_path / "missing")])
    assert missing.exit_code == 2


def test_run_happy_path_and_invalid_adapter(repo_root: Path, tmp_path: Path) -> None:
    decisions = tmp_path / "decisions.json"
    decisions.write_text(json.dumps([_decision()]), encoding="utf-8")
    output = tmp_path / "run"
    result = runner.invoke(
        app,
        [
            "run",
            "--project",
            str(repo_root / "examples" / "friendly_cli"),
            "--provider",
            "scripted",
            "--decision-file",
            str(decisions),
            "--output",
            str(output),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["overall_status"] == "goal_reached"
    assert (output / "result.json").is_file()

    invalid = runner.invoke(
        app,
        [
            "run",
            "--project",
            str(repo_root / "examples" / "friendly_cli"),
            "--adapter",
            "invalid",
            "--provider",
            "scripted",
            "--decision-file",
            str(decisions),
            "--json",
        ],
    )
    assert invalid.exit_code == 2
    assert "adapter must be" in invalid.stdout


def test_verify_provider_scripted_and_missing_decision_file(tmp_path: Path, monkeypatch) -> None:
    decisions = tmp_path / "provider.json"
    decisions.write_text(json.dumps([_decision()]), encoding="utf-8")
    output = tmp_path / "provider-check"
    result = runner.invoke(
        app,
        [
            "verify-provider",
            "--provider",
            "scripted",
            "--decision-file",
            str(decisions),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["ok"] is True
    assert (output / "provider-check.json").is_file()

    missing_root = tmp_path / "missing-provider"
    missing_root.mkdir()
    monkeypatch.chdir(missing_root)
    missing = runner.invoke(app, ["verify-provider", "--provider", "scripted"])
    assert missing.exit_code != 0
    assert not Path("witness-provider-check").exists()


def test_compare_benchmark_and_replay_commands(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    baseline.write_text(json.dumps({"findings": [{"fingerprint": "old"}]}), encoding="utf-8")
    current.write_text(
        json.dumps({"findings": [{"fingerprint": "old"}, {"fingerprint": "new"}]}),
        encoding="utf-8",
    )
    compared = runner.invoke(app, ["compare", str(baseline), str(current)])
    assert compared.exit_code == 0
    assert [item["fingerprint"] for item in json.loads(compared.stdout)["new"]] == ["new"]

    result_json = tmp_path / "result.json"
    truth = tmp_path / "truth.json"
    result_json.write_text(json.dumps({"findings": []}), encoding="utf-8")
    truth.write_text(json.dumps({"expected_findings": []}), encoding="utf-8")
    benchmarked = runner.invoke(app, ["benchmark", str(result_json), str(truth)])
    assert benchmarked.exit_code == 0
    assert json.loads(benchmarked.stdout)["recall"] == 0

    trace = tmp_path / "trace.json"
    trace.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "result": {"overall_status": "goal_reached"},
                "steps": [{"decision": {"next_action": {"kind": "goal_reached"}}}],
            }
        ),
        encoding="utf-8",
    )
    replayed = runner.invoke(app, ["replay", str(trace)])
    assert replayed.exit_code == 0
    assert json.loads(replayed.stdout)["step_count"] == 1

    missing = runner.invoke(app, ["replay", str(tmp_path / "missing.json")])
    assert missing.exit_code != 0


def test_remediate_command_delegates_and_handles_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result_path = tmp_path / "result.json"
    result_path.write_text("{}", encoding="utf-8")
    outcome = SimpleNamespace(
        changed_files=["app.py"],
        verified=True,
        report_path=tmp_path / "remediation.md",
        as_dict=lambda: {"verified": True, "changed_files": ["app.py"]},
    )
    runner_instance = MagicMock()
    runner_instance.run.return_value = outcome
    constructor = MagicMock(return_value=runner_instance)
    monkeypatch.setattr("witness_qa.remediation.RemediationRunner", constructor)

    result = runner.invoke(
        app,
        [
            "remediate",
            str(result_path),
            "--output",
            str(tmp_path / "fix"),
            "--verify",
            "pytest -q",
        ],
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["verified"] is True

    runner_instance.run.side_effect = WitnessError("cannot fix")
    failed = runner.invoke(app, ["remediate", str(result_path)])
    assert failed.exit_code == 2


def test_session_commands_delegate_to_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / ".witness" / "session.json"
    state.parent.mkdir(parents=True)
    state.write_text('{"port":1,"token":"x"}', encoding="utf-8")
    client = MagicMock()
    client.current.return_value = {"ok": True, "turn": 1}
    client.submit.return_value = {"ok": True, "turn": 2}
    client.status.return_value = {"ok": True, "status": "active"}
    client.finish.return_value = {"ok": True, "terminal": True}
    monkeypatch.setattr(cli_module, "HostSessionClient", MagicMock(return_value=client))

    requested = runner.invoke(app, ["session", "request", "--session", str(state)])
    assert requested.exit_code == 0
    submitted = runner.invoke(
        app,
        [
            "session",
            "submit",
            "--session",
            str(state),
            "--expected-turn",
            "1",
            "--decision-json",
            json.dumps(_decision()),
        ],
    )
    assert submitted.exit_code == 0
    assert runner.invoke(app, ["session", "status", "--session", str(state)]).exit_code == 0
    assert runner.invoke(app, ["session", "finish", "--session", str(state)]).exit_code == 0

    client.current.side_effect = WitnessError("offline")
    failed = runner.invoke(app, ["session", "request", "--session", str(state)])
    assert failed.exit_code == 2


def test_session_start_and_install_browser_are_testable(
    repo_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "out" / ".witness" / "session.json"
    monkeypatch.setattr(cli_module, "launch_host_session", lambda *args, **kwargs: (state, {}))
    client = MagicMock()
    client.current.return_value = {"ok": True, "turn": 1}
    monkeypatch.setattr(cli_module, "HostSessionClient", MagicMock(return_value=client))
    started = runner.invoke(
        app,
        [
            "session",
            "start",
            "--project",
            str(repo_root / "examples" / "friendly_cli"),
            "--output",
            str(tmp_path / "out"),
        ],
    )
    assert started.exit_code == 0, started.output
    assert json.loads(started.stdout)["session_state"] == str(state)

    completed = SimpleNamespace(returncode=0)
    subprocess_run = MagicMock(return_value=completed)
    monkeypatch.setattr(cli_module.subprocess, "run", subprocess_run)
    assert runner.invoke(app, ["install-browser", "--with-deps"]).exit_code == 0
    assert "--with-deps" in subprocess_run.call_args.args[0]

    subprocess_run.return_value = SimpleNamespace(returncode=7)
    assert runner.invoke(app, ["install-browser"]).exit_code == 7


def test_plan_and_run_accept_cost_budget(repo_root: Path, tmp_path: Path) -> None:
    project = repo_root / "examples" / "friendly_cli"
    plan_path = tmp_path / "budget-plan.md"
    planned = runner.invoke(
        app,
        ["plan", str(project), "--max-cost", "0.25", "--output", str(plan_path)],
    )
    assert planned.exit_code == 0, planned.output
    assert "Execution budget" in plan_path.read_text(encoding="utf-8")

    decisions = tmp_path / "decisions-budget.json"
    decisions.write_text(json.dumps([_decision()]), encoding="utf-8")
    output = tmp_path / "budget-run"
    run_result = runner.invoke(
        app,
        [
            "run",
            "--project",
            str(project),
            "--provider",
            "scripted",
            "--decision-file",
            str(decisions),
            "--max-cost",
            "0.10",
            "--output",
            str(output),
            "--json",
        ],
    )
    assert run_result.exit_code == 0, run_result.output
    payload = json.loads(run_result.stdout)
    assert payload["max_cost_usd"] == 0.1
    assert payload["budget_exceeded"] is False
