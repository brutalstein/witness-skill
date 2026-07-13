from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

from ..errors import AdapterError
from ..models import ProjectProfile
from ..safety import validate_command
from ..utils import ensure_dir, process_group_kwargs, shell_quote, terminate_process_tree
from .web import WebAdapter, WebSession


def sync_playwright():
    from playwright.sync_api import sync_playwright as real_sync_playwright

    return real_sync_playwright()


class ElectronAdapter(WebAdapter):
    """Drive Electron renderer windows through Chromium's DevTools Protocol.

    Witness launches the application with a loopback-only remote-debugging port, connects
    Playwright over CDP, and then reuses the hardened WebAdapter interaction, observation,
    screenshot, console, network, and visual-analysis implementation. Native OS dialogs and
    privileged main-process automation remain outside this adapter's trust boundary.
    """

    name = "desktop"

    def start(self, project_profile: ProjectProfile) -> WebSession:
        root = Path(project_profile.project_root or ".").resolve()
        ensure_dir(self.output_dir / "logs")
        ensure_dir(self.output_dir / "screenshots")
        ensure_dir(self.output_dir / "downloads")
        if not project_profile.entry_point:
            raise AdapterError(
                "Electron project has no launch command. Set project.start in witness.yaml "
                "or pass --start-command. The command may contain {debug_port}."
            )
        port = int(self.options.get("electron_debug_port") or self._free_loopback_port())
        isolated_profile = None
        if bool(self.options.get("electron_isolated_profile", True)):
            isolated_profile = ensure_dir(self.output_dir / "electron-user-data").resolve()
        command = self._launch_command(project_profile.entry_point, port, isolated_profile)
        validate_command(command)
        log_handle = (self.output_dir / "logs" / "electron-process.log").open("w", encoding="utf-8")
        env = os.environ.copy()
        env.update(
            {
                "WITNESS_ELECTRON_DEBUG_PORT": str(port),
                "ELECTRON_ENABLE_LOGGING": "1",
            }
        )
        process: subprocess.Popen[Any] | None = None
        playwright = None
        browser = None
        try:
            process = subprocess.Popen(
                command,
                cwd=root,
                shell=True,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                env=env,
                **process_group_kwargs(),
                text=True,
            )
            endpoint = f"http://127.0.0.1:{port}"
            self._wait_for_cdp(endpoint, process)
            playwright = sync_playwright().start()
            browser = playwright.chromium.connect_over_cdp(endpoint)
            deadline = time.monotonic() + float(self.options.get("startup_timeout", 45))
            context = None
            page = None
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise AdapterError(
                        f"Electron process exited during startup with code {process.returncode}"
                    )
                contexts = browser.contexts
                if contexts:
                    context = contexts[0]
                    pages = [
                        candidate for candidate in context.pages if candidate.url != "about:blank"
                    ]
                    page = pages[-1] if pages else (context.pages[-1] if context.pages else None)
                    if page is not None:
                        break
                time.sleep(0.2)
            if context is None or page is None:
                raise AdapterError("Electron exposed CDP but no renderer window became available")
            session = WebSession(
                profile=project_profile,
                playwright=playwright,
                browser=browser,
                context=context,
                page=page,
                process=process,
                process_log_handle=log_handle,
                base_url=page.url or endpoint,
            )
            context.route(
                "**/*",
                lambda route, request: self._guard_document_navigation(
                    route, request, session.base_url
                ),
            )
            self._wire_page(session, page)
            page.wait_for_timeout(350)
            return session
        except Exception as exc:
            if browser is not None:
                with contextlib.suppress(Exception):
                    browser.close()
            if playwright is not None:
                with contextlib.suppress(Exception):
                    playwright.stop()
            if process is not None:
                terminate_process_tree(process)
            log_handle.close()
            if isinstance(exc, AdapterError):
                raise
            raise AdapterError(f"Could not initialize Electron/CDP session: {exc}") from exc

    @staticmethod
    def _free_loopback_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    @staticmethod
    def _launch_command(command: str, port: int, user_data_dir: Path | None = None) -> str:
        rendered = command.format(debug_port=port) if "{debug_port}" in command else command
        flags: list[str] = []
        if "--remote-debugging-port" not in rendered:
            flags.append(f"--remote-debugging-port={port}")
        if "--remote-debugging-address" not in rendered:
            flags.append("--remote-debugging-address=127.0.0.1")
        if user_data_dir is not None and "--user-data-dir" not in rendered:
            flags.append(f"--user-data-dir={user_data_dir}")
        if not flags:
            return rendered
        lowered = rendered.strip().lower()
        package_runner = lowered.startswith(
            ("npm run ", "npm start", "pnpm run ", "pnpm start", "yarn ", "bun run ")
        )
        separator = " -- " if package_runner and " -- " not in rendered else " "
        return f"{rendered}{separator}{' '.join(shell_quote(flag) for flag in flags)}"

    def _wait_for_cdp(self, endpoint: str, process: subprocess.Popen[Any]) -> None:
        deadline = time.monotonic() + float(self.options.get("startup_timeout", 45))
        last_error = ""
        with httpx.Client(timeout=1.5) as client:
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise AdapterError(
                        f"Electron process exited during startup with code {process.returncode}"
                    )
                try:
                    response = client.get(f"{endpoint}/json/version")
                    if response.status_code == 200 and response.json().get("webSocketDebuggerUrl"):
                        return
                    last_error = f"HTTP {response.status_code}"
                except (httpx.HTTPError, ValueError) as exc:
                    last_error = str(exc)
                time.sleep(0.25)
        raise AdapterError(f"Timed out waiting for Electron CDP at {endpoint} ({last_error})")
