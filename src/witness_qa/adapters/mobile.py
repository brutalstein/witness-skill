from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from ..errors import AdapterError
from ..models import ActionKind, ActionResult, AdapterAction, Observation, ProjectProfile
from ..observation import analyze_image, compare_observations, dom_visual_heuristics
from ..utils import atomic_write_json, ensure_dir
from .base import Adapter

_BOUNDS_RE = re.compile(r"\[(?P<x1>-?\d+),(?P<y1>-?\d+)\]\[(?P<x2>-?\d+),(?P<y2>-?\d+)\]")
_COORDINATES_RE = re.compile(r"(-?\d+)\s*[,x ]\s*(-?\d+)")


@dataclass
class MobileSession:
    profile: ProjectProfile
    driver: Any
    server_url: str
    platform_name: str
    screenshot_index: int = 0
    previous_observation: Observation | None = None
    previous_screenshot: Path | None = None
    available_contexts: list[str] = field(default_factory=list)


class MobileAdapter(Adapter):
    """Drive Android and iOS apps through Appium with real-device style interactions."""

    name = "mobile"
    supported_actions = (
        "click",
        "type",
        "press",
        "check",
        "uncheck",
        "scroll",
        "wait",
    )

    def start(self, project_profile: ProjectProfile) -> MobileSession:
        ensure_dir(self.output_dir / "logs")
        ensure_dir(self.output_dir / "screenshots")
        server_url = str(
            self.options.get("appium_server_url")
            or project_profile.metadata.get("appium_server_url")
            or os.getenv("WITNESS_APPIUM_SERVER_URL")
            or "http://127.0.0.1:4723"
        )
        capabilities = self._build_capabilities(project_profile)
        platform_name = str(capabilities["platformName"]).lower()
        driver = self._create_driver(server_url, capabilities)
        contexts = self._driver_contexts(driver)
        return MobileSession(
            profile=project_profile,
            driver=driver,
            server_url=server_url,
            platform_name=platform_name,
            available_contexts=contexts,
        )

    def act(self, session_handle: MobileSession, action: AdapterAction) -> ActionResult:
        driver = session_handle.driver
        try:
            if action.kind is ActionKind.CLICK:
                coordinates = self._coordinates(action.target)
                if coordinates:
                    self._tap_coordinates(session_handle, *coordinates)
                else:
                    self._resolve_element(session_handle, action.target, purpose="click").click()
            elif action.kind is ActionKind.TYPE:
                if not action.text:
                    raise AdapterError("type requires text")
                element = (
                    self._resolve_element(session_handle, action.target, purpose="type")
                    if action.target
                    else getattr(driver.switch_to, "active_element")
                )
                if element is None:
                    raise AdapterError("No active mobile element is available for typing")
                clear = getattr(element, "clear", None)
                if callable(clear):
                    clear()
                element.send_keys(action.text)
            elif action.kind is ActionKind.PRESS:
                key = action.key or action.text
                if not key:
                    raise AdapterError("press requires a key")
                self._press_key(session_handle, key)
            elif action.kind in {ActionKind.CHECK, ActionKind.UNCHECK}:
                element = self._resolve_element(session_handle, action.target, purpose="toggle")
                selected = bool(getattr(element, "is_selected", lambda: False)())
                if (action.kind is ActionKind.CHECK and not selected) or (
                    action.kind is ActionKind.UNCHECK and selected
                ):
                    element.click()
            elif action.kind is ActionKind.SCROLL:
                self._scroll(session_handle, (action.direction or "down").lower())
            elif action.kind is ActionKind.WAIT:
                time.sleep(max(action.seconds, 0.25))
            else:
                raise AdapterError(f"MobileAdapter does not support action {action.kind.value}")
            return ActionResult(success=True, summary=action.human_summary())
        except Exception as exc:
            return ActionResult(
                success=False,
                summary=f"Could not perform {action.human_summary()}",
                infrastructure_error=f"Mobile action resolution/execution failed: {exc}",
            )

    def observe(self, session_handle: MobileSession) -> Observation:
        driver = session_handle.driver
        session_handle.screenshot_index += 1
        index = session_handle.screenshot_index
        screenshot_rel = Path("screenshots") / f"{index:03d}_mobile_state.png"
        screenshot_abs = self.output_dir / screenshot_rel
        if not driver.get_screenshot_as_file(str(screenshot_abs)):
            raise AdapterError("Appium did not produce a mobile screenshot")
        page_source = str(getattr(driver, "page_source", "") or "")
        viewport = self._window_size(driver)
        elements = self._extract_elements(page_source)
        interactive = [item for item in elements if item.get("interactive")][:160]
        heuristics = dom_visual_heuristics(elements, viewport)
        contexts = self._driver_contexts(driver)
        session_handle.available_contexts = contexts
        state = {
            "platform_name": session_handle.platform_name,
            "framework": session_handle.profile.metadata.get("framework", ""),
            "viewport": viewport,
            "available_contexts": contexts,
            "current_context": self._safe_attr(driver, "current_context"),
            "current_package": self._safe_attr(driver, "current_package"),
            "current_activity": self._safe_attr(driver, "current_activity"),
            "bundle_id": (
                session_handle.profile.metadata.get("mobile_bundle_id")
                or self.options.get("mobile_bundle_id")
                or ""
            ),
            "screen_title_candidates": self._text_preview(elements),
            "interactive": interactive,
            "elements": elements[:300],
            "source_length": len(page_source),
            "visual_heuristics": heuristics,
        }
        structured_rel = Path("logs") / f"{index:03d}_mobile.json"
        atomic_write_json(self.output_dir / structured_rel, state)
        visual_metrics = analyze_image(screenshot_abs, session_handle.previous_screenshot)
        visual_metrics.likely_clipping.extend(heuristics["likely_clipping"])
        visual_metrics.alignment_warnings.extend(heuristics["alignment_warnings"])
        visual_metrics.contrast_warnings.extend(heuristics["contrast_warnings"])
        errors = [
            *visual_metrics.likely_clipping,
            *visual_metrics.alignment_warnings,
            *visual_metrics.contrast_warnings,
        ]
        summary = (
            f"Mobile screen on {session_handle.platform_name}"
            f" ({self._safe_attr(driver, 'current_context') or 'NATIVE_APP'})"
        )
        current = Observation(
            adapter=self.name,
            summary=summary,
            text=json.dumps(state, ensure_ascii=False, indent=2),
            screenshot_path=screenshot_rel.as_posix(),
            structured_path=structured_rel.as_posix(),
            errors=errors[:60],
            visual_metrics=visual_metrics,
            metadata={
                "platform_name": session_handle.platform_name,
                "framework": session_handle.profile.metadata.get("framework", ""),
                "available_contexts": contexts,
                "current_package": self._safe_attr(driver, "current_package"),
                "current_activity": self._safe_attr(driver, "current_activity"),
            },
        )
        current.delta = compare_observations(session_handle.previous_observation, current)
        session_handle.previous_observation = current.model_copy(deep=True)
        session_handle.previous_screenshot = screenshot_abs
        return current

    def stop(self, session_handle: MobileSession) -> None:
        quit_driver = getattr(session_handle.driver, "quit", None)
        if callable(quit_driver):
            quit_driver()

    def _create_driver(self, server_url: str, capabilities: dict[str, Any]) -> Any:
        remote_driver, options_type = self._load_appium()
        options = options_type()
        load_capabilities = getattr(options, "load_capabilities", None)
        if callable(load_capabilities):
            load_capabilities(capabilities)
        else:
            for key, value in capabilities.items():
                options.set_capability(key, value)
        try:
            return remote_driver(server_url, options=options)
        except Exception as exc:  # pragma: no cover - exercised with a real Appium server
            raise AdapterError(
                f"Could not start Appium mobile session at {server_url}: {exc}"
            ) from exc

    @staticmethod
    def _load_appium() -> tuple[Any, Any]:
        try:
            from appium import webdriver
            from appium.options.common import AppiumOptions
        except ImportError as exc:  # pragma: no cover - depends on local installation
            raise AdapterError(
                "MobileAdapter requires Appium-Python-Client. "
                "Reinstall Witness after updating dependencies, then run a local Appium server."
            ) from exc
        return webdriver.Remote, AppiumOptions

    def _build_capabilities(self, profile: ProjectProfile) -> dict[str, Any]:
        metadata = profile.metadata
        platform_name = str(
            self.options.get("mobile_platform_name")
            or metadata.get("mobile_platform_name")
            or metadata.get("primary_mobile_platform")
            or os.getenv("WITNESS_MOBILE_PLATFORM")
            or ""
        ).strip()
        if not platform_name:
            raise AdapterError(
                "MobileAdapter requires mobile_platform_name (android or ios). "
                "Set it in witness.yaml or WITNESS_MOBILE_PLATFORM."
            )
        normalized_platform = platform_name.lower()
        if normalized_platform not in {"android", "ios"}:
            raise AdapterError("mobile_platform_name must be 'android' or 'ios'")
        automation_name = str(
            self.options.get("mobile_automation_name")
            or metadata.get("mobile_automation_name")
            or ("XCUITest" if normalized_platform == "ios" else "UiAutomator2")
        )
        capabilities: dict[str, Any] = {
            "platformName": "iOS" if normalized_platform == "ios" else "Android",
            "appium:automationName": automation_name,
            "appium:newCommandTimeout": int(
                self.options.get("mobile_new_command_timeout") or 180
            ),
            "appium:noReset": bool(self.options.get("mobile_no_reset", True)),
        }
        optional_values = {
            "appium:deviceName": self.options.get("mobile_device_name")
            or metadata.get("mobile_device_name")
            or os.getenv("WITNESS_MOBILE_DEVICE"),
            "appium:udid": self.options.get("mobile_udid")
            or metadata.get("mobile_udid")
            or os.getenv("WITNESS_MOBILE_UDID"),
            "appium:app": self.options.get("mobile_app")
            or metadata.get("mobile_app")
            or os.getenv("WITNESS_MOBILE_APP"),
        }
        for key, value in optional_values.items():
            if value:
                capabilities[key] = str(value)
        if normalized_platform == "android":
            app_package = (
                self.options.get("mobile_app_package")
                or metadata.get("mobile_app_package")
                or os.getenv("WITNESS_MOBILE_APP_PACKAGE")
            )
            app_activity = (
                self.options.get("mobile_app_activity")
                or metadata.get("mobile_app_activity")
                or os.getenv("WITNESS_MOBILE_APP_ACTIVITY")
            )
            if app_package:
                capabilities["appium:appPackage"] = str(app_package)
            if app_activity:
                capabilities["appium:appActivity"] = str(app_activity)
            capabilities.setdefault("appium:autoGrantPermissions", True)
        else:
            bundle_id = (
                self.options.get("mobile_bundle_id")
                or metadata.get("mobile_bundle_id")
                or os.getenv("WITNESS_MOBILE_BUNDLE_ID")
            )
            if bundle_id:
                capabilities["appium:bundleId"] = str(bundle_id)
            capabilities.setdefault("appium:autoAcceptAlerts", True)
        has_launch_target = any(
            key in capabilities
            for key in (
                "appium:app",
                "appium:appPackage",
                "appium:bundleId",
            )
        )
        if not has_launch_target:
            raise AdapterError(
                "MobileAdapter needs one of mobile_app, mobile_app_package, or mobile_bundle_id. "
                "Detection can infer package identifiers from Flutter projects, but you still need "
                "device/server settings in witness.yaml."
            )
        return capabilities

    def _resolve_element(
        self, session_handle: MobileSession, target: str, *, purpose: str
    ) -> Any:
        target = target.strip()
        if not target:
            raise AdapterError(f"{purpose} requires a target description")
        driver = session_handle.driver
        if target.startswith("accessibility_id="):
            element = self._first(driver.find_elements("accessibility id", target.split("=", 1)[1]))
            if element is not None:
                return element
        if target.startswith("id="):
            element = self._first(driver.find_elements("id", target.split("=", 1)[1]))
            if element is not None:
                return element
        if target.startswith("xpath="):
            element = self._first(driver.find_elements("xpath", target.split("=", 1)[1]))
            if element is not None:
                return element
        coordinates = self._coordinates(target)
        if coordinates:
            raise AdapterError("Coordinate-only targets should use click directly, not locator lookup")
        candidates: list[tuple[str, str]] = [
            ("accessibility id", target),
            (
                "xpath",
                "//*[" + " or ".join(
                    [
                        f"contains(@text, {self._xpath_literal(target)})",
                        f"contains(@content-desc, {self._xpath_literal(target)})",
                        f"contains(@label, {self._xpath_literal(target)})",
                        f"contains(@name, {self._xpath_literal(target)})",
                        f"contains(@value, {self._xpath_literal(target)})",
                        f"contains(@resource-id, {self._xpath_literal(target)})",
                    ]
                ) + "]",
            ),
        ]
        if session_handle.platform_name == "android":
            safe = target.replace('"', '\\"')
            candidates.append(
                (
                    "-android uiautomator",
                    f'new UiSelector().textContains("{safe}")',
                )
            )
            candidates.append(("-android uiautomator", f'new UiSelector().descriptionContains("{safe}")'))
        else:
            safe = target.replace("'", "\\'")
            candidates.append(
                (
                    "-ios predicate string",
                    f"label CONTAINS '{safe}' OR name CONTAINS '{safe}' OR value CONTAINS '{safe}'",
                )
            )
        for by, value in candidates:
            try:
                element = self._first(driver.find_elements(by, value))
            except Exception:
                continue
            if element is not None:
                return element
        raise AdapterError(f"No visible mobile element matched natural-language target '{target}'")

    @staticmethod
    def _first(elements: list[Any]) -> Any | None:
        for element in elements[:25]:
            is_displayed = getattr(element, "is_displayed", None)
            try:
                if callable(is_displayed) and not is_displayed():
                    continue
            except Exception:
                continue
            return element
        return None

    def _tap_coordinates(self, session_handle: MobileSession, x: int, y: int) -> None:
        driver = session_handle.driver
        try:
            if session_handle.platform_name == "android":
                driver.execute_script("mobile: clickGesture", {"x": x, "y": y})
            else:
                driver.execute_script("mobile: tap", {"x": x, "y": y})
        except Exception as exc:
            legacy_tap = getattr(driver, "tap", None)
            if callable(legacy_tap):
                legacy_tap([(x, y)])
                return
            raise AdapterError(f"Could not tap coordinates {x},{y}: {exc}") from exc

    def _scroll(self, session_handle: MobileSession, direction: str) -> None:
        driver = session_handle.driver
        viewport = self._window_size(driver)
        normalized = direction if direction in {"up", "down", "left", "right"} else "down"
        try:
            if session_handle.platform_name == "android":
                driver.execute_script(
                    "mobile: swipeGesture",
                    {
                        "left": 1,
                        "top": 1,
                        "width": max(1, viewport["width"] - 2),
                        "height": max(1, viewport["height"] - 2),
                        "direction": normalized,
                        "percent": 0.75,
                    },
                )
            else:
                driver.execute_script("mobile: swipe", {"direction": normalized})
        except Exception as exc:
            legacy_swipe = getattr(driver, "swipe", None)
            if callable(legacy_swipe):
                start_x = viewport["width"] // 2
                end_x = start_x
                start_y = int(viewport["height"] * 0.78)
                end_y = int(viewport["height"] * 0.24)
                if normalized == "up":
                    start_y, end_y = end_y, start_y
                elif normalized == "left":
                    start_x, end_x = int(viewport["width"] * 0.75), int(viewport["width"] * 0.25)
                    start_y = end_y = viewport["height"] // 2
                elif normalized == "right":
                    start_x, end_x = int(viewport["width"] * 0.25), int(viewport["width"] * 0.75)
                    start_y = end_y = viewport["height"] // 2
                legacy_swipe(start_x, start_y, end_x, end_y, 300)
                return
            raise AdapterError(f"Could not scroll {normalized}: {exc}") from exc

    def _press_key(self, session_handle: MobileSession, key: str) -> None:
        driver = session_handle.driver
        normalized = key.strip().lower()
        if normalized in {"back", "browserback"}:
            driver.back()
            return
        if session_handle.platform_name == "android":
            keycodes = {"home": 3, "enter": 66, "search": 84}
            press_keycode = getattr(driver, "press_keycode", None)
            if callable(press_keycode) and normalized in keycodes:
                press_keycode(keycodes[normalized])
                return
        if session_handle.platform_name == "ios" and normalized == "home":
            driver.execute_script("mobile: pressButton", {"name": "home"})
            return
        active_element = getattr(getattr(driver, "switch_to", None), "active_element", None)
        if active_element is None:
            raise AdapterError(f"Could not route mobile key '{key}' to an active element")
        active_element.send_keys("\n" if normalized == "enter" else key)

    @staticmethod
    def _window_size(driver: Any) -> dict[str, int]:
        try:
            raw = driver.get_window_size()
        except Exception:
            return {"width": 0, "height": 0}
        return {
            "width": int(raw.get("width", 0) or 0),
            "height": int(raw.get("height", 0) or 0),
        }

    @staticmethod
    def _driver_contexts(driver: Any) -> list[str]:
        try:
            contexts = getattr(driver, "contexts", None)
            if contexts is None:
                return []
            return [str(item) for item in contexts]
        except Exception:
            return []

    @staticmethod
    def _safe_attr(driver: Any, name: str) -> str:
        try:
            value = getattr(driver, name, "")
        except Exception:
            return ""
        return str(value or "")

    @classmethod
    def _extract_elements(cls, page_source: str) -> list[dict[str, Any]]:
        if not page_source.strip():
            return []
        try:
            root = ET.fromstring(page_source)
        except ET.ParseError:
            return []
        elements: list[dict[str, Any]] = []
        for node in root.iter():
            attrs = dict(node.attrib)
            box = cls._element_box(attrs)
            name = cls._element_name(attrs, node.tag)
            interactive = cls._is_interactive(attrs, node.tag)
            entry = {
                "tag": node.tag,
                "class": attrs.get("class", attrs.get("type", "")),
                "role": attrs.get("role", ""),
                "name": name,
                "text": attrs.get("text", attrs.get("label", attrs.get("value", ""))),
                "resource_id": attrs.get("resource-id", attrs.get("name", "")),
                "enabled": attrs.get("enabled", attrs.get("visible", "true")).lower() != "false",
                "selected": attrs.get("selected", "false").lower() == "true",
                "interactive": interactive,
                "box": box,
                "contrast_ratio": None,
            }
            elements.append(entry)
        return elements

    @staticmethod
    def _element_box(attrs: dict[str, str]) -> dict[str, float]:
        if bounds := attrs.get("bounds"):
            match = _BOUNDS_RE.search(bounds)
            if match:
                x1 = int(match.group("x1"))
                y1 = int(match.group("y1"))
                x2 = int(match.group("x2"))
                y2 = int(match.group("y2"))
                return {"x": x1, "y": y1, "width": max(0, x2 - x1), "height": max(0, y2 - y1)}
        keys = ("x", "y", "width", "height")
        if all(key in attrs for key in keys):
            try:
                return {key: float(attrs.get(key, 0) or 0) for key in keys}
            except ValueError:
                pass
        return {"x": 0, "y": 0, "width": 0, "height": 0}

    @staticmethod
    def _element_name(attrs: dict[str, str], tag: str) -> str:
        for key in ("text", "content-desc", "label", "name", "value", "resource-id"):
            value = str(attrs.get(key, "")).strip()
            if value:
                return value[:160]
        return tag[:160]

    @staticmethod
    def _is_interactive(attrs: dict[str, str], tag: str) -> bool:
        truthy = {"true", "1", "yes"}
        if str(attrs.get("clickable", "")).lower() in truthy:
            return True
        if str(attrs.get("focusable", "")).lower() in truthy:
            return True
        class_blob = f"{tag} {attrs.get('class', '')} {attrs.get('type', '')}".lower()
        return any(
            token in class_blob
            for token in (
                "button",
                "edittext",
                "textfield",
                "switch",
                "checkbox",
                "tab",
                "cell",
                "textfield",
                "input",
            )
        )

    @staticmethod
    def _text_preview(elements: list[dict[str, Any]]) -> list[str]:
        preview: list[str] = []
        for element in elements:
            value = str(element.get("name") or "").strip()
            if value and value not in preview:
                preview.append(value)
            if len(preview) >= 12:
                break
        return preview

    @staticmethod
    def _coordinates(target: str) -> tuple[int, int] | None:
        match = _COORDINATES_RE.search(target)
        if not match:
            return None
        return int(match.group(1)), int(match.group(2))

    @staticmethod
    def _xpath_literal(value: str) -> str:
        if '"' not in value:
            return f'"{value}"'
        if "'" not in value:
            return f"'{value}'"
        parts = value.split('"')
        return "concat(" + ', \'"\', '.join(f'"{part}"' for part in parts) + ")"
