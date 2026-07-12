from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .adapters.base import Adapter
from .adapters.registry import create_adapter
from .errors import ConfigurationError, ReasoningError, WitnessError
from .models import (
    ActionResult,
    AdapterAction,
    Observation,
    OverallStatus,
    Persona,
    ProjectProfile,
    ReasoningDecision,
    SessionResult,
    SessionStep,
    UsageMetrics,
)
from .reasoning.prompts import SYSTEM_PROMPT
from .reasoning.providers import PromptBuilder
from .reasoning.schema import DECISION_SCHEMA
from .reporting import ReportWriter
from .utils import atomic_write_json, ensure_dir

STATE_RELATIVE_PATH = Path(".witness") / "session.json"


class HostSessionRuntime:
    """Persistent adapter runtime controlled by an already-running host model."""

    def __init__(self, spec: dict[str, Any]) -> None:
        self.output_dir = Path(spec["output_dir"]).expanduser().resolve()
        self.profile = ProjectProfile.model_validate(spec["profile"])
        self.persona = Persona.model_validate(spec["persona"])
        self.max_turns = int(spec.get("max_turns", 20))
        self.seed = int(spec.get("seed", 0))
        self.idle_timeout = float(spec.get("idle_timeout", 1800))
        self.reporter = ReportWriter(self.output_dir, spec.get("report_formats"))
        self.adapter: Adapter = create_adapter(
            self.profile.project_type,
            self.output_dir,
            **dict(spec.get("adapter_options") or {}),
        )
        self.handle: Any | None = None
        self.steps: list[SessionStep] = []
        self.infrastructure_errors: list[str] = []
        self.started_at = datetime.now(UTC)
        self.last_activity = time.monotonic()
        self.previous_action = "initial_observation"
        self.action: AdapterAction | None = None
        self.action_result: ActionResult | None = None
        self.observation: Observation | None = None
        self.result: SessionResult | None = None
        self.status = "starting"
        self.lock = threading.RLock()
        self.shutdown_requested = False

    def start(self) -> None:
        with self.lock:
            try:
                self.handle = self.adapter.start(self.profile)
                self.observation = self.adapter.observe(self.handle)
                self.status = "active"
            except Exception as exc:
                self.infrastructure_errors.append(
                    f"Adapter start/initial observation failed: {exc}"
                )
                self.observation = Observation(
                    adapter=self.adapter.name,
                    summary="Witness could not start or observe the target",
                    text=str(exc),
                    errors=[str(exc)],
                )
                self._finalize(OverallStatus.INCONCLUSIVE)

    @property
    def finalized(self) -> bool:
        return self.result is not None

    def request_payload(self) -> dict[str, Any]:
        with self.lock:
            self.last_activity = time.monotonic()
            if self.finalized:
                return {
                    "ok": True,
                    "terminal": True,
                    "status": self.status,
                    "result": self.result.model_dump(mode="json") if self.result else None,
                }
            if self.observation is None:
                raise WitnessError("Host session has no observation")
            prompt = PromptBuilder.build(
                profile=self.profile,
                persona=self.persona,
                adapter_name=self.adapter.name,
                allowed_actions=self.adapter.supported_actions,
                history=self.steps,
                observation=self.observation,
                previous_action=self.previous_action,
            )
            screenshot = ""
            if self.observation.screenshot_path:
                screenshot = str((self.output_dir / self.observation.screenshot_path).resolve())
            structured = ""
            if self.observation.structured_path:
                structured = str((self.output_dir / self.observation.structured_path).resolve())
            return {
                "ok": True,
                "terminal": False,
                "status": self.status,
                "turn": len(self.steps) + 1,
                "max_turns": self.max_turns,
                "provider": "codex-host",
                "model": "current-codex-session",
                "system": SYSTEM_PROMPT,
                "prompt": prompt,
                "schema": DECISION_SCHEMA,
                "screenshot_path": screenshot,
                "structured_path": structured,
                "observation": self.observation.model_dump(mode="json"),
                "allowed_actions": list(self.adapter.supported_actions),
                "decision_instructions": (
                    "Inspect the current screenshot/structured artifact, reason as the active "
                    "Codex host model, then submit exactly one JSON object matching schema."
                ),
            }

    def submit(self, payload: dict[str, Any], expected_turn: int) -> dict[str, Any]:
        with self.lock:
            self.last_activity = time.monotonic()
            if self.finalized:
                raise WitnessError("Host session is already finalized")
            if self.observation is None:
                raise WitnessError("Host session has no current observation")
            current_turn = len(self.steps) + 1
            if expected_turn != current_turn:
                raise WitnessError(
                    f"Stale host decision: expected turn {expected_turn}, current turn is {current_turn}"
                )
            try:
                decision = ReasoningDecision.model_validate(payload)
            except ValidationError as exc:
                raise ReasoningError(f"Host decision does not match Witness schema: {exc}") from exc

            turn = len(self.steps) + 1
            self.steps.append(
                SessionStep(
                    turn=turn,
                    action=self.action,
                    action_result=self.action_result,
                    observation=self.observation,
                    decision=decision,
                )
            )
            next_action = decision.next_action
            if next_action.is_terminal:
                status = {
                    "goal_reached": OverallStatus.GOAL_REACHED,
                    "goal_blocked": OverallStatus.GOAL_BLOCKED,
                    "give_up_and_report": OverallStatus.INCONCLUSIVE,
                }[next_action.kind.value]
                if status is OverallStatus.GOAL_REACHED and any(
                    step.decision.judgment.value == "mismatch" for step in self.steps
                ):
                    status = OverallStatus.MIXED
                self._finalize(status)
                return self.request_payload()

            if turn >= self.max_turns:
                self.infrastructure_errors.append(
                    f"Host session reached max_turns={self.max_turns} without a terminal decision"
                )
                self._finalize(OverallStatus.INCONCLUSIVE)
                return self.request_payload()

            if next_action.kind.value not in self.adapter.supported_actions:
                self.infrastructure_errors.append(
                    f"Host requested unsupported {self.adapter.name} action: "
                    f"{next_action.kind.value}"
                )
                self._finalize(OverallStatus.INCONCLUSIVE)
                return self.request_payload()

            self.action = next_action
            self.action_result = self.adapter.act(self.handle, next_action)
            if self.action_result.infrastructure_error:
                self.infrastructure_errors.append(self.action_result.infrastructure_error)
            try:
                self.observation = self.adapter.observe(self.handle)
            except Exception as exc:
                self.infrastructure_errors.append(f"Observation after action failed: {exc}")
                self._finalize(OverallStatus.INCONCLUSIVE)
                return self.request_payload()
            self.previous_action = next_action.human_summary()
            return self.request_payload()

    def finish(self, status: OverallStatus = OverallStatus.INCONCLUSIVE) -> dict[str, Any]:
        with self.lock:
            if not self.finalized:
                self._finalize(status)
            self.shutdown_requested = True
            return self.request_payload()

    def idle_expired(self) -> bool:
        return not self.finalized and time.monotonic() - self.last_activity > self.idle_timeout

    def _finalize(self, status: OverallStatus) -> None:
        if self.result is not None:
            return
        if self.handle is not None:
            try:
                self.adapter.stop(self.handle)
            except Exception as exc:
                self.infrastructure_errors.append(f"Adapter teardown failed: {exc}")
            finally:
                self.handle = None
        self.result = self.reporter.write(
            profile=self.profile,
            persona=self.persona,
            steps=self.steps,
            overall_status=status,
            adapter=self.adapter.name,
            provider="codex-host",
            model="current-codex-session",
            started_at=self.started_at,
            infrastructure_errors=self.infrastructure_errors,
            usage=UsageMetrics(requests=len(self.steps)),
            seed=self.seed,
        )
        self.status = "finished"


