from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin, urlparse

import httpx

from ..errors import AdapterError
from ..models import ActionKind, ActionResult, AdapterAction, Observation, ProjectProfile
from ..observation import analyze_image, compare_observations, dom_visual_heuristics
from ..utils import atomic_write_json, ensure_dir, process_group_kwargs, terminate_process_tree
from .base import Adapter

if TYPE_CHECKING:
    from playwright.sync_api import (
        Browser,
        BrowserContext,
        Dialog,
        Download,
        Locator,
        Page,
        Playwright,
        Request,
        Route,
    )


def sync_playwright():
    from playwright.sync_api import sync_playwright as real_sync_playwright

    return real_sync_playwright()


@dataclass
class WebSession:
    profile: ProjectProfile
    playwright: Playwright
    browser: Browser
    context: BrowserContext
    page: Page
    process: subprocess.Popen[Any] | None
    process_log_handle: Any | None
    base_url: str
    screenshot_index: int = 0
    console_errors: list[str] = field(default_factory=list)
    network_errors: list[str] = field(default_factory=list)
    network_events: list[dict[str, Any]] = field(default_factory=list)
    dialogs: list[dict[str, str]] = field(default_factory=list)
    pending_dialog: Dialog | None = None
    downloads: list[str] = field(default_factory=list)
    previous_observation: Observation | None = None
    previous_screenshot: Path | None = None


