from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from witness_qa.models import Confidence, Observation, Persona, ProjectProfile, ProjectType
from witness_qa.reasoning.providers import CodexCLIReasoningEngine


def _decision() -> dict:
    return {
        "expectation": "The frame should be visible.",
        "action_taken": "initial_observation",
        "observation_summary": "The frame is visible.",
        "judgment": "match",
        "confidence": "high",
        "reasoning": "The supplied screenshot contains the expected state.",
        "hypothesis_if_mismatch": "",
        "severity": "none",
        "suggested_investigation": "",
        "visual_assessment": "The frame is readable and stable.",
        "next_action": {
            "kind": "goal_reached",
            "target": "",
            "source": "",
            "text": "",
            "key": "",
            "url": "",
            "direction": "",
            "command": "",
            "method": "",
            "path": "",
            "headers": {},
            "body": None,
            "files": [],
            "option": "",
            "tab_index": 0,
            "seconds": 0,
            "reason": "The visual goal is complete.",
        },
    }


def test_codex_cli_provider_reuses_login_and_passes_image_and_schema(tmp_path: Path) -> None:
    capture = tmp_path / "captured.json"
    executable = tmp_path / "codex"
    script = "\n".join(
        [
            "#!/usr/bin/env python3",
            "import json, pathlib, sys",
            "args = sys.argv[1:]",
            "if args == ['login', 'status']:",
            "    print('Logged in using ChatGPT')",
            "    raise SystemExit(0)",
            "output = pathlib.Path(args[args.index('--output-last-message') + 1])",
            "schema = pathlib.Path(args[args.index('--output-schema') + 1])",
            "prompt = sys.stdin.read()",
            "record = {'args': args, 'prompt': prompt, 'schema': json.loads(schema.read_text())}",
            f"pathlib.Path({str(capture)!r}).write_text(json.dumps(record))",
            f"output.write_text(json.dumps({_decision()!r}))",
            "",
        ]
    )
    executable.write_text(script, encoding="utf-8")
    executable.chmod(0o755)
    screenshot = tmp_path / "screenshots" / "frame.png"
    screenshot.parent.mkdir()
    Image.new("RGB", (20, 20), "white").save(screenshot)

    engine = CodexCLIReasoningEngine(
        model="test-codex",
        output_dir=tmp_path,
        executable=str(executable),
        timeout=10,
    )
    result = engine.decide(
        profile=ProjectProfile(
            target="fixture", project_type=ProjectType.GAME, confidence=Confidence.HIGH
        ),
        persona=Persona(name="Visual tester", goal="Review the frame"),
        adapter_name="game",
        allowed_actions=("goal_reached",),
        history=[],
        observation=Observation(
            adapter="game", summary="frame", screenshot_path="screenshots/frame.png"
        ),
        previous_action="initial_observation",
    )

    recorded = json.loads(capture.read_text(encoding="utf-8"))
    assert result.next_action.kind.value == "goal_reached"
    assert "--ephemeral" in recorded["args"]
    assert recorded["args"][recorded["args"].index("--sandbox") + 1] == "read-only"
    assert recorded["args"][recorded["args"].index("--image") + 1] == str(screenshot.resolve())
    assert recorded["schema"]["additionalProperties"] is False
    assert "Do not inspect the repository" in recorded["prompt"]
    assert engine.usage.requests == 1


def test_codex_cli_provider_supports_relative_output_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    executable = tmp_path / "codex"
    script = "\n".join(
        [
            "#!/usr/bin/env python3",
            "import json, pathlib, sys",
            "args = sys.argv[1:]",
            "if args == ['login', 'status']:",
            "    print('Logged in using ChatGPT')",
            "    raise SystemExit(0)",
            "output = pathlib.Path(args[args.index('--output-last-message') + 1])",
            f"output.write_text(json.dumps({_decision()!r}))",
            "",
        ]
    )
    executable.write_text(script, encoding="utf-8")
    executable.chmod(0o755)

    engine = CodexCLIReasoningEngine(
        model=None,
        output_dir=Path("relative-output"),
        executable=str(executable),
        timeout=10,
    )
    decision = engine.decide(
        profile=ProjectProfile(
            target="fixture", project_type=ProjectType.GAME, confidence=Confidence.HIGH
        ),
        persona=Persona(name="Visual tester", goal="Review the frame"),
        adapter_name="game",
        allowed_actions=("goal_reached",),
        history=[],
        observation=Observation(adapter="game", summary="frame"),
        previous_action="initial_observation",
    )

    assert decision.next_action.kind.value == "goal_reached"
    assert (tmp_path / "relative-output/logs/codex-cli/turn-001/decision.json").is_file()


def test_codex_cli_prompt_matches_changed_image_gating(tmp_path: Path) -> None:
    capture = tmp_path / "captured.json"
    executable = tmp_path / "codex"
    script = "\n".join(
        [
            "#!/usr/bin/env python3",
            "import json, pathlib, sys",
            "args = sys.argv[1:]",
            "if args == ['login', 'status']:",
            "    raise SystemExit(0)",
            "output = pathlib.Path(args[args.index('--output-last-message') + 1])",
            "prompt = sys.stdin.read()",
            f"pathlib.Path({str(capture)!r}).write_text(json.dumps({{'args': args, 'prompt': prompt}}))",
            f"output.write_text(json.dumps({_decision()!r}))",
            "",
        ]
    )
    executable.write_text(script, encoding="utf-8")
    executable.chmod(0o755)
    screenshot = tmp_path / "screenshots" / "frame.png"
    screenshot.parent.mkdir()
    Image.new("RGB", (20, 20), "white").save(screenshot)

    engine = CodexCLIReasoningEngine(
        model=None,
        output_dir=tmp_path,
        executable=str(executable),
        timeout=10,
        image_policy="never",
    )
    engine.decide(
        profile=ProjectProfile(
            target="fixture", project_type=ProjectType.WEB, confidence=Confidence.HIGH
        ),
        persona=Persona(name="Tester", goal="Inspect state"),
        adapter_name="web",
        allowed_actions=("goal_reached",),
        history=[],
        observation=Observation(
            adapter="web", summary="frame", screenshot_path="screenshots/frame.png"
        ),
        previous_action="initial_observation",
    )

    recorded = json.loads(capture.read_text(encoding="utf-8"))
    assert "--image" not in recorded["args"]
    assert "No screenshot is attached this turn" in recorded["prompt"]
    assert '"screenshot_attached":false' in recorded["prompt"]
