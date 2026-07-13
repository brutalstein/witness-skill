from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import shutil
import subprocess
import time
from abc import abstractmethod
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from ..errors import ConfigurationError, ReasoningError
from ..models import Observation, Persona, ProjectProfile, ReasoningDecision, SessionStep
from .base import ReasoningEngine
from .prompts import SYSTEM_PROMPT
from .schema import DECISION_SCHEMA


class PromptBuilder:
    """Build compact, delta-first prompts for multimodal QA turns.

    The full evidence remains on disk. The model receives a bounded history, compact metadata,
    a content hash, and the most relevant observation tail so long sessions do not repeatedly
    resend the same DOM/terminal payload.
    """

    @staticmethod
    def _compact(value: Any, *, max_chars: int = 4_000) -> Any:
        if isinstance(value, dict):
            compacted = {
                str(key): PromptBuilder._compact(item, max_chars=max_chars // 2)
                for key, item in list(value.items())[:40]
                if key not in {"readme_excerpt"}
            }
        elif isinstance(value, list):
            compacted = [
                PromptBuilder._compact(item, max_chars=max_chars // 2) for item in value[:30]
            ]
        elif isinstance(value, str) and len(value) > max_chars:
            compacted = value[: max_chars // 2] + "…" + value[-max_chars // 2 :]
        else:
            compacted = value
        encoded = json.dumps(compacted, ensure_ascii=False, separators=(",", ":"), default=str)
        if len(encoded) <= max_chars:
            return compacted
        return {"truncated": True, "preview": encoded[:max_chars]}

    @staticmethod
    def _visual_checklist(profile: ProjectProfile, persona: Persona) -> list[str]:
        project_type = profile.project_type.value
        base = {
            "web": [
                "button drift, overlap, or broken alignment",
                "clipped text, hidden CTA, or content outside the viewport",
                "low contrast, color-only feedback, or unreadable labels",
                "spacing, hierarchy, and empty/error state coherence",
            ],
            "desktop": [
                "window-resize breakage, clipped controls, or focus loss",
                "button drift, overlap, or inconsistent spacing",
                "hidden dialogs, cropped panels, or off-screen content",
                "low contrast, color collisions, or unreadable labels",
            ],
            "mobile": [
                "safe-area clipping, notch/home-indicator collisions, or off-screen CTA",
                "keyboard overlap, scroll traps, or blocked form submission",
                "button drift, touch-target crowding, or stacked overlaps",
                "contrast, hierarchy, and readability on a narrow viewport",
            ],
            "game": [
                "HUD drift, clipping, or z-order conflicts",
                "safe-area fit, aspect-ratio breakage, or stretched assets",
                "contrast, readability, and hierarchy failures",
                "flicker, stale overlays, or state-continuity defects",
            ],
        }.get(project_type, [])
        engine = str(profile.metadata.get("game_engine") or "").lower()
        simulator_profile = str(profile.metadata.get("simulator_profile") or "").lower()
        simulator_tags = {
            str(item).strip().lower()
            for item in (profile.metadata.get("simulation_tags") or [])
            if str(item).strip()
        }
        if engine == "unreal":
            base.extend(
                [
                    "Unreal temporal ghosting, shadow shimmer, or LOD pop-in",
                    "unexpected debug overlays, editor residue, or placeholder widgets",
                ]
            )
        if simulator_profile or simulator_tags:
            base.extend(
                [
                    "vehicle/world clipping, actor intersections, or impossible spatial overlap",
                    "lane markings, route cues, and traffic-sign readability",
                    "sensor, mirror, or telemetry overlays obscuring critical scene content",
                    "camera horizon, feed alignment, and aspect-ratio consistency",
                    "weather, glare, fog, and lighting effects harming scene readability",
                ]
            )
        if simulator_profile == "carla" or "carla" in simulator_tags:
            base.extend(
                [
                    "CARLA route/perception overlay conflicts with the driving scene",
                    "road-surface seams, floating actors, waypoint residue, or spawn anomalies",
                ]
            )
        persona_focus = [item.replace("_", " ") for item in persona.visual_focus]
        return list(dict.fromkeys([*base, *persona_focus]))[:12]

    @staticmethod
    def _visual_priority_hints(profile: ProjectProfile, observation: Observation) -> list[str]:
        hints: list[str] = []
        if observation.visual_metrics:
            hints.extend(observation.visual_metrics.likely_clipping[:5])
            hints.extend(observation.visual_metrics.alignment_warnings[:5])
            hints.extend(observation.visual_metrics.contrast_warnings[:5])
        hints.extend(observation.errors[:8])
        lowered_text = observation.text.lower()
        for needle, message in (
            ("safe_area", "Structured evidence mentions safe-area related state; inspect edge collisions."),
            ("keyboard", "Structured evidence mentions keyboard state; inspect occlusion and blocked controls."),
            ("scroll", "Structured evidence mentions scroll state; inspect hidden or unreachable content."),
            ("contrast_ratio", "Structured evidence includes contrast data; verify weak or conflicting color usage."),
        ):
            if needle in lowered_text:
                hints.append(message)
        simulator_profile = str(profile.metadata.get("simulator_profile") or "").lower()
        if simulator_profile:
            for needle, message in (
                ("sensor", "Structured evidence mentions sensor-related state; inspect feed clarity and occlusion."),
                ("telemetry", "Structured evidence mentions telemetry; inspect whether overlays hide critical scene content."),
                ("lane", "Structured evidence mentions lane-related state; inspect road guidance readability."),
                ("weather", "Structured evidence mentions weather state; inspect glare, fog, and visibility degradation."),
            ):
                if needle in lowered_text:
                    hints.append(message)
        return list(dict.fromkeys(item.strip() for item in hints if item.strip()))[:12]

    @staticmethod
    def build(
        *,
        profile: ProjectProfile,
        persona: Persona,
        adapter_name: str,
        allowed_actions: tuple[str, ...],
        history: list[SessionStep],
        observation: Observation,
        previous_action: str,
        history_turns: int = 6,
        max_observation_chars: int = 12_000,
        screenshot_attached: bool | None = None,
    ) -> str:
        history_turns = max(1, min(history_turns, 20))
        max_observation_chars = max(2_000, min(max_observation_chars, 48_000))
        compact_history = [
            {
                "turn": step.turn,
                "action": step.action.human_summary() if step.action else "initial_observation",
                "observation": step.decision.observation_summary[:800],
                "judgment": step.decision.judgment.value,
                "confidence": step.decision.confidence.value,
                "next_action": step.decision.next_action.human_summary(),
            }
            for step in history[-history_turns:]
        ]
        observation_text = observation.text
        if len(observation_text) > max_observation_chars:
            head = max_observation_chars // 3
            tail = max_observation_chars - head
            observation_text = (
                observation_text[:head] + "\n…[bounded evidence]…\n" + observation_text[-tail:]
            )
        attached = (
            bool(observation.screenshot_path)
            if screenshot_attached is None
            else screenshot_attached
        )
        request = {
            "persona": PromptBuilder._compact(persona.model_dump(mode="json")),
            "project_profile": {
                "type": profile.project_type.value,
                "confidence": profile.confidence.value,
                "entry_point": profile.entry_point,
                "reachable_address": profile.reachable_address,
                "metadata": PromptBuilder._compact(profile.metadata, max_chars=5_000),
                "raw_signals": [
                    signal.model_dump(mode="json") for signal in profile.raw_signals[-8:]
                ],
            },
            "adapter": adapter_name,
            "visual_audit": {
                "enabled": profile.project_type.value in {"web", "desktop", "mobile", "game"}
                or bool(persona.visual_focus),
                "audit_depth": (
                    "exhaustive"
                    if profile.project_type.value == "game"
                    or str(profile.metadata.get("simulator_profile") or "").strip()
                    else "standard"
                ),
                "focus_areas": PromptBuilder._visual_checklist(profile, persona),
                "priority_hints": PromptBuilder._visual_priority_hints(profile, observation),
                "reporting_expectation": (
                    "If you find a visual defect, name the concrete defect in observation_summary "
                    "and explain it crisply in visual_assessment. Do not use vague summaries such as "
                    "'looks fine' or 'readable' without naming the checked areas."
                ),
            },
            "allowed_nonterminal_actions": list(allowed_actions),
            "always_allowed_terminal_actions": [
                "goal_reached",
                "goal_blocked",
                "give_up_and_report",
            ],
            "previous_action": previous_action or "initial_observation",
            "history": compact_history,
            "current_observation": {
                "summary": observation.summary,
                "text": observation_text,
                "text_sha256": hashlib.sha256(observation.text.encode("utf-8")).hexdigest(),
                "errors": observation.errors[-20:],
                "exit_code": observation.exit_code,
                "metadata": PromptBuilder._compact(observation.metadata),
                "visual_metrics": observation.visual_metrics.model_dump(mode="json")
                if observation.visual_metrics
                else None,
                "delta": observation.delta.model_dump(mode="json") if observation.delta else None,
                "screenshot_attached": attached,
                "full_evidence_paths": {
                    "screenshot": observation.screenshot_path,
                    "structured": observation.structured_path,
                },
            },
        }
        visual_instruction = (
            "The attached screenshot is the current user-visible state. "
            if attached
            else "No screenshot is attached this turn; rely on the bounded structured evidence and delta. "
        )
        return (
            "Evaluate this exact QA turn and return only a schema-valid Witness decision. "
            + visual_instruction
            + "Treat artifact paths as evidence references and do not invent unseen details. "
            + "When visual_audit.enabled is true, actively search for layout breakage, hidden UI, "
            + "contrast/readability issues, overlaps, clipping, and state-visibility defects before you conclude the turn. "
            + "For game/simulator visuals, perform an explicit sweep over HUD, world geometry, temporal stability, "
            + "and scene readability before returning goal_reached.\n\n"
            + json.dumps(request, ensure_ascii=False, separators=(",", ":"))
        )


class HTTPReasoningEngine(ReasoningEngine):
    def __init__(
        self,
        *,
        model: str,
        output_dir: Path,
        timeout: float = 120,
        input_cost_per_million: float = 0.0,
        output_cost_per_million: float = 0.0,
        history_turns: int = 6,
        max_observation_chars: int = 12_000,
        max_output_tokens: int = 1_800,
        image_detail: str = "auto",
        image_policy: str = "changed",
        image_change_threshold: float = 0.005,
    ) -> None:
        super().__init__()
        self.model = model
        self.output_dir = output_dir
        self.timeout = timeout
        self.input_cost_per_million = max(0.0, input_cost_per_million)
        self.output_cost_per_million = max(0.0, output_cost_per_million)
        self.history_turns = history_turns
        self.max_observation_chars = max_observation_chars
        self.max_output_tokens = max(256, max_output_tokens)
        self.image_detail = image_detail if image_detail in {"low", "high", "auto"} else "auto"
        self.image_policy = (
            image_policy if image_policy in {"always", "changed", "never"} else "changed"
        )
        self.image_change_threshold = max(0.0, min(image_change_threshold, 1.0))

    def _should_attach_image(
        self, *, profile: ProjectProfile, history: list[SessionStep], observation: Observation
    ) -> bool:
        if not observation.screenshot_path or self.image_policy == "never":
            return False
        if self.image_policy == "always" or profile.project_type.value == "game" or not history:
            return True
        delta = observation.delta
        if delta is None:
            return True
        if delta.new_errors or delta.changed_text:
            return True
        return (delta.visual_change_ratio or 0.0) >= self.image_change_threshold

    def _refresh_cost(self) -> None:
        if self.input_cost_per_million <= 0 and self.output_cost_per_million <= 0:
            return
        self.usage.cost_estimate_available = True
        self.usage.estimated_cost_usd = round(
            (self.usage.input_tokens / 1_000_000) * self.input_cost_per_million
            + (self.usage.output_tokens / 1_000_000) * self.output_cost_per_million,
            8,
        )

    def decide(
        self,
        *,
        profile: ProjectProfile,
        persona: Persona,
        adapter_name: str,
        allowed_actions: tuple[str, ...],
        history: list[SessionStep],
        observation: Observation,
        previous_action: str,
    ) -> ReasoningDecision:
        should_attach = self._should_attach_image(
            profile=profile, history=history, observation=observation
        )
        screenshot = self._image_data(observation.screenshot_path) if should_attach else None
        prompt = PromptBuilder.build(
            profile=profile,
            persona=persona,
            adapter_name=adapter_name,
            allowed_actions=allowed_actions,
            history=history,
            observation=observation,
            previous_action=previous_action,
            history_turns=self.history_turns,
            max_observation_chars=self.max_observation_chars,
            screenshot_attached=screenshot is not None,
        )
        last_error: Exception | None = None
        for attempt in range(3):
            started = time.monotonic()
            try:
                payload = self._call(prompt=prompt, screenshot=screenshot)
                self.usage.requests += 1
                self.usage.provider_latency_seconds += time.monotonic() - started
                return ReasoningDecision.model_validate(payload)
            except (httpx.HTTPError, KeyError, ValueError, ValidationError, ReasoningError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1.5 * (2**attempt))
        raise ReasoningError(
            f"{self.provider_name} reasoning failed after 3 attempts: {last_error}"
        )

    def _image_data(self, relative_path: str) -> tuple[str, str] | None:
        if not relative_path:
            return None
        path = self.output_dir / relative_path
        if not path.is_file():
            return None
        media_type = mimetypes.guess_type(path.name)[0] or "image/png"
        return media_type, base64.b64encode(path.read_bytes()).decode("ascii")

    @abstractmethod
    def _call(self, *, prompt: str, screenshot: tuple[str, str] | None) -> dict[str, Any]:
        """Submit one multimodal decision request and return its structured payload."""


class OpenAIReasoningEngine(HTTPReasoningEngine):
    provider_name = "openai"

    def __init__(
        self,
        *,
        model: str,
        output_dir: Path,
        timeout: float = 120,
        input_cost_per_million: float = 0.0,
        output_cost_per_million: float = 0.0,
        history_turns: int = 6,
        max_observation_chars: int = 12_000,
        max_output_tokens: int = 1_800,
        image_detail: str = "auto",
        image_policy: str = "changed",
        image_change_threshold: float = 0.005,
    ) -> None:
        super().__init__(
            model=model,
            output_dir=output_dir,
            timeout=timeout,
            input_cost_per_million=input_cost_per_million,
            output_cost_per_million=output_cost_per_million,
            history_turns=history_turns,
            max_observation_chars=max_observation_chars,
            max_output_tokens=max_output_tokens,
            image_detail=image_detail,
            image_policy=image_policy,
            image_change_threshold=image_change_threshold,
        )
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        if not self.api_key:
            raise ConfigurationError("OPENAI_API_KEY is required for --provider openai")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    def _call(self, *, prompt: str, screenshot: tuple[str, str] | None) -> dict[str, Any]:
        content: list[dict[str, Any]] = []
        if screenshot:
            media_type, data = screenshot
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:{media_type};base64,{data}",
                    "detail": self.image_detail,
                }
            )
        content.append({"type": "input_text", "text": prompt})
        payload = {
            "model": self.model,
            "instructions": SYSTEM_PROMPT,
            "input": [{"role": "user", "content": content}],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "witness_decision",
                    "strict": True,
                    "schema": DECISION_SCHEMA,
                }
            },
            "max_output_tokens": self.max_output_tokens,
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if response.status_code >= 400:
            raise ReasoningError(
                f"OpenAI API returned {response.status_code}: {response.text[:2000]}"
            )
        data = response.json()
        usage = data.get("usage") or {}
        self.usage.input_tokens += int(usage.get("input_tokens", 0) or 0)
        self.usage.output_tokens += int(usage.get("output_tokens", 0) or 0)
        self._refresh_cost()
        if data.get("status") == "incomplete":
            raise ReasoningError(f"OpenAI response incomplete: {data.get('incomplete_details')}")
        texts: list[str] = []
        for item in data.get("output", []):
            if item.get("type") != "message":
                continue
            for block in item.get("content", []):
                if block.get("type") == "refusal":
                    raise ReasoningError(
                        f"OpenAI refused the reasoning request: {block.get('refusal')}"
                    )
                if block.get("type") == "output_text":
                    texts.append(block.get("text", ""))
        if not texts:
            raise ReasoningError("OpenAI response contained no output_text")
        return json.loads("\n".join(texts))


