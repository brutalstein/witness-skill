from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from witness_qa import __version__
from witness_qa.cli import app

runner = CliRunner()


def test_version_option() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_doctor_reports_native_host_readiness_without_api_key(monkeypatch, tmp_path: Path) -> None:
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "WITNESS_AGENT_COMMAND"):
        monkeypatch.delenv(name, raising=False)
    skill = tmp_path / "witness" / "SKILL.md"
    skill.parent.mkdir()
    skill.write_text("---\nname: witness\ndescription: test\n---\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["doctor", "--json", "--skip-browser", "--skill-path", str(skill)],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ready"] is True
    assert payload["capabilities"]["native_codex_host"]["ready"] is True
    assert payload["capabilities"]["native_codex_host"]["requires_api_key"] is False


def test_native_submit_requires_expected_turn() -> None:
    result = runner.invoke(
        app,
        ["session", "submit", "--decision-json", "{}"],
    )
    assert result.exit_code == 2
    assert "--expected-turn" in result.output
