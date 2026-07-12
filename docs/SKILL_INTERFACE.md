# Skill interface

Claude Code and Codex skills are instruction and installation surfaces over one shared `witness` CLI. They do not contain independent testing logic.

## Core invocation

```bash
witness detect PROJECT
witness plan PROJECT
witness run --project PROJECT --persona PERSONA --journey GOAL --output DIR
```

## Codex native invocation

Inside an interactive Codex task, the skill must prefer:

```bash
witness session start --project PROJECT --persona PERSONA --output DIR
witness session submit --session DIR --expected-turn TURN --decision-file DECISION.json
```

Codex itself inspects the evidence and creates the decision. This uses the current signed-in model, requires no API key, and avoids nested `codex exec` calls.

## Codex unattended invocation

Outside an interactive reasoning loop:

```bash
witness run --project PROJECT --provider codex-cli --output DIR
```

This reuses the cached Codex Sign in with ChatGPT authentication and runs strict image-enabled `codex exec` turns.

## Host responsibilities

- Obtain explicit target scope and production authorization.
- Prefer local/dev systems and disposable data.
- Choose personas and journeys deliberately.
- Inspect linked screenshots/logs before accepting findings.
- Keep product, provider, and adapter failures separate.
- Preserve expectation → observation → judgment → next-action structure.
- Avoid source claims not supported by black-box evidence.
- Use the current `turn` when submitting native decisions.
- Remove temporary decision files that could contain typed values.

## Machine outputs

`result.json` is the stable session contract. Campaign output uses `CampaignResult`. Human output is written to Markdown/HTML and evidence directories. Failures use exit code `2`; finding thresholds use exit code `1`.

## Keyless integration surfaces

- Native `witness session`: active host model, no nested model process
- `--provider codex-cli`: authenticated Codex CLI subprocess
- `--provider command --agent-command ...`: arbitrary trusted host/local process
- `--provider scripted --decision-file ...`: reproducible reviewed decisions

## Fix delegation

After a confirmed finding, the skill may invoke:

```bash
witness remediate RESULT_JSON --patch reviewed.patch --verify 'test command'
```

or a trusted fixer command. The host must review the patch and rerun the same persona/journey. `--apply` is permitted only with explicit user intent and passing verification.

## Installation surfaces

- Repository Codex skill: `.agents/skills/witness/`
- Distributable Codex skill: `skills/codex/witness/`
- Codex plugin: `.codex-plugin/plugin.json`
- Codex marketplace: `.agents/plugins/marketplace.json`
- User skill target: `~/.agents/skills/witness/`
- Claude Code: `.claude/skills/witness/` or `skills/claude/witness/`

The Codex installer creates an isolated runtime, installs Chromium, atomically copies the complete skill, verifies login, and produces JSON diagnostics. See [Codex integration](CODEX_INTEGRATION.md).
