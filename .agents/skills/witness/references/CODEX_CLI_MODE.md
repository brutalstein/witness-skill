# Codex CLI OAuth provider mode

Prerequisites:

```bash
codex login
codex login status
witness verify-provider --provider codex-cli
```

`codex login` supports Sign in with ChatGPT. Codex caches and refreshes that login; Witness does not read or copy the credential.

For each QA turn Witness executes Codex with:

- `codex exec`
- `--ephemeral`
- `--sandbox read-only`
- `--skip-git-repo-check`
- `--image <current evidence>` when available
- `--output-schema <strict Witness schema>`
- `--output-last-message <decision.json>`

The subprocess receives only the QA policy and observation prompt. It is instructed not to inspect/edit the repository or invoke tools. Provider artifacts are retained under `witness-output/logs/codex-cli/` for debugging; OAuth credentials are never written there.

Do not select this provider from the native `$witness` loop unless a nested Codex process is intentionally desired.
