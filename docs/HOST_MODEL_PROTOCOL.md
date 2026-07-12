# Host model protocol

Witness has two keyless host-model boundaries.

## Native interactive host protocol

`witness session` is the preferred protocol when Witness is invoked from an already-running Codex or Claude Code task. The host model reasons directly; Witness retains the live adapter handle and performs deterministic actions.

```bash
witness session start --project . --output witness-output
witness session request --session witness-output
witness session submit --session witness-output --expected-turn N --decision-file decision.json
witness session status --session witness-output
witness session finish --session witness-output --status inconclusive
```

Every nonterminal request includes the complete prompt, current observation, evidence paths, allowed actions, strict decision schema, and turn number. The host must inspect the screenshot when present and submit a full decision preserving expectation → observation → judgment → next action.

`--expected-turn` is an optimistic-concurrency guard. A stale decision is rejected before any action executes.

The runtime daemon listens only on loopback and authenticates requests with a random bearer token. The token is kept in the private session state while active and removed after completion.

See [Codex integration](CODEX_INTEGRATION.md) for the Codex-specific workflow.

## Generic command-provider protocol

`--provider command` is used when an external executable should supply each decision. The configured process receives one JSON request on stdin and must return one JSON object on stdout.

Request fields:

- `system`: complete Witness QA policy
- `prompt`: persona, project profile, allowed actions, history, observation, deltas, and metrics
- `schema`: strict JSON Schema for the decision
- `screenshot_path`: absolute path to current visual evidence

The process must inspect the screenshot when present and return a decision matching `schema`. Diagnostics belong on stderr; stdout must contain only JSON.

Security recommendations:

- Quote paths safely in wrappers.
- Do not forward unrelated environment secrets into model prompts.
- Set a timeout.
- Use an allowlisted executable.
- Prefer native host mode instead of recursive CLI invocation when the same interactive agent is already active.

## Codex CLI OAuth provider

`--provider codex-cli` is a productized command provider. It verifies `codex login status`, attaches the current screenshot, requests schema-constrained output, and validates the returned decision. It is intended for unattended execution, not the default native `$witness` loop.

## Remediation agent protocol

`witness remediate --agent-command ...` is a separate, explicitly trusted coding-agent boundary. It receives evidence-backed findings and an isolated workspace, edits only that workspace, and returns a JSON summary plus optional verification commands. Discovery reasoning and remediation are intentionally separate so a fixer cannot rewrite the evidence that justified the change. See [Remediation](REMEDIATION.md).
