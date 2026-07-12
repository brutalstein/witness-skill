from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectType(StrEnum):
    WEB = "web"
    CLI = "cli"
    API = "api"
    GAME = "game"
    DESKTOP = "desktop"
    MOBILE = "mobile"
    UNKNOWN = "unknown"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Judgment(StrEnum):
    MATCH = "match"
    MISMATCH = "mismatch"
    UNCERTAIN = "uncertain"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    NONE = "none"


class OverallStatus(StrEnum):
    GOAL_REACHED = "goal_reached"
    GOAL_BLOCKED = "goal_blocked"
    MIXED = "mixed"
    INCONCLUSIVE = "inconclusive"


class ActionKind(StrEnum):
    NAVIGATE = "navigate"
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    HOVER = "hover"
    TYPE = "type"
    PRESS = "press"
    SELECT_OPTION = "select_option"
    CHECK = "check"
    UNCHECK = "uncheck"
    UPLOAD_FILE = "upload_file"
    DRAG_AND_DROP = "drag_and_drop"
    SCROLL = "scroll"
    SCROLL_TO_ELEMENT = "scroll_to_element"
    WAIT = "wait"
    ACCEPT_DIALOG = "accept_dialog"
    DISMISS_DIALOG = "dismiss_dialog"
    OPEN_NEW_TAB = "open_new_tab"
    SWITCH_TAB = "switch_tab"
    DOWNLOAD_FILE = "download_file"
    RUN_COMMAND = "run_command"
    SEND_INPUT = "send_input"
    SEND_KEYPRESS = "send_keypress"
    WAIT_FOR_OUTPUT = "wait_for_output"
    HTTP_REQUEST = "http_request"
    NEXT_FRAME = "next_frame"
    CAPTURE_FRAME = "capture_frame"
    GOAL_REACHED = "goal_reached"
    GOAL_BLOCKED = "goal_blocked"
    GIVE_UP_AND_REPORT = "give_up_and_report"


TERMINAL_ACTIONS = {
    ActionKind.GOAL_REACHED,
    ActionKind.GOAL_BLOCKED,
    ActionKind.GIVE_UP_AND_REPORT,
}


class DetectionSignal(StrictModel):
    source: str
    project_type: ProjectType
    weight: float
    detail: str


class DetectionCandidate(StrictModel):
    project_type: ProjectType
    score: float


class ProjectProfile(StrictModel):
    target: str
    project_root: str | None = None
    project_type: ProjectType
    entry_point: str | None = None
    reachable_address: str | None = None
    confidence: Confidence
    raw_signals: list[DetectionSignal] = Field(default_factory=list)
    candidates: list[DetectionCandidate] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Persona(StrictModel):
    name: str
    role: str = "A realistic user approaching the software from the outside."
    goal: str
    patience: str = "medium"
    success_criteria: str = (
        "The goal is completed with clear, understandable feedback and no errors."
    )
    known_constraints: str = "Do not bypass authentication, verification, or safety controls."
    viewport: str = "desktop"
    locale: str = "en-US"
    network_profile: str = "normal"
    color_scheme: str = "light"
    reduced_motion: bool = False
    input_mode: str = "pointer"
    visual_focus: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_values(self) -> Persona:
        if self.patience not in {"low", "medium", "high"}:
            raise ValueError("patience must be low, medium, or high")
        if self.color_scheme not in {"light", "dark", "no-preference"}:
            raise ValueError("color_scheme must be light, dark, or no-preference")
        return self


class AdapterAction(StrictModel):
    kind: ActionKind
    target: str = ""
    source: str = ""
    text: str = ""
    key: str = ""
    url: str = ""
    direction: str = ""
    command: str = ""
    method: str = ""
    path: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    body: Any | None = None
    files: list[str] = Field(default_factory=list)
    option: str = ""
    tab_index: int = 0
    seconds: float = 0.0
    reason: str = ""

    @property
    def is_terminal(self) -> bool:
        return self.kind in TERMINAL_ACTIONS

    def human_summary(self) -> str:
        if self.kind in {ActionKind.TYPE, ActionKind.SEND_INPUT}:
            value = self.target or "[text redacted]"
        elif self.kind is ActionKind.HTTP_REQUEST:
            value = f"{self.method or 'GET'} {self.path or self.url}"
        else:
            value = (
                self.command
                or self.url
                or self.target
                or self.source
                or self.option
                or self.text
                or self.key
                or self.direction
            )
        return f"{self.kind.value}: {value}".rstrip(": ")


