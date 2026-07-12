# Roadmap

## Completed in v1.2 — hardening, budgets, Electron, and engine bridges

- Timing-safe native-daemon authentication, durable atomic state, and behavior-level security coverage.
- Defense-in-depth command screening plus explicit sandbox/copy trust-boundary documentation.
- More than 80% non-live coverage and a 70% CI floor.
- Real animated demo and reproducible transcript.
- Configurable direct-provider pricing, hard cost budgets, bounded delta-first prompts, and changed-image gating.
- Evidence-backed GitHub pull-request comments.
- First-class Electron detection and Playwright-over-CDP desktop testing.
- `witness-game.json`, packaged/atomically installable Unity and Unreal bridges, and constrained file-based capture/named-action transport.

## Completed in v1.1 — Codex-native distribution and OAuth execution

- Native host-driven sessions using the current interactive Codex model without API keys or nested agents.
- Persistent adapter lifecycle across host reasoning turns.
- Loopback bearer-token control plane, private state, idle cleanup, strict decision validation, and stale-turn rejection.
- Unattended `codex-cli` provider using cached Sign in with ChatGPT authentication, images, ephemeral sessions, read-only sandboxing, and output schemas.
- Repository skill, user skill, Codex plugin, marketplace package, rich metadata, POSIX/Windows installers, login/browser diagnostics, and clean-install CI smoke tests.

## Completed in v1.0 — product-grade Phase 1

1. Provider verification and keyless provider protocols.
2. Screenshot, DOM, terminal, API, game, visual metric, and delta observations.
3. Broad resilient WebAdapter actions.
4. Multi-persona and multi-journey campaigns.
5. Inspectable test planning and coverage notes.
6. Stateful OpenAPI-aware APIAdapter.
7. Real PTY CLI isolation and command guardrails.
8. Replay, manifests, fingerprints, and comparison.
9. Ground-truth benchmark scoring and 20 defect classes.
10. Markdown, HTML, JSON, JUnit, SARIF, CI, browser E2E, and packaging.

Additional capabilities include game/visual QA, engine capture/input bridges, and verification-gated evidence-to-fix remediation.

## Next — platform breadth

- Optional native desktop accessibility-tree/window automation beyond Electron renderer scope.
- MobileAdapter through Appium/platform test bridges.
- External adapter/provider entry points and community packs.
- Monorepo target selection and reusable authenticated test-state fixtures.

## Next — trust and optimization

- Larger independently authored benchmark corpus.
- Confidence calibration, flaky-run analysis, and statistical repeat policies.
- Video/temporal sampling for animation defects and performance hitch correlation.
- Stronger OS/container isolation for untrusted fixer commands.
- Optional code-aware localization after black-box evidence, with source hypotheses separated from observed facts.

## Deliberate safety boundaries

- Production testing always requires explicit authorization.
- The original source is never modified by remediation unless `--apply` is explicitly requested and all verification commands pass.
- Witness never treats a source hypothesis as a confirmed root cause without independent evidence.
- Native host and provider models never execute adapter actions directly.
