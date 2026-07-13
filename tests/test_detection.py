from pathlib import Path

from witness_qa.detection import ProjectDetector
from witness_qa.models import ProjectType


def test_detects_sample_web_app(repo_root: Path) -> None:
    profile = ProjectDetector().detect(str(repo_root / "examples" / "buggy_signup"))
    assert profile.project_type is ProjectType.WEB
    assert profile.entry_point and "app.py" in profile.entry_point
    assert profile.reachable_address == "http://127.0.0.1:4173"
    assert profile.raw_signals


def test_detects_sample_cli(repo_root: Path) -> None:
    profile = ProjectDetector().detect(str(repo_root / "examples" / "friendly_cli"))
    assert profile.project_type is ProjectType.CLI
    assert profile.entry_point and "cli.py" in profile.entry_point


def test_url_is_running_web_target() -> None:
    profile = ProjectDetector().detect("http://127.0.0.1:9999")
    assert profile.project_type is ProjectType.WEB
    assert profile.metadata["already_running"] is True


def test_static_site_uses_same_default_port_for_command_and_url(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>Hello</h1>", encoding="utf-8")
    profile = ProjectDetector().detect(str(tmp_path))
    assert profile.entry_point == "python -m http.server 4173 --bind 127.0.0.1"
    assert profile.reachable_address == "http://127.0.0.1:4173"


def test_detects_api_url_and_image_target(tmp_path: Path) -> None:
    api = ProjectDetector().detect("https://example.test/openapi.json")
    assert api.project_type is ProjectType.API
    assert api.metadata["already_running"] is True

    from PIL import Image

    frame = tmp_path / "frame.png"
    Image.new("RGB", (20, 20), "black").save(frame)
    visual = ProjectDetector().detect(str(frame))
    assert visual.project_type is ProjectType.GAME
    assert visual.metadata["frames"] == [str(frame.resolve())]


def test_missing_project_raises_detection_error(tmp_path: Path) -> None:
    import pytest

    from witness_qa.errors import DetectionError

    with pytest.raises(DetectionError):
        ProjectDetector().detect(str(tmp_path / "missing"))


def test_detects_openapi_unity_unreal_and_godot_projects(tmp_path: Path) -> None:
    api = tmp_path / "api"
    api.mkdir()
    (api / "openapi.yaml").write_text("openapi: 3.1.0\n", encoding="utf-8")
    assert ProjectDetector().detect(str(api)).project_type is ProjectType.API

    unity = tmp_path / "unity"
    (unity / "ProjectSettings").mkdir(parents=True)
    (unity / "ProjectSettings" / "ProjectSettings.asset").write_text("Unity", encoding="utf-8")
    unity_profile = ProjectDetector().detect(str(unity))
    assert unity_profile.project_type is ProjectType.GAME

    unreal = tmp_path / "unreal"
    unreal.mkdir()
    (unreal / "Arena.uproject").write_text("{}", encoding="utf-8")
    unreal_profile = ProjectDetector().detect(str(unreal))
    assert unreal_profile.project_type is ProjectType.GAME

    godot = tmp_path / "godot"
    godot.mkdir()
    (godot / "project.godot").write_text("[application]\n", encoding="utf-8")
    godot_profile = ProjectDetector().detect(str(godot))
    assert godot_profile.project_type is ProjectType.GAME
    assert godot_profile.entry_point == "godot --path ."


def test_detects_node_python_and_compiled_signals(tmp_path: Path) -> None:
    node = tmp_path / "node"
    node.mkdir()
    (node / "package.json").write_text(
        '{"name":"tool","bin":{"tool":"cli.js"},"scripts":{"start":"node cli.js"}}',
        encoding="utf-8",
    )
    node_profile = ProjectDetector().detect(str(node))
    assert node_profile.project_type is ProjectType.CLI
    assert node_profile.entry_point == "tool --help"

    python = tmp_path / "python"
    python.mkdir()
    (python / "pyproject.toml").write_text(
        '[project]\nname="demo"\ndependencies=["typer"]\n[project.scripts]\ndemo="app:main"\n',
        encoding="utf-8",
    )
    assert ProjectDetector().detect(str(python)).project_type is ProjectType.CLI

    rust = tmp_path / "rust"
    rust.mkdir()
    (rust / "Cargo.toml").write_text("[package]\nname='demo'\n", encoding="utf-8")
    rust_profile = ProjectDetector().detect(str(rust))
    assert rust_profile.project_type is ProjectType.CLI
    assert rust_profile.entry_point == "cargo run -- --help"


def test_readme_commands_ports_and_invalid_manifests(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "```bash\n$ python app.py --port 4321\n$ pip install ignored\n```\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "from http.server import HTTPServer\nif __name__ == '__main__': pass\n",
        encoding="utf-8",
    )
    (tmp_path / "package.json").write_text("{bad", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[bad", encoding="utf-8")
    profile = ProjectDetector().detect(str(tmp_path))
    assert profile.project_type is ProjectType.WEB
    assert profile.reachable_address == "http://127.0.0.1:4321"
    assert profile.metadata["readme_commands"] == ["python app.py --port 4321"]


def test_detector_helpers_cover_false_and_edge_paths(tmp_path: Path) -> None:
    detector = ProjectDetector()
    assert detector._read_json(tmp_path / "missing.json") == {}
    assert detector._read_toml(tmp_path / "missing.toml") == {}
    assert detector._find_port("no port") is None
    assert detector._find_port("PORT=70000") is None
    assert detector._looks_like_web_command("npm run dev") is True
    assert detector._looks_like_cli_command("python cli.py") is True
    assert detector._extract_commands("$ npm install\n$ npm run dev\n") == ["npm run dev"]


def test_detects_electron_as_supported_desktop_project(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        '{"name":"desk","main":"electron.js","dependencies":{"electron":"^30"},"scripts":{"start":"electron ."}}',
        encoding="utf-8",
    )
    (tmp_path / "electron.js").write_text("// main", encoding="utf-8")
    profile = ProjectDetector().detect(str(tmp_path))
    assert profile.project_type is ProjectType.DESKTOP
    assert profile.entry_point == "npm run start"
    assert profile.metadata["framework"] == "electron"


def test_game_manifest_selects_engine_bridge_and_packaged_build(tmp_path: Path) -> None:
    (tmp_path / "ProjectSettings").mkdir()
    (tmp_path / "ProjectSettings" / "ProjectSettings.asset").write_text("Unity", encoding="utf-8")
    (tmp_path / "witness-game.json").write_text(
        '{"version":1,"engine":"unity","start":"Builds/TestGame.exe","bridge":{"type":"file","directory":".witness/bridge"}}',
        encoding="utf-8",
    )
    profile = ProjectDetector().detect(str(tmp_path))
    assert profile.project_type is ProjectType.GAME
    assert profile.entry_point == "Builds/TestGame.exe"
    assert profile.metadata["game_engine"] == "unity"
    assert profile.metadata["game_manifest"]["bridge"]["type"] == "file"


def test_detects_flutter_mobile_project(tmp_path: Path) -> None:
    (tmp_path / "android" / "app" / "src" / "main").mkdir(parents=True)
    (tmp_path / "ios" / "Runner.xcodeproj").mkdir(parents=True)
    (tmp_path / "lib").mkdir()
    (tmp_path / "pubspec.yaml").write_text(
        "name: demo\nflutter:\n  uses-material-design: true\n",
        encoding="utf-8",
    )
    (tmp_path / "lib" / "main.dart").write_text("void main() {}\n", encoding="utf-8")
    (tmp_path / "android" / "app" / "src" / "main" / "AndroidManifest.xml").write_text(
        '<manifest package="com.example.demo"><application><activity android:name=".MainActivity" /></application></manifest>',
        encoding="utf-8",
    )
    (tmp_path / "ios" / "Runner.xcodeproj" / "project.pbxproj").write_text(
        "PRODUCT_BUNDLE_IDENTIFIER = com.example.demo;",
        encoding="utf-8",
    )
    profile = ProjectDetector().detect(str(tmp_path))
    assert profile.project_type is ProjectType.MOBILE
    assert profile.entry_point == "flutter run"
    assert profile.metadata["framework"] == "flutter"
    assert profile.metadata["mobile_app_package"] == "com.example.demo"
    assert profile.metadata["mobile_app_activity"] == "com.example.demo.MainActivity"
    assert profile.metadata["mobile_bundle_id"] == "com.example.demo"


def test_detects_unreal_carla_simulator_context(tmp_path: Path) -> None:
    (tmp_path / "Docs").mkdir(parents=True)
    (tmp_path / "Town01.uproject").write_text("{}", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "CARLA simulator for autonomous driving research.\n",
        encoding="utf-8",
    )
    profile = ProjectDetector().detect(str(tmp_path))
    assert profile.project_type is ProjectType.GAME
    assert profile.metadata["game_engine"] == "unreal"
    assert profile.metadata["simulator_profile"] == "carla"
    assert "carla" in profile.metadata["simulation_tags"]
