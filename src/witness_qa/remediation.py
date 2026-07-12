from __future__ import annotations

import difflib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .errors import ConfigurationError, WitnessError
from .models import Finding, SessionResult
from .safety import validate_command
from .utils import atomic_write_json, atomic_write_text, ensure_dir

_IGNORED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "witness-output",
}


class RemediationError(WitnessError):
    """A safe remediation workflow could not complete."""


@dataclass
class VerificationRecord:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float

    @property
    def passed(self) -> bool:
        return self.exit_code == 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class RemediationOutcome:
    workspace: Path
    changed_files: list[str]
    removed_files: list[str]
    verification: list[VerificationRecord]
    applied_to_source: bool
    patch_path: Path
    report_path: Path
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def verified(self) -> bool:
        return bool(self.verification) and all(item.passed for item in self.verification)

    def as_dict(self) -> dict[str, Any]:
        return {
            "workspace": str(self.workspace.resolve()),
            "changed_files": self.changed_files,
            "removed_files": self.removed_files,
            "verification": [item.as_dict() for item in self.verification],
            "verified": self.verified,
            "applied_to_source": self.applied_to_source,
            "patch_path": str(self.patch_path.resolve()),
            "report_path": str(self.report_path.resolve()),
            "metadata": self.metadata,
        }


def _is_ignored(path: Path) -> bool:
    return any(part in _IGNORED_PARTS or part.startswith("witness-output") for part in path.parts)


def _files(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if _is_ignored(relative):
            continue
        result[relative.as_posix()] = path
    return result


def _safe_relative(path: str) -> str:
    cleaned = path.strip().replace("\\", "/")
    if cleaned.startswith(("/", "~/")) or ":/" in cleaned:
        raise RemediationError(f"Patch contains an absolute path: {path}")
    parts = Path(cleaned).parts
    if ".." in parts:
        raise RemediationError(f"Patch attempts to escape the workspace: {path}")
    if cleaned.startswith(("a/", "b/")):
        cleaned = cleaned[2:]
    return cleaned


def _validate_patch_paths(patch_text: str) -> None:
    found = False
    for line in patch_text.splitlines():
        if not line.startswith(("--- ", "+++ ")):
            continue
        raw = line[4:].split("\t", 1)[0].strip()
        if raw == "/dev/null":
            continue
        _safe_relative(raw)
        found = True
    if not found:
        raise RemediationError("The patch contains no unified-diff file headers.")


def _read_text(path: Path) -> list[str] | None:
    try:
        if path.stat().st_size > 2_000_000:
            return None
        return path.read_text(encoding="utf-8").splitlines(keepends=True)
    except (OSError, UnicodeDecodeError):
        return None


def _diff_trees(source: Path, workspace: Path) -> tuple[str, list[str], list[str]]:
    before = _files(source)
    after = _files(workspace)
    changed: list[str] = []
    removed: list[str] = []
    chunks: list[str] = []
    for relative in sorted(set(before) | set(after)):
        old = before.get(relative)
        new = after.get(relative)
        if old and new and old.read_bytes() == new.read_bytes():
            continue
        changed.append(relative)
        if old and not new:
            removed.append(relative)
        old_lines = _read_text(old) if old else []
        new_lines = _read_text(new) if new else []
        if old_lines is None or new_lines is None:
            chunks.append(f"Binary files differ: {relative}\n")
            continue
        chunks.extend(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=f"a/{relative}" if old else "/dev/null",
                tofile=f"b/{relative}" if new else "/dev/null",
            )
        )
    return "".join(chunks), changed, removed


def _copy_project(source: Path, workspace: Path) -> None:
    if workspace.exists():
        shutil.rmtree(workspace)
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
        ".ruff_cache",
    )
    shutil.copytree(source, workspace, ignore=ignore, symlinks=False)


def _load_result(result_path: Path) -> SessionResult:
    try:
        return SessionResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RemediationError(f"Could not load Witness result {result_path}: {exc}") from exc


def _finding_payload(findings: list[Finding], result_path: Path) -> list[dict[str, Any]]:
    base = result_path.parent
    payload: list[dict[str, Any]] = []
    for finding in findings:
        item = finding.model_dump(mode="json")
        evidence = Path(finding.evidence_path)
        if finding.evidence_path and not evidence.is_absolute():
            evidence = (base / evidence).resolve()
        item["evidence_path"] = str(evidence) if finding.evidence_path else ""
        payload.append(item)
    return payload


