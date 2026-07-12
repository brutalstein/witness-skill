# Witness repository guidance for Codex

## When the user asks to install this repository

1. Inspect `README.md`, `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json`, and the platform-appropriate installer before execution.
2. Prefer the repository installer from a trusted checkout:
   - POSIX: `./scripts/install-codex.sh`
   - Windows PowerShell: `.\scripts\install-codex.ps1`
3. Do not request `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`. This integration is designed for the user's existing Codex **Sign in with ChatGPT** session.
4. Confirm `codex login status` succeeds. If it does not, ask the user to run `codex login` and choose Sign in with ChatGPT; never inspect or copy Codex credential files.
5. Confirm `witness doctor --json` reports native Codex-host readiness and that `~/.agents/skills/witness/SKILL.md` exists.
6. If the skill was added during an active Codex task and is not visible, start a new task/session, then invoke `$witness` explicitly.

The repository can also be distributed as a Codex plugin/marketplace source:

```bash
codex plugin marketplace add OWNER/REPOSITORY
codex plugin add witness-qa@witness
```

The plugin supplies the skill; its reviewed bootstrap installs the shared Python runtime on first use.

## When using Witness

- From an interactive Codex task, prefer `witness session ...` native host mode. Use the returned `turn` as `--expected-turn` for every decision.
- Use `--provider codex-cli` only for deliberate unattended/headless execution. It reuses `codex login` through ephemeral, image-enabled, schema-constrained `codex exec` turns.
- Never run both modes for the same live adapter session.
- Preserve evidence-first judgment and use remediation only in an isolated workspace until verification passes.
