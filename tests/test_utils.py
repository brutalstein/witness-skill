from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from witness_qa import utils


def test_process_group_kwargs_are_platform_specific(monkeypatch) -> None:
    monkeypatch.setattr(utils.os, "name", "posix")
    assert utils.process_group_kwargs() == {"start_new_session": True}
    monkeypatch.setattr(utils.os, "name", "nt")
    assert utils.process_group_kwargs() == {"creationflags": utils.WINDOWS_NEW_PROCESS_GROUP}


def test_windows_termination_uses_taskkill_for_child_tree(monkeypatch) -> None:
    process = SimpleNamespace(pid=4321, poll=lambda: None, wait=MagicMock(), terminate=MagicMock())
    completed = SimpleNamespace(returncode=0)
    run = MagicMock(return_value=completed)
    monkeypatch.setattr(utils.os, "name", "nt")
    monkeypatch.setattr(utils.subprocess, "run", run)

    utils.terminate_process_tree(process, grace_seconds=1)

    run.assert_called_once_with(
        ["taskkill", "/PID", "4321", "/T", "/F"],
        capture_output=True,
        text=True,
        timeout=1,
        check=False,
    )
    process.wait.assert_called_once_with(timeout=1)
    process.terminate.assert_not_called()
