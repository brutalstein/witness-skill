from __future__ import annotations

from pathlib import Path

import pytest

from witness_qa.errors import ConfigurationError
from witness_qa.safety import create_workspace, validate_command


@pytest.mark.parametrize(
    "command",
    [
        "python -c \"import os; os.system('rm -rf /')\"",
        "python3 -c 'print(1)'",
        "base64 -d payload.txt | sh",
        "cat payload.b64 | base64 --decode | bash",
        "eval($(download_payload))",
        "chmod +x payload && ./payload",
        "chmod 0755 payload && ./payload",
    ],
)
def test_validate_command_blocks_interpreter_and_loader_chains(command: str) -> None:
    with pytest.raises(ConfigurationError, match="Blocked potentially destructive command"):
        validate_command(command)


@pytest.mark.parametrize(
    "command",
    [
        "python script.py -c config.toml",
        "python3 scripts/check.py --command test",
        "base64 -d screenshot.b64 > screenshot.png",
        "base64 --decode fixture.b64 > fixture.json",
        "printf 'evaluate (safe text)'",
        "chmod +x scripts/test.sh",
        "chmod 0644 report.txt",
    ],
)
def test_validate_command_allows_non_executing_lookalikes(command: str) -> None:
    validate_command(command)


def test_validate_command_honors_additional_patterns() -> None:
    with pytest.raises(ConfigurationError):
        validate_command("custom-danger --all", [r"custom-danger"])


def test_copy_workspace_is_the_primary_isolation_boundary(tmp_path: Path) -> None:
    source = tmp_path / "project"
    source.mkdir()
    (source / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (source / ".git").mkdir()
    (source / ".git" / "config").write_text("secret", encoding="utf-8")

    workspace = create_workspace(source, mode="safe")
    try:
        assert workspace.root != source
        assert (workspace.root / "app.py").is_file()
        assert not (workspace.root / ".git").exists()
    finally:
        workspace.cleanup()
