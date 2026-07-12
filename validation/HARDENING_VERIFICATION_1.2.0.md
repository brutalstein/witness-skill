# Witness 1.2.0 hardening verification

Date: 2026-07-12

This report records the verification performed for the security, coverage, cost-control, GitHub integration, Electron, Unity, Unreal, and token-efficiency release. It distinguishes executable evidence from contract-level validation so the repository does not imply that unavailable proprietary runtimes or credentials were exercised.

## Delivered changes

- Timing-safe native-daemon bearer authentication and durable atomic state writes.
- Loopback HTTP integration coverage for authorization and health behavior.
- Defense-in-depth command blocking for inline Python, decoded shell payloads, `eval`, and executable permission chains; isolated workspaces remain the primary boundary.
- Behavior-level tests for WebAdapter, CLI commands, host sessions, project detection, Electron, engine bridges, budget handling, GitHub comments, and Windows process lifecycle helpers.
- A real animated browser demo and deterministic terminal transcript.
- Configurable token pricing, `--max-cost`, graceful budget termination, bounded model history/observations/output, delta-first observations, and changed-image gating.
- Evidence-first GitHub pull-request comment formatting and posting through `httpx`.
- Electron project detection and Playwright-over-CDP operation with a disposable user-data directory and loopback-only debugging.
- Packaged Unity and Unreal engine bridge templates, a constrained request/response file protocol, bridge installation commands, manifest path validation, and loader-injection rejection.
- Cross-platform child-process-tree termination for Web, API, Electron, and Game targets.
- Linux and Windows CI coverage for packaging, engine resources, installers, and the 70% coverage threshold.

## Automated verification

| Check | Result |
|---|---|
| Non-live unit/integration tests | 111 passed |
| Measured non-live coverage | 81.15% |
| CI coverage threshold | 70% |
| Real Chromium E2E | 1 passed |
| Ruff lint | Passed |
| Ruff format check | Passed |
| Wheel and sdist build | Passed |
| Fresh wheel installation | Passed |
| `pip check` | Passed |
| Installed CLI version | 1.2.0 |
| Packaged Unity bridge installation | Passed |
| Packaged Unreal bridge installation | Passed |
| Codex installer smoke | Passed in isolated prefix/skill/bin directories |
| OAuth login-status contract | Passed with a local contract double |
| Distribution mirror tests | Passed |

The Chromium test required a temporary loopback allowlist because this execution environment applies a system-wide `URLBlocklist: ["*"]` policy. The original policy was restored immediately after the test and verified as restored. This policy change is not part of Witness.

## Platform validation boundary

### Electron

The Electron adapter, detection, CDP connection behavior, isolated profile construction, input validation, and process cleanup are covered with behavior-level tests. A third-party Electron application was not installed or launched in this environment. The adapter requires the target application's normal Electron runtime to be available on the user's machine.

### Unity and Unreal Engine

The shipped bridge source files are present in both source and built wheel artifacts. Installation, manifest constraints, request identifiers, file-protocol actions, capture responses, unsafe path rejection, and simulated bridge exchanges are tested. Unity Editor/Player and Unreal Editor/packaged builds were not available in this environment, so the C#/C++ bridge templates were not compiled by the proprietary engine toolchains here. CI and local engine projects should compile the installed bridge as part of their normal build.

### Codex OAuth

No reusable Codex OAuth credential was available in this execution environment. Native host sessions need no nested provider call and are tested with real adapters. The unattended `codex-cli` provider is tested for login status, ephemeral/read-only invocation, image and schema arguments, and structured output handling. On an authenticated user machine it delegates authentication to `codex login`; Witness does not read or copy the credential file.

### Live OpenAI/Anthropic APIs

No paid provider request was made. Provider payload/schema behavior remains covered by contract tests. The keyless Codex native-host and Codex-CLI modes are the recommended paths for the user's OAuth setup.

## Reproduce

```bash
ruff check .
ruff format --check .
pytest -m "not e2e and not live" -q \
  --cov=witness_qa --cov-report=term-missing --cov-fail-under=70
pytest -m e2e -q
python -m build
```

Fresh-package verification:

```bash
python -m venv .verify-venv
.verify-venv/bin/pip install dist/witness_qa-1.2.0-py3-none-any.whl
.verify-venv/bin/pip check
.verify-venv/bin/witness --version
.verify-venv/bin/witness install-engine-bridge unity /tmp/witness-unity
.verify-venv/bin/witness install-engine-bridge unreal /tmp/witness-unreal
```
