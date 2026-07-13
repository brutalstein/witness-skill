from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Any

import typer
from PIL import Image, ImageDraw
from rich.console import Console
from rich.table import Table

from . import __version__
from .adapters.registry import REGISTRY, create_adapter
from .benchmark import score_findings
from .campaign import CampaignRunner
from .config import WitnessConfig, env_override, load_config, write_default_config
from .detection import ProjectDetector
from .engine_bridges import available_engine_bridges, install_engine_bridge
from .errors import ConfigurationError, WitnessError
from .host_session import HostSessionClient, launch_host_session, resolve_state_path
from .integrations.github import format_findings_as_pr_comment, post_pr_comment
from .models import (
    CampaignResult,
    OverallStatus,
    Persona,
    ProjectProfile,
    ProjectType,
    SessionResult,
)
from .orchestrator import Orchestrator
from .personas import built_in_persona_names, load_persona
from .planning import TestPlanner, render_plan_markdown
from .reasoning.providers import create_reasoning_engine
from .replay import TraceReplay
from .safety import validate_target_url
from .utils import atomic_write_json, is_url

app = typer.Typer(
    name="witness",
    help="Evidence-backed agentic QA for web, Flutter mobile, Electron desktop, CLI, API, and game/visual software.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
console = Console(stderr=True)
session_app = typer.Typer(
    name="session",
    help="Host-driven QA sessions for the current Codex/Claude model; no API key or nested model process.",
    no_args_is_help=True,
)
app.add_typer(session_app, name="session")


def _version_callback(value: bool) -> None:
    if value:
        print(__version__)
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Print the Witness version and exit.",
        ),
    ] = False,
) -> None:
    """Evidence-backed agentic QA."""


def _viewport(persona: Persona) -> tuple[int, int]:
    if persona.viewport == "mobile":
        return 390, 844
    if persona.viewport == "tablet":
        return 820, 1180
    return 1440, 1000


def _apply_config(profile: ProjectProfile, config: WitnessConfig) -> ProjectProfile:
    if config.project.type != "auto":
        profile.project_type = ProjectType(config.project.type)
    if config.project.start:
        profile.entry_point = config.project.start
    if config.project.url:
        profile.reachable_address = config.project.url
    if config.project.root:
        profile.project_root = str(Path(config.project.root).expanduser().resolve())
    profile.metadata.update(
        {
            "capture_command": config.project.capture_command,
            "input_command": config.project.input_command,
            "frames": config.project.frames or profile.metadata.get("frames", []),
            "reference_images": config.visual.reference_images,
        }
    )
    return profile


def _adapter_options(
    config: WitnessConfig, persona: Persona, allow_production: bool
) -> dict[str, Any]:
    width, height = _viewport(persona)
    return {
        "headless": config.session.headless,
        "allow_external_navigation": allow_production,
        "viewport_width": width,
        "viewport_height": height,
        "locale": persona.locale,
        "color_scheme": persona.color_scheme,
        "reduced_motion": persona.reduced_motion,
        "full_page": config.visual.full_page,
        "reference_images": config.visual.reference_images,
        "visual_regression_threshold": config.visual.visual_regression_threshold,
        "capture_command": config.project.capture_command,
        "input_command": config.project.input_command,
        "frames": config.project.frames,
        "sandbox": config.safety.sandbox,
        "blocked_commands": config.safety.blocked_commands,
        "command_timeout": config.safety.max_process_seconds,
        "startup_timeout": config.project.ready_timeout,
        "electron_debug_port": config.project.electron_debug_port,
        "electron_isolated_profile": config.project.electron_isolated_profile,
        "appium_server_url": config.project.appium_server_url,
        "mobile_platform_name": config.project.mobile_platform_name,
        "mobile_device_name": config.project.mobile_device_name,
        "mobile_automation_name": config.project.mobile_automation_name,
        "mobile_app": config.project.mobile_app,
        "mobile_app_package": config.project.mobile_app_package,
        "mobile_app_activity": config.project.mobile_app_activity,
        "mobile_bundle_id": config.project.mobile_bundle_id,
        "mobile_udid": config.project.mobile_udid,
        "mobile_no_reset": config.project.mobile_no_reset,
        "mobile_new_command_timeout": config.project.mobile_new_command_timeout,
    }


