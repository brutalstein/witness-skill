from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if check and completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n{detail}"
        )
    return completed


def main() -> int:
    parser = argparse.ArgumentParser(description="Install Witness and its Codex skill.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--prefix", type=Path, default=Path.home() / ".local" / "share" / "witness")
    parser.add_argument("--skill-root", type=Path, default=Path.home() / ".agents" / "skills")
    parser.add_argument("--bin-dir", type=Path, default=Path.home() / ".local" / "bin")
    parser.add_argument("--skip-browser", action="store_true")
    parser.add_argument("--with-browser-deps", action="store_true")
    parser.add_argument("--no-login-check", action="store_true")
    args = parser.parse_args()

    repo = args.repo_root.expanduser().resolve()
    pyproject = repo / "pyproject.toml"
    source_skill = repo / "skills" / "codex" / "witness"
    if not pyproject.is_file() or not source_skill.joinpath("SKILL.md").is_file():
        raise RuntimeError(f"{repo} is not a complete Witness repository checkout")

    prefix = args.prefix.expanduser().resolve()
    venv_dir = prefix / "venv"
    prefix.mkdir(parents=True, exist_ok=True)
    if not venv_dir.exists():
        venv.EnvBuilder(with_pip=True, clear=False).create(venv_dir)
    if os.name == "nt":
        python = venv_dir / "Scripts" / "python.exe"
        witness = venv_dir / "Scripts" / "witness.exe"
    else:
        python = venv_dir / "bin" / "python"
        witness = venv_dir / "bin" / "witness"
    run([str(python), "-m", "pip", "install", "--upgrade", str(repo)])

    browser_ok = False
    browser_detail = "skipped"
    if not args.skip_browser:
        command = [str(python), "-m", "playwright", "install"]
        if args.with_browser_deps:
            command.append("--with-deps")
        command.append("chromium")
        completed = run(command, check=False)
        browser_ok = completed.returncode == 0
        browser_detail = (completed.stderr or completed.stdout).strip()[-1200:]
    else:
        browser_ok = True

    destination = args.skill_root.expanduser().resolve() / "witness"
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged_skill = destination.parent / f".witness-stage-{os.getpid()}"
    backup_skill = destination.parent / f".witness-backup-{os.getpid()}"
    for stale in (staged_skill, backup_skill):
        if stale.is_dir() and not stale.is_symlink():
            shutil.rmtree(stale)
        elif stale.exists() or stale.is_symlink():
            stale.unlink()
    shutil.copytree(source_skill, staged_skill)
    try:
        if destination.exists() or destination.is_symlink():
            destination.rename(backup_skill)
        staged_skill.rename(destination)
    except Exception:
        if not destination.exists() and backup_skill.exists():
            backup_skill.rename(destination)
        raise
    finally:
        if staged_skill.exists():
            shutil.rmtree(staged_skill, ignore_errors=True)
        if backup_skill.is_dir() and not backup_skill.is_symlink():
            shutil.rmtree(backup_skill, ignore_errors=True)
        elif backup_skill.exists() or backup_skill.is_symlink():
            backup_skill.unlink(missing_ok=True)

    bin_dir = args.bin_dir.expanduser().resolve()
    bin_dir.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        launcher = bin_dir / "witness.cmd"
        launcher.write_text(f'@echo off\r\n"{witness}" %*\r\n', encoding="utf-8")
    else:
        launcher = bin_dir / "witness"
        launcher.write_text(f'#!/usr/bin/env sh\nexec "{witness}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)

    codex_path = shutil.which("codex")
    codex_logged_in = False
    codex_detail = "Codex CLI not found"
    if codex_path:
        if args.no_login_check:
            codex_detail = "login check skipped"
        else:
            completed = run([codex_path, "login", "status"], check=False)
            codex_logged_in = completed.returncode == 0
            codex_detail = (completed.stdout or completed.stderr).strip()

    browser_requested = not args.skip_browser
    login_required = not args.no_login_check
    core_ok = (
        witness.is_file() and launcher.is_file() and destination.joinpath("SKILL.md").is_file()
    )
    browser_requirement_ok = browser_ok if browser_requested else True
    login_requirement_ok = bool(codex_path) and codex_logged_in if login_required else True

    doctor_command = [
        str(witness),
        "doctor",
        "--json",
        "--skill-path",
        str(destination / "SKILL.md"),
    ]
    if args.skip_browser:
        doctor_command.append("--skip-browser")
    doctor_environment = os.environ.copy()
    if codex_path:
        doctor_environment["WITNESS_CODEX_PATH"] = codex_path
    verification = subprocess.run(
        doctor_command,
        text=True,
        capture_output=True,
        check=False,
        env=doctor_environment,
    )
    try:
        doctor_payload = json.loads(verification.stdout) if verification.stdout.strip() else {}
    except ValueError:
        doctor_payload = {
            "ready": False,
            "error": "doctor returned non-JSON output",
            "stdout": verification.stdout[-1200:],
            "stderr": verification.stderr[-1200:],
        }

    ok = core_ok and browser_requirement_ok and login_requirement_ok
    metadata = {
        "schema_version": "1.1",
        "repository": str(repo),
        "prefix": str(prefix),
        "witness": str(witness),
        "launcher": str(launcher),
        "skill": str(destination),
        "browser_requested": browser_requested,
        "browser_ok": browser_ok if browser_requested else None,
        "codex_path": codex_path or "",
        "codex_login_required": login_required,
        "codex_logged_in": codex_logged_in,
        "core_ok": core_ok,
        "ok": ok,
    }
    (prefix / "install.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    next_steps: list[str] = []
    if str(bin_dir) not in os.getenv("PATH", "").split(os.pathsep):
        next_steps.append(f"Add {bin_dir} to PATH (the skill can also use this absolute launcher).")
    if login_required and not codex_logged_in:
        next_steps.append(
            "Run `codex login` and choose Sign in with ChatGPT, then rerun the installer."
        )
    if browser_requested and not browser_ok:
        next_steps.append("Run `witness install-browser` when network access is available.")
    next_steps.append(
        "Restart Codex if needed, then invoke `$witness` or ask Codex to test a project."
    )

    payload = {
        **metadata,
        "browser_detail": browser_detail,
        "codex_detail": codex_detail,
        "doctor": doctor_payload,
        "next_steps": next_steps,
    }
    print(json.dumps(payload, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(2) from exc
