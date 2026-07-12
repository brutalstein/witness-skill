# Codex integration

Witness supports Codex without an OpenAI API key through two different execution models. They share the same adapters, evidence models, decision schema, reports, and safety policy.

## Distribution surfaces

The repository is both a Codex Agent Skill and a Codex plugin:

```text
.agents/skills/witness/             repo-scoped skill
skills/codex/witness/               distributable plugin skill
.codex-plugin/plugin.json           plugin manifest
.agents/plugins/marketplace.json    marketplace catalog
scripts/install-codex.sh            POSIX runtime/user-skill installer
scripts/install-codex.ps1           Windows runtime/user-skill installer
```

After the repository is public, Codex can register and install it with:

```bash
codex plugin marketplace add OWNER/REPOSITORY
codex plugin add witness-qa@witness
```

For a direct checkout:

```bash
git clone https://github.com/OWNER/REPOSITORY.git
cd REPOSITORY
./scripts/install-codex.sh
```

The installer:

1. Creates an isolated virtual environment under `~/.local/share/witness/venv` by default.
2. Installs the local repository and its runtime dependencies.
3. Installs Playwright Chromium unless `--skip-browser` is selected.
4. Atomically installs the complete skill folder at `~/.agents/skills/witness`.
5. Creates a launcher under `~/.local/bin/witness`.
6. Runs `codex login status` unless explicitly disabled for packaging tests.
7. Runs `witness doctor --json` against the installed skill.

It never asks for or reads an OpenAI API key.

## Mode 1: native Codex host

Use this mode from an interactive Codex task. The current Codex model sees the evidence and returns the strict Witness decision. No nested Codex process is created.

```text
Codex task
  ├─ reads SKILL.md
  ├─ starts Witness session daemon
  ├─ inspects screenshot + structured evidence
  ├─ reasons about expectation vs observation
  └─ submits one strict decision
          │
          v
HostSessionRuntime
  ├─ owns browser / PTY / HTTP / game handle
  ├─ performs exactly one requested action
  ├─ captures the next observation
  └─ writes the same report contract as Orchestrator
```

Start:

```bash
witness session start \
  --project . \
  --persona first-time-user \
  --output witness-output
```

The JSON response contains:

- `turn` and `max_turns`
- `system` and `prompt`
- strict `schema`
- `observation`
- absolute `screenshot_path` and `structured_path`
- adapter `allowed_actions`

Codex must inspect every available visual artifact, create one complete `ReasoningDecision`, and submit it with the returned turn number:

```bash
witness session submit \
  --session witness-output \
  --expected-turn 1 \
  --decision-file /tmp/witness-decision.json
rm -f /tmp/witness-decision.json
```

Repeat until `terminal` is true. Then inspect `report.md`, `result.json`, screenshots, and the trace before summarizing.

### Native-session guarantees

- The target process and adapter remain alive across turns.
- The daemon binds only to loopback.
- A random bearer token protects every request.
- The state file is written with mode `0600` where supported.
- The bearer token is removed from the final state file.
- `--expected-turn` rejects stale or duplicated actions.
- Schema-invalid decisions do not advance the target.
- Adapter/infrastructure failures finalize as inconclusive, not as product findings.
- Idle sessions are closed and reported.

The daemon is an implementation detail. Codex normally uses the `witness session` CLI commands rather than contacting it directly.

## Mode 2: Codex CLI OAuth provider

Use this mode for a self-running command outside an interactive Codex reasoning loop:

```bash
codex login
codex login status
witness verify-provider --provider codex-cli
witness run --project . --provider codex-cli --output witness-output
```

`CodexCLIReasoningEngine` verifies login, then executes one isolated Codex turn per Witness observation using:

```text
codex exec
--ephemeral
--sandbox read-only
--skip-git-repo-check
--image <current screenshot>          when present
--output-schema <decision schema>
--output-last-message <decision.json>
-
```

The prompt limits the child model to reasoning over supplied evidence. It is instructed not to inspect or edit the repository and not to run tools. The subprocess starts in a turn-specific artifact directory. Its final output is validated again with Witness's Pydantic model before any target action is performed.

Codex CLI reuses its own cached Sign in with ChatGPT authentication. Witness does not open, parse, copy, or log the Codex credential store.

### Configuration

```yaml
provider:
  name: codex-cli
  codex_path: codex
  codex_profile: null
  codex_sandbox: read-only
  timeout: 180
```

Environment overrides:

```bash
WITNESS_CODEX_PATH=/custom/path/codex
WITNESS_CODEX_PROFILE=qa-readonly
WITNESS_CODEX_SANDBOX=read-only
WITNESS_MODEL=
```

Omit `WITNESS_MODEL` to use the current Codex default. A model override is optional and may not be available in every workspace.

## Choosing a mode

| Situation | Mode |
|---|---|
| User invokes `$witness` in an active Codex task | Native host |
| Codex is already looking at screenshots and repository context | Native host |
| Terminal/cron/local automation should run end to end by itself | Codex CLI OAuth provider |
| Another host agent needs Codex as a reasoning subprocess | Codex CLI OAuth provider |
| CI/CD | Prefer the official Codex automation guidance and explicit trusted credentials; do not copy personal OAuth credentials into untrusted runners |

Do not invoke `--provider codex-cli` from native mode unless the user deliberately wants nested Codex execution.

## Installation prompt for Codex

A user can paste this after sharing the GitHub URL:

```text
Install this Witness repository as my global Codex QA plugin and skill. Review the
installer first, then run it. Verify `codex login status` and `witness doctor --json`.
Do not ask for an API key; use my existing Sign in with ChatGPT session. Prefer native
Witness sessions when I invoke the skill interactively and codex-cli only for unattended runs.
```

## Troubleshooting

### Skill is not visible

- Confirm `~/.agents/skills/witness/SKILL.md` exists.
- Run `witness doctor --json`.
- Restart Codex if the installation happened during an already-running task.
- Invoke explicitly with `$witness`.

### `codex-cli` says not signed in

```bash
codex login
codex login status
```

Complete Sign in with ChatGPT in the browser or use Codex device authentication when appropriate.

### Browser is missing

```bash
witness install-browser
```

On Linux hosts that need system packages:

```bash
witness install-browser --with-deps
```

### Native session is stale

```bash
witness session status --session witness-output
witness session request --session witness-output
```

Use the newest returned `turn` in `--expected-turn`. If the task was abandoned:

```bash
witness session finish --session witness-output --status inconclusive
```

### Installer is not on PATH

The default launcher is `~/.local/bin/witness`. Add that directory to PATH or let the skill call the absolute launcher through `scripts/run-witness.sh`.
