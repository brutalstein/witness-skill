from pathlib import Path

from witness_qa.adapters.game import GameAdapter
from witness_qa.models import ActionKind, AdapterAction, Confidence, ProjectProfile, ProjectType


def test_game_adapter_reviews_frame_sequence(repo_root: Path, tmp_path: Path) -> None:
    root = repo_root / "examples" / "game_visual_review"
    frames = [str(root / "frames" / f"frame_{index:02d}.png") for index in range(1, 4)]
    references = [str(root / "references" / f"frame_{index:02d}.png") for index in range(1, 4)]
    profile = ProjectProfile(
        target=str(root / "frames"),
        project_root=str(root),
        project_type=ProjectType.GAME,
        confidence=Confidence.HIGH,
        metadata={"frames": frames, "reference_images": references},
    )
    adapter = GameAdapter(tmp_path, reference_images=references, visual_regression_threshold=0.001)
    session = adapter.start(profile)
    try:
        first = adapter.observe(session)
        moved = adapter.act(session, AdapterAction(kind=ActionKind.NEXT_FRAME))
        second = adapter.observe(session)
    finally:
        adapter.stop(session)
    assert moved.success
    assert first.visual_metrics is not None
    assert second.visual_metrics is not None
    assert "reference_comparison" in second.text
    assert (tmp_path / second.screenshot_path).is_file()


def test_game_adapter_file_bridge_captures_and_sends_named_action(tmp_path: Path) -> None:
    import json
    import threading
    import time

    from PIL import Image

    root = tmp_path / "game"
    bridge = root / ".witness" / "bridge"
    bridge.mkdir(parents=True)
    profile = ProjectProfile(
        target=str(root),
        project_root=str(root),
        project_type=ProjectType.GAME,
        confidence=Confidence.HIGH,
        metadata={
            "game_engine": "unity",
            "game_manifest": {
                "version": 1,
                "engine": "unity",
                "bridge": {"type": "file", "directory": ".witness/bridge", "timeout": 2},
            },
        },
    )
    seen: list[dict] = []

    def engine_bridge() -> None:
        last_id = ""
        deadline = time.monotonic() + 5
        while len(seen) < 2 and time.monotonic() < deadline:
            command_path = bridge / "command.json"
            if command_path.is_file():
                try:
                    command = json.loads(command_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    time.sleep(0.01)
                    continue
                if command["id"] != last_id:
                    last_id = command["id"]
                    seen.append(command)
                    if command["kind"] == "capture":
                        Image.new("RGB", (64, 48), "navy").save(command["output"])
                    (bridge / "ack.json").write_text(
                        json.dumps({"id": command["id"], "ok": True, "error": ""}),
                        encoding="utf-8",
                    )
            time.sleep(0.01)

    thread = threading.Thread(target=engine_bridge, daemon=True)
    thread.start()
    adapter = GameAdapter(tmp_path / "out")
    session = adapter.start(profile)
    try:
        observation = adapter.observe(session)
        action = adapter.act(
            session, AdapterAction(kind=ActionKind.CLICK, target="StartGame 10,20")
        )
    finally:
        adapter.stop(session)
    thread.join(timeout=2)
    assert action.success
    assert Path(tmp_path / "out" / observation.screenshot_path).is_file()
    assert [command["kind"] for command in seen] == ["capture", "click"]
    assert seen[1]["x"] == 10 and seen[1]["y"] == 20


def test_game_adapter_rejects_external_bridge_directory(tmp_path: Path) -> None:
    from witness_qa.errors import AdapterError

    root = tmp_path / "game"
    root.mkdir()
    profile = ProjectProfile(
        target=str(root),
        project_root=str(root),
        project_type=ProjectType.GAME,
        confidence=Confidence.HIGH,
        metadata={
            "game_manifest": {
                "version": 1,
                "engine": "unity",
                "bridge": {
                    "type": "file",
                    "directory": str(tmp_path.parent / "outside-bridge"),
                },
            }
        },
    )
    adapter = GameAdapter(tmp_path / "out")
    try:
        adapter.start(profile)
    except AdapterError as exc:
        assert "must stay inside" in str(exc)
    else:
        raise AssertionError("external bridge directory should be rejected")


def test_game_manifest_rejects_loader_injection_environment(tmp_path: Path) -> None:
    from witness_qa.errors import AdapterError

    root = tmp_path / "game"
    root.mkdir()
    frame = root / "frame.png"
    from PIL import Image

    Image.new("RGB", (8, 8), "black").save(frame)
    profile = ProjectProfile(
        target=str(root),
        project_root=str(root),
        project_type=ProjectType.GAME,
        confidence=Confidence.HIGH,
        metadata={
            "game_manifest": {
                "version": 1,
                "engine": "custom",
                "frames": ["frame.png"],
                "environment": {"LD_PRELOAD": "/tmp/evil.so"},
            }
        },
    )
    adapter = GameAdapter(tmp_path / "out")
    try:
        adapter.start(profile)
    except AdapterError as exc:
        assert "loader variable" in str(exc)
    else:
        raise AssertionError("loader injection environment should be rejected")
