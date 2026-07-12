from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def test_codex_skill_and_plugin_distribution_are_consistent() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    plugin = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    marketplace = json.loads(
        (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
    )

    assert plugin["name"] == "witness-qa"
    assert plugin["version"] == version
    assert plugin["skills"] == "./skills/codex/"
    assert plugin["interface"]["displayName"] == "Witness QA"
    assert marketplace["name"] == "witness"
    entry = marketplace["plugins"][0]
    assert entry["name"] == plugin["name"]
    assert entry["source"] == {"source": "local", "path": "./"}
    assert entry["policy"]["installation"] == "AVAILABLE"


def test_repo_and_distributable_codex_skills_are_exact_mirrors() -> None:
    repo_skill = ROOT / ".agents" / "skills" / "witness"
    packaged_skill = ROOT / "skills" / "codex" / "witness"
    repo_files = {
        path.relative_to(repo_skill): path.read_bytes()
        for path in repo_skill.rglob("*")
        if path.is_file()
    }
    packaged_files = {
        path.relative_to(packaged_skill): path.read_bytes()
        for path in packaged_skill.rglob("*")
        if path.is_file()
    }
    assert repo_files == packaged_files

    skill_text = (packaged_skill / "SKILL.md").read_text(encoding="utf-8")
    assert skill_text.startswith("---\nname: witness\n")
    assert "Native host mode" in skill_text
    assert "--provider codex-cli" in skill_text
    assert "--expected-turn" in skill_text
    assert (packaged_skill / "scripts" / "bootstrap.ps1").is_file()
    assert (packaged_skill / "scripts" / "run-witness.ps1").is_file()
    metadata = yaml.safe_load(
        (packaged_skill / "agents" / "openai.yaml").read_text(encoding="utf-8")
    )
    assert metadata["policy"]["allow_implicit_invocation"] is True
    assert "Electron" in skill_text
    assert "Unity/Unreal" in skill_text
    assert "--max-cost" in skill_text
    assert (ROOT / ".claude" / "skills" / "witness" / "SKILL.md").read_bytes() == (
        packaged_skill / "SKILL.md"
    ).read_bytes()
    assert (ROOT / "skills" / "claude" / "witness" / "SKILL.md").read_bytes() == (
        packaged_skill / "SKILL.md"
    ).read_bytes()

    if os.name != "nt":
        for script in (packaged_skill / "scripts").glob("*.sh"):
            assert script.stat().st_mode & 0o111
