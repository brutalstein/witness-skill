---
name: witness
description: Run evidence-backed QA on local web apps, Electron desktop apps, CLIs, APIs, Unity/Unreal/Godot games, screenshots, and visual flows. Use when asked to test, visually inspect, reproduce, find UX defects, verify a fix, or exercise a real user journey. Prefer the native host session so the current signed-in coding agent reasons without separate API keys.
---

# Witness QA

Use Witness as a deterministic action/observation harness. The current Codex or Claude task is the model by default. Do not launch a nested model process from an interactive task unless the user explicitly requests an unattended/headless run.

## Ensure installation

1. Run `scripts/run-witness.sh doctor --json`; on Windows use `scripts/run-witness.ps1 doctor --json`.
2. If the runtime is missing and this skill belongs to a complete Witness checkout/plugin, run `scripts/bootstrap.sh`; on Windows use `scripts/bootstrap.ps1`.
3. If only a copied skill folder is available, clone the GitHub repository supplied by the user, review its installer, then run `scripts/install-codex.sh` (`scripts/install-codex.ps1` on Windows).
4. The installer creates an isolated Witness virtual environment, installs Chromium, atomically installs the user skill, creates a launcher, and validates available host capabilities.
5. Never ask for `OPENAI_API_KEY` when the user has signed into Codex with ChatGPT. Native host mode needs no provider credential; unattended Codex mode reuses Codex OAuth.

## Native host mode — default inside Codex or Claude Code

1. Start one persistent adapter session:
   ```bash
   scripts/run-witness.sh session start --project . --persona first-time-user --output witness-output
   ```
2. Parse the returned JSON. Record `turn`; read `prompt`, `observation`, and `structured_path`; inspect `screenshot_path` whenever present.
3. Produce exactly one object matching `schema`. Preserve expectation → observation → judgment → next_action. Use one small reversible action, listed actions only, and observable evidence only.
4. Submit against the same live turn:
   ```bash
   scripts/run-witness.sh session submit \
     --session witness-output \
     --expected-turn <TURN> \
     --decision-file <DECISION.json>
   ```
5. Repeat with the newest turn until `terminal` is true. Never resubmit an old turn or submit concurrently.
6. Read `report.md`, `result.json`, and linked artifacts before summarizing.
7. For confirmed defects, use `witness remediate` in an isolated workspace, review the diff, verify it, and rerun the same persona/journey before applying.
8. Close abandoned sessions with `session finish --status inconclusive`.

## Unattended Codex OAuth mode

Use only outside an active Codex reasoning loop or when explicitly requested:

```bash
scripts/run-witness.sh run --project . --provider codex-cli --output witness-output
```

Witness verifies `codex login status`, then uses schema-constrained, image-enabled, read-only, ephemeral `codex exec` turns with cached Sign in with ChatGPT credentials. No API key is required.

## Target-specific rules

- **Web:** use accessible locators; collect screenshots, DOM geometry, console/page errors, request failures, dialogs, downloads, and responsive evidence.
- **Electron:** select `desktop`; Witness launches with loopback-only CDP, a disposable user-data profile, and WebAdapter evidence. Do not silently automate privileged OS dialogs or keychains.
- **CLI:** use the real PTY and isolated copy workspace. Treat command denylisting as defense-in-depth, not the sandbox boundary.
- **API:** use documented public endpoints; redact auth headers and sensitive body values.
- **Unity/Unreal/Godot:** prefer `witness-game.json` and the file bridge. For Unity/Unreal, install packaged bridges with `witness install-engine-bridge unity Packages/com.witness.qa` or `witness install-engine-bridge unreal Plugins/WitnessBridge`. Inspect safe areas, clipping, scale, hierarchy, contrast, z-order, seams, flicker, state continuity, HUD feedback, debug overlays, aspect ratios, localization expansion, accessibility, and reference differences.

## Cost and token discipline

- Prefer native host mode during an interactive task; it avoids nested model sessions.
- For direct providers, honor `--max-cost` and current configured token prices.
- Keep `history_turns`, `max_observation_chars`, and `max_output_tokens` bounded.
- Use observation deltas and changed-image gating; keep images on game turns where visual continuity is the evidence.
- Never claim an exact USD estimate when the provider does not return billable token metadata.

## Reporting and GitHub

- Preserve Markdown, JSON, screenshots, structured evidence, JUnit, and SARIF artifacts.
- Use `witness post-github-comment result.json --dry-run` before posting to a PR.
- Keep typed secrets out of reports and comments.

## Safety and quality rules

- Default to local/dev targets and disposable data. Require explicit authorization for production.
- Never reinterpret adapter, browser, network, authentication, engine-bridge, or infrastructure failures as product defects.
- Use one small reversible action per turn. Stop only when success, blockage, or inconclusiveness is observable.
- Review generated patches and verification output before `--apply`.
- Do not bypass host tokens, stale-turn guards, allowed-action schemas, target policy, workspace isolation, or remediation gates.
