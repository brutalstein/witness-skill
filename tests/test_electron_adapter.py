from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from witness_qa.adapters.electron import ElectronAdapter
from witness_qa.models import Confidence, ProjectProfile, ProjectType


class FakeProcess:
    returncode = None

    def poll(self):
        return None


def test_electron_launch_command_handles_package_runners() -> None:
    package_command = ElectronAdapter._launch_command(
        "npm run start", 9222, Path("profile with spaces")
    )
    assert package_command.startswith("npm run start -- --remote-debugging-port=9222")
    assert "--remote-debugging-address=127.0.0.1" in package_command
    assert "--user-data-dir=" in package_command
    assert "profile with spaces" in package_command
    direct_command = ElectronAdapter._launch_command("npx electron .", 9223)
    assert "--remote-debugging-port=9223" in direct_command
    assert direct_command.endswith("--remote-debugging-address=127.0.0.1")
    templated = ElectronAdapter._launch_command("run --port={debug_port}", 42)
    assert templated.startswith("run --port=42")
    assert "--remote-debugging-address=127.0.0.1" in templated


def test_electron_adapter_connects_to_renderer_over_cdp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}
    process = FakeProcess()

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return process

    page = MagicMock()
    page.url = "file:///app/index.html"
    context = MagicMock()
    context.pages = [page]
    browser = MagicMock()
    browser.contexts = [context]
    chromium = MagicMock()
    chromium.connect_over_cdp.return_value = browser
    playwright = SimpleNamespace(chromium=chromium, stop=MagicMock())
    manager = MagicMock()
    manager.start.return_value = playwright

    monkeypatch.setattr("witness_qa.adapters.electron.subprocess.Popen", fake_popen)
    monkeypatch.setattr("witness_qa.adapters.electron.sync_playwright", lambda: manager)
    monkeypatch.setattr(ElectronAdapter, "_wait_for_cdp", lambda self, endpoint, child: None)
    monkeypatch.setattr("witness_qa.adapters.web.terminate_process_tree", lambda child: None)

    profile = ProjectProfile(
        target=str(tmp_path),
        project_root=str(tmp_path),
        project_type=ProjectType.DESKTOP,
        entry_point="npm run start",
        confidence=Confidence.HIGH,
        metadata={"framework": "electron"},
    )
    adapter = ElectronAdapter(tmp_path / "out", electron_debug_port=9333)
    session = adapter.start(profile)
    try:
        assert "--remote-debugging-port=9333" in str(captured["command"])
        assert "--user-data-dir=" in str(captured["command"])
        chromium.connect_over_cdp.assert_called_once_with("http://127.0.0.1:9333")
        assert session.page is page
        assert session.base_url == "file:///app/index.html"
        page.on.assert_called()
    finally:
        adapter.stop(session)