class AnthropicReasoningEngine(HTTPReasoningEngine):
    provider_name = "anthropic"

    def __init__(
        self,
        *,
        model: str,
        output_dir: Path,
        timeout: float = 120,
        input_cost_per_million: float = 0.0,
        output_cost_per_million: float = 0.0,
        history_turns: int = 6,
        max_observation_chars: int = 12_000,
        max_output_tokens: int = 1_800,
        image_detail: str = "auto",
        image_policy: str = "changed",
        image_change_threshold: float = 0.005,
    ) -> None:
        super().__init__(
            model=model,
            output_dir=output_dir,
            timeout=timeout,
            input_cost_per_million=input_cost_per_million,
            output_cost_per_million=output_cost_per_million,
            history_turns=history_turns,
            max_observation_chars=max_observation_chars,
            max_output_tokens=max_output_tokens,
            image_detail=image_detail,
            image_policy=image_policy,
            image_change_threshold=image_change_threshold,
        )
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise ConfigurationError("ANTHROPIC_API_KEY is required for --provider anthropic")
        self.base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1").rstrip("/")

    def _call(self, *, prompt: str, screenshot: tuple[str, str] | None) -> dict[str, Any]:
        content: list[dict[str, Any]] = []
        if screenshot:
            media_type, data = screenshot
            content.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": data},
                }
            )
        content.append({"type": "text", "text": prompt})
        tool_name = "submit_witness_decision"
        payload = {
            "model": self.model,
            "max_tokens": self.max_output_tokens,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": content}],
            "thinking": {"type": "disabled"},
            "tools": [
                {
                    "name": tool_name,
                    "description": "Submit the schema-valid decision for the current Witness QA turn.",
                    "input_schema": DECISION_SCHEMA,
                    "strict": True,
                }
            ],
            "tool_choice": {"type": "tool", "name": tool_name},
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            )
        if response.status_code >= 400:
            raise ReasoningError(
                f"Anthropic API returned {response.status_code}: {response.text[:2000]}"
            )
        data = response.json()
        usage = data.get("usage") or {}
        self.usage.input_tokens += int(usage.get("input_tokens", 0) or 0)
        self.usage.output_tokens += int(usage.get("output_tokens", 0) or 0)
        self._refresh_cost()
        if data.get("stop_reason") == "refusal":
            raise ReasoningError(
                f"Anthropic refused the reasoning request: {data.get('stop_details') or data.get('content')}"
            )
        for block in data.get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == tool_name:
                return block["input"]
        raise ReasoningError(
            f"Anthropic returned no {tool_name} tool call (stop_reason={data.get('stop_reason')})"
        )