def _reasoner(
    config: WitnessConfig,
    output: Path,
    provider: str,
    model: str | None,
    agent_command: str | None,
    decision_file: Path | None,
):
    return create_reasoning_engine(
        provider,
        model=model,
        output_dir=output,
        timeout=config.provider.timeout,
        agent_command=agent_command or config.provider.agent_command,
        decision_file=decision_file
        or (Path(config.provider.decision_file) if config.provider.decision_file else None),
        codex_executable=config.provider.codex_path,
        codex_profile=config.provider.codex_profile,
        codex_sandbox=config.provider.codex_sandbox,
        input_cost_per_million=float(
            os.getenv("WITNESS_INPUT_COST_PER_MILLION", config.provider.input_cost_per_million)
        ),
        output_cost_per_million=float(
            os.getenv("WITNESS_OUTPUT_COST_PER_MILLION", config.provider.output_cost_per_million)
        ),
        history_turns=config.provider.history_turns,
        max_observation_chars=config.provider.max_observation_chars,
        max_output_tokens=config.provider.max_output_tokens,
        image_detail=config.provider.image_detail,
        image_policy=config.provider.image_policy,
        image_change_threshold=config.provider.image_change_threshold,
    )


def _severity_reached(findings: list[Any], threshold: str) -> bool:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "none": 5}
    limit = order.get(threshold.lower(), 1)
    return any(order.get(finding.severity.value, 5) <= limit for finding in findings)