class HostSessionClient:
    def __init__(self, state_path: Path) -> None:
        self.state_path = resolve_state_path(state_path)
        try:
            self.state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ConfigurationError(f"Could not read Witness session state: {exc}") from exc
        self.base_url = f"http://127.0.0.1:{self.state['port']}"
        self.token = self.state["token"]

    def request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        body = None
        headers = {"Authorization": f"Bearer {self.token}"}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise WitnessError(f"Witness host session returned HTTP {exc.code}: {detail}") from exc
        except (OSError, ValueError) as exc:
            raise WitnessError(f"Could not contact Witness host session: {exc}") from exc
        if not data.get("ok", False):
            raise WitnessError(str(data.get("error", "Unknown host session error")))
        return data

    def health(self) -> dict[str, Any]:
        return self.request("GET", "/health")

    def current(self) -> dict[str, Any]:
        return self.request("GET", "/request")

    def submit(self, decision: dict[str, Any], expected_turn: int) -> dict[str, Any]:
        return self.request(
            "POST",
            "/decision",
            {"decision": decision, "expected_turn": expected_turn},
        )

    def status(self) -> dict[str, Any]:
        return self.request("GET", "/status")

    def finish(self, status: OverallStatus = OverallStatus.INCONCLUSIVE) -> dict[str, Any]:
        return self.request("POST", "/finish", {"status": status.value})


