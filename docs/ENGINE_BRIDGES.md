# Unity and Unreal Engine bridges

Witness performs black-box visual QA against packaged or development builds. The recommended
integration is an explicit file bridge: no listening TCP port, no global input injection, and no
privileged automation. Witness atomically writes `command.json`; the engine responds with
`ack.json` and, for capture requests, a PNG.

## Manifest

Create `witness-game.json` in the game repository root:

```json
{
  "$schema": "./docs/schemas/witness-game.schema.json",
  "version": 1,
  "engine": "unity",
  "start": "Builds/MyGame.exe -screen-width 1440 -screen-height 900",
  "bridge": {"type": "file", "directory": ".witness/game-bridge", "timeout": 20},
  "references": ["Tests/VisualReferences/main-menu.png"],
  "startup_wait": 3
}
```

The schema is available at `docs/schemas/witness-game.schema.json`. Relative paths resolve from
the project root. The bridge directory is exported to the child process as
`WITNESS_BRIDGE_DIR`.

## Install the packaged bridges

Witness wheels include both bridge templates, so a GitHub/skill installation does not depend on the original checkout remaining available:

```bash
witness install-engine-bridge unity Packages/com.witness.qa
witness install-engine-bridge unreal Plugins/WitnessBridge
```

The installer refuses to replace a non-empty directory unless `--force` is explicit and performs replacements through a staged directory with rollback. Review existing custom bridge changes before forcing an update.

## Unity

Install `Packages/com.witness.qa` with the command above (or copy `integrations/unity/com.witness.qa` from a source checkout), then add the
`WitnessBridge` component to a bootstrap object. Capture works immediately through
`ScreenCapture.CaptureScreenshot`. `click` and `press` commands are intentionally emitted as
`OnNamedAction` events; bind those events to public, test-safe game actions. This avoids faking
private input state or bypassing gameplay rules.

For CI, create a deterministic test build with fixed resolution, fixed random seed, disabled
analytics, and fixture/reset controls. Point `start` at that build. Do not run Witness against a
production multiplayer service without an isolated test account and explicit host allowlisting.

## Unreal Engine

Install `Plugins/WitnessBridge` with the command above (or copy `integrations/unreal/WitnessBridge` from a source checkout) and enable it.
The `UWitnessBridgeSubsystem` is available from the Game Instance. It captures frames with
`FScreenshotRequest` and broadcasts `OnNamedAction` to Blueprint/C++ for explicit test actions.
Package a Development or Test build and point the manifest's `start` command at it.

## Command-template fallback

Existing projects can avoid an engine plugin by providing commands:

```json
{
  "version": 1,
  "engine": "custom",
  "start": "./game-test-build",
  "capture": "./tools/capture-frame --output {output}",
  "input": "./tools/send-test-input --kind {kind} --target {target} --key {key} --x {x} --y {y}"
}
```

Witness validates these commands with its defense-in-depth denylist and should still run them in
an isolated copy/sandbox. The commands are project-owned trust boundaries.


## Bridge security

- Use a relative bridge directory under the project (for example `.witness/game-bridge`). Witness rejects external absolute bridge directories by default so an untrusted manifest cannot redirect `command.json` writes elsewhere on the host.
- The bridge has no listening network socket. Requests are atomic files carrying unique IDs; acknowledgements must match the current request ID.
- Manifest environment variables are scoped to the launched game process. Loader-injection variables such as `LD_PRELOAD`, `DYLD_INSERT_LIBRARIES`, `PYTHONPATH`, and `NODE_OPTIONS` are rejected.
- Named `click`/`press` events are opt-in test seams. Bind them only to public, reversible test actions; do not expose arbitrary console execution or production administration.
- Use deterministic development/test builds, disposable accounts, fixed seeds, and isolated backends. The command denylist remains defense-in-depth rather than a sandbox.
