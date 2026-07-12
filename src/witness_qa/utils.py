from __future__ import annotations

import contextlib
import json
import os
import re
import shlex
import signal
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
WINDOWS_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def atomic_write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text).replace("\r", "")


def is_url(value: str) -> bool:
    return urlparse(value).scheme in {"http", "https"}


def is_local_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.hostname in {"localhost", "127.0.0.1", "::1", None}


def shell_quote(value: str) -> str:
    """Quote one argument for the current platform shell."""
    return subprocess.list2cmdline([value]) if os.name == "nt" else shlex.quote(value)


def shell_join(parts: list[str]) -> str:
    """Join arguments for the current platform shell without losing spaces."""
    return subprocess.list2cmdline(parts) if os.name == "nt" else shlex.join(parts)


def process_group_kwargs() -> dict[str, Any]:
    """Return platform-appropriate Popen options for later tree termination."""
    if os.name == "nt":
        return {"creationflags": WINDOWS_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def terminate_process_tree(process: subprocess.Popen[Any], grace_seconds: float = 5.0) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            completed = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=grace_seconds,
                check=False,
            )
            if completed.returncode == 0:
                process.wait(timeout=grace_seconds)
                return
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            process.terminate()
            process.wait(timeout=grace_seconds)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            with contextlib.suppress(ProcessLookupError):
                process.kill()
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=grace_seconds)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
