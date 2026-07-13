# Graph Report - Witness-v1.2.0  (2026-07-13)

## Corpus Check
- 202 files · ~111,547 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1273 nodes · 2820 edges · 120 communities (99 shown, 21 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 342 edges (avg confidence: 0.63)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c35a1daf`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- AdapterError
- WitnessError
- ConfigurationError
- remediation.py
- WebAdapter
- WitnessBridge
- ProjectDetector
- Handler
- format_findings_as_pr_comment
- Witness
- observation.py
- ProjectProfile
- Adapter
- help
- cli.py
- .start
- Platform validation boundary
- APIAdapter
- Path
- properties
- test_cli_commands.py
- properties
- Codex integration
- TestPlanner
- CLIAdapter
- witness-game.schema.json
- package.json
- package.json
- type
- frames
- Handler
- enum
- Handler
- WitnessBridgeSubsystem.cpp
- WitnessBridgeSubsystem.cpp
- WitnessBridge
- conftest.py
- test_cli_surface.py
- run
- test_engine_distribution.py
- witness.sarif.json
- witness.sarif.json
- witness.sarif.json
- witness.sarif.json
- witness.sarif.json
- witness.sarif.json
- bridge_timeout
- FakeClient
- startup_wait
- test_readme_demo_is_real_and_animated
- bootstrap.sh script
- run-witness.sh script
- WitnessBridgeSubsystem.h
- install-codex.sh script
- witness-codex
- run-witness.sh
- bootstrap.sh script
- run-witness.sh script
- WitnessBridgeSubsystem.h
- witness-qa
- Engine guidance
- Host model protocol
- load_persona
- test_web_adapter_unit.py
- High-value contributions
- README.md
- Architecture
- Skill interface
- score_findings
- Witness QA Report
- cli.py
- Witness QA
- Witness QA
- Adapters
- Witness QA
- Witness QA
- Any
- Witness QA Report
- Persona System
- Reporting
- Roadmap
- Witness QA Report
- Witness QA Report
- Witness QA Report
- Witness QA Report
- Unity and Unreal Engine bridges
- Observation and Reasoning Engine
- FakeProcess
- Witness Remediation Report
- Native Codex host mode
- Changelog
- Security Policy
- Native Codex host mode
- main_callback
- Flutter mobile testing
- Project Detection
- Witness repository guidance for Codex
- start
- CODEX_CLI_MODE.md
- README.md
- README.md
- README.md
- README.md
- CODEX_CLI_MODE.md
- shell_join
- README.md

## God Nodes (most connected - your core abstractions)
1. `ProjectProfile` - 84 edges
2. `ConfigurationError` - 58 edges
3. `AdapterAction` - 43 edges
4. `ProjectDetector` - 41 edges
5. `AdapterError` - 41 edges
6. `Observation` - 41 edges
7. `Persona` - 37 edges
8. `WitnessError` - 35 edges
9. `HostSessionClient` - 33 edges
10. `Adapter` - 30 edges

## Surprising Connections (you probably didn't know these)
- `CostlyReasoner` --uses--> `CLIAdapter`  [INFERRED]
  tests/test_campaign.py → src/witness_qa/adapters/cli.py
- `DoneReasoner` --uses--> `CLIAdapter`  [INFERRED]
  tests/test_campaign.py → src/witness_qa/adapters/cli.py
- `DeterministicReasoner` --uses--> `CLIAdapter`  [INFERRED]
  tests/test_orchestrator.py → src/witness_qa/adapters/cli.py
- `FakeProcess` --uses--> `ElectronAdapter`  [INFERRED]
  tests/test_electron_adapter.py → src/witness_qa/adapters/electron.py
- `test_default_config_round_trip()` --calls--> `load_config()`  [INFERRED]
  tests/test_config.py → src/witness_qa/config.py

## Import Cycles
- None detected.

## Communities (120 total, 21 thin omitted)

### Community 0 - "AdapterError"
Cohesion: 0.06
Nodes (21): GameAdapter, GameSession, Any, Path, Visual QA adapter for browser-exported or desktop games.      It supports three, MobileAdapter, MobileSession, Any (+13 more)

### Community 1 - "WitnessError"
Cohesion: 0.09
Nodes (29): Exception, create_adapter(), Any, Path, Base exception for expected Witness failures., WitnessError, HostSessionClient, HostSessionRuntime (+21 more)

### Community 2 - "ConfigurationError"
Cohesion: 0.06
Nodes (39): Protocol, ConfigModel, find_config(), ProjectConfig, ProviderConfig, BaseModel, Path, ReportingConfig (+31 more)

### Community 3 - "remediation.py"
Cohesion: 0.14
Nodes (22): _copy_project(), _diff_trees(), _files(), _finding_payload(), _is_ignored(), _load_result(), Any, Path (+14 more)

### Community 4 - "WebAdapter"
Cohesion: 0.16
Nodes (11): Dialog, Download, Locator, Page, Request, Route, Any, Popen (+3 more)

### Community 5 - "WitnessBridge"
Cohesion: 0.09
Nodes (23): WitnessQA, bool, DateTime, float, IEnumerator, int, string, WitnessAck (+15 more)

### Community 6 - "ProjectDetector"
Cohesion: 0.14
Nodes (21): ProjectDetector, Path, README-first, weighted detector for web, mobile, Electron, CLI, API, and game ta, DetectionError, The target could not be inspected or profiled., DetectionCandidate, DetectionSignal, Path (+13 more)

### Community 7 - "Handler"
Cohesion: 0.13
Nodes (21): HTTPServer, Handler, main(), _private_write_json(), Any, BaseHTTPRequestHandler, Path, SessionHTTPServer (+13 more)

### Community 8 - "format_findings_as_pr_comment"
Cohesion: 0.14
Nodes (17): _evidence_link(), format_findings_as_pr_comment(), post_pr_comment(), Any, Post a Witness result as a GitHub pull-request issue comment., Render a bounded, evidence-first PR comment from Witness result JSON., _text(), Optional delivery integrations for Witness reports. (+9 more)

### Community 9 - "Witness"
Cohesion: 0.06
Nodes (32): 1. Native Codex host mode — default inside Codex, 2. Codex CLI OAuth provider — unattended/headless, API QA, Architecture, Browser games, CLI QA, Codex without an API key, Configuration (+24 more)

### Community 10 - "observation.py"
Cohesion: 0.22
Nodes (18): Image, VisualMetrics, _alignment_warnings(), analyze_image(), _average_hash(), _blank_ratio(), _border_warnings(), _contrast_warnings() (+10 more)

### Community 11 - "ProjectProfile"
Cohesion: 0.05
Nodes (76): CampaignRunner, Path, _slug(), The configured LLM provider failed or returned unusable output., ReasoningError, AdapterAction, CampaignResult, Confidence (+68 more)

### Community 12 - "Adapter"
Cohesion: 0.24
Nodes (15): Adapter, ABC, Perform one atomic action., ActionKind, ActionResult, compare_observations(), atomic_write_json(), atomic_write_text() (+7 more)

### Community 13 - "help"
Cohesion: 0.13
Nodes (21): Argument, help, hidden, min, benchmark(), compare(), detect(), install_engine_bridge_command() (+13 more)

### Community 14 - "cli.py"
Cohesion: 0.20
Nodes (19): max, _adapter_options(), adapters_command(), _apply_config(), Any, Run one session or a multi-persona/journey campaign., Start a persistent adapter session controlled by the current host model., List installed adapters and supported actions. (+11 more)

### Community 15 - ".start"
Cohesion: 0.31
Nodes (6): ElectronAdapter, Any, Path, Popen, Drive Electron renderer windows through Chromium's DevTools Protocol.      Witne, sync_playwright()

### Community 16 - "Platform validation boundary"
Cohesion: 0.10
Nodes (17): Codex CLI OAuth provider contract, Codex OAuth integration verification, Installer verification, Native Codex host protocol, Automated verification, Codex OAuth, Delivered changes, Electron (+9 more)

### Community 17 - "APIAdapter"
Cohesion: 0.25
Nodes (6): Client, APIAdapter, APISession, Any, Path, Popen

### Community 18 - "Path"
Cohesion: 0.16
Nodes (17): Option, doctor(), init(), install_browser(), Path, Return the current observation, visual artifact paths, prompt, and decision sche, Show active turn count or the final report metadata., Finalize an active native session and write its reports. (+9 more)

### Community 19 - "properties"
Cohesion: 0.17
Nodes (12): type, minimum, type, type, type, properties, bridge_dir, capture (+4 more)

### Community 20 - "test_cli_commands.py"
Cohesion: 0.36
Nodes (11): _decision(), MonkeyPatch, Path, test_compare_benchmark_and_replay_commands(), test_detect_plan_init_personas_and_adapters_commands(), test_plan_and_run_accept_cost_budget(), test_remediate_command_delegates_and_handles_errors(), test_run_happy_path_and_invalid_adapter() (+3 more)

### Community 21 - "properties"
Cohesion: 0.18
Nodes (11): additionalProperties, properties, type, type, bridge, directory, timeout, type (+3 more)

### Community 22 - "Codex integration"
Cohesion: 0.14
Nodes (14): Browser is missing, Choosing a mode, `codex-cli` says not signed in, Codex integration, Configuration, Distribution surfaces, Installation prompt for Codex, Installer is not on PATH (+6 more)

### Community 23 - "TestPlanner"
Cohesion: 0.28
Nodes (9): plan(), Generate an inspectable test-journey plan without running the product., TestJourney, TestPlan, Path, render_plan_markdown(), TestPlanner, test_game_plan_includes_visual_journeys() (+1 more)

### Community 24 - "CLIAdapter"
Cohesion: 0.34
Nodes (4): CLIAdapter, CLISession, Path, strip_ansi()

### Community 25 - "witness-game.schema.json"
Cohesion: 0.22
Nodes (8): additionalProperties, $id, required, $schema, title, type, engine, version

### Community 26 - "package.json"
Cohesion: 0.25
Nodes (7): author, name, description, displayName, name, unity, version

### Community 27 - "package.json"
Cohesion: 0.25
Nodes (7): author, name, description, displayName, name, unity, version

### Community 28 - "type"
Cohesion: 0.29
Nodes (7): type, additionalProperties, type, environment, boolean, number, string

### Community 29 - "frames"
Cohesion: 0.29
Nodes (7): items, type, type, frames, references, items, type

### Community 31 - "enum"
Cohesion: 0.33
Nodes (6): enum, engine, custom, godot, unity, unreal

### Community 32 - "Handler"
Cohesion: 0.40
Nodes (3): Handler, main(), SimpleHTTPRequestHandler

### Community 33 - "WitnessBridgeSubsystem.cpp"
Cohesion: 0.33
Nodes (4): FString, FSubsystemCollectionBase, UWitnessBridgeSubsystem::Initialize(), UWitnessBridgeSubsystem::WriteAck()

### Community 34 - "WitnessBridgeSubsystem.cpp"
Cohesion: 0.33
Nodes (4): FString, FSubsystemCollectionBase, UWitnessBridgeSubsystem::Initialize(), UWitnessBridgeSubsystem::WriteAck()

### Community 35 - "WitnessBridge"
Cohesion: 0.40
Nodes (3): WitnessBridge, ModuleRules, WitnessBridge

### Community 36 - "conftest.py"
Cohesion: 0.50
Nodes (3): Path, repo_root(), sample_server()

### Community 38 - "run"
Cohesion: 0.67
Nodes (3): CompletedProcess, main(), run()

### Community 39 - "test_engine_distribution.py"
Cohesion: 0.67
Nodes (3): Path, test_packaged_engine_resources_match_repository_templates(), test_unity_and_unreal_bridge_templates_are_distributed()

### Community 40 - "witness.sarif.json"
Cohesion: 0.50
Nodes (3): runs, $schema, version

### Community 41 - "witness.sarif.json"
Cohesion: 0.50
Nodes (3): runs, $schema, version

### Community 42 - "witness.sarif.json"
Cohesion: 0.50
Nodes (3): runs, $schema, version

### Community 43 - "witness.sarif.json"
Cohesion: 0.50
Nodes (3): runs, $schema, version

### Community 44 - "witness.sarif.json"
Cohesion: 0.50
Nodes (3): runs, $schema, version

### Community 45 - "witness.sarif.json"
Cohesion: 0.50
Nodes (3): runs, $schema, version

### Community 46 - "bridge_timeout"
Cohesion: 0.67
Nodes (3): minimum, type, bridge_timeout

### Community 47 - "FakeClient"
Cohesion: 0.29
Nodes (7): FakeClient, FakeResponse, Any, Path, test_anthropic_provider_sends_vision_and_forced_strict_tool(), test_openai_provider_sends_vision_and_strict_schema(), test_provider_tracks_configured_cost_and_uses_bounded_output()

### Community 48 - "startup_wait"
Cohesion: 0.67
Nodes (3): startup_wait, minimum, type

### Community 74 - "Engine guidance"
Cohesion: 0.15
Nodes (12): Custom engines, Engine guidance, Fix and verification loop, Game and Visual QA, Godot, Reference regression, Running builds, Screenshot review (+4 more)

### Community 75 - "Host model protocol"
Cohesion: 0.17
Nodes (10): Codex CLI OAuth provider, Generic command-provider protocol, Host model protocol, Native interactive host protocol, Remediation agent protocol, Applying changes, Evidence-to-Fix Remediation, Game/visual repair loop (+2 more)

### Community 76 - "load_persona"
Cohesion: 0.24
Nodes (10): personas_command(), List built-in persona identifiers., built_in_persona_names(), load_persona(), _load_persona_path(), Path, Path, test_builtin_persona_loads() (+2 more)

### Community 77 - "test_web_adapter_unit.py"
Cohesion: 0.42
Nodes (11): _profile(), MonkeyPatch, Path, _session(), test_act_returns_structured_failure_for_invalid_actions(), test_act_supports_browser_action_contract(), test_event_capture_navigation_guard_and_stop(), test_locator_resolution_and_recovery() (+3 more)

### Community 78 - "High-value contributions"
Cohesion: 0.18
Nodes (10): Add a persona, Add an adapter, Codex integration changes, Contributing to Witness, Core principles, Development setup, High-value contributions, Improve game/visual QA (+2 more)

### Community 79 - "README.md"
Cohesion: 0.20
Nodes (4): Electron desktop testing, Security and determinism, GitHub Actions example, GitHub pull-request comments

### Community 80 - "Architecture"
Cohesion: 0.18
Nodes (11): Adapter boundary, Architecture, Controller / reasoning separation, Core components, Discovery / remediation separation, Failure classes, Load-bearing boundaries, Observation / judgment separation (+3 more)

### Community 81 - "Skill interface"
Cohesion: 0.18
Nodes (9): Codex native invocation, Codex unattended invocation, Core invocation, Fix delegation, Host responsibilities, Installation surfaces, Keyless integration surfaces, Machine outputs (+1 more)

### Community 82 - "score_findings"
Cohesion: 0.24
Nodes (6): BenchmarkScore, Path, score_findings(), _finding(), Path, test_benchmark_matches_full_finding_evidence_and_alternatives()

### Community 83 - "Witness QA Report"
Cohesion: 0.18
Nodes (10): 1. [HIGH] The right SHIELDS panel continues beyond the right frame edge and its label is rendered in very low-contrast gray, while the left SCORE panel is fully visible and bright., 2. [HIGH] A bright magenta rectangle and the text 'STALE DEBUG BOUNDS' remain over the central gameplay object in the final frame., 3. [MEDIUM] The SCORE panel shifts downward relative to the previous frame, and the MISSION READY panel shifts left and downward while the center object and SHIELDS panel remain stable., Detection Evidence, Findings, Full Narrative Trace, Persona, Session Metadata (+2 more)

### Community 84 - "cli.py"
Cohesion: 0.40
Nodes (6): changed_files(), create_workspace(), Path, Safety helpers for targets, commands, and isolated workspaces.  The command deny, SandboxWorkspace, snapshot_tree()

### Community 85 - "Witness QA"
Cohesion: 0.22
Nodes (8): Cost and token discipline, Ensure installation, Native host mode — default inside Codex or Claude Code, Reporting and GitHub, Safety and quality rules, Target-specific rules, Unattended Codex OAuth mode, Witness QA

### Community 86 - "Witness QA"
Cohesion: 0.22
Nodes (8): Cost and token discipline, Ensure installation, Native host mode — default inside Codex or Claude Code, Reporting and GitHub, Safety and quality rules, Target-specific rules, Unattended Codex OAuth mode, Witness QA

### Community 87 - "Adapters"
Cohesion: 0.22
Nodes (9): Adapters, APIAdapter, CLIAdapter, ElectronAdapter, GameAdapter, MobileAdapter, Natural-language actions, Registry (+1 more)

### Community 88 - "Witness QA"
Cohesion: 0.22
Nodes (8): Cost and token discipline, Ensure installation, Native host mode — default inside Codex or Claude Code, Reporting and GitHub, Safety and quality rules, Target-specific rules, Unattended Codex OAuth mode, Witness QA

### Community 89 - "Witness QA"
Cohesion: 0.22
Nodes (8): Cost and token discipline, Ensure installation, Native host mode — default inside Codex or Claude Code, Reporting and GitHub, Safety and quality rules, Target-specific rules, Unattended Codex OAuth mode, Witness QA

### Community 90 - "Any"
Cohesion: 0.22
Nodes (5): Any, Path, Boot or connect to the target and return an adapter-owned session handle., Capture the externally observable state., Tear down only resources created by this adapter.

### Community 91 - "Witness QA Report"
Cohesion: 0.22
Nodes (8): 1. [HIGH] A visible error says 'Unable to create account. Please try again later.' and the user remains on the signup form., Detection Evidence, Findings, Full Narrative Trace, Persona, Session Metadata, Summary, Witness QA Report

### Community 92 - "Persona System"
Cohesion: 0.25
Nodes (7): Multiple Personas, One Project, Persona System, Purpose, Scoping a Persona to a Project, Suggested Built-In Persona Library, Suggested Persona Shape, Why Personas Instead of Test Scripts

### Community 93 - "Reporting"
Cohesion: 0.25
Nodes (7): Artifacts, CI behavior, Finding contract, Redaction, Remediation artifacts, Reporting, Reproducibility metadata

### Community 94 - "Roadmap"
Cohesion: 0.25
Nodes (7): Completed in v1.0 — product-grade Phase 1, Completed in v1.1 — Codex-native distribution and OAuth execution, Completed in v1.2 — hardening, budgets, Electron, and engine bridges, Deliberate safety boundaries, Next — platform breadth, Next — trust and optimization, Roadmap

### Community 95 - "Witness QA Report"
Cohesion: 0.25
Nodes (7): Detection Evidence, Findings, Full Narrative Trace, Persona, Session Metadata, Summary, Witness QA Report

### Community 96 - "Witness QA Report"
Cohesion: 0.25
Nodes (7): Detection Evidence, Findings, Full Narrative Trace, Persona, Session Metadata, Summary, Witness QA Report

### Community 97 - "Witness QA Report"
Cohesion: 0.25
Nodes (7): Detection Evidence, Findings, Full Narrative Trace, Persona, Session Metadata, Summary, Witness QA Report

### Community 98 - "Witness QA Report"
Cohesion: 0.25
Nodes (7): Detection Evidence, Findings, Full Narrative Trace, Persona, Session Metadata, Summary, Witness QA Report

### Community 99 - "Unity and Unreal Engine bridges"
Cohesion: 0.29
Nodes (7): Bridge security, Command-template fallback, Install the packaged bridges, Manifest, Unity, Unity and Unreal Engine bridges, Unreal Engine

### Community 100 - "Observation and Reasoning Engine"
Cohesion: 0.29
Nodes (6): Observation and Reasoning Engine, Observation deltas, Observation envelope, Providers, Strict decision contract, Visual analysis

### Community 101 - "FakeProcess"
Cohesion: 0.38
Nodes (5): FakeProcess, MonkeyPatch, Path, test_electron_adapter_connects_to_renderer_over_cdp(), test_electron_launch_command_handles_package_runners()

### Community 102 - "Witness Remediation Report"
Cohesion: 0.29
Nodes (6): Changed files, PASS — `python generate_frames.py`, PASS — `python verify_frames.py`, Safety model, Verification, Witness Remediation Report

### Community 103 - "Native Codex host mode"
Cohesion: 0.33
Nodes (5): Native Codex host mode, One-turn discipline, Recover and close, Start, Why this is the default in Codex

### Community 104 - "Changelog"
Cohesion: 0.33
Nodes (5): 0.1.0, 1.0.0 — 2026-07-11, 1.1.0 — 2026-07-12, 1.2.0 — 2026-07-12, Changelog

### Community 105 - "Security Policy"
Cohesion: 0.33
Nodes (5): Codex authentication and native sessions, Electron and native game bridges, Execution model, Reporting a vulnerability, Security Policy

### Community 106 - "Native Codex host mode"
Cohesion: 0.33
Nodes (5): Native Codex host mode, One-turn discipline, Recover and close, Start, Why this is the default in Codex

### Community 107 - "main_callback"
Cohesion: 0.40
Nodes (5): callback, is_eager, main_callback(), Evidence-backed agentic QA., _version_callback()

### Community 108 - "Flutter mobile testing"
Cohesion: 0.40
Nodes (5): Example, Flutter mobile testing, Minimal configuration, Notes, Supported flow

### Community 109 - "Project Detection"
Cohesion: 0.40
Nodes (4): Configuration, Project Detection, Signals, Supported profiles

### Community 110 - "Witness repository guidance for Codex"
Cohesion: 0.50
Nodes (3): When the user asks to install this repository, When using Witness, Witness repository guidance for Codex

### Community 111 - "start"
Cohesion: 0.67
Nodes (3): start, minLength, type

## Knowledge Gaps
- **301 isolated node(s):** `bootstrap.sh script`, `run-witness.sh script`, `$schema`, `$id`, `title` (+296 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **21 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ProjectProfile` connect `ProjectProfile` to `AdapterError`, `WitnessError`, `ConfigurationError`, `remediation.py`, `WebAdapter`, `FakeProcess`, `ProjectDetector`, `Adapter`, `test_web_adapter_unit.py`, `cli.py`, `.start`, `APIAdapter`, `Path`, `cli.py`, `TestPlanner`, `Any`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **Why does `ConfigurationError` connect `ConfigurationError` to `AdapterError`, `WitnessError`, `remediation.py`, `format_findings_as_pr_comment`, `ProjectProfile`, `Adapter`, `load_persona`, `cli.py`, `cli.py`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Why does `Observation` connect `ProjectProfile` to `AdapterError`, `WitnessError`, `ConfigurationError`, `WebAdapter`, `observation.py`, `Adapter`, `cli.py`, `APIAdapter`, `Path`, `cli.py`, `CLIAdapter`, `Any`?**
  _High betweenness centrality (0.024) - this node is a cross-community bridge._
- **Are the 40 inferred relationships involving `ProjectProfile` (e.g. with `CampaignRunner` and `ProjectDetector`) actually correct?**
  _`ProjectProfile` has 40 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `ConfigurationError` (e.g. with `ConfigModel` and `ProjectConfig`) actually correct?**
  _`ConfigurationError` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `AdapterAction` (e.g. with `HostSessionClient` and `HostSessionRuntime`) actually correct?**
  _`AdapterAction` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `ProjectDetector` (e.g. with `DetectionError` and `Confidence`) actually correct?**
  _`ProjectDetector` has 19 INFERRED edges - model-reasoned connections that need verification._