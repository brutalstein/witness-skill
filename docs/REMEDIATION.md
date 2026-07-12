# Evidence-to-Fix Remediation

Witness keeps defect discovery and code modification separate. A finding must first be grounded in a screenshot, terminal state, HTTP exchange, or structured observation. Only then can `witness remediate` prepare a fix.

## Safety workflow

1. Load an existing `result.json` and resolve its evidence paths.
2. Copy the project into `witness-remediation/workspace` while excluding VCS, dependencies, build outputs, and prior Witness artifacts.
3. Apply either a reviewed unified diff or run a **trusted** fixer command in that copy.
4. Record every changed/removed file and generate `remediation.patch`.
5. Run repeatable verification commands in the copy.
6. Keep the source untouched unless `--apply` was explicitly supplied and every verification passed.

```bash
witness remediate witness-output/result.json \
  --patch proposed-fix.patch \
  --verify 'ruff check .' \
  --verify 'pytest -q'
```

## Host-agent fixer contract

A fixer command receives one JSON request on stdin and these environment variables:

- `WITNESS_WORKSPACE`: isolated project copy it may edit.
- `WITNESS_REMEDIATION_REQUEST`: path to the same request JSON.

The request includes the project type, evidence-resolved findings, and safety rules. Stdout must be one JSON object; diagnostics belong on stderr.

```json
{
  "summary": "Anchored HUD panels to the shared safe area",
  "verification_commands": [
    "python generate_frames.py",
    "python verify_frames.py"
  ]
}
```

The command is trusted code and is not a security boundary. Use a reviewed wrapper, a container, or a locked-down CI runner for third-party agents.

## Applying changes

`--apply` copies only the final changed files from the verified workspace. It is rejected when verification is absent or any command fails. Review `remediation.patch`, the verification transcript, and a Witness re-test before applying.

```bash
witness run --project witness-remediation/workspace --output after-fix
witness compare witness-output/result.json after-fix/result.json
witness remediate witness-output/result.json --patch proposed-fix.patch \
  --verify 'pytest -q' --apply
```

## Game/visual repair loop

For game UI, the recommended gate is:

1. Capture deterministic before frames.
2. Run `game-visual-director` against references/resolutions.
3. Fix layout, assets, render layers, or state handling in a remediation workspace.
4. Rebuild/capture frames.
5. Run deterministic image assertions and another model-guided visual session.
6. Compare findings and apply only when the target defects resolve without new regressions.

The included `examples/game_visual_review` fixture demonstrates this workflow.
