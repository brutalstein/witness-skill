from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PIL import Image

import witness_qa.adapters.web as web_module
from witness_qa.adapters.web import WebAdapter, WebSession
from witness_qa.errors import AdapterError
from witness_qa.models import ActionKind, AdapterAction, Confidence, ProjectProfile, ProjectType


def _profile(tmp_path: Path, **metadata: object) -> ProjectProfile:
    return ProjectProfile(
        target=str(tmp_path),
        project_root=str(tmp_path),
        project_type=ProjectType.WEB,
        entry_point="python app.py",
        reachable_address="http://127.0.0.1:4173",
        confidence=Confidence.HIGH,
        metadata=dict(metadata),
    )


def _session(tmp_path: Path) -> WebSession:
    return WebSession(
        profile=_profile(tmp_path, already_running=True),
        playwright=MagicMock(),
        browser=MagicMock(),
        context=MagicMock(),
        page=MagicMock(),
        process=None,
        process_log_handle=None,
        base_url="http://127.0.0.1:4173",
    )


def test_start_configures_playwright_context_without_starting_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "chromium"
    executable.write_text("", encoding="utf-8")
    playwright = MagicMock()
    playwright.chromium.executable_path = str(executable)
    browser = playwright.chromium.launch.return_value
    context = browser.new_context.return_value
    page = context.new_page.return_value
    manager = MagicMock()
    manager.start.return_value = playwright
    monkeypatch.setattr(web_module, "sync_playwright", lambda: manager)

    adapter = WebAdapter(
        tmp_path / "out",
        headless=False,
        viewport_width=800,
        viewport_height=600,
        locale="tr-TR",
        color_scheme="dark",
        reduced_motion=True,
    )
    monkeypatch.setattr(adapter, "_wait_until_reachable", MagicMock())

    session = adapter.start(_profile(tmp_path, already_running=True))

    playwright.chromium.launch.assert_called_once_with(headless=False)
    browser.new_context.assert_called_once_with(
        viewport={"width": 800, "height": 600},
        ignore_https_errors=False,
        locale="tr-TR",
        color_scheme="dark",
        reduced_motion="reduce",
        accept_downloads=True,
    )
    context.route.assert_called_once()
    page.goto.assert_called_once_with(
        "http://127.0.0.1:4173", wait_until="domcontentloaded", timeout=30_000
    )
    assert session.page is page


def test_start_rejects_missing_address_or_command(tmp_path: Path) -> None:
    adapter = WebAdapter(tmp_path)
    profile = _profile(tmp_path)
    profile.reachable_address = None
    with pytest.raises(AdapterError, match="no reachable address"):
        adapter.start(profile)

    profile = _profile(tmp_path)
    profile.entry_point = None
    with pytest.raises(AdapterError, match="no start command"):
        adapter.start(profile)


def test_act_supports_browser_action_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = WebAdapter(tmp_path)
    session = _session(tmp_path)
    page = session.page
    locator = MagicMock()
    monkeypatch.setattr(adapter, "_resolve_with_recovery", MagicMock(return_value=locator))

    actions = [
        AdapterAction(kind=ActionKind.NAVIGATE, url="/settings"),
        AdapterAction(kind=ActionKind.CLICK, target="Save"),
        AdapterAction(kind=ActionKind.DOUBLE_CLICK, target="Card"),
        AdapterAction(kind=ActionKind.RIGHT_CLICK, target="Card"),
        AdapterAction(kind=ActionKind.HOVER, target="Tooltip"),
        AdapterAction(kind=ActionKind.TYPE, target="Email", text="qa@example.com"),
        AdapterAction(kind=ActionKind.TYPE, text="keyboard text"),
        AdapterAction(kind=ActionKind.PRESS, target="Search", key="Enter"),
        AdapterAction(kind=ActionKind.PRESS, key="Escape"),
        AdapterAction(kind=ActionKind.SELECT_OPTION, target="Country", option="Türkiye"),
        AdapterAction(kind=ActionKind.CHECK, target="Terms"),
        AdapterAction(kind=ActionKind.UNCHECK, target="Marketing"),
        AdapterAction(kind=ActionKind.UPLOAD_FILE, target="Avatar", files=["avatar.png"]),
        AdapterAction(kind=ActionKind.DRAG_AND_DROP, source="Card A", target="Column B"),
        AdapterAction(kind=ActionKind.SCROLL, direction="down"),
        AdapterAction(kind=ActionKind.SCROLL, direction="right"),
        AdapterAction(kind=ActionKind.SCROLL_TO_ELEMENT, target="Footer"),
        AdapterAction(kind=ActionKind.WAIT, seconds=0),
    ]
    locator.select_option.side_effect = [RuntimeError("label missing"), None]
    for action in actions:
        assert adapter.act(session, action).success, action

    session.pending_dialog = MagicMock()
    assert adapter.act(
        session, AdapterAction(kind=ActionKind.ACCEPT_DIALOG, text="confirmed")
    ).success
    session.pending_dialog = MagicMock()
    assert adapter.act(session, AdapterAction(kind=ActionKind.DISMISS_DIALOG)).success

    new_page = MagicMock()
    session.context.new_page.return_value = new_page
    assert adapter.act(session, AdapterAction(kind=ActionKind.OPEN_NEW_TAB, url="/help")).success
    new_page.goto.assert_called_once()

    first, second = MagicMock(), MagicMock()
    session.context.pages = [first, second]
    assert adapter.act(session, AdapterAction(kind=ActionKind.SWITCH_TAB, tab_index=1)).success
    assert session.page is second
    second.bring_to_front.assert_called_once()

    session.page = page
    download = MagicMock(suggested_filename="report.csv")
    download_context = MagicMock()
    download_context.__enter__.return_value.value = download
    page.expect_download.return_value = download_context
    assert adapter.act(
        session, AdapterAction(kind=ActionKind.DOWNLOAD_FILE, target="Export")
    ).success
    download.save_as.assert_called_once_with(tmp_path / "downloads" / "report.csv")

    assert page.goto.call_args.args[0].endswith("/settings")
    locator.fill.assert_called_once_with("qa@example.com", timeout=10_000)
    page.keyboard.type.assert_called_once_with("keyboard text")
    page.mouse.wheel.assert_any_call(0, 700)
    page.mouse.wheel.assert_any_call(700, 0)