class ActionResult(StrictModel):
    success: bool
    summary: str
    infrastructure_error: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualMetrics(StrictModel):
    width: int = 0
    height: int = 0
    entropy: float = 0.0
    edge_density: float = 0.0
    blank_ratio: float = 0.0
    dominant_colors: list[str] = Field(default_factory=list)
    perceptual_hash: str = ""
    change_ratio: float = 0.0
    likely_clipping: list[str] = Field(default_factory=list)
    alignment_warnings: list[str] = Field(default_factory=list)
    contrast_warnings: list[str] = Field(default_factory=list)


class ObservationDelta(StrictModel):
    changed_text: list[str] = Field(default_factory=list)
    new_errors: list[str] = Field(default_factory=list)
    resolved_errors: list[str] = Field(default_factory=list)
    visual_change_ratio: float = 0.0
    changed_interactives: list[str] = Field(default_factory=list)


class Observation(StrictModel):
    adapter: str
    summary: str
    text: str = ""
    screenshot_path: str = ""
    structured_path: str = ""
    exit_code: int | None = None
    errors: list[str] = Field(default_factory=list)
    visual_metrics: VisualMetrics | None = None
    delta: ObservationDelta | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReasoningDecision(StrictModel):
    expectation: str
    action_taken: str
    observation_summary: str
    judgment: Judgment
    confidence: Confidence
    reasoning: str
    hypothesis_if_mismatch: str
    severity: Severity
    suggested_investigation: str = ""
    visual_assessment: str = ""
    next_action: AdapterAction


class SessionStep(StrictModel):
    turn: int
    action: AdapterAction | None
    action_result: ActionResult | None
    observation: Observation
    decision: ReasoningDecision


class Finding(StrictModel):
    fingerprint: str = ""
    persona: str
    severity: Severity
    summary: str
    expectation: str
    observation: str
    evidence_path: str
    reasoning: str
    hypothesis: str
    suggested_investigation: str = ""
    visual_assessment: str = ""
    turn: int
    occurrences: int = 1


class UsageMetrics(StrictModel):
    input_tokens: int = 0
    output_tokens: int = 0
    requests: int = 0
    estimated_cost_usd: float = 0.0
    cost_estimate_available: bool = False
    provider_latency_seconds: float = 0.0


class SessionMetadata(StrictModel):
    adapter: str
    provider: str
    model: str
    project_type: ProjectType
    project_confidence: Confidence
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    turns: int
    witness_version: str = ""
    project_revision: str = ""
    usage: UsageMetrics = Field(default_factory=UsageMetrics)
    seed: int = 0


class SessionResult(StrictModel):
    overall_status: OverallStatus
    personas_run: list[str]
    findings: list[Finding]
    report_path: str
    trace_path: str
    profile: ProjectProfile
    metadata: SessionMetadata
    infrastructure_errors: list[str] = Field(default_factory=list)
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    budget_exceeded: bool = False
    max_cost_usd: float | None = None


class TestJourney(StrictModel):
    id: str
    name: str
    goal: str
    priority: str = "medium"
    source: str = "inferred"
    success_criteria: str = ""


class TestPlan(StrictModel):
    project_type: ProjectType
    journeys: list[TestJourney]
    risks: list[str] = Field(default_factory=list)
    coverage_notes: list[str] = Field(default_factory=list)


class CampaignResult(StrictModel):
    overall_status: OverallStatus
    sessions: list[SessionResult]
    findings: list[Finding]
    personas_run: list[str]
    report_path: str
    junit_path: str = ""
    sarif_path: str = ""
    html_path: str = ""
    budget_exceeded: bool = False
    max_cost_usd: float | None = None
    estimated_cost_usd: float = 0.0
