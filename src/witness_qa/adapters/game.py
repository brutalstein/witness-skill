from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from ..errors import AdapterError
from ..models import ActionKind, ActionResult, AdapterAction, Observation, ProjectProfile
from ..observation import analyze_image, compare_observations
from ..safety import validate_command
from ..utils import (
    atomic_write_json,
    ensure_dir,
    process_group_kwargs,
    shell_quote,
    terminate_process_tree,
)
from .base import Adapter


@dataclass
class GameSession:
    profile: ProjectProfile
    root: Path
    process: subprocess.Popen[Any] | None
    process_log_handle: Any | None
    frames: list[Path] = field(default_factory=list)
    frame_index: int = 0
    observation_index: int = 0
    previous_observation: Observation | None = None
    previous_screenshot: Path | None = None
    action_log: list[dict[str, Any]] = field(default_factory=list)
    bridge_dir: Path | None = None
    bridge_timeout: float = 20.0
    command_counter: int = 0


class GameAdapter(Adapter):
    """Visual QA adapter for browser-exported or desktop games.

    It supports three capture modes:
    1. A configured sequence of PNG/JPEG frames.
    2. A capture command containing ``{output}``.
    3. A project screenshot directory discovered from the target.
    4. The file-based Unity/Unreal Witness bridge described by ``witness-game.json``.

    Desktop input is intentionally explicit: configure ``input_command`` with placeholders,
    or install xdotool on Linux. This avoids hidden, privileged OS automation.
    """

    name = "game"
    supported_actions = (
        "click",
        "press",
        "wait",
        "next_frame",
        "capture_frame",
        "run_command",
        "goal_reached",
        "goal_blocked",
        "give_up_and_report",
    )

    def start(self, project_profile: ProjectProfile) -> GameSession:
        root = Path(project_profile.project_root or ".").resolve()
        ensure_dir(self.output_dir / "logs")
        ensure_dir(self.output_dir / "screenshots")
        manifest = self._load_manifest(project_profile, root)
        if manifest:
            project_profile.metadata["game_manifest"] = manifest
            project_profile.metadata["game_engine"] = str(
                manifest.get("engine") or project_profile.metadata.get("game_engine") or ""
            ).lower()
            for manifest_key, metadata_key in (
                ("capture", "capture_command"),
                ("input", "input_command"),
                ("frames", "frames"),
                ("references", "reference_images"),
            ):
                if manifest.get(manifest_key):
                    project_profile.metadata[metadata_key] = manifest[manifest_key]
            if not project_profile.entry_point and manifest.get("start"):
                project_profile.entry_point = str(manifest["start"])
        bridge = manifest.get("bridge", {}) if isinstance(manifest.get("bridge"), dict) else {}
        bridge_value = bridge.get("directory") or manifest.get("bridge_dir")
        bridge_dir = None
        if bridge_value:
            bridge_dir = Path(str(bridge_value))
            if not bridge_dir.is_absolute():
                bridge_dir = root / bridge_dir
            bridge_dir = bridge_dir.resolve()
            allowed_roots = (root, self.output_dir.resolve())
            if not any(bridge_dir.is_relative_to(base) for base in allowed_roots) and not bool(
                self.options.get("allow_external_bridge", False)
            ):
                raise AdapterError(
                    "Engine bridge directory must stay inside the project or Witness output. "
                    "Set allow_external_bridge only for an explicitly trusted external bridge."
                )
            ensure_dir(bridge_dir)
        bridge_timeout = float(
            bridge.get("timeout")
            or manifest.get("bridge_timeout")
            or self.options.get("capture_timeout", 20)
        )

        manifest_environment = self._manifest_environment(manifest.get("environment") or {})
        process = None
        log_handle = None
        try:
            if project_profile.entry_point:
                validate_command(project_profile.entry_point)
                log_handle = (self.output_dir / "logs" / "game-process.log").open(
                    "w", encoding="utf-8"
                )
                env = os.environ.copy()
                env.update(manifest_environment)
                if bridge_dir:
                    env["WITNESS_BRIDGE_DIR"] = str(bridge_dir)
                env["WITNESS_ENGINE"] = str(project_profile.metadata.get("game_engine") or "")
                process = subprocess.Popen(
                    project_profile.entry_point,
                    cwd=root,
                    shell=True,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    env=env,
                    **process_group_kwargs(),
                    text=True,
                )
                time.sleep(
                    float(manifest.get("startup_wait") or self.options.get("startup_wait", 2))
                )
                if process.poll() is not None:
                    raise AdapterError(
                        f"Game process exited during startup with code {process.returncode}"
                    )
            frames = self._resolve_frames(project_profile, root)
            if not frames and not self._capture_command(project_profile) and not bridge_dir:
                raise AdapterError(
                    "GameAdapter needs image frames, a capture command, or an engine bridge. "
                    "Configure witness-game.json, project.frames, or project.capture_command. "
                    "Browser games can use --adapter web."
                )
            return GameSession(
                profile=project_profile,
                root=root,
                process=process,
                process_log_handle=log_handle,
                frames=frames,
                bridge_dir=bridge_dir,
                bridge_timeout=bridge_timeout,
            )
        except Exception:
            if process is not None:
                terminate_process_tree(process)
            if log_handle is not None:
                with contextlib.suppress(OSError):
                    log_handle.close()
            raise

    def act(self, session_handle: GameSession, action: AdapterAction) -> ActionResult:
        try:
            if action.kind is ActionKind.WAIT:
                time.sleep(max(action.seconds, 0.25))
            elif action.kind is ActionKind.NEXT_FRAME:
                if session_handle.frame_index + 1 >= len(session_handle.frames):
                    raise AdapterError("No next configured game frame")
                session_handle.frame_index += 1
            elif action.kind is ActionKind.CAPTURE_FRAME:
                self._capture_live_frame(session_handle, force=True)
            elif action.kind in {ActionKind.CLICK, ActionKind.PRESS}:
                self._send_input(session_handle, action)
            elif action.kind is ActionKind.RUN_COMMAND:
                command = action.command or action.text
                validate_command(command)
                completed = subprocess.run(
                    command,
                    cwd=session_handle.root,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=float(self.options.get("command_timeout", 20)),
                    check=False,
                )
                session_handle.action_log.append(
                    {
                        "kind": "run_command",
                        "command": command,
                        "exit_code": completed.returncode,
                        "output": (completed.stdout + completed.stderr)[-8000:],
                    }
                )
            else:
                raise AdapterError(f"GameAdapter does not support action {action.kind.value}")
            session_handle.action_log.append(
                {"kind": action.kind.value, "summary": action.human_summary()}
            )
            return ActionResult(success=True, summary=action.human_summary())
        except Exception as exc:
            return ActionResult(
                success=False,
                summary=f"Could not perform {action.human_summary()}",
                infrastructure_error=f"Game action failed: {exc}",
            )

    def observe(self, session_handle: GameSession) -> Observation:
        session_handle.observation_index += 1
        index = session_handle.observation_index
        source = self._capture_live_frame(session_handle)
        screenshot_rel = Path("screenshots") / f"{index:03d}_game_frame.png"
        screenshot_abs = self.output_dir / screenshot_rel
        with Image.open(source) as image:
            image.convert("RGB").save(screenshot_abs)
        metrics = analyze_image(screenshot_abs, session_handle.previous_screenshot)
        reference_metrics: dict[str, Any] = {}
        reference = self._reference_for(session_handle)
        if reference:
            reference_metrics = self._reference_comparison(screenshot_abs, reference)
        state = {
            "frame_source": str(source),
            "frame_index": session_handle.frame_index,
            "frame_count": len(session_handle.frames),
            "game_engine": session_handle.profile.metadata.get("game_engine", ""),
            "engine_bridge": str(session_handle.bridge_dir or ""),
            "visual_metrics": metrics.model_dump(mode="json"),
            "reference_comparison": reference_metrics,
            "recent_actions": session_handle.action_log[-20:],
            "visual_review_checklist": [
                "misaligned HUD and menu elements",
                "text or sprites clipped at screen/safe-area edges",
                "inconsistent spacing, scale, color, shadows, and icon style",
                "low contrast or unreadable text over moving backgrounds",
                "stretched assets, wrong aspect ratio, blur, aliasing, or pixel shimmer",
                "z-order errors, occlusion, seams, flicker, and state-transition residue",
                "inconsistent animation pose, feedback, or affordance across frames",
            ],
        }
        structured_rel = Path("logs") / f"{index:03d}_game.json"
        atomic_write_json(self.output_dir / structured_rel, state)
        warnings = [
            *metrics.likely_clipping,
            *metrics.alignment_warnings,
            *metrics.contrast_warnings,
        ]
        if reference_metrics.get("difference_ratio", 0) > float(
            self.options.get("visual_regression_threshold", 0.02)
        ):
            warnings.append(
                f"Frame differs from reference by {reference_metrics['difference_ratio']:.2%}."
            )
        observation = Observation(
            adapter=self.name,
            summary=f"Game frame {session_handle.frame_index + 1} of {max(1, len(session_handle.frames))} captured",
            text=json.dumps(state, ensure_ascii=False, indent=2),
            screenshot_path=screenshot_rel.as_posix(),
            structured_path=structured_rel.as_posix(),
            errors=warnings,
            visual_metrics=metrics,
            metadata={
                "frame_source": str(source),
                "reference": str(reference) if reference else "",
                "game_engine": session_handle.profile.metadata.get("game_engine", ""),
                "engine_bridge": str(session_handle.bridge_dir or ""),
            },
        )
        observation.delta = compare_observations(session_handle.previous_observation, observation)
        session_handle.previous_observation = observation.model_copy(deep=True)
        session_handle.previous_screenshot = screenshot_abs
        return observation

    def stop(self, session_handle: GameSession) -> None:
        if session_handle.process:
            terminate_process_tree(session_handle.process)
        if session_handle.process_log_handle:
            session_handle.process_log_handle.close()

    def _resolve_frames(self, profile: ProjectProfile, root: Path) -> list[Path]:
        configured = profile.metadata.get("frames") or self.options.get("frames") or []
        paths = [Path(item) if Path(item).is_absolute() else root / item for item in configured]
        if not paths:
            target = Path(profile.target)
            if target.is_file() and target.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                paths = [target.resolve()]
            elif target.is_dir():
                for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
                    paths.extend(sorted(target.glob(pattern)))
        return [path.resolve() for path in paths if path.is_file()]

    def _capture_command(self, profile: ProjectProfile) -> str:
        return str(
            profile.metadata.get("capture_command") or self.options.get("capture_command") or ""
        )

    def _capture_live_frame(self, session: GameSession, force: bool = False) -> Path:
        if session.bridge_dir:
            output = self.output_dir / "screenshots" / "_live_capture.png"
            self._bridge_request(session, kind="capture", output=output)
            if not output.is_file():
                raise AdapterError("Engine bridge acknowledged capture but produced no screenshot")
            return output
        command = self._capture_command(session.profile)
        if command:
            output = self.output_dir / "screenshots" / "_live_capture.png"
            rendered = command.format(output=shell_quote(str(output)))
            validate_command(rendered)
            completed = subprocess.run(
                rendered,
                cwd=session.root,
                shell=True,
                capture_output=True,
                text=True,
                timeout=float(self.options.get("capture_timeout", 20)),
                check=False,
            )
            if completed.returncode or not output.is_file():
                raise AdapterError(
                    f"Capture command failed: {(completed.stdout + completed.stderr)[-2000:]}"
                )
            return output
        if not session.frames:
            raise AdapterError("No game frame available")
        return session.frames[session.frame_index]

    def _send_input(self, session: GameSession, action: AdapterAction) -> None:
        if session.bridge_dir:
            x, y = self._coordinates(action.target)
            self._bridge_request(
                session,
                kind=action.kind.value,
                target=action.target,
                key=action.key or action.text,
                x=x,
                y=y,
            )
            return
        template = str(
            session.profile.metadata.get("input_command") or self.options.get("input_command") or ""
        )
        x, y = self._coordinates(action.target)
        if template:
            command = template.format(
                kind=action.kind.value,
                key=shell_quote(action.key or action.text),
                target=shell_quote(action.target),
                x=x,
                y=y,
            )
        elif shutil.which("xdotool"):
            command = (
                f"xdotool mousemove {x} {y} click 1"
                if action.kind is ActionKind.CLICK
                else f"xdotool key {shell_quote(action.key or action.text)}"
            )
        else:
            raise AdapterError(
                "No game input_command is configured and xdotool is unavailable. "
                "Configure an engine-specific safe input bridge."
            )
        validate_command(command)
        completed = subprocess.run(
            command,
            cwd=session.root,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if completed.returncode:
            raise AdapterError(
                f"Input command failed: {(completed.stdout + completed.stderr)[-2000:]}"
            )

    def _bridge_request(
        self,
        session: GameSession,
        *,
        kind: str,
        output: Path | None = None,
        target: str = "",
        key: str = "",
        x: int = 0,
        y: int = 0,
    ) -> dict[str, Any]:
        if session.bridge_dir is None:
            raise AdapterError("Engine bridge is not configured")
        session.command_counter += 1
        request_id = f"{int(time.time() * 1000)}-{session.command_counter}"
        command_path = session.bridge_dir / "command.json"
        ack_path = session.bridge_dir / "ack.json"
        payload = {
            "id": request_id,
            "kind": kind,
            "output": str(output.resolve()) if output else "",
            "target": target,
            "key": key,
            "x": x,
            "y": y,
        }
        atomic_write_json(command_path, payload)
        deadline = time.monotonic() + session.bridge_timeout
        last_error = ""
        while time.monotonic() < deadline:
            if session.process and session.process.poll() is not None:
                raise AdapterError(
                    f"Game process exited while waiting for engine bridge (code {session.process.returncode})"
                )
            if ack_path.is_file():
                try:
                    ack = json.loads(ack_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    last_error = str(exc)
                else:
                    if ack.get("id") == request_id:
                        if not ack.get("ok", False):
                            raise AdapterError(
                                f"Engine bridge rejected {kind}: {ack.get('error') or 'unknown error'}"
                            )
                        if output:
                            output_deadline = min(deadline, time.monotonic() + 5)
                            while time.monotonic() < output_deadline and not output.is_file():
                                time.sleep(0.05)
                        return ack
            time.sleep(0.05)
        raise AdapterError(
            f"Timed out waiting for engine bridge acknowledgement for {kind}"
            + (f" ({last_error})" if last_error else "")
        )

    @classmethod
    def _load_manifest(cls, profile: ProjectProfile, root: Path) -> dict[str, Any]:
        manifest = profile.metadata.get("game_manifest")
        if isinstance(manifest, dict) and manifest:
            return cls._validate_manifest(dict(manifest))
        path = root / "witness-game.json"
        if not path.is_file():
            return {}
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AdapterError(f"Invalid witness-game.json: {exc}") from exc
        if not isinstance(parsed, dict):
            raise AdapterError("witness-game.json must contain a JSON object")
        return cls._validate_manifest(parsed)

    @staticmethod
    def _validate_manifest(parsed: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "$schema",
            "version",
            "engine",
            "start",
            "capture",
            "input",
            "frames",
            "references",
            "startup_wait",
            "capture_timeout",
            "bridge",
            "bridge_dir",
            "bridge_timeout",
            "environment",
        }
        unknown = sorted(set(parsed) - allowed)
        if unknown:
            raise AdapterError(f"Unsupported witness-game.json keys: {', '.join(unknown)}")
        if parsed.get("version", 1) != 1:
            raise AdapterError("witness-game.json version must be 1")
        engine = str(parsed.get("engine") or "custom").lower()
        if engine not in {"unity", "unreal", "godot", "custom"}:
            raise AdapterError("witness-game.json engine must be unity, unreal, godot, or custom")
        parsed["engine"] = engine
        for key in ("frames", "references"):
            if key in parsed and not (
                isinstance(parsed[key], list) and all(isinstance(item, str) for item in parsed[key])
            ):
                raise AdapterError(f"witness-game.json {key} must be a list of strings")
        bridge = parsed.get("bridge")
        if bridge is not None:
            if not isinstance(bridge, dict) or bridge.get("type", "file") != "file":
                raise AdapterError("witness-game.json bridge must be a file bridge object")
            if not bridge.get("directory"):
                raise AdapterError("witness-game.json bridge.directory is required")
        environment = parsed.get("environment", {})
        if not isinstance(environment, dict):
            raise AdapterError("witness-game.json environment must be an object")
        return parsed

    @staticmethod
    def _manifest_environment(value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            raise AdapterError("witness-game.json environment must be an object")
        blocked = {
            "LD_PRELOAD",
            "LD_LIBRARY_PATH",
            "DYLD_INSERT_LIBRARIES",
            "DYLD_LIBRARY_PATH",
            "PYTHONPATH",
            "PYTHONHOME",
            "NODE_OPTIONS",
        }
        result: dict[str, str] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                raise AdapterError(f"Unsafe game environment variable name: {key}")
            if key.upper() in blocked:
                raise AdapterError(f"Game manifest may not override loader variable {key}")
            result[key] = str(raw_value)
        return result

    @staticmethod
    def _coordinates(target: str) -> tuple[int, int]:
        match = re.search(r"(-?\d+)\s*[,x ]\s*(-?\d+)", target)
        if not match:
            return (0, 0)
        return int(match.group(1)), int(match.group(2))

    def _reference_for(self, session: GameSession) -> Path | None:
        references = (
            self.options.get("reference_images")
            or session.profile.metadata.get("reference_images")
            or []
        )
        if session.frame_index >= len(references):
            return None
        path = Path(references[session.frame_index])
        if not path.is_absolute():
            path = session.root / path
        return path if path.is_file() else None

    @staticmethod
    def _reference_comparison(actual_path: Path, reference_path: Path) -> dict[str, Any]:
        from PIL import ImageChops

        with (
            Image.open(actual_path) as actual_opened,
            Image.open(reference_path) as reference_opened,
        ):
            actual = actual_opened.convert("RGB")
            reference = reference_opened.convert("RGB").resize(actual.size)
            diff = ImageChops.difference(actual, reference).convert("L")
            histogram = diff.histogram()
            changed = sum(count for value, count in enumerate(histogram) if value > 12)
            ratio = changed / max(1, actual.width * actual.height)
            return {"difference_ratio": round(ratio, 6), "reference": str(reference_path)}
