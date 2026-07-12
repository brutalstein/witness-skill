# Adapters

Adapters are the only target-specific layer. Every implementation provides:

```python
start(project_profile) -> session_handle
act(session_handle, action) -> action_result
observe(session_handle) -> observation
stop(session_handle) -> None
```

`act` performs one atomic user-like operation. `observe` is separate so the orchestrator can inspect initial, asynchronous, or post-wait states without inventing an action. Adapter startup/driver failures are infrastructure errors, not product findings.

## WebAdapter

Uses real Playwright Chromium sessions. Supported operations include navigation, click/double/right-click, hover, typing, key presses, select/check, upload, drag/drop, scrolling, dialogs, tabs, downloads, and waits.

Locator recovery prefers accessible role/name, label, placeholder, test id, text, then stable CSS. Observations contain screenshots, visible text, interactive inventory and geometry, estimated contrast, DOM state, console/page errors, request failures, HTTP failures, dialogs, downloads, visual metrics, and turn deltas. External navigation is blocked unless authorized.

## ElectronAdapter

Launches Electron with a loopback-only Chromium remote-debugging endpoint and connects Playwright over CDP. Renderer interactions and observations reuse WebAdapter, including accessible locators, screenshots, DOM geometry, console/network failures, dialogs, downloads, and visual deltas. The adapter does not silently control native OS dialogs, keychains, or privileged main-process APIs. See [Electron testing](ELECTRON.md).

## CLIAdapter

Uses a real pseudo-terminal rather than a plain pipe, preserving prompts, colors, TUI layout behavior, and TTY-sensitive code paths. It supports commands, text input, key presses, and output waits. Observations include a rendered terminal PNG, transcript, exit status, recent output, and changed files.

Safe mode operates on a copied workspace, blocks privileged/destructive patterns, applies timeouts, and terminates the process tree during cleanup.

## APIAdapter

Starts or connects to a real HTTP service, discovers common OpenAPI/Swagger locations, and performs stateful requests. Observations include request method/path, response status/headers/body, timing, contract metadata, errors, and a rendered API-state PNG. Authorization/cookie/API-key headers and sensitive body fields are redacted from traces while still being used for the actual request.

## GameAdapter

Supports ordered PNG/JPEG/WebP frame sequences and running builds. A native build may supply command templates or the file-based engine bridge from `witness-game.json`. The included Unity package and Unreal plugin capture real engine frames and emit named, opt-in test actions without opening a network listener. Browser games may use WebAdapter when DOM/browser telemetry is valuable.

Observations contain the current frame, reference comparison, frame index, recent input history, deterministic visual metrics, heuristic warnings, and cross-frame deltas. The multimodal reasoner evaluates layout, safe areas, contrast, hierarchy, typography, assets, z-order, debug residue, state continuity, resolution behavior, and temporal jitter.

## Registry

`adapters/registry.py` maps `ProjectType` to adapter classes. The registry is the only selection point. Future mobile/community adapters should preserve the same contract and return the shared `Observation`/`ActionResult` models.

## Natural-language actions

Reasoners describe intent using human-facing targets such as `Create account` or `Email`, not brittle selectors. Each adapter resolves that intent using its structured capabilities. Coordinates and raw selectors remain escape hatches, not the default reasoning language.
