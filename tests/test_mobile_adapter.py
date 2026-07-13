from __future__ import annotations

from pathlib import Path

from PIL import Image

from witness_qa.adapters.mobile import MobileAdapter
from witness_qa.models import ActionKind, AdapterAction, Confidence, ProjectProfile, ProjectType


class FakeElement:
    def __init__(self, name: str) -> None:
        self.name = name
        self.sent: list[str] = []
        self.clicked = 0
        self.cleared = 0

    def click(self) -> None:
        self.clicked += 1

    def clear(self) -> None:
        self.cleared += 1

    def send_keys(self, value: str) -> None:
        self.sent.append(value)

    def is_displayed(self) -> bool:
        return True

    def is_selected(self) -> bool:
        return False


class FakeDriver:
    def __init__(self) -> None:
        self.page_source = """
        <hierarchy>
          <node class="android.widget.TextView" text="Welcome" bounds="[10,10][200,60]" />
          <node class="android.widget.Button" text="Sign in" clickable="true" bounds="[20,80][220,140]" />
          <node class="android.widget.EditText" text="" resource-id="email" clickable="true" bounds="[20,160][300,220]" />
        </hierarchy>
        """
        self.contexts = ["NATIVE_APP", "FLUTTER"]
        self.current_context = "NATIVE_APP"
        self.current_package = "com.example.demo"
        self.current_activity = ".MainActivity"
        self.scripts: list[tuple[str, dict]] = []
        self.elements = {
            "Sign in": FakeElement("Sign in"),
            "email": FakeElement("email"),
        }
        self.switch_to = type("SwitchTo", (), {"active_element": FakeElement("active")})()
        self.back_calls = 0
        self.quit_called = False

    def get_window_size(self) -> dict[str, int]:
        return {"width": 390, "height": 844}

    def get_screenshot_as_file(self, path: str) -> bool:
        Image.new("RGB", (390, 844), "white").save(path)
        return True

    def find_elements(self, by: str, value: str):
        if by == "accessibility id" and value == "Sign in":
            return [self.elements["Sign in"]]
        if by == "id" and value == "email":
            return [self.elements["email"]]
        if by == "xpath" and "Sign in" in value:
            return [self.elements["Sign in"]]
        if by == "xpath" and "email" in value:
            return [self.elements["email"]]
        return []

    def execute_script(self, script: str, payload: dict) -> None:
        self.scripts.append((script, payload))

    def back(self) -> None:
        self.back_calls += 1

    def quit(self) -> None:
        self.quit_called = True


def test_mobile_adapter_builds_capabilities_and_observes(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}
    driver = FakeDriver()

    def fake_create_driver(self, server_url: str, capabilities: dict[str, object]):
        captured["server_url"] = server_url
        captured["capabilities"] = capabilities
        return driver

    monkeypatch.setattr(MobileAdapter, "_create_driver", fake_create_driver)
    profile = ProjectProfile(
        target="mobile",
        project_root=str(tmp_path),
        project_type=ProjectType.MOBILE,
        confidence=Confidence.HIGH,
        metadata={
            "framework": "flutter",
            "mobile_app_package": "com.example.demo",
            "mobile_app_activity": "com.example.demo.MainActivity",
        },
    )
    adapter = MobileAdapter(
        tmp_path / "out",
        mobile_platform_name="android",
        mobile_device_name="emulator-5554",
        appium_server_url="http://127.0.0.1:4723",
    )
    session = adapter.start(profile)
    try:
        observation = adapter.observe(session)
    finally:
        adapter.stop(session)
    capabilities = captured["capabilities"]
    assert captured["server_url"] == "http://127.0.0.1:4723"
    assert capabilities["platformName"] == "Android"
    assert capabilities["appium:appPackage"] == "com.example.demo"
    assert capabilities["appium:appActivity"] == "com.example.demo.MainActivity"
    assert (tmp_path / "out" / observation.screenshot_path).is_file()
    assert "FLUTTER" in observation.text
    assert observation.visual_metrics is not None
    assert driver.quit_called is True


def test_mobile_adapter_executes_realistic_actions(tmp_path: Path) -> None:
    profile = ProjectProfile(
        target="mobile",
        project_root=str(tmp_path),
        project_type=ProjectType.MOBILE,
        confidence=Confidence.HIGH,
        metadata={"framework": "flutter"},
    )
    adapter = MobileAdapter(tmp_path / "out")
    session = type(
        "Session",
        (),
        {
            "profile": profile,
            "driver": FakeDriver(),
            "server_url": "http://127.0.0.1:4723",
            "platform_name": "android",
            "screenshot_index": 0,
            "previous_observation": None,
            "previous_screenshot": None,
            "available_contexts": [],
        },
    )()
    click = adapter.act(session, AdapterAction(kind=ActionKind.CLICK, target="Sign in"))
    typed = adapter.act(
        session, AdapterAction(kind=ActionKind.TYPE, target="id=email", text="user@example.com")
    )
    pressed = adapter.act(session, AdapterAction(kind=ActionKind.PRESS, key="back"))
    scrolled = adapter.act(session, AdapterAction(kind=ActionKind.SCROLL, direction="down"))
    assert click.success
    assert typed.success
    assert pressed.success
    assert scrolled.success
    assert session.driver.elements["Sign in"].clicked == 1
    assert session.driver.elements["email"].sent == ["user@example.com"]
    assert session.driver.back_calls == 1
    assert session.driver.scripts[0][0] == "mobile: swipeGesture"