class WebAdapter(Adapter):
    name = "web"
    supported_actions = tuple(
        kind.value
        for kind in (
            ActionKind.NAVIGATE,
            ActionKind.CLICK,
            ActionKind.DOUBLE_CLICK,
            ActionKind.RIGHT_CLICK,
            ActionKind.HOVER,
            ActionKind.TYPE,
            ActionKind.PRESS,
            ActionKind.SELECT_OPTION,
            ActionKind.CHECK,
            ActionKind.UNCHECK,
            ActionKind.UPLOAD_FILE,
            ActionKind.DRAG_AND_DROP,
            ActionKind.SCROLL,
            ActionKind.SCROLL_TO_ELEMENT,
            ActionKind.WAIT,
            ActionKind.ACCEPT_DIALOG,
            ActionKind.DISMISS_DIALOG,
            ActionKind.OPEN_NEW_TAB,
            ActionKind.SWITCH_TAB,
            ActionKind.DOWNLOAD_FILE,
        )
    )

    def start(self, project_profile: ProjectProfile) -> WebSession:
        if not project_profile.reachable_address:
            raise AdapterError("Web project profile has no reachable address")
        root = Path(project_profile.project_root or ".")
        ensure_dir(self.output_dir / "logs")
        ensure_dir(self.output_dir / "screenshots")
        ensure_dir(self.output_dir / "downloads")

        process: subprocess.Popen[Any] | None = None
        log_handle = None
        if not project_profile.metadata.get("already_running"):
            if not project_profile.entry_point:
                raise AdapterError(
                    "Web project was detected but no start command could be inferred. "
                    "Pass --start-command explicitly."
                )
            log_path = self.output_dir / "logs" / "target-process.log"
            log_handle = log_path.open("w", encoding="utf-8")
            env = os.environ.copy()
            detected_port = project_profile.metadata.get("detected_port")
            if detected_port:
                env.setdefault("PORT", str(detected_port))
                env.setdefault("HOST", "127.0.0.1")
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

        playwright: Playwright | None = None
        browser: Browser | None = None
        context: BrowserContext | None = None
        try:
            self._wait_until_reachable(project_profile.reachable_address, process)
            playwright = sync_playwright().start()
            launch_options: dict[str, Any] = {"headless": bool(self.options.get("headless", True))}
            explicit_browser = self.options.get("browser_executable") or os.getenv(
                "WITNESS_BROWSER_EXECUTABLE"
            )
            if explicit_browser:
                launch_options["executable_path"] = str(explicit_browser)
            elif not Path(playwright.chromium.executable_path).exists():
                system_browser = next(
                    (
                        path
                        for name in (
                            "chromium",
                            "chromium-browser",
                            "google-chrome",
                            "google-chrome-stable",
                        )
                        if (path := shutil.which(name))
                    ),
                    None,
                )
                if system_browser:
                    launch_options["executable_path"] = system_browser
            browser = playwright.chromium.launch(**launch_options)
            viewport = {
                "width": int(self.options.get("viewport_width", 1440)),
                "height": int(self.options.get("viewport_height", 1000)),
            }
            context = browser.new_context(
                viewport=viewport,
                ignore_https_errors=bool(self.options.get("ignore_https_errors", False)),
                locale=str(self.options.get("locale", "en-US")),
                color_scheme=str(self.options.get("color_scheme", "light")),
                reduced_motion="reduce" if self.options.get("reduced_motion") else "no-preference",
                accept_downloads=True,
            )
            context.route(
                "**/*",
                lambda route, request: self._guard_document_navigation(
                    route, request, project_profile.reachable_address
                ),
            )
            page = context.new_page()
            session = WebSession(
                profile=project_profile,
                playwright=playwright,
                browser=browser,
                context=context,
                page=page,
                process=process,
                process_log_handle=log_handle,
                base_url=project_profile.reachable_address,
            )
            self._wire_page(session, page)
            page.goto(session.base_url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(500)
            return session
        except Exception as exc:
            for resource in (context, browser, playwright):
                if resource is None:
                    continue
                try:
                    resource.close() if resource is not playwright else resource.stop()
                except Exception:
                    continue
            if process:
                terminate_process_tree(process)
            if log_handle:
                log_handle.close()
            if isinstance(exc, AdapterError):
                raise
            raise AdapterError(
                f"Could not initialize Playwright web session: {exc}. "
                "Run `witness install-browser` if Chromium is not installed."
            ) from exc

    def _wire_page(self, session: WebSession, page: Page) -> None:
        page.on("console", lambda msg: self._capture_console(session, msg.type, msg.text))
        page.on("pageerror", lambda error: session.console_errors.append(f"pageerror: {error}"))
        page.on("response", lambda response: self._capture_response(session, response))
        page.on("requestfailed", lambda request: self._capture_request_failure(session, request))
        page.on("dialog", lambda dialog: self._capture_dialog(session, dialog))
        page.on("download", lambda download: self._capture_download(session, download))

    def act(self, session_handle: WebSession, action: AdapterAction) -> ActionResult:
        page = session_handle.page
        try:
            if action.kind is ActionKind.NAVIGATE:
                destination = action.url or action.target
                if not destination:
                    raise AdapterError("navigate requires a URL")
                page.goto(
                    urljoin(session_handle.base_url, destination), wait_until="domcontentloaded"
                )
            elif action.kind in {ActionKind.CLICK, ActionKind.DOUBLE_CLICK, ActionKind.RIGHT_CLICK}:
                locator = self._resolve_with_recovery(page, action.target, purpose="click")
                if action.kind is ActionKind.DOUBLE_CLICK:
                    locator.dblclick(timeout=10_000)
                elif action.kind is ActionKind.RIGHT_CLICK:
                    locator.click(button="right", timeout=10_000)
                else:
                    locator.click(timeout=10_000)
            elif action.kind is ActionKind.HOVER:
                self._resolve_with_recovery(page, action.target, purpose="click").hover()
            elif action.kind is ActionKind.TYPE:
                if not action.text:
                    raise AdapterError("type requires text")
                if action.target:
                    locator = self._resolve_with_recovery(page, action.target, purpose="type")
                    locator.fill(action.text, timeout=10_000)
                else:
                    page.keyboard.type(action.text)
            elif action.kind is ActionKind.PRESS:
                key = action.key or action.text
                if not key:
                    raise AdapterError("press requires a key")
                if action.target:
                    self._resolve_with_recovery(page, action.target, purpose="type").press(key)
                else:
                    page.keyboard.press(key)
            elif action.kind is ActionKind.SELECT_OPTION:
                option = action.option or action.text
                if not option:
                    raise AdapterError("select_option requires option or text")
                locator = self._resolve_with_recovery(page, action.target, purpose="type")
                try:
                    locator.select_option(label=option)
                except Exception:
                    locator.select_option(value=option)
            elif action.kind in {ActionKind.CHECK, ActionKind.UNCHECK}:
                locator = self._resolve_with_recovery(page, action.target, purpose="type")
                locator.check() if action.kind is ActionKind.CHECK else locator.uncheck()
            elif action.kind is ActionKind.UPLOAD_FILE:
                files = action.files or ([action.text] if action.text else [])
                if not files:
                    raise AdapterError("upload_file requires files")
                self._resolve_with_recovery(page, action.target, purpose="type").set_input_files(
                    files
                )
            elif action.kind is ActionKind.DRAG_AND_DROP:
                source = action.source or action.text
                if not source or not action.target:
                    raise AdapterError("drag_and_drop requires source and target")
                self._resolve_with_recovery(page, source, purpose="click").drag_to(
                    self._resolve_with_recovery(page, action.target, purpose="click")
                )
            elif action.kind is ActionKind.SCROLL:
                direction = (action.direction or "down").lower()
                delta = 700 if direction in {"down", "right"} else -700
                page.mouse.wheel(delta, 0) if direction in {"left", "right"} else page.mouse.wheel(
                    0, delta
                )
            elif action.kind is ActionKind.SCROLL_TO_ELEMENT:
                self._resolve_with_recovery(
                    page, action.target, purpose="click"
                ).scroll_into_view_if_needed()
            elif action.kind is ActionKind.WAIT:
                page.wait_for_timeout(int(max(action.seconds, 0.25) * 1000))
            elif action.kind in {ActionKind.ACCEPT_DIALOG, ActionKind.DISMISS_DIALOG}:
                dialog = session_handle.pending_dialog
                if not dialog:
                    raise AdapterError("No pending browser dialog")
                dialog.accept(
                    action.text
                ) if action.kind is ActionKind.ACCEPT_DIALOG else dialog.dismiss()
                session_handle.pending_dialog = None
            elif action.kind is ActionKind.OPEN_NEW_TAB:
                page = session_handle.context.new_page()
                self._wire_page(session_handle, page)
                session_handle.page = page
                if action.url or action.target:
                    page.goto(urljoin(session_handle.base_url, action.url or action.target))
            elif action.kind is ActionKind.SWITCH_TAB:
                pages = session_handle.context.pages
                if not pages:
                    raise AdapterError("No browser tabs are open")
                index = action.tab_index if action.tab_index >= 0 else len(pages) - 1
                session_handle.page = pages[index]
                session_handle.page.bring_to_front()
            elif action.kind is ActionKind.DOWNLOAD_FILE:
                with page.expect_download(timeout=15_000) as download_info:
                    self._resolve_with_recovery(page, action.target, purpose="click").click()
                download = download_info.value
                saved = self.output_dir / "downloads" / download.suggested_filename
                download.save_as(saved)
                session_handle.downloads.append(saved.relative_to(self.output_dir).as_posix())
            else:
                raise AdapterError(f"WebAdapter does not support action {action.kind.value}")
            session_handle.page.wait_for_timeout(250)
            return ActionResult(success=True, summary=action.human_summary())
        except Exception as exc:
            return ActionResult(
                success=False,
                summary=f"Could not perform {action.human_summary()}",
                infrastructure_error=f"Web action resolution/execution failed: {exc}",
            )

    def observe(self, session_handle: WebSession) -> Observation:
        page = session_handle.page
        session_handle.screenshot_index += 1
        index = session_handle.screenshot_index
        screenshot_rel = Path("screenshots") / f"{index:03d}_web_state.png"
        screenshot_abs = self.output_dir / screenshot_rel
        page.screenshot(
            path=str(screenshot_abs),
            full_page=bool(self.options.get("full_page", True)),
        )

        snapshot = page.evaluate(
            r"""
            () => {
              const visible = (el) => {
                const s = window.getComputedStyle(el);
                const r = el.getBoundingClientRect();
                return s.visibility !== 'hidden' && s.display !== 'none' && Number(s.opacity) > 0 && r.width > 0 && r.height > 0;
              };
              const luminance = (color) => {
                const m = color.match(/[\d.]+/g); if (!m || m.length < 3) return null;
                const c = m.slice(0,3).map(v => { const x = Number(v)/255; return x <= .03928 ? x/12.92 : Math.pow((x+.055)/1.055,2.4); });
                return .2126*c[0]+.7152*c[1]+.0722*c[2];
              };
              const contrast = (a,b) => { const x=luminance(a), y=luminance(b); if(x===null||y===null)return null; return (Math.max(x,y)+.05)/(Math.min(x,y)+.05); };
              const nodes = Array.from(document.querySelectorAll('body *')).filter(visible).slice(0, 500);
              const elements = nodes.map((el, i) => {
                const r=el.getBoundingClientRect(), s=getComputedStyle(el);
                return { index:i, tag:el.tagName.toLowerCase(), role:el.getAttribute('role')||'', name:(el.getAttribute('aria-label')||el.innerText||el.getAttribute('placeholder')||el.getAttribute('name')||el.id||'').trim().slice(0,160), type:el.getAttribute('type')||'', placeholder:el.getAttribute('placeholder')||'', href:el.getAttribute('href')||'', disabled:!!el.disabled, box:{x:r.x,y:r.y,width:r.width,height:r.height}, font_size:s.fontSize, color:s.color, background:s.backgroundColor, contrast_ratio:contrast(s.color,s.backgroundColor)};
              });
              const interactive = elements.filter(e => ['a','button','input','textarea','select'].includes(e.tag) || ['button','link','checkbox','textbox','combobox'].includes(e.role)).slice(0, 160);
              const alerts = Array.from(document.querySelectorAll('[role="alert"], .error, .alert, .toast')).filter(visible).map(el => el.innerText).filter(Boolean).slice(0, 30);
              return { title:document.title, url:location.href, viewport:{width:innerWidth,height:innerHeight}, scroll:{x:scrollX,y:scrollY,max_y:Math.max(0,document.documentElement.scrollHeight-innerHeight)}, visible_text:(document.body?.innerText||'').slice(0,16000), interactive, elements, alerts };
            }
            """
        )
        heuristics = dom_visual_heuristics(
            snapshot.get("elements", []), snapshot.get("viewport", {})
        )
        snapshot["visual_heuristics"] = heuristics
        snapshot["network_events"] = session_handle.network_events[-50:]
        snapshot["dialogs"] = session_handle.dialogs[-20:]
        snapshot["downloads"] = session_handle.downloads[-20:]
        structured_rel = Path("logs") / f"{index:03d}_dom.json"
        atomic_write_json(self.output_dir / structured_rel, snapshot)
        errors = (session_handle.console_errors + session_handle.network_errors)[-50:]
        visual_metrics = analyze_image(screenshot_abs, session_handle.previous_screenshot)
        visual_metrics.likely_clipping.extend(heuristics["likely_clipping"])
        visual_metrics.alignment_warnings.extend(heuristics["alignment_warnings"])
        visual_metrics.contrast_warnings.extend(heuristics["contrast_warnings"])
        summary = f"Page '{snapshot.get('title', '')}' at {snapshot.get('url', page.url)}"
        current = Observation(
            adapter=self.name,
            summary=summary,
            text=json.dumps(snapshot, ensure_ascii=False, indent=2),
            screenshot_path=screenshot_rel.as_posix(),
            structured_path=structured_rel.as_posix(),
            errors=errors,
            visual_metrics=visual_metrics,
            metadata={
                "url": page.url,
                "title": snapshot.get("title", ""),
                "network_failures": len(session_handle.network_errors),
                "console_errors": len(session_handle.console_errors),
                "downloads": session_handle.downloads,
            },
        )
        current.delta = compare_observations(session_handle.previous_observation, current)
        session_handle.previous_observation = current.model_copy(deep=True)
        session_handle.previous_screenshot = screenshot_abs
        return current

    def stop(self, session_handle: WebSession) -> None:
        errors: list[Exception] = []
        for closer in (
            session_handle.context.close,
            session_handle.browser.close,
            session_handle.playwright.stop,
        ):
            try:
                closer()
            except Exception as exc:
                errors.append(exc)
        if session_handle.process:
            terminate_process_tree(session_handle.process)
        if session_handle.process_log_handle:
            session_handle.process_log_handle.close()
        if errors:
            (self.output_dir / "logs" / "teardown-errors.log").write_text(
                "\n".join(str(error) for error in errors), encoding="utf-8"
            )

    def _guard_document_navigation(self, route: Route, request: Request, base_url: str) -> None:
        if request.resource_type != "document" or self.options.get(
            "allow_external_navigation", False
        ):
            route.continue_()
            return
        base = urlparse(base_url)
        target = urlparse(request.url)
        same_origin = (target.scheme, target.hostname, target.port) == (
            base.scheme,
            base.hostname,
            base.port,
        )
        route.continue_() if same_origin else route.abort("blockedbyclient")

    def _wait_until_reachable(self, url: str, process: subprocess.Popen[Any] | None) -> None:
        deadline = time.monotonic() + float(self.options.get("startup_timeout", 45))
        last_error = ""
        with httpx.Client(follow_redirects=True, verify=False, timeout=2) as client:
            while time.monotonic() < deadline:
                if process and process.poll() is not None:
                    raise AdapterError(
                        f"Target process exited during startup with code {process.returncode}"
                    )
                try:
                    response = client.get(url)
                    if response.status_code < 500:
                        return
                    last_error = f"HTTP {response.status_code}"
                except httpx.HTTPError as exc:
                    last_error = str(exc)
                time.sleep(0.4)
        raise AdapterError(f"Timed out waiting for {url} to become reachable ({last_error})")

    @staticmethod
    def _capture_console(session: WebSession, level: str, text: str) -> None:
        if level in {"error", "warning"}:
            session.console_errors.append(f"console {level}: {text}")

    @staticmethod
    def _capture_response(session: WebSession, response: Any) -> None:
        event = {
            "method": response.request.method,
            "url": response.url,
            "status": response.status,
            "resource_type": response.request.resource_type,
        }
        session.network_events.append(event)
        if response.status >= 400:
            session.network_errors.append(
                f"HTTP {response.status}: {response.request.method} {response.url}"
            )

    @staticmethod
    def _capture_request_failure(session: WebSession, request: Request) -> None:
        failure = request.failure or "request failed"
        session.network_errors.append(f"REQUEST FAILED: {request.method} {request.url}: {failure}")
        session.network_events.append(
            {"method": request.method, "url": request.url, "failure": failure}
        )

    @staticmethod
    def _capture_dialog(session: WebSession, dialog: Dialog) -> None:
        session.pending_dialog = dialog
        session.dialogs.append({"type": dialog.type, "message": dialog.message})

    def _capture_download(self, session: WebSession, download: Download) -> None:
        session.downloads.append(f"downloads/{download.suggested_filename}")

    def _resolve_with_recovery(self, page: Page, target: str, *, purpose: str) -> Locator:
        try:
            return self._resolve_locator(page, target, purpose=purpose)
        except AdapterError:
            page.wait_for_timeout(500)
            return self._resolve_locator(page, target, purpose=purpose)

    def _resolve_locator(self, page: Page, target: str, *, purpose: str) -> Locator:
        target = target.strip()
        if not target:
            raise AdapterError(f"{purpose} requires a target description")
        if target.startswith("testid="):
            return self._first_visible(page.get_by_test_id(target[7:]))
        if target.startswith("css="):
            return self._first_visible(page.locator(target[4:]))
        if target.startswith("xpath="):
            return self._first_visible(page.locator(target))
        if target.startswith(("#", ".", "[")):
            try:
                return self._first_visible(page.locator(target))
            except Exception:
                pass
        escaped = re.escape(target)
        candidates: list[Locator] = []
        if purpose == "click":
            candidates.extend(
                [
                    page.get_by_role("button", name=re.compile(escaped, re.I)),
                    page.get_by_role("link", name=re.compile(escaped, re.I)),
                    page.get_by_role("menuitem", name=re.compile(escaped, re.I)),
                ]
            )
        candidates.extend(
            [
                page.get_by_label(re.compile(escaped, re.I)),
                page.get_by_placeholder(re.compile(escaped, re.I)),
                page.get_by_text(re.compile(escaped, re.I), exact=False),
                page.locator(f'[data-testid*="{self._css_string(target)}" i]'),
                page.locator(f'[aria-label*="{self._css_string(target)}" i]'),
                page.locator(f'[name*="{self._css_string(target)}" i]'),
            ]
        )
        for locator in candidates:
            try:
                return self._first_visible(locator)
            except Exception:
                continue
        raise AdapterError(f"No visible element matched natural-language target '{target}'")

    @staticmethod
    def _first_visible(locator: Locator) -> Locator:
        count = locator.count()
        for index in range(min(count, 25)):
            candidate = locator.nth(index)
            if candidate.is_visible():
                return candidate
        raise AdapterError("Locator matched no visible elements")

    @staticmethod
    def _css_string(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')
