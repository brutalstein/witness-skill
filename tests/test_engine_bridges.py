from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from witness_qa.cli import app
from witness_qa.engine_bridges import install_engine_bridge
from witness_qa.errors import ConfigurationError


def test_install_unity_and_unreal_engine_bridges(tmp_path: Path) -> None:
    unity = tmp_path / "Packages" / "com.witness.qa"
    unreal = tmp_path / "Plugins" / "WitnessBridge"
    unity_files = install_engine_bridge("unity", unity)
    unreal_files = install_engine_bridge("unreal", unreal)
    assert unity / "Runtime" / "WitnessBridge.cs" in unity_files
    assert (unity / "package.json").is_file()
    assert unreal / "WitnessBridge.uplugin" in unreal_files
    assert (unreal / "Source" / "WitnessBridge" / "WitnessBridge.Build.cs").is_file()


def test_engine_bridge_install_refuses_existing_content_without_force(tmp_path: Path) -> None:
    destination = tmp_path / "bridge"
    destination.mkdir()
    marker = destination / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Refusing to overwrite"):
        install_engine_bridge("unity", destination)
    assert marker.read_text(encoding="utf-8") == "keep"
    install_engine_bridge("unity", destination, force=True)
    assert not marker.exists()


def test_engine_bridge_cli_reports_invalid_engine(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["install-engine-bridge", "cryengine", str(tmp_path / "x")])
    assert result.exit_code == 2
    assert "Unsupported engine bridge" in result.output