@app.command()
def run(
    project: Annotated[
        str,
        typer.Option("--project", "-p", help="Project directory, URL, or game frame directory."),
    ] = ".",
    persona: Annotated[
        list[str] | None,
        typer.Option("--persona", help="Repeat for multiple personas; name, file, or inline goal."),
    ] = None,
    journey: Annotated[
        list[str] | None, typer.Option("--journey", help="Repeat to run explicit user journeys.")
    ] = None,
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Artifact/report directory.")
    ] = Path("witness-output"),
    config_path: Annotated[
        Path | None, typer.Option("--config", help="Path to witness.yaml.")
    ] = None,
    max_turns: Annotated[int | None, typer.Option("--max-turns", min=1, max=100)] = None,
    max_cost: Annotated[
        float | None,
        typer.Option("--max-cost", min=0.0, help="Maximum estimated direct-provider spend in USD."),
    ] = None,
    adapter: Annotated[
        str, typer.Option("--adapter", help="auto, web, mobile, desktop, cli, api, or game.")
    ] = "auto",
    provider: Annotated[
        str,
        typer.Option(
            "--provider", help="auto, openai, anthropic, codex-cli, command, or scripted."
        ),
    ] = "auto",
    model: Annotated[str | None, typer.Option("--model", help="Provider model ID.")] = None,
    agent_command: Annotated[
        str | None,
        typer.Option(
            "--agent-command",
            help="Local/host model command reading JSON stdin and returning decision JSON.",
        ),
    ] = None,
    decision_file: Annotated[
        Path | None,
        typer.Option("--decision-file", help="JSON decisions exported by the host agent."),
    ] = None,
    start_command: Annotated[
        str | None, typer.Option("--start-command", help="Override inferred target start command.")
    ] = None,
    reachable_address: Annotated[
        str | None, typer.Option("--url", help="Override inferred web/API URL.")
    ] = None,
    headless: Annotated[
        bool | None, typer.Option("--headless/--headed", help="Run Chromium headlessly.")
    ] = None,
    allow_production: Annotated[
        bool, typer.Option("--allow-production", help="Explicitly allow a non-local URL target.")
    ] = False,
    fail_on: Annotated[
        str | None, typer.Option("--fail-on", help="critical, high, medium, low, info, or none.")
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Print only machine-readable result.")
    ] = False,
) -> None:
    """Run one session or a multi-persona/journey campaign."""
    try:
        config = env_override(load_config(project, config_path))
        if max_turns is not None:
            config.session.max_turns = max_turns
        if max_cost is not None:
            config.session.max_cost_usd = max_cost
        if headless is not None:
            config.session.headless = headless
        if provider != "auto":
            config.provider.name = provider
        if model:
            config.provider.model = model
        allow_production = allow_production or config.safety.allow_production
        if is_url(project):
            validate_target_url(project, config.safety.allowed_hosts, allow_production)
        output = output.expanduser().resolve()
        profile = ProjectDetector().detect(
            project, start_command=start_command, reachable_address=reachable_address
        )
        profile = _apply_config(profile, config)
        if adapter != "auto":
            try:
                profile.project_type = ProjectType(adapter.lower())
            except ValueError as exc:
                raise typer.BadParameter(
                    "adapter must be auto, web, mobile, desktop, cli, api, or game"
                ) from exc
        if profile.project_type is ProjectType.UNKNOWN:
            details = "; ".join(signal.detail for signal in profile.raw_signals[-8:])
            raise typer.BadParameter(
                f"Project type is unsupported or low-confidence. Pass --adapter explicitly. Signals: {details}"
            )
        if profile.reachable_address:
            validate_target_url(
                profile.reachable_address, config.safety.allowed_hosts, allow_production
            )

        persona_values = persona or config.session.personas or ["first-time-user"]
        personas = [load_persona(value) for value in persona_values]
        journey_values = journey or config.session.journeys
        plan = TestPlanner().build(profile, journey_values)
        selected_journeys = plan.journeys if journey_values else []

        def adapter_factory(session_output: Path, effective_persona: Persona):
            return create_adapter(
                profile.project_type,
                session_output,
                **_adapter_options(config, effective_persona, allow_production),
            )

        def reasoner_factory(session_output: Path):
            return _reasoner(
                config,
                session_output,
                config.provider.name,
                config.provider.model,
                agent_command,
                decision_file,
            )

        is_campaign = len(personas) > 1 or len(selected_journeys) > 1
        if is_campaign:
            result: CampaignResult | SessionResult = CampaignRunner(
                output_dir=output,
                adapter_factory=adapter_factory,
                reasoner_factory=reasoner_factory,
                max_turns=config.session.max_turns,
                report_formats=config.reporting.formats,
                seed=config.session.seed,
                max_cost_usd=config.session.max_cost_usd,
            ).run(profile=profile, personas=personas, journeys=selected_journeys)
        else:
            effective = personas[0]
            if selected_journeys:
                effective = effective.model_copy(
                    update={
                        "goal": selected_journeys[0].goal,
                        "name": f"{effective.name} · {selected_journeys[0].name}",
                    }
                )
            adapter_instance = adapter_factory(output, effective)
            reasoner = reasoner_factory(output)
            result = Orchestrator(
                adapter=adapter_instance,
                reasoner=reasoner,
                output_dir=output,
                max_turns=config.session.max_turns,
                report_formats=config.reporting.formats,
                seed=config.session.seed,
                max_cost_usd=config.session.max_cost_usd,
            ).run(profile=profile, persona=effective)
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
        if not json_output:
            console.print(
                f"[bold]Witness:[/bold] {result.overall_status.value}; {len(result.findings)} unique finding(s). Report: {result.report_path}"
            )
        threshold = fail_on or config.reporting.fail_on
        if threshold != "none" and _severity_reached(result.findings, threshold):
            raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except (WitnessError, typer.BadParameter, ValueError) as exc:
        if json_output:
            print(json.dumps({"error": str(exc), "type": type(exc).__name__}, ensure_ascii=False))
        else:
            console.print(f"[bold red]Witness error:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc


@session_app.command("start")
def session_start(
    project: Annotated[
        str,
        typer.Option("--project", "-p", help="Project directory, URL, or game frame directory."),
    ] = ".",
    persona: Annotated[
        str, typer.Option("--persona", help="Built-in persona, persona file, or inline goal.")
    ] = "first-time-user",
    journey: Annotated[
        str | None, typer.Option("--journey", help="Override the persona goal for this session.")
    ] = None,
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Artifact/report directory.")
    ] = Path("witness-output"),
    config_path: Annotated[Path | None, typer.Option("--config")] = None,
    max_turns: Annotated[int | None, typer.Option("--max-turns", min=1, max=100)] = None,
    adapter: Annotated[
        str, typer.Option("--adapter", help="auto, web, mobile, desktop, cli, api, or game.")
    ] = "auto",
    start_command: Annotated[str | None, typer.Option("--start-command")] = None,
    reachable_address: Annotated[str | None, typer.Option("--url")] = None,
    headless: Annotated[bool | None, typer.Option("--headless/--headed")] = None,
    allow_production: Annotated[bool, typer.Option("--allow-production")] = False,
    idle_timeout: Annotated[
        float, typer.Option("--idle-timeout", min=30, help="Auto-finish an abandoned session.")
    ] = 1800,
) -> None:
    """Start a persistent adapter session controlled by the current host model."""
    try:
        config = env_override(load_config(project, config_path))
        if max_turns is not None:
            config.session.max_turns = max_turns
        if headless is not None:
            config.session.headless = headless
        allow_production = allow_production or config.safety.allow_production
        if is_url(project):
            validate_target_url(project, config.safety.allowed_hosts, allow_production)
        output = output.expanduser().resolve()
        profile = ProjectDetector().detect(
            project, start_command=start_command, reachable_address=reachable_address
        )
        profile = _apply_config(profile, config)
        if adapter != "auto":
            try:
                profile.project_type = ProjectType(adapter.lower())
            except ValueError as exc:
                raise typer.BadParameter(
                    "adapter must be auto, web, mobile, desktop, cli, api, or game"
                ) from exc
        if profile.project_type is ProjectType.UNKNOWN:
            raise typer.BadParameter(
                "Project type is unsupported or low-confidence. Pass --adapter explicitly."
            )
        if profile.reachable_address:
            validate_target_url(
                profile.reachable_address, config.safety.allowed_hosts, allow_production
            )
        effective_persona = load_persona(persona)
        if journey:
            effective_persona = effective_persona.model_copy(
                update={"name": f"{effective_persona.name} · {journey}", "goal": journey}
            )
        spec = {
            "output_dir": str(output),
            "profile": profile.model_dump(mode="json"),
            "persona": effective_persona.model_dump(mode="json"),
            "adapter_options": _adapter_options(config, effective_persona, allow_production),
            "max_turns": config.session.max_turns,
            "report_formats": config.reporting.formats,
            "seed": config.session.seed,
            "idle_timeout": idle_timeout,
        }
        state_path, _ = launch_host_session(
            spec, output, startup_timeout=max(config.project.ready_timeout + 10, 30)
        )
        payload = HostSessionClient(state_path).current()
        payload["session_state"] = str(state_path)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        typer.echo(
            f"Witness native session started: {state_path}. "
            "Inspect the evidence, submit one schema-valid decision, and repeat.",
            err=True,
        )
    except (WitnessError, typer.BadParameter, ValueError) as exc:
        console.print(f"[bold red]Witness session error:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc


@session_app.command("request")
def session_request(
    session: Annotated[
        Path, typer.Option("--session", "-s", help="Output directory or .witness/session.json.")
    ] = Path("witness-output"),
) -> None:
    """Return the current observation, visual artifact paths, prompt, and decision schema."""
    try:
        print(json.dumps(HostSessionClient(session).current(), ensure_ascii=False, indent=2))
    except WitnessError as exc:
        console.print(f"[bold red]Witness session error:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc


@session_app.command("submit")
def session_submit(
    session: Annotated[
        Path, typer.Option("--session", "-s", help="Output directory or .witness/session.json.")
    ] = Path("witness-output"),
    decision_file: Annotated[
        Path | None, typer.Option("--decision-file", "-f", help="Strict Witness decision JSON.")
    ] = None,
    decision_json: Annotated[
        str | None, typer.Option("--decision-json", help="Inline strict Witness decision JSON.")
    ] = None,
    expected_turn: Annotated[
        int,
        typer.Option(
            "--expected-turn",
            min=1,
            help="Required live turn token; rejects stale or duplicated submissions.",
        ),
    ] = ...,
) -> None:
    """Record a host-model judgment, execute its next action, and return the next observation."""
    try:
        if decision_file and decision_json:
            raise typer.BadParameter("Use only one of --decision-file or --decision-json")
        if decision_file:
            raw = decision_file.read_text(encoding="utf-8")
        elif decision_json:
            raw = decision_json
        elif not sys.stdin.isatty():
            raw = sys.stdin.read()
        else:
            raise typer.BadParameter(
                "Provide --decision-file, --decision-json, or pipe the decision JSON on stdin"
            )
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise typer.BadParameter("Decision JSON must be an object")
        response = HostSessionClient(session).submit(payload, expected_turn=expected_turn)
        print(json.dumps(response, ensure_ascii=False, indent=2))
    except (OSError, ValueError, WitnessError, typer.BadParameter) as exc:
        console.print(f"[bold red]Witness session error:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc


@session_app.command("status")
def session_status(
    session: Annotated[Path, typer.Option("--session", "-s")] = Path("witness-output"),
) -> None:
    """Show active turn count or the final report metadata."""
    state_path = resolve_state_path(session)
    try:
        print(json.dumps(HostSessionClient(state_path).status(), ensure_ascii=False, indent=2))
    except WitnessError as exc:
        # A completed daemon intentionally exits; preserve a useful final state pointer.
        if state_path.is_file():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
                if state.get("status") == "finished":
                    print(json.dumps({"ok": True, **state}, ensure_ascii=False, indent=2))
                    return
            except (OSError, ValueError):
                pass
        console.print(f"[bold red]Witness session error:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc


@session_app.command("finish")
def session_finish(
    session: Annotated[Path, typer.Option("--session", "-s")] = Path("witness-output"),
    status: Annotated[
        str, typer.Option("--status", help="goal_reached, goal_blocked, mixed, or inconclusive.")
    ] = "inconclusive",
) -> None:
    """Finalize an active native session and write its reports."""
    try:
        response = HostSessionClient(session).finish(OverallStatus(status))
        print(json.dumps(response, ensure_ascii=False, indent=2))
    except (ValueError, WitnessError) as exc:
        console.print(f"[bold red]Witness session error:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc


@app.command()
def detect(
    project: Annotated[str, typer.Argument(help="Project directory, URL, or image.")] = ".",
    start_command: Annotated[str | None, typer.Option("--start-command")] = None,
) -> None:
    """Inspect a target and print its scored Project Profile."""
    try:
        profile = ProjectDetector().detect(project, start_command=start_command)
        print(profile.model_dump_json(indent=2))
    except WitnessError as exc:
        console.print(f"[bold red]Detection error:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc


@app.command()
def init(
    path: Annotated[Path, typer.Option("--path", help="Config path.")] = Path("witness.yaml"),
) -> None:
    """Create a documented witness.yaml configuration."""
    try:
        write_default_config(path)
        console.print(f"Created {path}")
    except WitnessError as exc:
        console.print(f"[bold red]Witness error:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc


@app.command()
def plan(
    project: Annotated[str, typer.Argument(help="Project directory or URL.")] = ".",
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("witness-plan.md"),
    journey: Annotated[list[str] | None, typer.Option("--journey")] = None,
    max_cost: Annotated[
        float | None,
        typer.Option("--max-cost", min=0.0, help="Planned maximum provider spend in USD."),
    ] = None,
) -> None:
    """Generate an inspectable test-journey plan without running the product."""
    profile = ProjectDetector().detect(project)
    test_plan = TestPlanner().build(profile, journey)
    if max_cost is not None:
        test_plan.coverage_notes.append(
            f"Execution budget: stop gracefully when estimated direct-provider cost exceeds ${max_cost:.6f}."
        )
    render_plan_markdown(test_plan, output)
    print(test_plan.model_dump_json(indent=2))
    console.print(f"Plan written to {output}")


@app.command("verify-provider")
def verify_provider(
    provider: Annotated[str, typer.Option("--provider")] = "auto",
    model: Annotated[str | None, typer.Option("--model")] = None,
    agent_command: Annotated[str | None, typer.Option("--agent-command")] = None,
    decision_file: Annotated[Path | None, typer.Option("--decision-file")] = None,
    output: Annotated[Path, typer.Option("--output")] = Path("witness-provider-check"),
) -> None:
    """Make one schema-constrained vision decision and report provider health."""
    from .models import Confidence, Observation

    config = WitnessConfig()
    engine = _reasoner(config, output, provider, model, agent_command, decision_file)
    output.mkdir(parents=True, exist_ok=True)
    (output / "screenshots").mkdir(exist_ok=True)
    image_path = output / "screenshots" / "provider-check.png"
    image = Image.new("RGB", (640, 360), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 110, 560, 250), outline="black", width=4)
    draw.text((170, 165), "Witness provider vision check", fill="black")
    image.save(image_path)
    decision = engine.decide(
        profile=ProjectProfile(
            target="synthetic", project_type=ProjectType.GAME, confidence=Confidence.HIGH
        ),
        persona=Persona(
            name="Provider verifier",
            goal="Confirm that the centered test card is visible and finish.",
        ),
        adapter_name="game",
        allowed_actions=("goal_reached",),
        history=[],
        observation=Observation(
            adapter="game",
            summary="Synthetic provider verification image",
            screenshot_path="screenshots/provider-check.png",
        ),
        previous_action="initial_observation",
    )
    payload = {
        "ok": True,
        "provider": engine.provider_name,
        "model": engine.model,
        "decision": decision.model_dump(mode="json"),
        "usage": getattr(engine, "usage", None).model_dump(mode="json")
        if getattr(engine, "usage", None)
        else {},
    }
    atomic_write_json(output / "provider-check.json", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command()
def remediate(
    result: Annotated[Path, typer.Argument(help="Witness result.json containing findings.")],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("witness-remediation"),
    project_root: Annotated[Path | None, typer.Option("--project-root")] = None,
    patch: Annotated[
        Path | None,
        typer.Option("--patch", help="Trusted unified diff to apply in an isolated workspace."),
    ] = None,
    agent_command: Annotated[
        str | None,
        typer.Option(
            "--agent-command",
            help="Trusted fixer command; receives remediation JSON on stdin and edits the workspace.",
        ),
    ] = None,
    verify: Annotated[
        list[str] | None,
        typer.Option(
            "--verify", help="Repeatable verification command executed inside the fixed workspace."
        ),
    ] = None,
    apply: Annotated[
        bool, typer.Option("--apply", help="Copy verified changes back to the source project.")
    ] = False,
    timeout: Annotated[float, typer.Option("--timeout", min=1)] = 300,
) -> None:
    """Safely delegate fixes, preserve a patch, verify them, and optionally apply them."""
    from .remediation import RemediationRunner

    try:
        outcome = RemediationRunner(
            result_path=result,
            output_dir=output,
            project_root=project_root,
            timeout=timeout,
        ).run(
            patch_file=patch,
            agent_command=agent_command,
            verification_commands=verify,
            apply_to_source=apply,
        )
        print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
        console.print(
            f"[bold]Witness remediation:[/bold] {len(outcome.changed_files)} changed file(s); "
            f"verified={outcome.verified}; report={outcome.report_path}"
        )
    except (WitnessError, typer.BadParameter, ValueError) as exc:
        console.print(f"[bold red]Witness remediation error:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc


@app.command()
def replay(
    trace: Annotated[Path, typer.Argument(help="session_trace.json")],
    execute: Annotated[
        bool, typer.Option("--execute", help="Re-execute non-sensitive actions.")
    ] = False,
    output: Annotated[Path, typer.Option("--output")] = Path("witness-replay"),
) -> None:
    """Inspect or action-replay a deterministic Witness trace."""
    replay_data = TraceReplay(trace)
    if not execute:
        print(json.dumps(replay_data.summary(), ensure_ascii=False, indent=2))
        return
    data = replay_data.data
    profile = ProjectProfile.model_validate(data["result"]["profile"])
    adapter = create_adapter(profile.project_type, output, headless=True, sandbox="copy")
    handle = adapter.start(profile)
    records = []
    try:
        records.append({"initial": adapter.observe(handle).model_dump(mode="json")})
        for action in replay_data.actions():
            result = adapter.act(handle, action)
            observation = adapter.observe(handle)
            records.append(
                {
                    "action": action.model_dump(mode="json"),
                    "result": result.model_dump(mode="json"),
                    "observation": observation.model_dump(mode="json"),
                }
            )
    finally:
        adapter.stop(handle)
    output.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output / "replay.json", records)
    print(
        json.dumps(
            {
                "ok": True,
                "actions": len(records) - 1,
                "output": str((output / "replay.json").resolve()),
            },
            indent=2,
        )
    )


@app.command("post-github-comment")
def post_github_comment(
    result_path: Annotated[
        Path, typer.Argument(help="Witness result.json or campaign-result.json.")
    ],
    repository: Annotated[
        str | None,
        typer.Option("--repository", help="GitHub owner/name; defaults to GITHUB_REPOSITORY."),
    ] = None,
    pr_number: Annotated[
        int | None,
        typer.Option("--pr-number", min=1, help="Pull request number; defaults to PR_NUMBER."),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Print the comment without calling GitHub.")
    ] = False,
    api_url: Annotated[str, typer.Option("--api-url", hidden=True)] = "https://api.github.com",
) -> None:
    """Post an evidence-backed Witness summary to a GitHub pull request."""
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if not isinstance(result, dict):
            raise ValueError("result file must contain a JSON object")
        body = format_findings_as_pr_comment(result)
        if dry_run:
            print(body)
            return
        resolved_repository = repository or os.getenv("GITHUB_REPOSITORY", "")
        raw_pr = pr_number or int(os.getenv("PR_NUMBER", "0") or 0)
        payload = post_pr_comment(
            result=result,
            token=os.getenv("GITHUB_TOKEN", ""),
            repository=resolved_repository,
            pr_number=raw_pr,
            api_url=api_url,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        console.print(f"GitHub PR comment posted: {payload.get('html_url', 'created')}")
    except (OSError, ValueError, json.JSONDecodeError, WitnessError) as exc:
        console.print(f"[bold red]GitHub integration error:[/bold red] {exc}")
        raise typer.Exit(code=2) from exc


@app.command()
def compare(
    baseline: Annotated[Path, typer.Argument(help="Baseline result.json")],
    current: Annotated[Path, typer.Argument(help="Current result.json")],
) -> None:
    """Compare stable finding fingerprints between two runs."""
    before = json.loads(baseline.read_text(encoding="utf-8"))
    after = json.loads(current.read_text(encoding="utf-8"))
    before_map = {item["fingerprint"]: item for item in before.get("findings", [])}
    after_map = {item["fingerprint"]: item for item in after.get("findings", [])}
    payload = {
        "new": [after_map[key] for key in sorted(after_map.keys() - before_map.keys())],
        "resolved": [before_map[key] for key in sorted(before_map.keys() - after_map.keys())],
        "persistent": [after_map[key] for key in sorted(after_map.keys() & before_map.keys())],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command()
def benchmark(
    result: Annotated[Path, typer.Argument(help="Witness result.json")],
    ground_truth: Annotated[Path, typer.Argument(help="Ground-truth JSON")],
) -> None:
    """Score finding precision/recall against a benchmark case."""
    data = json.loads(result.read_text(encoding="utf-8"))
    findings = [
        __import__("witness_qa.models", fromlist=["Finding"]).Finding.model_validate(item)
        for item in data.get("findings", [])
    ]
    print(json.dumps(score_findings(findings, ground_truth).as_dict(), indent=2))


@app.command("personas")
def personas_command() -> None:
    """List built-in persona identifiers."""
    table = Table(title="Built-in Witness personas")
    table.add_column("Identifier")
    for name in built_in_persona_names():
        table.add_row(name)
    console.print(table)


@app.command("adapters")
def adapters_command() -> None:
    """List installed adapters and supported actions."""
    table = Table(title="Witness adapters")
    table.add_column("Type")
    table.add_column("Adapter")
    table.add_column("Actions")
    for project_type, adapter_class in REGISTRY.items():
        table.add_row(
            project_type.value, adapter_class.__name__, ", ".join(adapter_class.supported_actions)
        )
    console.print(table)


@app.command("install-engine-bridge")
def install_engine_bridge_command(
    engine: Annotated[str, typer.Argument(help="unity or unreal")],
    destination: Annotated[
        Path, typer.Argument(help="Unity Packages/com.witness.qa or Unreal Plugins/WitnessBridge")
    ],
    force: Annotated[
        bool, typer.Option("--force", help="Replace an existing bridge directory")
    ] = False,
) -> None:
    """Install a packaged native game-engine bridge without downloading extra code."""
    try:
        written = install_engine_bridge(engine, destination, force=force)
    except ConfigurationError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    console.print(
        f"Installed {engine.lower()} Witness bridge to {destination.resolve()} "
        f"({len(written)} files)."
    )
    console.print(f"Available bridges: {', '.join(available_engine_bridges())}")


@app.command("install-browser")
def install_browser(with_deps: Annotated[bool, typer.Option("--with-deps")] = False) -> None:
    """Install the Playwright Chromium browser used by WebAdapter."""
    command = [sys.executable, "-m", "playwright", "install"]
    if with_deps:
        command.append("--with-deps")
    command.append("chromium")
    completed = subprocess.run(command, check=False)
    if completed.returncode:
        raise typer.Exit(code=completed.returncode)


@app.command()
def doctor(
    json_output: Annotated[bool, typer.Option("--json")] = False,
    skill_path: Annotated[
        Path | None,
        typer.Option(
            "--skill-path",
            help="Override the Codex skill path checked by doctor.",
        ),
    ] = None,
    skip_browser: Annotated[
        bool,
        typer.Option(
            "--skip-browser",
            help="Skip launching Chromium (useful for CLI/API-only installations).",
        ),
    ] = False,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Exit 2 unless at least one supported reasoning mode is ready.",
        ),
    ] = False,
) -> None:
    """Check runtime, Codex OAuth, skill installation, browser, and provider modes."""
    checks: list[tuple[str, bool, str]] = []
    python_ok = sys.version_info >= (3, 11)
    checks.append(("Python >= 3.11", python_ok, sys.version.split()[0]))

    openai_ok = bool(os.getenv("OPENAI_API_KEY"))
    anthropic_ok = bool(os.getenv("ANTHROPIC_API_KEY"))
    command_ok = bool(os.getenv("WITNESS_AGENT_COMMAND"))
    checks.append(("OpenAI credential", openai_ok, "OPENAI_API_KEY"))
    checks.append(("Anthropic credential", anthropic_ok, "ANTHROPIC_API_KEY"))
    checks.append(("Host agent command", command_ok, "WITNESS_AGENT_COMMAND"))

    codex_path = shutil.which(os.getenv("WITNESS_CODEX_PATH", "codex"))
    checks.append(("Codex CLI", bool(codex_path), codex_path or "not found on PATH"))
    codex_login = False
    codex_login_detail = "Codex CLI not installed"
    if codex_path:
        try:
            completed = subprocess.run(
                [codex_path, "login", "status"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            codex_login = completed.returncode == 0
            codex_login_detail = (completed.stdout or completed.stderr).strip() or (
                "logged in" if codex_login else "run codex login"
            )
        except (OSError, subprocess.SubprocessError) as exc:
            codex_login_detail = str(exc)
    checks.append(("Codex ChatGPT login", codex_login, codex_login_detail))

    configured_skill = skill_path or (
        Path(os.environ["WITNESS_SKILL_PATH"])
        if os.getenv("WITNESS_SKILL_PATH")
        else Path.home() / ".agents" / "skills" / "witness" / "SKILL.md"
    )
    configured_skill = configured_skill.expanduser().resolve()
    skill_ok = configured_skill.is_file()
    checks.append(("Codex user skill", skill_ok, str(configured_skill)))

    browser_ok = False
    browser_detail = "check skipped"
    if not skip_browser:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                browser.close()
            browser_ok = True
            browser_detail = "launch succeeded"
        except Exception as exc:
            browser_detail = f"{exc} (run witness install-browser)"
        checks.append(("Playwright Chromium", browser_ok, browser_detail))

    target_runtime_ok = python_ok and (browser_ok or skip_browser)
    capabilities = {
        "native_codex_host": {
            "ready": target_runtime_ok and skill_ok,
            "requires_api_key": False,
            "detail": "Uses the current interactive Codex model; no nested process.",
        },
        "codex_cli_oauth": {
            "ready": target_runtime_ok and bool(codex_path) and codex_login,
            "requires_api_key": False,
            "detail": "Uses cached Sign in with ChatGPT credentials through codex exec.",
        },
        "direct_api": {
            "ready": target_runtime_ok and (openai_ok or anthropic_ok),
            "requires_api_key": True,
            "detail": "OpenAI or Anthropic direct provider.",
        },
        "host_command": {
            "ready": target_runtime_ok and command_ok,
            "requires_api_key": False,
            "detail": "Trusted local/enterprise command provider.",
        },
    }
    ready = any(value["ready"] for value in capabilities.values())
    payload = {
        "version": __version__,
        "ready": ready,
        "browser_check_skipped": skip_browser,
        "checks": [{"name": name, "ok": ok, "detail": detail} for name, ok, detail in checks],
        "capabilities": capabilities,
    }
    if json_output:
        print(json.dumps(payload, indent=2))
    else:
        table = Table(title=f"Witness {__version__} doctor")
        table.add_column("Check")
        table.add_column("Status")
        table.add_column("Detail")
        for name, ok, detail in checks:
            table.add_row(name, "OK" if ok else "MISSING", detail)
        console.print(table)
        for name, value in capabilities.items():
            console.print(f"{name}: {'READY' if value['ready'] else 'not ready'}")
        if not ready:
            console.print(
                "[yellow]Inside Codex, install the user skill and use `witness session start`. "
                "For unattended runs, run `codex login` and select --provider codex-cli.[/yellow]"
            )
    if strict and not ready:
        raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