def resolve_state_path(path: Path) -> Path:
    candidate = path.expanduser().resolve()
    if candidate.is_dir() or candidate.suffix != ".json":
        candidate = candidate / STATE_RELATIVE_PATH
    return candidate


def launch_host_session(
    spec: dict[str, Any], output_dir: Path, startup_timeout: float = 60
) -> tuple[Path, dict[str, Any]]:
    output_dir = output_dir.expanduser().resolve()
    control_dir = ensure_dir(output_dir / STATE_RELATIVE_PATH.parent)
    spec_path = control_dir / "launch.json"
    state_path = control_dir / "session.json"
    log_path = control_dir / "daemon.log"
    if state_path.exists():
        try:
            existing = HostSessionClient(state_path)
            existing.health()
        except WitnessError:
            state_path.unlink(missing_ok=True)
        else:
            raise ConfigurationError(
                f"A Witness host session is already active at {state_path}. Finish or stop it first."
            )
    atomic_write_json(spec_path, spec)
    command = [
        sys.executable,
        "-m",
        "witness_qa.host_daemon",
        "--spec",
        str(spec_path),
        "--state",
        str(state_path),
    ]
    creationflags = 0
    popen_kwargs: dict[str, Any] = {}
    child_env = os.environ.copy()
    # Keep detached host sessions importable from a source checkout as well as an
    # installed wheel. This also makes `pytest` and contributor workflows behave
    # exactly like the packaged CLI without relying on the caller's working directory.
    source_root = str(Path(__file__).resolve().parents[1])
    existing_pythonpath = child_env.get("PYTHONPATH", "")
    pythonpath_entries = [entry for entry in existing_pythonpath.split(os.pathsep) if entry]
    if source_root not in pythonpath_entries:
        child_env["PYTHONPATH"] = os.pathsep.join([source_root, *pythonpath_entries])
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0
        )
    else:
        popen_kwargs["start_new_session"] = True
    with log_path.open("a", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            close_fds=os.name != "nt",
            creationflags=creationflags,
            env=child_env,
            **popen_kwargs,
        )
    deadline = time.monotonic() + startup_timeout
    last_error = ""
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        if state_path.is_file():
            try:
                client = HostSessionClient(state_path)
                health = client.health()
                return state_path, health
            except WitnessError as exc:
                last_error = str(exc)
        time.sleep(0.15)
    detail = (
        log_path.read_text(encoding="utf-8", errors="replace")[-3000:] if log_path.exists() else ""
    )
    raise ConfigurationError(f"Witness host session failed to start. {last_error} {detail}".strip())