class RemediationRunner:
    """Apply a trusted patch or delegate a fix inside an isolated persistent workspace.

    The original project is untouched unless ``apply_to_source`` is explicitly requested and
    every configured verification command passes. A complete diff and command transcript are
    always emitted.
    """

    def __init__(
        self,
        *,
        result_path: Path,
        output_dir: Path,
        project_root: Path | None = None,
        timeout: float = 300,
        blocked_commands: list[str] | None = None,
    ) -> None:
        self.result_path = result_path.expanduser().resolve()
        self.result = _load_result(self.result_path)
        inferred = self.result.profile.project_root
        if project_root is None and not inferred:
            raise RemediationError(
                "The result has no project_root; pass --project-root explicitly."
            )
        self.source = (project_root or Path(inferred or ".")).expanduser().resolve()
        if not self.source.is_dir():
            raise RemediationError(f"Project root is not a directory: {self.source}")
        self.output_dir = output_dir.expanduser().resolve()
        self.workspace = self.output_dir / "workspace"
        self.timeout = timeout
        self.blocked_commands = blocked_commands or []

    def run(
        self,
        *,
        patch_file: Path | None = None,
        agent_command: str | None = None,
        verification_commands: list[str] | None = None,
        apply_to_source: bool = False,
    ) -> RemediationOutcome:
        if bool(patch_file) == bool(agent_command):
            raise ConfigurationError(
                "Choose exactly one remediation source: --patch or --agent-command."
            )
        ensure_dir(self.output_dir)
        _copy_project(self.source, self.workspace)
        request = {
            "contract_version": 1,
            "mode": "remediation",
            "workspace": str(self.workspace),
            "project_type": self.result.profile.project_type.value,
            "findings": _finding_payload(self.result.findings, self.result_path),
            "rules": [
                "Modify only files inside the provided workspace.",
                "Preserve public behavior except for the reported defects.",
                "Do not weaken tests or remove assertions to obtain a passing result.",
                "Return JSON with summary and optional verification_commands.",
            ],
        }
        atomic_write_json(self.output_dir / "remediation-request.json", request)
        metadata: dict[str, Any] = {}
        requested_verification = list(verification_commands or [])
        if patch_file:
            metadata["source"] = "patch"
            metadata["patch_file"] = str(patch_file.expanduser().resolve())
            self._apply_patch(patch_file)
        else:
            metadata["source"] = "agent-command"
            response = self._run_agent(agent_command or "", request)
            metadata["agent_response"] = response
            for command in response.get("verification_commands", []):
                if isinstance(command, str) and command not in requested_verification:
                    requested_verification.append(command)

        initial_patch, initial_changed, _ = _diff_trees(self.source, self.workspace)
        if not initial_changed:
            raise RemediationError("The remediation produced no project changes.")
        verification = [self._verify(command) for command in requested_verification]
        patch_text, changed, removed = _diff_trees(self.source, self.workspace)
        if not changed:
            raise RemediationError("Verification removed all remediation changes.")
        patch_path = self.output_dir / "remediation.patch"
        atomic_write_text(
            patch_path, patch_text or initial_patch or "# Only binary files changed.\n"
        )
        verification_ok = bool(verification) and all(record.passed for record in verification)
        applied = False
        if apply_to_source:
            if not verification_ok:
                raise RemediationError(
                    "Refusing --apply because no verification command ran successfully or at least one verification failed."
                )
            self._apply_workspace_changes(changed, removed)
            applied = True

        report_path = self.output_dir / "remediation.md"
        outcome = RemediationOutcome(
            workspace=self.workspace,
            changed_files=changed,
            removed_files=removed,
            verification=verification,
            applied_to_source=applied,
            patch_path=patch_path,
            report_path=report_path,
            metadata=metadata,
        )
        atomic_write_json(self.output_dir / "remediation.json", outcome.as_dict())
        atomic_write_text(report_path, self._render_report(outcome))
        return outcome

    def _apply_patch(self, patch_file: Path) -> None:
        path = patch_file.expanduser().resolve()
        try:
            patch_text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RemediationError(f"Could not read patch {path}: {exc}") from exc
        _validate_patch_paths(patch_text)
        for args in (["git", "apply", "--check", str(path)], ["git", "apply", str(path)]):
            completed = subprocess.run(
                args,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            if completed.returncode:
                raise RemediationError(
                    f"Patch application failed ({' '.join(args)}): {completed.stderr.strip()}"
                )

    def _run_agent(self, command: str, request: dict[str, Any]) -> dict[str, Any]:
        validate_command(command, self.blocked_commands)
        env = os.environ.copy()
        env["WITNESS_WORKSPACE"] = str(self.workspace)
        env["WITNESS_REMEDIATION_REQUEST"] = str(
            (self.output_dir / "remediation-request.json").resolve()
        )
        try:
            completed = subprocess.run(
                command if os.name == "nt" else ["/bin/sh", "-lc", command],
                cwd=self.workspace,
                input=json.dumps(request, ensure_ascii=False),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,
                check=False,
                shell=os.name == "nt",
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RemediationError(f"Remediation agent failed to run: {exc}") from exc
        atomic_write_text(self.output_dir / "agent.stdout.log", completed.stdout)
        atomic_write_text(self.output_dir / "agent.stderr.log", completed.stderr)
        if completed.returncode:
            raise RemediationError(
                f"Remediation agent exited {completed.returncode}: {completed.stderr[-2000:]}"
            )
        if not completed.stdout.strip():
            return {"summary": "Agent changed the workspace without a JSON response."}
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RemediationError(
                "Remediation agent stdout must be a single JSON object."
            ) from exc
        if not isinstance(payload, dict):
            raise RemediationError("Remediation agent response must be a JSON object.")
        return payload

    def _verify(self, command: str) -> VerificationRecord:
        validate_command(command, self.blocked_commands)
        started = datetime.now(UTC)
        try:
            completed = subprocess.run(
                command if os.name == "nt" else ["/bin/sh", "-lc", command],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                shell=os.name == "nt",
            )
            exit_code = completed.returncode
            stdout = completed.stdout[-20000:]
            stderr = completed.stderr[-20000:]
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            stdout = (exc.stdout or "")[-20000:] if isinstance(exc.stdout, str) else ""
            stderr = "Verification timed out."
        except OSError as exc:
            exit_code = 127
            stdout = ""
            stderr = str(exc)
        duration = (datetime.now(UTC) - started).total_seconds()
        return VerificationRecord(command, exit_code, stdout, stderr, duration)

    def _apply_workspace_changes(self, changed: list[str], removed: list[str]) -> None:
        for relative in changed:
            source_path = self.workspace / relative
            destination = self.source / relative
            if relative in removed:
                if destination.exists() and destination.is_file():
                    destination.unlink()
                continue
            if source_path.is_symlink():
                raise RemediationError(f"Refusing to apply symlink from remediation: {relative}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)

    @staticmethod
    def _render_report(outcome: RemediationOutcome) -> str:
        lines = [
            "# Witness Remediation Report",
            "",
            f"- **Workspace:** `{outcome.workspace}`",
            f"- **Verified:** {'yes' if outcome.verified else 'no'}",
            f"- **Applied to source:** {'yes' if outcome.applied_to_source else 'no'}",
            f"- **Patch:** `{outcome.patch_path}`",
            "",
            "## Changed files",
            "",
        ]
        lines.extend(f"- `{path}`" for path in outcome.changed_files)
        if outcome.removed_files:
            lines.extend(["", "## Removed files", ""])
            lines.extend(f"- `{path}`" for path in outcome.removed_files)
        lines.extend(["", "## Verification", ""])
        if not outcome.verification:
            lines.append(
                "No verification command was supplied; the original project was not modified."
            )
        for item in outcome.verification:
            lines.extend(
                [
                    f"### {'PASS' if item.passed else 'FAIL'} — `{item.command}`",
                    "",
                    f"Exit code: `{item.exit_code}` · Duration: `{item.duration_seconds:.2f}s`",
                    "",
                    "```text",
                    (item.stdout + ("\n" + item.stderr if item.stderr else "")).strip(),
                    "```",
                    "",
                ]
            )
        lines.extend(
            [
                "## Safety model",
                "",
                "Witness edits a persistent copy by default. Applying changes back to the source requires `--apply` and a completely passing verification set.",
                "",
            ]
        )
        return "\n".join(lines)
