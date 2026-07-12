# Contributing to Witness

Witness keeps its observation/reasoning core small and centrally coherent while making adapters, personas, and project-detection signals additive extension points.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
witness install-browser
ruff check .
ruff format --check .
pytest -m "not e2e and not live" --cov=witness_qa --cov-fail-under=60
pytest -m e2e
# For a local packaging-only smoke test (CI additionally verifies login status):
python scripts/install_codex.py --prefix /tmp/witness-codex --skill-root /tmp/witness-skills --bin-dir /tmp/witness-bin --skip-browser --no-login-check
```

## High-value contributions

### Add a persona

Add a focused YAML file under `src/witness_qa/builtin_personas/`. A persona describes intent and constraints, not scripted clicks or commands. Include loader tests.

### Improve project detection

Add weighted, inspectable evidence in `detection.py`. Do not turn detection into an opaque first-match chain. Include a fixture or sample project that proves both the positive signal and a nearby non-match.

### Add an adapter

Implement the stable `start() / act() / observe() / stop()` contract in `src/witness_qa/adapters/`. Register it by project type without adding type-specific branches to the orchestrator. New adapters must produce inspectable evidence and distinguish target behavior from adapter infrastructure failures.

### Improve game/visual QA

Add deterministic fixtures, references, resolutions, or engine bridges rather than prompt-only claims. Visual heuristics should be conservative and model findings must still link to the exact frame.

### Improve remediation

Preserve the discovery/remediation boundary. Fixes run in a copy by default, must emit an auditable diff, and may not be applied to the source without explicit intent and passing verification. Never weaken a target test to make a remediation appear successful.

## Core principles

- Every product judgment must be falsifiable and linked to evidence.
- The reasoning engine is never told that the target is "supposed to work."
- `observation_summary` remains separate from `judgment`.
- Root causes remain hypotheses unless independently verified.
- Infrastructure failures and product defects are never conflated.
- The orchestrator stays adapter-agnostic.
- No production target is exercised without explicit authorization.

Open an issue before a large core change. Adapter pull requests should include tests and, where practical, screenshots or a short recording of a real run.

## Codex integration changes

Changes to native host mode or the Codex CLI provider must preserve the shared `ReasoningDecision` schema and must not bypass adapter safety. Include tests for schema validation, image/schema CLI flags, login failures, turn concurrency, private session state, and plugin/skill metadata consistency. Keep `.agents/skills/witness/` and `skills/codex/witness/` byte-for-byte identical.
