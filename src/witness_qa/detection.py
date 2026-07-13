from __future__ import annotations

import json
import plistlib
import re
import tomllib
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlparse

from .errors import DetectionError
from .models import (
    Confidence,
    DetectionCandidate,
    DetectionSignal,
    ProjectProfile,
    ProjectType,
)
from .utils import is_url, shell_quote

IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".cache",
    "__pycache__",
    "coverage",
}
SHELL_COMMAND_RE = re.compile(
    r"^(?:\$\s*)?((?:npm|pnpm|yarn|bun|python(?:3)?|uv|poetry|pipx|cargo|go|dotnet|java|ruby|php|make)\s+[^\n`]+)$",
    re.MULTILINE,
)
PORT_RE = re.compile(r"(?:--port(?:=|\s+)|PORT=|localhost:|127\.0\.0\.1:)(\d{2,5})", re.I)


class ProjectDetector:
    """README-first, weighted detector for web, mobile, Electron, CLI, API, and game targets."""

    def detect(
        self,
        target: str,
        *,
        start_command: str | None = None,
        reachable_address: str | None = None,
    ) -> ProjectProfile:
        if is_url(target):
            parsed = urlparse(target)
            url_type = (
                ProjectType.API
                if any(token in parsed.path.lower() for token in ("openapi", "swagger", "/api"))
                else ProjectType.WEB
            )
            return ProjectProfile(
                target=target,
                project_type=url_type,
                reachable_address=target,
                confidence=Confidence.HIGH,
                raw_signals=[
                    DetectionSignal(
                        source="target",
                        project_type=url_type,
                        weight=10,
                        detail=f"HTTP(S) target supplied for host {parsed.hostname}",
                    )
                ],
                candidates=[DetectionCandidate(project_type=url_type, score=10)],
                metadata={"already_running": True},
            )

        root = Path(target).expanduser().resolve()
        if root.is_file() and root.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            return ProjectProfile(
                target=target,
                project_root=str(root.parent),
                project_type=ProjectType.GAME,
                confidence=Confidence.HIGH,
                raw_signals=[
                    DetectionSignal(
                        source="target",
                        project_type=ProjectType.GAME,
                        weight=10,
                        detail="Visual frame supplied for game/UI review",
                    )
                ],
                candidates=[DetectionCandidate(project_type=ProjectType.GAME, score=10)],
                metadata={"frames": [str(root)]},
            )
        if not root.exists() or not root.is_dir():
            raise DetectionError(f"Project path does not exist or is not a directory: {root}")

        files = self._scan_files(root)
        readme_text, readme_path = self._read_readme(root, files)
        signals: list[DetectionSignal] = []
        scores: dict[ProjectType, float] = defaultdict(float)
        framework = ""
        game_engine = ""
        game_manifest = self._read_json(root / "witness-game.json")

        def signal(kind: ProjectType, weight: float, source: str, detail: str) -> None:
            scores[kind] += weight
            signals.append(
                DetectionSignal(source=source, project_type=kind, weight=weight, detail=detail)
            )

        package = self._read_json(root / "package.json")
        package_scripts: dict[str, str] = {}
        if package:
            dependencies = {
                **package.get("dependencies", {}),
                **package.get("devDependencies", {}),
            }
            package_scripts = package.get("scripts", {}) or {}
            web_deps = sorted(
                set(dependencies)
                & {
                    "react",
                    "next",
                    "vue",
                    "vite",
                    "svelte",
                    "@angular/core",
                    "astro",
                    "remix",
                }
            )
            if web_deps:
                signal(
                    ProjectType.WEB, 7, "package.json", f"Web dependencies: {', '.join(web_deps)}"
                )
            if "electron" in dependencies or package.get("main", "").endswith(
                ("electron.js", "main.js")
            ):
                framework = "electron"
                signal(
                    ProjectType.DESKTOP, 12, "package.json", "Electron entry/dependency detected"
                )
            if package.get("bin"):
                signal(ProjectType.CLI, 8, "package.json", "Node package exposes a bin entry")
            if any(name in package_scripts for name in ("dev", "serve", "start")):
                signal(ProjectType.WEB, 2.5, "package.json", "Runnable dev/start script detected")

        pubspec_text = self._read_text(root / "pubspec.yaml")
        android_manifest = root / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
        bundle_id = self._detect_ios_bundle_id(root)
        mobile_platforms: list[str] = []
        if pubspec_text and (
            re.search(r"^\s*flutter\s*:", pubspec_text, re.MULTILINE)
            or re.search(r"sdk\s*:\s*flutter", pubspec_text, re.IGNORECASE)
        ):
            framework = "flutter"
            signal(ProjectType.MOBILE, 16, "pubspec.yaml", "Flutter SDK project detected")
        if (root / "android").is_dir():
            mobile_platforms.append("android")
            signal(ProjectType.MOBILE, 4, "filesystem", "Android app directory detected")
        if (root / "ios").is_dir():
            mobile_platforms.append("ios")
            signal(ProjectType.MOBILE, 4, "filesystem", "iOS app directory detected")
        if (root / "lib" / "main.dart").is_file():
            signal(ProjectType.MOBILE, 4, "filesystem", "Flutter main.dart entry point detected")
        android_package, android_activity = self._detect_android_app(android_manifest)
        if android_package:
            signal(ProjectType.MOBILE, 6, "AndroidManifest.xml", f"Android package {android_package}")
        if android_activity:
            signal(
                ProjectType.MOBILE,
                3,
                "AndroidManifest.xml",
                f"Android launch activity {android_activity}",
            )
        if bundle_id:
            signal(ProjectType.MOBILE, 6, "ios", f"iOS bundle identifier {bundle_id}")

        pyproject = self._read_toml(root / "pyproject.toml")
        if pyproject:
            project_scripts = (pyproject.get("project", {}) or {}).get("scripts", {}) or {}
            poetry_scripts = (
                ((pyproject.get("tool", {}) or {}).get("poetry", {}) or {}).get("scripts", {})
            ) or {}
            if project_scripts or poetry_scripts:
                signal(
                    ProjectType.CLI,
                    8,
                    "pyproject.toml",
                    "Python console script entry point detected",
                )
            deps_blob = json.dumps(pyproject).lower()
            if any(name in deps_blob for name in ('"typer', '"click', '"argparse')):
                signal(ProjectType.CLI, 3.5, "pyproject.toml", "CLI framework dependency detected")
            if any(
                name in deps_blob
                for name in ('"flask', '"fastapi', '"django', '"streamlit', '"gradio')
            ):
                signal(
                    ProjectType.WEB, 5, "pyproject.toml", "Python web framework dependency detected"
                )
            if any(
                name in deps_blob for name in ('"fastapi', '"litestar', '"falcon', '"connexion')
            ):
                signal(
                    ProjectType.API, 5, "pyproject.toml", "Python API framework dependency detected"
                )
            if any(name in deps_blob for name in ('"pygame', '"arcade', '"pyglet', '"panda3d')):
                signal(
                    ProjectType.GAME,
                    8,
                    "pyproject.toml",
                    "Python game framework dependency detected",
                )

        relative_names = {path.relative_to(root).as_posix() for path in files}
        names = {path.name for path in files}
        if "index.html" in names:
            signal(ProjectType.WEB, 5, "filesystem", "index.html detected")
        if any(
            name in names
            for name in ("vite.config.ts", "vite.config.js", "next.config.js", "next.config.mjs")
        ):
            signal(ProjectType.WEB, 5, "filesystem", "Web framework configuration detected")
        if "Cargo.toml" in names or "go.mod" in names:
            signal(
                ProjectType.CLI, 3, "filesystem", "Compiled-language application manifest detected"
            )
        if any(name in names for name in ("openapi.yaml", "openapi.yml", "swagger.json")):
            signal(ProjectType.API, 14, "filesystem", "OpenAPI/Swagger specification detected")
        if "manage.py" in names:
            signal(ProjectType.WEB, 5, "filesystem", "Django manage.py detected")
        if "project.godot" in names:
            game_engine = "godot"
            signal(ProjectType.GAME, 12, "filesystem", "Godot project detected")
        if "ProjectSettings.asset" in names or any(
            "ProjectSettings/" in name for name in relative_names
        ):
            game_engine = "unity"
            signal(ProjectType.GAME, 12, "filesystem", "Unity project detected")
        if any(name.endswith(".uproject") for name in relative_names):
            game_engine = "unreal"
            signal(ProjectType.GAME, 12, "filesystem", "Unreal Engine project detected")
        if game_manifest:
            game_engine = str(game_manifest.get("engine") or game_engine).lower()
            signal(
                ProjectType.GAME,
                16,
                "witness-game.json",
                "Explicit Witness game bridge manifest detected",
            )
        image_files = [
            path for path in files if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        ]
        if (
            image_files
            and len(image_files) >= 2
            and any(
                token in path.as_posix().lower()
                for path in image_files
                for token in ("screenshot", "frame", "capture", "reference")
            )
        ):
            signal(ProjectType.GAME, 6, "filesystem", "Game/UI screenshot sequence detected")

        python_files = [p for p in files if p.suffix == ".py"][:80]
        for path in python_files:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")[:80_000]
            except OSError:
                continue
            rel = path.relative_to(root).as_posix()
            if re.search(r"\b(?:argparse|click|typer)\b", text) and "__main__" in text:
                signal(ProjectType.CLI, 4, rel, "CLI framework and executable main guard detected")
                break
        for path in python_files:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")[:80_000]
            except OSError:
                continue
            rel = path.relative_to(root).as_posix()
            if re.search(r"\b(?:Flask|FastAPI|Django|HTTPServer|ThreadingHTTPServer)\b", text):
                signal(ProjectType.WEB, 4, rel, "Python web server/framework code detected")
                break

        readme_commands = self._extract_commands(readme_text)
        if readme_path and readme_commands:
            for command in readme_commands[:6]:
                lowered = command.lower()
                if self._looks_like_web_command(lowered):
                    signal(ProjectType.WEB, 6, readme_path, f"README run instruction: {command}")
                elif self._looks_like_mobile_command(lowered):
                    signal(
                        ProjectType.MOBILE, 6, readme_path, f"README mobile instruction: {command}"
                    )
                elif self._looks_like_cli_command(lowered):
                    signal(ProjectType.CLI, 4, readme_path, f"README invocation: {command}")

        if not scores:
            scores[ProjectType.UNKNOWN] = 1
            signals.append(
                DetectionSignal(
                    source="filesystem",
                    project_type=ProjectType.UNKNOWN,
                    weight=1,
                    detail="No supported web or CLI signals were found",
                )
            )

        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        chosen_type, top_score = ordered[0]

        second_score = ordered[1][1] if len(ordered) > 1 else 0
        margin = top_score - second_score
        if top_score >= 10 and margin >= 3:
            confidence = Confidence.HIGH
        elif top_score >= 5 and margin >= 1:
            confidence = Confidence.MEDIUM
        else:
            confidence = Confidence.LOW

        port = self._find_port("\n".join(readme_commands) + "\n" + json.dumps(package_scripts))
        entry = start_command or self._choose_entry_point(
            root=root,
            project_type=chosen_type,
            package=package,
            pyproject=pyproject,
            readme_commands=readme_commands,
            port=port,
            relative_names=relative_names,
            game_manifest=game_manifest,
            game_engine=game_engine,
        )
        if chosen_type in {ProjectType.WEB, ProjectType.API}:
            port = port or (8000 if chosen_type is ProjectType.API else 4173)
            address = reachable_address or f"http://127.0.0.1:{port}"
        else:
            address = reachable_address

        return ProjectProfile(
            target=target,
            project_root=str(root),
            project_type=chosen_type,
            entry_point=entry,
            reachable_address=address,
            confidence=confidence,
            raw_signals=signals,
            candidates=[
                DetectionCandidate(project_type=kind, score=score) for kind, score in ordered
            ],
            metadata={
                "readme": readme_path,
                "readme_excerpt": readme_text[:6_000],
                "readme_commands": readme_commands,
                "package_scripts": package_scripts,
                "detected_port": port,
                "scan_file_count": len(files),
                "framework": framework,
                "primary_mobile_platform": mobile_platforms[0] if mobile_platforms else "",
                "mobile_platforms": mobile_platforms,
                "mobile_app_package": android_package,
                "mobile_app_activity": android_activity,
                "mobile_bundle_id": bundle_id,
                "flutter_project": framework == "flutter",
                "game_engine": game_engine,
                "game_manifest": game_manifest,
                "capture_command": game_manifest.get("capture") if game_manifest else None,
                "input_command": game_manifest.get("input") if game_manifest else None,
                "reference_images": game_manifest.get("references", []) if game_manifest else [],
                "frames": (
                    game_manifest.get("frames", [])
                    if game_manifest and game_manifest.get("frames")
                    else [str(path) for path in image_files[:100]]
                    if chosen_type is ProjectType.GAME
                    else []
                ),
            },
        )

    def _scan_files(self, root: Path) -> list[Path]:
        found: list[Path] = []
        for path in root.rglob("*"):
            try:
                rel_parts = path.relative_to(root).parts
            except ValueError:
                continue
            if any(part in IGNORE_DIRS for part in rel_parts):
                continue
            if path.is_file():
                found.append(path)
            if len(found) >= 5_000:
                break
        return found

    def _read_readme(self, root: Path, files: Iterable[Path]) -> tuple[str, str | None]:
        candidates = [
            root / "README.md",
            root / "README.rst",
            root / "README.txt",
            root / "CONTRIBUTING.md",
        ]
        candidates.extend(path for path in files if path.name.lower().startswith("readme"))
        seen: set[Path] = set()
        chunks: list[str] = []
        first: str | None = None
        for path in candidates:
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")[:120_000]
            except OSError:
                continue
            if first is None:
                first = path.relative_to(root).as_posix()
            chunks.append(content)
            if len(chunks) >= 3:
                break
        return "\n\n".join(chunks), first

    @staticmethod
    def _read_json(path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _read_toml(path: Path) -> dict:
        try:
            return tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, tomllib.TOMLDecodeError):
            return {}

    @staticmethod
    def _read_text(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="ignore") if path.is_file() else ""
        except OSError:
            return ""

    @staticmethod
    def _extract_commands(text: str) -> list[str]:
        commands: list[str] = []
        for match in SHELL_COMMAND_RE.finditer(text):
            command = match.group(1).strip().rstrip(".;")
            if command not in commands and not command.startswith(
                ("pip install", "npm install", "pnpm install", "yarn install")
            ):
                commands.append(command)
        return commands

    @staticmethod
    def _looks_like_web_command(command: str) -> bool:
        return any(
            marker in command
            for marker in (
                " run dev",
                " run start",
                " serve",
                "http.server",
                "manage.py runserver",
                "uvicorn",
                "gunicorn",
                "flask run",
                "streamlit run",
                "gradio",
                "--port",
            )
        )

    @staticmethod
    def _looks_like_cli_command(command: str) -> bool:
        return any(
            command.startswith(prefix)
            for prefix in ("python ", "python3 ", "uv run ", "cargo run", "go run", "dotnet run")
        )

    @staticmethod
    def _looks_like_mobile_command(command: str) -> bool:
        return any(
            marker in command
            for marker in (
                "flutter run",
                "flutter drive",
                "adb ",
                "xcodebuild",
                "gradlew install",
                "appium",
            )
        )

    @staticmethod
    def _find_port(blob: str) -> int | None:
        match = PORT_RE.search(blob)
        if not match:
            return None
        port = int(match.group(1))
        return port if 1 <= port <= 65535 else None

    def _choose_entry_point(
        self,
        *,
        root: Path,
        project_type: ProjectType,
        package: dict,
        pyproject: dict,
        readme_commands: list[str],
        port: int | None,
        relative_names: set[str],
        game_manifest: dict,
        game_engine: str,
    ) -> str | None:
        if project_type is ProjectType.WEB:
            for command in readme_commands:
                if self._looks_like_web_command(command.lower()):
                    return command
            scripts = package.get("scripts", {}) if package else {}
            manager = (
                "pnpm"
                if (root / "pnpm-lock.yaml").exists()
                else "yarn"
                if (root / "yarn.lock").exists()
                else "npm"
            )
            for name in ("dev", "serve", "start"):
                if name in scripts:
                    return f"{manager} run {name}"
            for candidate in ("app.py", "server.py", "main.py"):
                if candidate in relative_names:
                    return f"python {candidate} --port {port or 4173}"
            if "index.html" in relative_names:
                return f"python -m http.server {port or 4173} --bind 127.0.0.1"
            return None

        if project_type is ProjectType.API:
            for command in readme_commands:
                lowered = command.lower()
                if any(
                    marker in lowered
                    for marker in ("uvicorn", "gunicorn", "flask run", "manage.py runserver")
                ):
                    return command
            for candidate in ("app.py", "server.py", "main.py"):
                if candidate in relative_names:
                    return f"python {candidate} --port {port or 8000}"
            return None

        if project_type is ProjectType.DESKTOP:
            for command in readme_commands:
                if "electron" in command.lower():
                    return command
            scripts = package.get("scripts", {}) if package else {}
            manager = (
                "pnpm"
                if (root / "pnpm-lock.yaml").exists()
                else "yarn"
                if (root / "yarn.lock").exists()
                else "npm"
            )
            for name in ("start", "dev", "electron"):
                if name in scripts:
                    return f"{manager} run {name}"
            return "npx electron ." if package else None

        if project_type is ProjectType.MOBILE:
            for command in readme_commands:
                if self._looks_like_mobile_command(command.lower()):
                    return command
            if "pubspec.yaml" in relative_names:
                return "flutter run"
            return None

        if project_type is ProjectType.GAME:
            if game_manifest.get("start"):
                return str(game_manifest["start"])
            for command in readme_commands:
                if any(
                    marker in command.lower()
                    for marker in ("godot", "unity", "unreal", "pygame", "game")
                ):
                    return command
            if "project.godot" in relative_names:
                return "godot --path ."
            packaged = self._find_packaged_game(root, game_engine)
            return shell_quote(str(packaged.relative_to(root))) if packaged else None

        if project_type is ProjectType.CLI:
            for command in readme_commands:
                if self._looks_like_cli_command(command.lower()):
                    return command
            if package and package.get("bin"):
                bin_value = package["bin"]
                name = (
                    next(iter(bin_value))
                    if isinstance(bin_value, dict)
                    else package.get("name", "")
                )
                if name:
                    return f"{name} --help"
            project_scripts = (
                (pyproject.get("project", {}) or {}).get("scripts", {}) if pyproject else {}
            ) or {}
            poetry_scripts = (
                ((pyproject.get("tool", {}) or {}).get("poetry", {}) or {}).get("scripts", {})
                if pyproject
                else {}
            ) or {}
            names = list(project_scripts) + list(poetry_scripts)
            if names:
                return f"{names[0]} --help"
            for candidate in ("cli.py", "main.py", "app.py"):
                if candidate in relative_names:
                    return f"python {candidate} --help"
            if "Cargo.toml" in relative_names:
                return "cargo run -- --help"
            if "go.mod" in relative_names:
                return "go run . --help"
        return None

    @staticmethod
    def _find_packaged_game(root: Path, engine: str) -> Path | None:
        if engine not in {"unity", "unreal"}:
            return None
        roots = [
            root / "Build",
            root / "Builds",
            root / "Binaries",
            root / "Saved" / "StagedBuilds",
        ]
        candidates: list[Path] = []
        for search_root in roots:
            if not search_root.is_dir():
                continue
            for path in search_root.rglob("*"):
                if not path.is_file():
                    continue
                suffix = path.suffix.lower()
                if suffix in {".exe", ".x86_64"} or (not suffix and path.stat().st_mode & 0o111):
                    candidates.append(path)
        return (
            sorted(candidates, key=lambda path: (len(path.parts), path.as_posix()))[0]
            if candidates
            else None
        )

    @classmethod
    def _detect_android_app(cls, manifest_path: Path) -> tuple[str, str]:
        text = cls._read_text(manifest_path)
        if not text:
            return "", ""
        package_match = re.search(r'<manifest[^>]+package="([^"]+)"', text)
        activity_match = re.search(r'<activity[^>]+android:name="([^"]+)"', text)
        package = package_match.group(1) if package_match else ""
        activity = activity_match.group(1) if activity_match else ""
        if activity.startswith(".") and package:
            activity = f"{package}{activity}"
        return package, activity

    @classmethod
    def _detect_ios_bundle_id(cls, root: Path) -> str:
        plist_path = root / "ios" / "Runner" / "Info.plist"
        if plist_path.is_file():
            try:
                parsed = plistlib.loads(plist_path.read_bytes())
            except (OSError, ValueError):
                parsed = {}
            bundle = str(parsed.get("CFBundleIdentifier", "")).strip()
            if bundle and "$(" not in bundle:
                return bundle
        project_text = cls._read_text(root / "ios" / "Runner.xcodeproj" / "project.pbxproj")
        match = re.search(r"PRODUCT_BUNDLE_IDENTIFIER\s*=\s*([^;]+);", project_text)
        return match.group(1).strip() if match else ""
