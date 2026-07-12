# Witness validation evidence

This directory contains deterministic product-flow evidence from the earlier adapter/remediation validation and the current release verification.

## Current release

- [Witness 1.2.0 hardening verification](HARDENING_VERIFICATION_1.2.0.md)
- [Final verification summary](FINAL_VERIFICATION.txt)

## Codex integration

- [Codex integration verification](CODEX_INTEGRATION_VERIFICATION.md)
- Native host artifacts: `codex-native-session/`
- Codex CLI provider contract: `codex-cli-provider-contract/`

## Product-flow artifacts

`validation/results/` contains reports, screenshots, structured results, remediation output, and after-fix evidence for real Web, CLI, API, and game fixture processes. `validation/decisions/` contains reviewed deterministic host decisions used where reusable paid-provider or OAuth credentials were not available in the build environment.

The current 1.2.0 automated suite contains 111 non-live tests at 81.15% coverage plus one real Chromium E2E test. Exact platform and credential boundaries are documented in the hardening report rather than implied as live validation.
