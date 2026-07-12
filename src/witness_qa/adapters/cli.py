from __future__ import annotations

import os
import re
import subprocess
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from ..errors import AdapterError
from ..models import ActionKind, ActionResult, AdapterAction, Observation, ProjectProfile
from ..observation import analyze_image, compare_observations
from ..safety import (
    SandboxWorkspace,
    changed_files,
    create_workspace,
    snapshot_tree,
    validate_command,
)
from ..utils import atomic_write_text, ensure_dir, strip_ansi
from .base import Adapter

try:
    import pexpect
except ImportError:  # pragma: no cover - Windows fallback
    pexpect = None


@dataclass
class CLISession:
    profile: ProjectProfile
    child: Any | None
    root: Path
    transcript: str = ""
    delta: str = ""
    screenshot_index: int = 0
    last_exit_code: int | None = None
    fallback_history: list[str] = field(default_factory=list)
    workspace: SandboxWorkspace | None = None
    tree_before: dict[str, tuple[int, int]] = field(default_factory=dict)
    previous_observation: Observation | None = None
    previous_screenshot: Path | None = None


class CLIAdapter(Adapter):
    name = "cli"
    supported_actions = ("run_command", "send_input", "send_keypress", "wait", "wait_for_output")

    PROMPT = "__WITNESS_PROMPT__ "

    DANGEROUS_COMMAND_PATTERNS = (
        re.compile(r"(?:^|[;&|]\s*)(?:sudo|su)\b", re.IGNORECASE),
        re.compile(
            r"(?:^|[;&|]\s*)(?:shutdown|reboot|poweroff|halt|mkfs(?:\.\w+)?|fdisk|parted)\b",
            re.IGNORECASE,
        ),
        re.compile(r"\bdd\s+[^\n]*\bof=/dev/", re.IGNORECASE),
        re.compile(r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:ba|z|k)?sh\b", re.IGNORECASE),
        re.compile(r"\bgit\s+(?:reset\s+--hard|clean\s+-[a-z]*f)", re.IGNORECASE),
        re.compile(
            r"\brm\s+(?:-[a-z]*[rf][a-z]*\s+)+(?:/|~)(?:\s|$|\*)",
            re.IGNORECASE,
        ),
    )

    def start(self, project_profile: ProjectProfile) -> CLISession:
        source_root = Path(project_profile.project_root or ".")
        workspace = create_workspace(source_root, str(self.options.get("sandbox", "none")))
        root = workspace.root
        ensure_dir(self.output_dir / "logs")
        ensure_dir(self.output_dir / "screenshots")
        if os.name == "posix" and pexpect is not None:
            env = os.environ.copy()
            env.update({"PS1": self.PROMPT, "PROMPT_COMMAND": "", "TERM": "xterm-256color"})
            try:
                child = pexpect.spawn(
                    "/bin/bash",
                    ["--noprofile", "--norc", "-i"],
                    cwd=str(root),
                    env=env,
                    encoding="utf-8",
                    codec_errors="replace",
                    echo=False,
                    timeout=2,
                    dimensions=(40, 120),
                )
                child.expect_exact(self.PROMPT, timeout=5)
            except Exception as exc:
                raise AdapterError(f"Could not create CLI pseudo-terminal: {exc}") from exc
            session = CLISession(
                profile=project_profile,
                child=child,
                root=root,
                workspace=workspace,
                tree_before=snapshot_tree(root),
            )
            suggested = (
                project_profile.entry_point
                or "Inspect the README and run the CLI's --help command."
            )
            session.transcript = (
                f"Witness PTY ready in {root}\nSuggested entry point: {suggested}\n"
            )
            session.delta = session.transcript
            return session

        # Windows or environments without pexpect still support real non-interactive commands.
        session = CLISession(
            profile=project_profile,
            child=None,
            root=root,
            workspace=workspace,
            tree_before=snapshot_tree(root),
        )
        session.transcript = (
            f"Witness command session ready in {root}. Interactive PTY input is unavailable on this platform.\n"
            f"Suggested entry point: {project_profile.entry_point or 'unknown'}\n"
        )
        session.delta = session.transcript
        return session

    def act(self, session_handle: CLISession, action: AdapterAction) -> ActionResult:
        try:
            if action.kind is ActionKind.RUN_COMMAND:
                command = action.command or action.text or action.target
                if not command:
                    raise AdapterError("run_command requires a command")
                self._validate_command(command)
                if session_handle.child is None:
                    return self._run_fallback(session_handle, command)
                return self._run_in_pty(session_handle, command)
            if session_handle.child is None:
                raise AdapterError("This platform only supports run_command for CLI projects")
            if action.kind is ActionKind.SEND_INPUT:
                session_handle.child.sendline(action.text)
                time.sleep(0.15)
                self._drain(session_handle)
            elif action.kind is ActionKind.SEND_KEYPRESS:
                self._send_key(session_handle, action.key or action.text)
                time.sleep(0.15)
                self._drain(session_handle)
            elif action.kind in {ActionKind.WAIT, ActionKind.WAIT_FOR_OUTPUT}:
                time.sleep(max(action.seconds, 1.0))
                self._drain(session_handle)
            else:
                raise AdapterError(f"CLIAdapter does not support action {action.kind.value}")
            return ActionResult(success=True, summary=action.human_summary())
        except Exception as exc:
            return ActionResult(
                success=False,
                summary=f"Could not perform {action.human_summary()}",
                infrastructure_error=f"CLI action failed: {exc}",
            )

    def observe(self, session_handle: CLISession) -> Observation:
        if session_handle.child is not None:
            self._drain(session_handle)
        session_handle.screenshot_index += 1
        index = session_handle.screenshot_index
        clean_transcript = strip_ansi(session_handle.transcript)
        clean_delta = strip_ansi(session_handle.delta)
        session_handle.delta = ""

        transcript_rel = Path("logs") / "terminal-transcript.txt"
        atomic_write_text(self.output_dir / transcript_rel, clean_transcript)
        screenshot_rel = Path("screenshots") / f"{index:03d}_terminal.png"
        screenshot_abs = self.output_dir / screenshot_rel
        self._render_terminal(clean_transcript, screenshot_abs)
        text = (
            f"Suggested entry point: {session_handle.profile.entry_point or 'unknown'}\n"
            f"Exit code of most recently completed command: {session_handle.last_exit_code}\n"
            f"Output since last observation:\n{clean_delta[-10000:]}\n\n"
            f"Current terminal buffer:\n{clean_transcript[-16000:]}"
        )
        visual_metrics = analyze_image(screenshot_abs, session_handle.previous_screenshot)
        observation = Observation(
            adapter=self.name,
            summary="CLI terminal state captured",
            text=text,
            screenshot_path=screenshot_rel.as_posix(),
            structured_path=transcript_rel.as_posix(),
            exit_code=session_handle.last_exit_code,
            visual_metrics=visual_metrics,
            metadata={
                "suggested_entry_point": session_handle.profile.entry_point,
                "sandbox_root": str(session_handle.root),
                "changed_files": changed_files(session_handle.tree_before, session_handle.root),
            },
        )
        observation.delta = compare_observations(session_handle.previous_observation, observation)
        session_handle.previous_observation = observation.model_copy(deep=True)
        session_handle.previous_screenshot = screenshot_abs
        return observation

    def stop(self, session_handle: CLISession) -> None:
        if session_handle.child is not None:
            try:
                if session_handle.child.isalive():
                    session_handle.child.sendcontrol("c")
                    session_handle.child.sendline("exit")
                    session_handle.child.close(force=True)
            except Exception:
                session_handle.child.close(force=True)
        if session_handle.workspace:
            session_handle.workspace.cleanup()

    def _validate_command(self, command: str) -> None:
        if self.options.get("allow_destructive_commands", False):
            return
        try:
            validate_command(command, list(self.options.get("blocked_commands", [])))
        except Exception as exc:
            raise AdapterError(
                "Command blocked by Witness's default safety policy. "
                "Run destructive or privileged setup manually outside the agentic session."
            ) from exc
        if any(pattern.search(command) for pattern in self.DANGEROUS_COMMAND_PATTERNS):
            raise AdapterError(
                "Command blocked by Witness's default safety policy. "
                "Run destructive or privileged setup manually outside the agentic session."
            )

    def _run_in_pty(self, session: CLISession, command: str) -> ActionResult:
        marker = f"__WITNESS_EXIT_{uuid.uuid4().hex}__"
        wrapped = f"{command}; __witness_code=$?; printf '\\n{marker}%s\\n' \"$__witness_code\""
        session.child.sendline(wrapped)
        timeout = float(self.options.get("command_timeout", 10))
        try:
            session.child.expect(re.escape(marker) + r"(\d+)", timeout=timeout)
            chunk = session.child.before or ""
            code = int(session.child.match.group(1))
            session.last_exit_code = code
            self._append(session, f"$ {command}\n{chunk}\n[exit {code}]\n")
            with suppress(Exception):
                session.child.expect_exact(self.PROMPT, timeout=2)
            return ActionResult(
                success=True, summary=f"Ran command: {command}", metadata={"exit_code": code}
            )
        except pexpect.TIMEOUT:
            chunk = session.child.before or ""
            self._append(
                session, f"$ {command}\n{chunk}\n[command still running after {timeout:g}s]\n"
            )
            return ActionResult(
                success=True,
                summary=f"Started command and left it running interactively: {command}",
                metadata={"still_running": True},
            )
        except pexpect.EOF:
            chunk = session.child.before or ""
            self._append(session, f"$ {command}\n{chunk}\n[shell exited]\n")
            session.last_exit_code = session.child.exitstatus
            return ActionResult(success=True, summary=f"Command ended the shell: {command}")

    def _run_fallback(self, session: CLISession, command: str) -> ActionResult:
        completed = subprocess.run(
            command,
            cwd=session.root,
            shell=True,
            capture_output=True,
            text=True,
            timeout=float(self.options.get("command_timeout", 20)),
            errors="replace",
        )
        output = completed.stdout + completed.stderr
        session.last_exit_code = completed.returncode
        self._append(session, f"$ {command}\n{output}\n[exit {completed.returncode}]\n")
        return ActionResult(
            success=True,
            summary=f"Ran command: {command}",
            metadata={"exit_code": completed.returncode},
        )

    def _drain(self, session: CLISession) -> None:
        if session.child is None:
            return
        chunks: list[str] = []
        while True:
            try:
                chunks.append(session.child.read_nonblocking(size=4096, timeout=0))
            except (pexpect.TIMEOUT, pexpect.EOF):
                break
        if chunks:
            self._append(session, "".join(chunks))

    @staticmethod
    def _append(session: CLISession, text: str) -> None:
        session.transcript += text
        session.delta += text
        session.transcript = session.transcript[-120_000:]

    @staticmethod
    def _send_key(session: CLISession, key: str) -> None:
        normalized = key.strip().lower().replace("_", "-")
        controls = {"ctrl-c": "c", "control-c": "c", "ctrl-d": "d", "control-d": "d"}
        if normalized in controls:
            session.child.sendcontrol(controls[normalized])
        elif normalized in {"enter", "return"}:
            session.child.sendline("")
        elif normalized == "tab":
            session.child.send("\t")
        elif normalized in {"up", "arrowup"}:
            session.child.send("\x1b[A")
        elif normalized in {"down", "arrowdown"}:
            session.child.send("\x1b[B")
        else:
            session.child.send(key)

    @staticmethod
    def _render_terminal(transcript: str, path: Path) -> None:
        lines = transcript.splitlines()[-42:] or [""]
        lines = [line[:140] for line in lines]
        font = ImageFont.load_default()
        bbox = font.getbbox("M")
        char_w = max(bbox[2] - bbox[0], 7)
        line_h = max(bbox[3] - bbox[1], 14) + 3
        width = max(900, min(1600, (max(len(line) for line in lines) + 4) * char_w))
        height = max(300, (len(lines) + 3) * line_h)
        image = Image.new("RGB", (width, height), "#111418")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, width, 28), fill="#252a31")
        draw.text((12, 8), "Witness terminal observation", font=font, fill="#d8dee9")
        y = 38
        for line in lines:
            draw.text((12, y), line, font=font, fill="#e5e9f0")
            y += line_h
        image.save(path, format="PNG")
