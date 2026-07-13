# Graph Report - Witness-v1.2.0  (2026-07-13)

## Corpus Check
- 187 files · ~104,101 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1104 nodes · 2703 edges · 94 communities (75 shown, 19 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 372 edges (avg confidence: 0.64)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3c2d7ad6`
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
- test_web_adapter_unit.py
- test_codex_cli_prompt_matches_changed_image_gating
- CLIAdapter
- package.json
- package.json
- Handler
- Handler
- WitnessBridgeSubsystem.cpp
- WitnessBridgeSubsystem.cpp
- WitnessBridge
- conftest.py
- run
- test_engine_distribution.py
- witness.sarif.json
- witness.sarif.json
- witness.sarif.json
- witness.sarif.json
- witness.sarif.json
- witness.sarif.json
- FakeClient
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
- High-value contributions
- score_findings
- Witness QA Report
- cli.py
- Witness QA
- Witness QA
- Witness QA
- Witness QA
- Any
- Witness QA Report
- Roadmap
- Witness QA Report
- Witness QA Report
- Witness QA Report
- Witness QA Report
- Witness Remediation Report
- Native Codex host mode
- Changelog
- Native Codex host mode
- Witness repository guidance for Codex
- CODEX_CLI_MODE.md
- README.md
- README.md
- README.md
- README.md
- CODEX_CLI_MODE.md
- README.md

## God Nodes (most connected - your core abstractions)
1. `ProjectProfile` - 94 edges
2. `ConfigurationError` - 58 edges
3. `Observation` - 44 edges
4. `AdapterAction` - 43 edges
5. `ProjectDetector` - 42 edges
6. `AdapterError` - 41 edges
7. `Persona` - 38 edges
8. `WitnessError` - 35 edges
9. `HostSessionClient` - 33 edges
10. `Adapter` - 30 edges

## Surprising Connections (you probably didn't know these)
- `test_api_adapter_discovers_openapi_and_sends_request()` --calls--> `APIAdapter`  [INFERRED]
  tests/test_api_adapter.py → src/witness_qa/adapters/api.py
- `CostlyReasoner` --uses--> `CLIAdapter`  [INFERRED]
  tests/test_campaign.py → src/witness_qa/adapters/cli.py
- `DoneReasoner` --uses--> `CLIAdapter`  [INFERRED]
  tests/test_campaign.py → src/witness_qa/adapters/cli.py
- `test_campaign_runs_multiple_personas()` --calls--> `CLIAdapter`  [INFERRED]
  tests/test_campaign.py → src/witness_qa/adapters/cli.py
- `test_campaign_stops_and_preserves_results_when_budget_is_exceeded()` --calls--> `CLIAdapter`  [INFERRED]
  tests/test_campaign.py → src/witness_qa/adapters/cli.py

## Import Cycles
- None detected.

## Communities (94 total, 19 thin omitted)

### Community 0 - "AdapterError"
Cohesion: 0.09
Nodes (9): MobileAdapter, MobileSession, Any, Drive Android and iOS apps through Appium with real-device style interactions., FakeDriver, FakeElement, Path, test_mobile_adapter_builds_capabilities_and_observes() (+1 more)

### Community 1 - "WitnessError"
Cohesion: 0.06
Nodes (52): Exception, HTTPServer, Finalize an active native session and write its reports., session_finish(), The configured LLM provider failed or returned unusable output., Base exception for expected Witness failures., ReasoningError, WitnessError (+44 more)

### Community 2 - "ConfigurationError"
Cohesion: 0.22
Nodes (11): Protocol, _copy_tree(), install_engine_bridge(), Path, Atomically install a packaged Unity or Unreal bridge into ``destination``., _remove_path(), Traversable, Path (+3 more)

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
Cohesion: 0.13
Nodes (22): ProjectDetector, Path, README-first, weighted detector for web, mobile, Electron, CLI, API, and game ta, DetectionError, The target could not be inspected or profiled., DetectionCandidate, DetectionSignal, Path (+14 more)

### Community 7 - "Handler"
Cohesion: 0.17
Nodes (13): Path, Observation, Persona, ReasoningDecision, SessionStep, Judge the current observation and choose one next action or stopping condition., PromptBuilder, Build compact, delta-first prompts for multimodal QA turns.      The full eviden (+5 more)

### Community 8 - "format_findings_as_pr_comment"
Cohesion: 0.14
Nodes (17): _evidence_link(), format_findings_as_pr_comment(), post_pr_comment(), Any, Post a Witness result as a GitHub pull-request issue comment., Render a bounded, evidence-first PR comment from Witness result JSON., _text(), Optional delivery integrations for Witness reports. (+9 more)

### Community 9 - "Witness"
Cohesion: 0.05
Nodes (37): 1. Native Codex host mode — default inside Codex, 2. Codex CLI OAuth provider — unattended/headless, API QA, Architecture, Browser games, CLI QA, Codex without an API key, Configuration (+29 more)

### Community 10 - "observation.py"
Cohesion: 0.23
Nodes (17): Image, ObservationDelta, VisualMetrics, _alignment_warnings(), analyze_image(), _average_hash(), _blank_ratio(), _border_warnings() (+9 more)

### Community 11 - "ProjectProfile"
Cohesion: 0.16
Nodes (18): CampaignRunner, _slug(), CampaignResult, Finding, BaseModel, SessionMetadata, SessionResult, StrictModel (+10 more)

### Community 12 - "Adapter"
Cohesion: 0.19
Nodes (18): APISession, Adapter, ABC, ActionResult, compare_observations(), dom_visual_heuristics(), Any, atomic_write_json() (+10 more)

### Community 13 - "help"
Cohesion: 0.05
Nodes (76): Argument, callback, help, hidden, is_eager, max, min, Option (+68 more)

### Community 14 - "cli.py"
Cohesion: 0.17
Nodes (19): ActionKind, Confidence, Judgment, ProjectType, Severity, StrEnum, CostlyReasoner, DoneReasoner (+11 more)

### Community 15 - ".start"
Cohesion: 0.31
Nodes (6): ElectronAdapter, Any, Path, Popen, Drive Electron renderer windows through Chromium's DevTools Protocol.      Witne, sync_playwright()

### Community 16 - "Platform validation boundary"
Cohesion: 0.10
Nodes (17): Codex CLI OAuth provider contract, Codex OAuth integration verification, Installer verification, Native Codex host protocol, Automated verification, Codex OAuth, Delivered changes, Electron (+9 more)

### Community 17 - "APIAdapter"
Cohesion: 0.28
Nodes (5): Client, APIAdapter, Any, Path, Popen

### Community 18 - "Path"
Cohesion: 0.20
Nodes (9): GameAdapter, GameSession, Any, Path, Visual QA adapter for browser-exported or desktop games.      It supports three, AdapterError, An adapter could not operate the target infrastructure., Quote one argument for the current platform shell. (+1 more)

### Community 19 - "properties"
Cohesion: 0.15
Nodes (8): AdapterAction, Path, test_api_adapter_discovers_openapi_and_sends_request(), Path, test_cli_adapter_blocks_privileged_command(), test_cli_adapter_runs_real_command(), Path, test_web_adapter_captures_and_interacts()

### Community 20 - "test_cli_commands.py"
Cohesion: 0.36
Nodes (11): _decision(), MonkeyPatch, Path, test_compare_benchmark_and_replay_commands(), test_detect_plan_init_personas_and_adapters_commands(), test_plan_and_run_accept_cost_budget(), test_remediate_command_delegates_and_handles_errors(), test_run_happy_path_and_invalid_adapter() (+3 more)

### Community 21 - "properties"
Cohesion: 0.18
Nodes (17): ProjectProfile, TestJourney, TestPlan, Path, render_plan_markdown(), TestPlanner, Path, test_command_provider_uses_local_host_model_protocol() (+9 more)

### Community 22 - "test_web_adapter_unit.py"
Cohesion: 0.42
Nodes (11): _profile(), MonkeyPatch, Path, _session(), test_act_returns_structured_failure_for_invalid_actions(), test_act_supports_browser_action_contract(), test_event_capture_navigation_guard_and_stop(), test_locator_resolution_and_recovery() (+3 more)

### Community 23 - "test_codex_cli_prompt_matches_changed_image_gating"
Cohesion: 0.67
Nodes (5): _decision(), Path, test_codex_cli_prompt_matches_changed_image_gating(), test_codex_cli_provider_reuses_login_and_passes_image_and_schema(), test_codex_cli_provider_supports_relative_output_directory()

### Community 24 - "CLIAdapter"
Cohesion: 0.36
Nodes (3): CLIAdapter, CLISession, Path

### Community 26 - "package.json"
Cohesion: 0.25
Nodes (7): author, name, description, displayName, name, unity, version

### Community 27 - "package.json"
Cohesion: 0.25
Nodes (7): author, name, description, displayName, name, unity, version

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

### Community 47 - "FakeClient"
Cohesion: 0.06
Nodes (42): ConfigModel, find_config(), ProjectConfig, ProviderConfig, BaseModel, Path, ReportingConfig, SafetyConfig (+34 more)

### Community 78 - "High-value contributions"
Cohesion: 0.18
Nodes (10): Add a persona, Add an adapter, Codex integration changes, Contributing to Witness, Core principles, Development setup, High-value contributions, Improve game/visual QA (+2 more)

### Community 82 - "score_findings"
Cohesion: 0.24
Nodes (6): BenchmarkScore, Path, score_findings(), _finding(), Path, test_benchmark_matches_full_finding_evidence_and_alternatives()

### Community 83 - "Witness QA Report"
Cohesion: 0.18
Nodes (10): 1. [HIGH] The right SHIELDS panel continues beyond the right frame edge and its label is rendered in very low-contrast gray, while the left SCORE panel is fully visible and bright., 2. [HIGH] A bright magenta rectangle and the text 'STALE DEBUG BOUNDS' remain over the central gameplay object in the final frame., 3. [MEDIUM] The SCORE panel shifts downward relative to the previous frame, and the MISSION READY panel shifts left and downward while the center object and SHIELDS panel remain stable., Detection Evidence, Findings, Full Narrative Trace, Persona, Session Metadata (+2 more)

### Community 84 - "cli.py"
Cohesion: 0.21
Nodes (13): changed_files(), create_workspace(), Path, Safety helpers for targets, commands, and isolated workspaces.  The command deny, SandboxWorkspace, snapshot_tree(), validate_command(), strip_ansi() (+5 more)

### Community 85 - "Witness QA"
Cohesion: 0.22
Nodes (8): Cost and token discipline, Ensure installation, Native host mode — default inside Codex or Claude Code, Reporting and GitHub, Safety and quality rules, Target-specific rules, Unattended Codex OAuth mode, Witness QA

### Community 86 - "Witness QA"
Cohesion: 0.22
Nodes (8): Cost and token discipline, Ensure installation, Native host mode — default inside Codex or Claude Code, Reporting and GitHub, Safety and quality rules, Target-specific rules, Unattended Codex OAuth mode, Witness QA

### Community 88 - "Witness QA"
Cohesion: 0.22
Nodes (8): Cost and token discipline, Ensure installation, Native host mode — default inside Codex or Claude Code, Reporting and GitHub, Safety and quality rules, Target-specific rules, Unattended Codex OAuth mode, Witness QA

### Community 89 - "Witness QA"
Cohesion: 0.22
Nodes (8): Cost and token discipline, Ensure installation, Native host mode — default inside Codex or Claude Code, Reporting and GitHub, Safety and quality rules, Target-specific rules, Unattended Codex OAuth mode, Witness QA

### Community 90 - "Any"
Cohesion: 0.18
Nodes (6): Any, Path, Boot or connect to the target and return an adapter-owned session handle., Perform one atomic action., Capture the externally observable state., Tear down only resources created by this adapter.

### Community 91 - "Witness QA Report"
Cohesion: 0.22
Nodes (8): 1. [HIGH] A visible error says 'Unable to create account. Please try again later.' and the user remains on the signup form., Detection Evidence, Findings, Full Narrative Trace, Persona, Session Metadata, Summary, Witness QA Report

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

### Community 102 - "Witness Remediation Report"
Cohesion: 0.29
Nodes (6): Changed files, PASS — `python generate_frames.py`, PASS — `python verify_frames.py`, Safety model, Verification, Witness Remediation Report

### Community 103 - "Native Codex host mode"
Cohesion: 0.33
Nodes (5): Native Codex host mode, One-turn discipline, Recover and close, Start, Why this is the default in Codex

### Community 104 - "Changelog"
Cohesion: 0.33
Nodes (5): 0.1.0, 1.0.0 — 2026-07-11, 1.1.0 — 2026-07-12, 1.2.0 — 2026-07-12, Changelog

### Community 106 - "Native Codex host mode"
Cohesion: 0.33
Nodes (5): Native Codex host mode, One-turn discipline, Recover and close, Start, Why this is the default in Codex

### Community 110 - "Witness repository guidance for Codex"
Cohesion: 0.50
Nodes (3): When the user asks to install this repository, When using Witness, Witness repository guidance for Codex

## Knowledge Gaps
- **182 isolated node(s):** `bootstrap.sh script`, `run-witness.sh script`, `name`, `version`, `displayName` (+177 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ProjectProfile` connect `properties` to `AdapterError`, `WitnessError`, `remediation.py`, `WebAdapter`, `ProjectDetector`, `Handler`, `ProjectProfile`, `Adapter`, `help`, `cli.py`, `.start`, `APIAdapter`, `Path`, `properties`, `test_web_adapter_unit.py`, `test_codex_cli_prompt_matches_changed_image_gating`, `CLIAdapter`, `FakeClient`, `cli.py`, `Any`?**
  _High betweenness centrality (0.114) - this node is a cross-community bridge._
- **Why does `ConfigurationError` connect `FakeClient` to `WitnessError`, `ConfigurationError`, `remediation.py`, `format_findings_as_pr_comment`, `Adapter`, `help`, `cli.py`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Why does `ProjectDetector` connect `ProjectDetector` to `properties`, `help`, `cli.py`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Are the 44 inferred relationships involving `ProjectProfile` (e.g. with `CampaignRunner` and `ProjectDetector`) actually correct?**
  _`ProjectProfile` has 44 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `ConfigurationError` (e.g. with `ConfigModel` and `ProjectConfig`) actually correct?**
  _`ConfigurationError` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `Observation` (e.g. with `HostSessionClient` and `HostSessionRuntime`) actually correct?**
  _`Observation` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `AdapterAction` (e.g. with `HostSessionClient` and `HostSessionRuntime`) actually correct?**
  _`AdapterAction` has 22 INFERRED edges - model-reasoned connections that need verification._