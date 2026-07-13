# Architecture

Witness is an evidence-first agentic QA system. The core never assumes that an action succeeded merely because it was issued. Every turn preserves the same contract:

```text
expectation → real action → observation → judgment → next action
```

## Runtime flow

1. **CLI / skill surface** resolves configuration, target, personas, journeys, provider, safety profile, and report formats.
2. **ProjectDetector** scores README, manifests, filesystem markers, OpenAPI documents, game-engine files, screenshots, URLs, and explicit overrides into a `ProjectProfile`.
3. **TestPlanner** produces inspectable user journeys and risks. A campaign may execute persona × journey combinations independently.
4. **Adapter registry** maps the profile to one four-method adapter: `start`, `act`, `observe`, `stop`.
5. **Execution controller** is either the regular `Orchestrator` or `HostSessionRuntime`. The orchestrator calls a configured Reasoning Engine; the host runtime exposes the same decision boundary to an already-running Codex/Claude model while retaining the live adapter handle.
6. **Observation Engine** combines the user-visible state with structured support evidence and a delta from the previous turn.
7. **Reporting** writes the immutable trace, stable findings, screenshots/logs, machine contracts, and CI formats. Both controller paths use the same report writer and `ReasoningDecision` contract.
8. **Remediation** is optional and happens only after evidence exists. It prepares a separate workspace, delegates or applies a fix, verifies it, and never mutates the source without an explicit verified `--apply`.

## Load-bearing boundaries

### Adapter boundary

Adapters contain all target-specific mechanics. The orchestrator does not know whether an action is a browser/Electron click, PTY command, HTTP request, or game input. Adding an adapter must not require changing the reasoning loop.

### Controller / reasoning separation

The regular orchestrator controls lifecycle, history, safety limits, and stopping while a Reasoning Engine returns a strict `ReasoningDecision`. Native host mode preserves the same boundary: `HostSessionRuntime` controls the adapter and accepts a schema-validated decision from the current host model. Neither provider nor host model executes target actions directly.

Native submissions carry an expected turn number. Stale or duplicated decisions are rejected before an action is performed.

### Observation / judgment separation

An observation is captured fact: pixels, visible text, terminal bytes, status codes, errors, timings, and metrics. A judgment compares that fact with an explicit expectation. Reports preserve observed fact, impact/reasoning, hypothesis, and suggested investigation as separate fields.

### Discovery / remediation separation

A fixer cannot rewrite the QA trace that justified a change. Remediation consumes a completed `result.json` and linked evidence, works in a copy, emits a diff, and requires verification before source application.

## Core components

- `detection.py`: weighted target profiling and entry-point inference.
- `planning.py`: journey/risk plan generation.
- `campaign.py`: independent persona/journey sessions and finding deduplication.
- `adapters/`: Web, Flutter mobile, Electron desktop, CLI, API, and Game implementations.
- `observation.py`: visual metrics, heuristic warnings, and state deltas.
- `reasoning/`: strict schema, prompts, API providers, Codex CLI OAuth provider, command provider, and scripted provider.
- `orchestrator.py`: adapter-agnostic provider-driven state machine.
- `host_session.py` / `host_daemon.py`: loopback, token-protected native host-model state machine for active Codex/Claude tasks.
- `reporting.py`: Markdown, HTML, JSON, JUnit, SARIF, fingerprints, and trace redaction.
- `replay.py` / `benchmark.py`: reproducibility and reviewed-quality measurement.
- `remediation.py`: isolated evidence-to-fix workflow.
- `safety.py`: URL/command policy, isolated workspaces, and changed-file accounting.

## Failure classes

Witness keeps these distinct:

- **Product mismatch:** the target ran, an action was performed, and evidence contradicted the expectation.
- **Goal blocked:** observed product behavior prevents the persona goal.
- **Inconclusive:** evidence is insufficient or the agent cannot make safe progress.
- **Witness infrastructure error:** browser/process/provider/configuration failed. This must never be reported as a product defect.

## State and reproducibility

The orchestrator is stateful within a session; adapters expose a session handle but keep policy and reasoning outside. Every result records Witness version, target revision when available, provider/model, seed, duration, usage, actions, observations, and evidence paths. `witness replay`, `witness compare`, and stable finding fingerprints support repeatable investigation.

## Security model

Witness defaults to local/dev hosts, command guardrails, sensitive-field redaction, and copy sandboxes. A user must explicitly authorize production targets and source application. Host model/fixer commands are trusted executables; stronger OS/container isolation is recommended for untrusted third-party agents.
