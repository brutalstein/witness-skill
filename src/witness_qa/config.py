from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .errors import ConfigurationError


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectConfig(ConfigModel):
    type: str = "auto"
    start: str | None = None
    url: str | None = None
    root: str | None = None
    capture_command: str | None = None
    input_command: str | None = None
    frames: list[str] = Field(default_factory=list)
    ready_timeout: float = 45.0
    electron_debug_port: int | None = None
    electron_isolated_profile: bool = True
    appium_server_url: str | None = None
    mobile_platform_name: str | None = None
    mobile_device_name: str | None = None
    mobile_automation_name: str | None = None
    mobile_app: str | None = None
    mobile_app_package: str | None = None
    mobile_app_activity: str | None = None
    mobile_bundle_id: str | None = None
    mobile_udid: str | None = None
    mobile_no_reset: bool = True
    mobile_new_command_timeout: int = 180


class ProviderConfig(ConfigModel):
    name: str = "auto"
    model: str | None = None
    timeout: float = 120.0
    agent_command: str | None = None
    decision_file: str | None = None
    codex_path: str = "codex"
    codex_profile: str | None = None
    codex_sandbox: str = "read-only"
    input_cost_per_million: float = 0.0
    output_cost_per_million: float = 0.0
    history_turns: int = 6
    max_observation_chars: int = 12_000
    max_output_tokens: int = 1_800
    image_detail: str = "auto"
    image_policy: str = "changed"
    image_change_threshold: float = 0.005


class SessionConfig(ConfigModel):
    max_turns: int = 20
    max_cost_usd: float | None = None
    personas: list[str] = Field(default_factory=lambda: ["first-time-user"])
    journeys: list[str] = Field(default_factory=list)
    seed: int = 0
    headless: bool = True


class SafetyConfig(ConfigModel):
    profile: str = "safe"
    allow_production: bool = False
    allowed_hosts: list[str] = Field(default_factory=lambda: ["127.0.0.1", "localhost", "::1"])
    blocked_commands: list[str] = Field(default_factory=list)
    sandbox: str = "copy"
    max_process_seconds: int = 300
    network: str = "local"


class ReportingConfig(ConfigModel):
    formats: list[str] = Field(
        default_factory=lambda: ["markdown", "json", "html", "junit", "sarif"]
    )
    fail_on: str = "high"
    baseline: str | None = None


class VisualConfig(ConfigModel):
    enabled: bool = True
    full_page: bool = True
    visual_regression_threshold: float = 0.02
    detect_alignment: bool = True
    detect_contrast: bool = True
    detect_clipping: bool = True
    reference_images: list[str] = Field(default_factory=list)


class WitnessConfig(ConfigModel):
    version: int = 1
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    visual: VisualConfig = Field(default_factory=VisualConfig)


def find_config(project: str | Path = ".", explicit: Path | None = None) -> Path | None:
    if explicit:
        path = explicit.expanduser().resolve()
        return path if path.is_file() else None
    candidate = Path(project)
    if candidate.is_file():
        candidate = candidate.parent
    candidate = candidate.expanduser().resolve()
    for name in ("witness.yaml", "witness.yml"):
        path = candidate / name
        if path.is_file():
            return path
    return None


def load_config(project: str | Path = ".", explicit: Path | None = None) -> WitnessConfig:
    path = find_config(project, explicit)
    if not path:
        return WitnessConfig()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return WitnessConfig.model_validate(raw)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"Could not load Witness config from {path}: {exc}") from exc


def write_default_config(path: Path) -> None:
    if path.exists():
        raise ConfigurationError(f"Refusing to overwrite existing {path}")
    content = """version: 1

project:
  type: auto
  # start: npm run dev
  # url: http://127.0.0.1:3000
  # Electron launch commands may include {debug_port}; otherwise Witness appends the flag.
  # electron_debug_port: 9222
  electron_isolated_profile: true
  # Flutter / mobile QA via Appium:
  # appium_server_url: http://127.0.0.1:4723
  # mobile_platform_name: android   # or ios
  # mobile_device_name: emulator-5554
  # mobile_app: build/app/outputs/flutter-apk/app-debug.apk
  # mobile_app_package: com.example.app
  # mobile_app_activity: .MainActivity
  # mobile_bundle_id: com.example.app

provider:
  name: auto
  # model: gpt-5.6
  # For ChatGPT OAuth via Codex CLI: name: codex-cli
  # codex_path: codex
  # codex_profile: default
  # codex_sandbox: read-only
  # Direct API pricing is configurable so cost limits remain accurate as vendors change prices.
  # input_cost_per_million: 0
  # output_cost_per_million: 0
  history_turns: 6
  max_observation_chars: 12000
  max_output_tokens: 1800
  image_detail: auto
  image_policy: changed  # always, changed, or never; game sessions always retain visual evidence
  image_change_threshold: 0.005

session:
  max_turns: 20
  # max_cost_usd: 1.00
  personas:
    - first-time-user
  journeys: []
  seed: 0
  headless: true

safety:
  profile: safe
  allow_production: false
  allowed_hosts: ["127.0.0.1", "localhost", "::1"]
  sandbox: copy
  network: local
  max_process_seconds: 300

visual:
  enabled: true
  full_page: true
  visual_regression_threshold: 0.02
  detect_alignment: true
  detect_contrast: true
  detect_clipping: true
  reference_images: []

reporting:
  formats: [markdown, json, html, junit, sarif]
  fail_on: high
"""
    path.write_text(content, encoding="utf-8")


def env_override(config: WitnessConfig) -> WitnessConfig:
    data: dict[str, Any] = config.model_dump()
    if provider := os.getenv("WITNESS_PROVIDER"):
        data["provider"]["name"] = provider
    if model := os.getenv("WITNESS_MODEL"):
        data["provider"]["model"] = model
    return WitnessConfig.model_validate(data)
