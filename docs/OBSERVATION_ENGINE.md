# Observation and Reasoning Engine

The engine judges what a real user could observe after a real action. It never receives a hidden assertion that the product is “supposed to work.”

## Observation envelope

All adapters emit the same high-level fields:

- summary and visible text/state
- screenshot or rendered evidence
- structured evidence path
- errors and exit/status information
- adapter metadata
- deterministic visual metrics
- delta from the previous observation

Web evidence adds DOM geometry, interactives, console/page/network errors, dialogs, and downloads. CLI adds terminal transcript and exit state. API adds status/headers/body/timing/OpenAPI context. Game adds frame/reference indices, recent inputs, and visual comparison data.

## Visual analysis

Before a model call, Witness computes dimensions, entropy, edge density, blank ratio, dominant colors, perceptual hash, frame-change ratio, and available reference difference. It also emits conservative heuristic warnings for likely clipping, alignment anomalies, and very weak contrast. These signals focus the model; they do not replace visual judgment.

## Observation deltas

Witness reports changed text, new/resolved errors, changed interactives, and visual-change ratio. The model therefore sees what changed after an action instead of repeatedly rediscovering the entire state. Full evidence remains linked for audit and replay.

## Strict decision contract

Every provider returns:

- expectation
- action taken
- observation summary
- judgment: match / mismatch / uncertain
- confidence
- reasoning / player-user impact
- black-box hypothesis when warranted
- severity
- visual assessment and suggested investigation
- one next action or terminal decision

The next action must belong to the adapter allowlist or be `goal_reached`, `goal_blocked`, or `give_up_and_report`.

## Providers

- OpenAI Responses API with image input and strict JSON Schema.
- Anthropic Messages API with image input and forced strict tool output.
- Command provider for Claude Code, Codex, local multimodal models, or enterprise gateways without API keys.
- Scripted provider for genuine host-agent decisions and deterministic regression/benchmark runs.

Provider retries handle transport, invalid schema, and refusal/incomplete cases without fabricating a decision. Usage, latency, and provider/model identity are attached to the session result.
