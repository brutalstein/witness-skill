"""Safety helpers for targets, commands, and isolated workspaces.

The command denylist is deliberately best-effort defense in depth, not a complete parser or
the sole security boundary. Obfuscated interpreters, aliases, or novel shell syntax may bypass
pattern matching. Real isolation comes from :func:`create_workspace`, least-privilege process
execution, and explicit user authorization for trusted mode.
"""

from __future__ import annotations

import re
import shlex
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .errors import ConfigurationError

DEFAULT_BLOCKED_PATTERNS = (
    r"(^|\s)rm\s+-[^\n]*r[^\n]*f",
    r"(^|\s)(mkfs|fdisk|parted|shutdown|reboot|poweroff)(\s|$)",
    r"(^|\s)(sudo|su)(\s|$)",
    r"(^|\s)git\s+(push|reset\s+--hard|clean\s+-f)",
    r"(^|\s)(curl|wget)[^\n]*\|\s*(sh|bash)",
    r"(^|\s)docker\s+(system\s+prune|rm\s+-f)",
    r"(^|\s)kubectl\s+(delete|apply)(\s|$)",
    r"(^|\s)(npm|pnpm|yarn)\s+publish(\s|$)",
    r"(^|\s)(pip|twine)\s+.*upload(\s|$)",
    r"(^|\s)python\s+-c(\s|$)",
    r"(^|\s)python3\s+-c(\s|$)",
    r"(^|\s)base64\s+(?:-d|--decode)(?:\s+[^|]+)?\s*\|\s*(?:sh|bash)(\s|$)",
    r"(^|\s)eval\s*\(",
    r"(^|\s)chmod\s+(?:[0-7]{3,4}|\+x)\s+[^&]+&&",
)


@dataclass
class SandboxWorkspace:
    source: Path
    root: Path
    temporary: tempfile.TemporaryDirectory[str] | None

    def cleanup(self) -> None:
        if self.temporary:
            self.temporary.cleanup()


def validate_command(command: str, additional_patterns: list[str] | None = None) -> None:
    normalized = " ".join(shlex.split(command)) if command.strip() else ""
    patterns = [*DEFAULT_BLOCKED_PATTERNS, *(additional_patterns or [])]
    for pattern in patterns:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            raise ConfigurationError(f"Blocked potentially destructive command: {command}")


def validate_target_url(url: str, allowed_hosts: list[str], allow_production: bool) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ConfigurationError(f"Unsupported target URL scheme: {parsed.scheme}")
    host = (parsed.hostname or "").lower()
    if allow_production or host in {item.lower() for item in allowed_hosts}:
        return
    raise ConfigurationError(
        f"Target host '{host}' is not allowed by the safety profile. "
        "Use a local/staging host or explicitly authorize production testing."
    )


def create_workspace(project_root: Path, mode: str = "copy") -> SandboxWorkspace:
    source = project_root.expanduser().resolve()
    if mode in {"none", "trusted"}:
        return SandboxWorkspace(source=source, root=source, temporary=None)
    if mode not in {"copy", "safe"}:
        raise ConfigurationError("sandbox must be copy, safe, none, or trusted")
    temp = tempfile.TemporaryDirectory(prefix="witness-sandbox-")
    root = Path(temp.name) / source.name
    ignore = shutil.ignore_patterns(
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        "witness-output*",
        "__pycache__",
        ".pytest_cache",
    )
    shutil.copytree(source, root, ignore=ignore)
    return SandboxWorkspace(source=source, root=root, temporary=temp)


def changed_files(before: dict[str, tuple[int, int]], root: Path) -> list[str]:
    after = snapshot_tree(root)
    paths = set(before) | set(after)
    return sorted(path for path in paths if before.get(path) != after.get(path))


def snapshot_tree(root: Path) -> dict[str, tuple[int, int]]:
    snapshot: dict[str, tuple[int, int]] = {}
    for path in root.rglob("*"):
        if not path.is_file() or any(
            part in {".git", "node_modules", ".venv"} for part in path.parts
        ):
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        snapshot[path.relative_to(root).as_posix()] = (stat.st_size, stat.st_mtime_ns)
    return snapshot
