from pathlib import Path

from witness_qa.adapters.cli import CLIAdapter
from witness_qa.models import ActionKind, AdapterAction, Confidence, ProjectProfile, ProjectType


def test_cli_adapter_runs_real_command(tmp_path: Path) -> None:
    profile = ProjectProfile(
        target=str(tmp_path),
        project_root=str(tmp_path),
        project_type=ProjectType.CLI,
        entry_point="python --version",
        confidence=Confidence.HIGH,
    )
    adapter = CLIAdapter(tmp_path / "out")
    session = adapter.start(profile)
    try:
        result = adapter.act(
            session, AdapterAction(kind=ActionKind.RUN_COMMAND, command="printf hello")
        )
        observation = adapter.observe(session)
    finally:
        adapter.stop(session)
    assert result.success
    assert "hello" in observation.text
    assert (tmp_path / "out" / observation.screenshot_path).is_file()


def test_cli_adapter_blocks_privileged_command(tmp_path: Path) -> None:
    profile = ProjectProfile(
        target=str(tmp_path),
        project_root=str(tmp_path),
        project_type=ProjectType.CLI,
        entry_point="python --version",
        confidence=Confidence.HIGH,
    )
    adapter = CLIAdapter(tmp_path / "out")
    session = adapter.start(profile)
    try:
        result = adapter.act(
            session, AdapterAction(kind=ActionKind.RUN_COMMAND, command="sudo reboot")
        )
    finally:
        adapter.stop(session)
    assert not result.success
    assert "safety policy" in result.infrastructure_error