class CodexCLIReasoningEngine(ReasoningEngine):
    """Use an authenticated Codex CLI session as Witness's multimodal reasoner.

    Codex CLI reuses the user's cached Sign in with ChatGPT credentials, so no
    OPENAI_API_KEY is required. Each turn is isolated, schema-constrained,
    read-only, and ephemeral. The native Codex skill mode is preferred when
    Witness is already running inside an interactive Codex session.
    """

    provider_name = "codex-cli"

    def __init__(
        self,
        *,
        model: str | None,
        output_dir: Path,
        timeout: float = 180,
        executable: str = "codex",
        profile: str | None = None,
        sandbox: str = "read-only",
        verify_login: bool = True,
        history_turns: int = 6,
        max_observation_chars: int = 12_000,
        image_policy: str = "changed",
        image_change_threshold: float = 0.005,
    ) -> None:
        super().__init__()
        resolved = shutil.which(executable) if not Path(executable).is_file() else executable
        if not resolved:
            raise ConfigurationError(
                "Codex CLI was not found. Install it, run `codex login`, then retry "
                "with --provider codex-cli."
            )
        self.executable = str(resolved)
        self.model = model or "codex-default"
        # Codex executes with a per-turn cwd. Resolve once so schema, output, and
        # screenshot arguments remain valid when users pass a relative output path.
        self.output_dir = output_dir.expanduser().resolve()
        self.timeout = timeout
        self.profile = profile
        self.sandbox = sandbox
        self.history_turns = history_turns
        self.max_observation_chars = max_observation_chars
        self.image_policy = (
            image_policy if image_policy in {"always", "changed", "never"} else "changed"
        )
        self.image_change_threshold = max(0.0, min(image_change_threshold, 1.0))
        self.turn = 0
        if verify_login:
            self._verify_login()

    def _verify_login(self) -> None:
        try:
            completed = subprocess.run(
                [self.executable, "login", "status"],
                capture_output=True,
                text=True,
                timeout=min(self.timeout, 20),
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ConfigurationError(f"Could not check Codex login status: {exc}") from exc
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()[-1000:]
            raise ConfigurationError(
                "Codex CLI is not signed in. Run `codex login` and choose Sign in with ChatGPT."
                + (f" Details: {detail}" if detail else "")
            )

    def decide(
        self,
        *,
        profile: ProjectProfile,
        persona: Persona,
        adapter_name: str,
        allowed_actions: tuple[str, ...],
        history: list[SessionStep],
        observation: Observation,
        previous_action: str,
    ) -> ReasoningDecision:
        attach_image = bool(observation.screenshot_path) and self.image_policy != "never"
        if self.image_policy == "changed" and history and profile.project_type.value != "game":
            delta = observation.delta
            attach_image = (
                delta is None
                or bool(delta.new_errors or delta.changed_text)
                or ((delta.visual_change_ratio or 0.0) >= self.image_change_threshold)
            )
        screenshot = (
            (self.output_dir / observation.screenshot_path).resolve() if attach_image else None
        )
        if screenshot is not None and not screenshot.is_file():
            screenshot = None
        prompt = PromptBuilder.build(
            profile=profile,
            persona=persona,
            adapter_name=adapter_name,
            allowed_actions=allowed_actions,
            history=history,
            observation=observation,
            previous_action=previous_action,
            history_turns=self.history_turns,
            max_observation_chars=self.max_observation_chars,
            screenshot_attached=screenshot is not None,
        )
        self.turn += 1
        run_dir = self.output_dir / "logs" / "codex-cli" / f"turn-{self.turn:03d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        schema_path = run_dir / "decision.schema.json"
        output_path = run_dir / "decision.json"
        schema_path.write_text(json.dumps(DECISION_SCHEMA, indent=2), encoding="utf-8")
        full_prompt = (
            SYSTEM_PROMPT
            + "\n\nYou are the reasoning component only. Do not inspect the repository, run shell "
            "commands, edit files, or call external tools. Judge only the supplied observation and "
            "attached screenshot. Return the final Witness decision matching the output schema.\n\n"
            + prompt
        )
        command = [
            self.executable,
            "exec",
            "--ephemeral",
            "--sandbox",
            self.sandbox,
            "--skip-git-repo-check",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
        ]
        if self.profile:
            command.extend(["--profile", self.profile])
        if self.model and self.model != "codex-default":
            command.extend(["--model", self.model])
        if screenshot is not None:
            command.extend(["--image", str(screenshot)])
        command.append("-")

        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                input=full_prompt,
                capture_output=True,
                text=True,
                cwd=run_dir,
                timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ReasoningError(f"Codex CLI reasoning failed: {exc}") from exc
        self.usage.requests += 1
        self.usage.provider_latency_seconds += time.monotonic() - started
        (run_dir / "stderr.log").write_text(completed.stderr[-10000:], encoding="utf-8")
        if completed.returncode != 0:
            raise ReasoningError(
                f"Codex CLI exited {completed.returncode}: "
                f"{(completed.stderr or completed.stdout)[-2000:]}"
            )
        try:
            raw = output_path.read_text(encoding="utf-8")
            return ReasoningDecision.model_validate_json(raw)
        except (OSError, ValueError, ValidationError) as exc:
            fallback = completed.stdout[-2000:]
            raise ReasoningError(
                f"Codex CLI returned invalid Witness decision JSON: {exc}; stdout={fallback}"
            ) from exc


class ScriptedReasoningEngine(ReasoningEngine):
    """Replays model decisions exported by Claude Code/Codex or a benchmark fixture."""

    provider_name = "scripted"

    def __init__(self, *, decision_file: Path, output_dir: Path) -> None:
        super().__init__()
        self.model = "host-agent-decisions"
        self.output_dir = output_dir
        try:
            raw = decision_file.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict) and "decisions" in data:
                data = data["decisions"]
            if not isinstance(data, list):
                raise ValueError("decision file must contain a JSON array or {decisions: [...]}")
            self.decisions = [ReasoningDecision.model_validate(item) for item in data]
        except (OSError, ValueError, ValidationError) as exc:
            raise ConfigurationError(
                f"Could not load scripted decisions from {decision_file}: {exc}"
            ) from exc
        self.index = 0

    def decide(self, **_: Any) -> ReasoningDecision:
        if self.index >= len(self.decisions):
            raise ReasoningError("Scripted decision file is exhausted")
        decision = self.decisions[self.index]
        self.index += 1
        self.usage.requests += 1
        return decision


