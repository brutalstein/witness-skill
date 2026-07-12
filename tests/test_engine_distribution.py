from pathlib import Path


def test_unity_and_unreal_bridge_templates_are_distributed(repo_root: Path) -> None:
    assert (repo_root / "integrations/unity/com.witness.qa/Runtime/WitnessBridge.cs").is_file()
    assert (repo_root / "integrations/unreal/WitnessBridge/WitnessBridge.uplugin").is_file()
    assert (repo_root / "docs/schemas/witness-game.schema.json").is_file()
    docs = (repo_root / "docs/ENGINE_BRIDGES.md").read_text(encoding="utf-8")
    assert "WITNESS_BRIDGE_DIR" in docs
    assert "Unity" in docs and "Unreal Engine" in docs


def test_packaged_engine_resources_match_repository_templates(repo_root: Path) -> None:
    pairs = [
        (
            repo_root / "integrations/unity/com.witness.qa",
            repo_root / "src/witness_qa/resources/engine_bridges/unity",
        ),
        (
            repo_root / "integrations/unreal/WitnessBridge",
            repo_root / "src/witness_qa/resources/engine_bridges/unreal",
        ),
    ]
    for source, packaged in pairs:
        source_files = {
            path.relative_to(source): path.read_bytes()
            for path in source.rglob("*")
            if path.is_file()
        }
        packaged_files = {
            path.relative_to(packaged): path.read_bytes()
            for path in packaged.rglob("*")
            if path.is_file()
        }
        assert source_files == packaged_files
