# Codex OAuth integration verification

Witness 1.1 provides two API-key-free Codex paths.

## Native Codex host protocol

`validation/codex-native-session/` was generated against the real PTY-backed CLI adapter. A persistent loopback daemon owned the process and evidence state while three strict host decisions were submitted with turns `1`, `2`, and `3`.

Result:

- Provider metadata: `codex-host` / `current-codex-session`
- Real adapter: CLIAdapter with an isolated copy and real pseudo-terminal
- Final state: `goal_reached`
- Findings: zero
- Reports: Markdown, JSON, HTML, JUnit, and SARIF
- API key required: no
- Stale/duplicate turn rejection: covered by `tests/test_host_session.py`

The decisions used for this deterministic verification are in `validation/decisions/cli_happy.json`. In an actual `$witness` task, the active Codex model authors these same schema-valid decisions after reading each observation and screenshot.

## Codex CLI OAuth provider contract

`validation/codex-cli-provider-contract/` was generated through the public `witness verify-provider --provider codex-cli` command using a contract double for the Codex executable. The test verifies:

- `codex login status` is checked before execution
- `codex exec` is ephemeral and read-only
- the current screenshot is attached with `--image`
- the strict Witness JSON Schema is passed with `--output-schema`
- the final decision is read through `--output-last-message`
- relative output directories resolve correctly even though the subprocess changes working directory
- no OpenAI API key is read or required

The actual cached ChatGPT credential was not available in this build environment, so this artifact is a CLI transport/schema contract verification rather than a claim of a live OAuth model call. On an installed user's machine, the same command uses the existing `codex login` session without reading or copying Codex credential storage.

## Installer verification

The cross-platform installer was exercised in a clean temporary prefix with:

- a fresh Python virtual environment
- a clean skill root
- a clean launcher directory
- a Codex login-status contract double

It atomically installed `~/.agents/skills/witness` semantics, produced the launcher, and made `witness doctor --json` report both `native_codex_host` and `codex_cli_oauth` ready without provider API keys.
