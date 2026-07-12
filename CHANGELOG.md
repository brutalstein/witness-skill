# Changelog

All notable changes to Witness are documented here.

## 1.2.0 — 2026-07-12

- Hardened native host authentication with timing-safe token comparison and durable atomic state writes; added real loopback HTTP integration coverage.
- Expanded command safety defense-in-depth for Python inline code, decoded shell payloads, eval, and executable chaining while documenting sandbox isolation as the primary boundary.
- Raised non-live coverage above 80%, added behavior-level WebAdapter/CLI/host/detection tests, and increased the CI threshold to 70%.
- Replaced the README demo placeholder with a real animated browser run and exact terminal transcript.
- Added configurable provider pricing, `--max-cost`, graceful budget termination, report/result budget fields, bounded output/history/observations, and changed-image gating with prompt/attachment consistency.
- Added evidence-backed GitHub pull-request comments with a tested HTTP integration and Actions guide.
- Added first-class Electron detection and a Playwright-over-CDP desktop adapter with loopback-only remote debugging and disposable user-data profiles.
- Added `witness-game.json`, a constrained file-based engine bridge protocol, packaged Unity/Unreal templates, atomic `install-engine-bridge`, packaged-build discovery, and engine-specific documentation.
- Hardened Windows process lifecycle handling so web, API, Electron, and game launches use dedicated process groups and terminate complete child trees instead of leaving renderer or engine subprocesses behind.


## 1.1.0 — 2026-07-12

- Added native Codex host sessions so the current interactive Codex model can drive real Witness adapters without an API key or nested model process.
- Added a token-protected loopback daemon, private session state, strict schema validation, idle cleanup, and expected-turn concurrency guards.
- Added the `codex-cli` reasoning provider using cached Sign in with ChatGPT credentials, image attachments, ephemeral runs, read-only sandboxing, and JSON Schema output.
- Added Codex plugin and marketplace manifests, rich skill metadata, mirrored repo/user skill packages, cross-platform installers, atomic skill updates, login/browser diagnostics, and installation smoke tests.
- Added `witness --version` and capability-oriented `witness doctor --json` output.
- Added complete Codex installation, native mode, unattended mode, security, and troubleshooting documentation.
- Hardened native sessions with mandatory optimistic turn tokens, machine-only JSON stdout, and source-checkout daemon import support.
- Fixed relative output paths for `codex exec` schema/result artifacts and added regression coverage.

## 1.0.0 — 2026-07-11

- Added production-grade Web, CLI, API, and Game/Visual adapters.
- Added multimodal OpenAI/Anthropic providers plus keyless command and scripted host-agent modes.
- Added visual metrics, references, observation deltas, game defect taxonomy, and engine bridge guidance.
- Added multi-persona/journey campaigns, planning, replay, comparison, benchmark scoring, and stable fingerprints.
- Added Markdown, HTML, JSON, JUnit, and SARIF reporting with trace redaction and usage manifests.
- Added safe copy workspaces, command/URL guardrails, and evidence-to-fix remediation with verification-gated apply.
- Added sample web, CLI, API, and game projects; 20-class benchmark catalog; CI, browser E2E, package verification, Claude Code skill, and Codex skill.

## 0.1.0

- Initial Phase 1 MVP with Web/CLI adapters, project detection, personas, multimodal reasoning, reports, skills, tests, and packaging.