class CommandReasoningEngine(ReasoningEngine):
    """Uses any local/host model command without requiring an API key.

    The command receives one JSON object on stdin with system prompt, turn prompt, schema,
    and screenshot path. It must print a single decision JSON object on stdout. This makes
    Claude Code, Codex CLI, Ollama wrappers, or an enterprise model gateway pluggable.
    """

    provider_name = "command"

    def __init__(
        self,
        *,
        command: str,
        model: str | None,
        output_dir: Path,
        timeout: float = 180,
        history_turns: int = 6,
        max_observation_chars: int = 12_000,
    ) -> None:
        super().__init__()
        if not command.strip():
            raise ConfigurationError("--agent-command or WITNESS_AGENT_COMMAND is required")
        self.command = command
        self.model = model or "host-agent"
        self.output_dir = output_dir
        self.timeout = timeout
        self.history_turns = history_turns
        self.max_observation_chars = max_observation_chars

    def decide(
        self,
        *,
        profile: ProjectProfile,
        persona: Persona,
        adapter_name: str,
        allowed_actions: tuple[str, ...],
        history: list[SessionStep],
        observation: Observation,
        previous_action: str,
    ) -> ReasoningDecision:
        prompt = PromptBuilder.build(
            profile=profile,
            persona=persona,
            adapter_name=adapter_name,
            allowed_actions=allowed_actions,
            history=history,
            observation=observation,
            previous_action=previous_action,
            history_turns=self.history_turns,
            max_observation_chars=self.max_observation_chars,
        )
        request = {
            "system": SYSTEM_PROMPT,
            "prompt": prompt,
            "schema": DECISION_SCHEMA,
            "screenshot_path": str((self.output_dir / observation.screenshot_path).resolve())
            if observation.screenshot_path
            else "",
        }
        started = time.monotonic()
        try:
            completed = subprocess.run(
                self.command if os.name == "nt" else ["/bin/sh", "-lc", self.command],
                input=json.dumps(request, ensure_ascii=False),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                shell=os.name == "nt",
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ReasoningError(f"Agent command failed: {exc}") from exc
        self.usage.requests += 1
        self.usage.provider_latency_seconds += time.monotonic() - started
        if completed.returncode:
            raise ReasoningError(
                f"Agent command exited {completed.returncode}: {completed.stderr[-2000:]}"
            )
        try:
            payload = json.loads(completed.stdout)
            return ReasoningDecision.model_validate(payload)
        except (ValueError, ValidationError) as exc:
            raise ReasoningError(
                f"Agent command returned invalid decision JSON: {exc}; stdout={completed.stdout[-2000:]}"
            ) from exc


def create_reasoning_engine(
    provider: str,
    *,
    model: str | None,
    output_dir: Path,
    timeout: float = 120,
    agent_command: str | None = None,
    decision_file: Path | None = None,
    codex_executable: str = "codex",
    codex_profile: str | None = None,
    codex_sandbox: str = "read-only",
    input_cost_per_million: float = 0.0,
    output_cost_per_million: float = 0.0,
    history_turns: int = 6,
    max_observation_chars: int = 12_000,
    max_output_tokens: int = 1_800,
    image_detail: str = "auto",
    image_policy: str = "changed",
    image_change_threshold: float = 0.005,
) -> ReasoningEngine:
    selected = provider.lower()
    if selected == "auto":
        if os.getenv("OPENAI_API_KEY"):
            selected = "openai"
        elif os.getenv("ANTHROPIC_API_KEY"):
            selected = "anthropic"
        elif agent_command or os.getenv("WITNESS_AGENT_COMMAND"):
            selected = "command"
        elif decision_file or os.getenv("WITNESS_DECISION_FILE"):
            selected = "scripted"
        else:
            raise ConfigurationError(
                "No reasoning provider is configured. Inside an interactive Codex task, use "
                "`witness session start` so the current signed-in Codex host performs the reasoning. "
                "For unattended OAuth-backed runs, run `codex login` and select "
                "`--provider codex-cli`. Alternatively configure OPENAI_API_KEY/ANTHROPIC_API_KEY, "
                "use --provider command with --agent-command, or use --provider scripted with "
                "--decision-file."
            )
    if selected == "openai":
        return OpenAIReasoningEngine(
            model=model or os.getenv("WITNESS_MODEL", "gpt-5.6"),
            output_dir=output_dir,
            timeout=timeout,
            input_cost_per_million=input_cost_per_million,
            output_cost_per_million=output_cost_per_million,
            history_turns=history_turns,
            max_observation_chars=max_observation_chars,
            max_output_tokens=max_output_tokens,
            image_detail=image_detail,
            image_policy=image_policy,
            image_change_threshold=image_change_threshold,
        )
    if selected == "anthropic":
        return AnthropicReasoningEngine(
            model=model or os.getenv("WITNESS_MODEL", "claude-sonnet-5"),
            output_dir=output_dir,
            timeout=timeout,
            input_cost_per_million=input_cost_per_million,
            output_cost_per_million=output_cost_per_million,
            history_turns=history_turns,
            max_observation_chars=max_observation_chars,
            max_output_tokens=max_output_tokens,
            image_detail=image_detail,
            image_policy=image_policy,
            image_change_threshold=image_change_threshold,
        )
    if selected in {"codex", "codex-cli"}:
        return CodexCLIReasoningEngine(
            model=model or os.getenv("WITNESS_MODEL"),
            output_dir=output_dir,
            timeout=timeout,
            executable=os.getenv("WITNESS_CODEX_PATH", codex_executable),
            profile=os.getenv("WITNESS_CODEX_PROFILE", codex_profile),
            sandbox=os.getenv("WITNESS_CODEX_SANDBOX", codex_sandbox),
            history_turns=history_turns,
            max_observation_chars=max_observation_chars,
            image_policy=image_policy,
            image_change_threshold=image_change_threshold,
        )
    if selected == "command":
        return CommandReasoningEngine(
            command=agent_command or os.getenv("WITNESS_AGENT_COMMAND", ""),
            model=model,
            output_dir=output_dir,
            timeout=timeout,
            history_turns=history_turns,
            max_observation_chars=max_observation_chars,
        )
    if selected == "scripted":
        file_value = decision_file or (
            Path(os.environ["WITNESS_DECISION_FILE"])
            if os.getenv("WITNESS_DECISION_FILE")
            else None
        )
        if not file_value:
            raise ConfigurationError("--decision-file is required for --provider scripted")
        return ScriptedReasoningEngine(decision_file=file_value, output_dir=output_dir)
    raise ConfigurationError(
        "provider must be auto, openai, anthropic, codex-cli, command, or scripted"
    )