def test_act_returns_structured_failure_for_invalid_actions(tmp_path: Path) -> None:
    adapter = WebAdapter(tmp_path)
    session = _session(tmp_path)
    assert not adapter.act(session, AdapterAction(kind=ActionKind.NAVIGATE)).success
    assert not adapter.act(session, AdapterAction(kind=ActionKind.TYPE, target="Email")).success
    assert not adapter.act(session, AdapterAction(kind=ActionKind.ACCEPT_DIALOG)).success
    unsupported = adapter.act(session, AdapterAction(kind=ActionKind.GOAL_REACHED))
    assert unsupported.success is False
    assert "does not support" in unsupported.infrastructure_error


def test_observe_writes_screenshot_dom_and_delta(tmp_path: Path) -> None:
    adapter = WebAdapter(tmp_path, full_page=False)
    (tmp_path / "screenshots").mkdir()
    (tmp_path / "logs").mkdir()
    session = _session(tmp_path)
    page = session.page
    page.url = "http://127.0.0.1:4173/dashboard"

    def screenshot(*, path: str, full_page: bool) -> None:
        assert full_page is False
        Image.new("RGB", (80, 50), "white").save(path)

    page.screenshot.side_effect = screenshot
    page.evaluate.return_value = {
        "title": "Dashboard",
        "url": page.url,
        "viewport": {"width": 80, "height": 50},
        "visible_text": "Welcome",
        "interactive": [{"tag": "button", "name": "Save"}],
        "elements": [
            {
                "tag": "button",
                "name": "Save",
                "box": {"x": 5, "y": 5, "width": 40, "height": 20},
                "contrast_ratio": 5,
            }
        ],
        "alerts": [],
    }
    session.console_errors.append("console error: boom")
    session.network_errors.append("HTTP 500: GET /api")

    observation = adapter.observe(session)

    assert observation.summary.startswith("Page 'Dashboard'")
    assert observation.metadata["console_errors"] == 1
    assert observation.metadata["network_failures"] == 1
    assert (tmp_path / observation.screenshot_path).is_file()
    structured = json.loads((tmp_path / observation.structured_path).read_text(encoding="utf-8"))
    assert structured["title"] == "Dashboard"
    assert observation.delta is not None
    assert session.previous_screenshot is not None


def test_event_capture_navigation_guard_and_stop(tmp_path: Path) -> None:
    adapter = WebAdapter(tmp_path)
    session = _session(tmp_path)
    adapter._wire_page(session, session.page)
    assert {call.args[0] for call in session.page.on.call_args_list} == {
        "console",
        "pageerror",
        "response",
        "requestfailed",
        "dialog",
        "download",
    }

    adapter._capture_console(session, "info", "ignored")
    adapter._capture_console(session, "warning", "watch out")
    response = SimpleNamespace(
        request=SimpleNamespace(method="POST", resource_type="xhr"),
        url="http://127.0.0.1/api",
        status=503,
    )
    adapter._capture_response(session, response)
    request = SimpleNamespace(method="GET", url="http://127.0.0.1/missing", failure="reset")
    adapter._capture_request_failure(session, request)
    dialog = SimpleNamespace(type="alert", message="Hello")
    adapter._capture_dialog(session, dialog)
    adapter._capture_download(session, SimpleNamespace(suggested_filename="x.zip"))
    assert len(session.console_errors) == 1
    assert len(session.network_errors) == 2
    assert session.pending_dialog is dialog
    assert session.downloads == ["downloads/x.zip"]

    same_route, external_route = MagicMock(), MagicMock()
    adapter._guard_document_navigation(
        same_route,
        SimpleNamespace(resource_type="document", url="http://127.0.0.1:4173/ok"),
        session.base_url,
    )
    adapter._guard_document_navigation(
        external_route,
        SimpleNamespace(resource_type="document", url="https://example.com/"),
        session.base_url,
    )
    same_route.continue_.assert_called_once()
    external_route.abort.assert_called_once_with("blockedbyclient")

    adapter.stop(session)
    session.context.close.assert_called_once()
    session.browser.close.assert_called_once()
    session.playwright.stop.assert_called_once()


def test_locator_resolution_and_recovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = WebAdapter(tmp_path)
    page = MagicMock()
    locator = MagicMock()
    candidate = locator.nth.return_value
    locator.count.return_value = 1
    candidate.is_visible.return_value = True
    page.get_by_test_id.return_value = locator
    assert adapter._resolve_locator(page, "testid=save", purpose="click") is candidate

    failing = MagicMock(side_effect=[AdapterError("first"), candidate])
    monkeypatch.setattr(adapter, "_resolve_locator", failing)
    page.wait_for_timeout.reset_mock()
    assert adapter._resolve_with_recovery(page, "Save", purpose="click") is candidate
    page.wait_for_timeout.assert_called_once_with(500)

    hidden = MagicMock()
    hidden.count.return_value = 1
    hidden.nth.return_value.is_visible.return_value = False
    with pytest.raises(AdapterError, match="no visible"):
        adapter._first_visible(hidden)
    assert adapter._css_string('a\\"b') == 'a\\\\\\"b'
