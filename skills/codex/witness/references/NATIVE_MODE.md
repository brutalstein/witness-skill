# Native Codex host mode

Native mode separates deterministic software control from model reasoning:

```text
Current Codex task (vision + reasoning)
        ↕ one strict decision JSON per numbered turn
Witness local host session (127.0.0.1 + random bearer token)
        ↕
Web / CLI / API / Game adapter
```

The daemon binds only to loopback, stores its random bearer token in `witness-output/.witness/session.json` with user-only permissions where supported, owns the live browser/PTY/process handle, rejects stale or duplicated decisions, and exits after a terminal decision or idle timeout.

## Start

```bash
scripts/run-witness.sh session start \
  --project . \
  --persona first-time-user \
  --output witness-output
```

The response contains:

- `turn`: monotonically increasing optimistic-concurrency token
- `prompt`: reasoner instructions for the current state
- `schema`: exact JSON Schema for the decision
- `observation`: compact current evidence
- `structured_path`: complete structured evidence on disk
- `screenshot_path`: current visual evidence when available
- `allowed_actions`: actions the adapter will accept

## One-turn discipline

1. Inspect the current evidence, including the screenshot when present.
2. Create one complete decision matching the returned schema.
3. Submit it with the exact current turn:

```bash
scripts/run-witness.sh session submit \
  --session witness-output \
  --expected-turn 1 \
  --decision-file /tmp/witness-decision.json
rm -f /tmp/witness-decision.json
```

A nonterminal `next_action` is executed exactly once and the next observation receives a new `turn`. A terminal action writes Markdown, JSON, HTML, JUnit, SARIF, screenshots, and the trace, then closes the adapter.

Never call only an adapter action and never omit the full decision. The evidence trace must retain expectation, neutral observation, judgment, reasoning, findings, and next action. Never submit an old `turn`; a stale submission is rejected before product state changes.

## Recover and close

Read the current request again without acting:

```bash
scripts/run-witness.sh session request --session witness-output
```

Inspect status:

```bash
scripts/run-witness.sh session status --session witness-output
```

Close an abandoned session safely:

```bash
scripts/run-witness.sh session finish \
  --session witness-output \
  --status inconclusive
```

## Why this is the default in Codex

The active Codex task already has reasoning, vision, repository context, user intent, and ChatGPT OAuth. Native mode reuses that host directly rather than recursively starting another Codex process. Witness remains responsible for repeatable actions, observations, schemas, safety, evidence, and reports.
