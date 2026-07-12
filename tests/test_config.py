from pathlib import Path

from witness_qa.config import load_config, write_default_config


def test_default_config_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "witness.yaml"
    write_default_config(path)
    config = load_config(tmp_path)
    assert config.version == 1
    assert config.visual.enabled
    assert "markdown" in config.reporting.formats
