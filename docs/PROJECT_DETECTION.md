# Project Detection

Detection produces a scored `ProjectProfile`; it does not launch the target. Explicit CLI/config overrides always win.

## Signals

Witness inspects, within bounded limits:

- README commands and project description
- package/lock/build manifests and scripts
- framework dependency markers
- executable/CLI entry points
- OpenAPI/Swagger documents and API server patterns
- Electron package/main-process markers
- Flutter `pubspec.yaml`, `android/`, `ios/`, and `lib/main.dart` markers
- Godot, Unity, Unreal, and custom game-engine markers plus `witness-game.json`
- screenshot/frame sequences and reference directories
- static HTML, dev-server configuration, and common ports
- already-running URLs supplied by the user

Each signal records its source, candidate type, weight, and human-readable detail. Candidates are sorted by score and converted into high/medium/low confidence.

## Supported profiles

- `web`: reachable URL and inferred server/static entry point
- `desktop`: Electron launch command and CDP connection policy
- `mobile`: Flutter/Appium-oriented Android and iOS targets, package/bundle metadata, and device-launch settings
- `cli`: executable/script command and project root
- `api`: start command, base URL, and optional OpenAPI metadata
- `game`: frame list and/or capture/input/start commands

Low-confidence or ambiguous targets require an explicit `--adapter` rather than a silent guess.

## Configuration

`witness.yaml` can override type, root, start command, URL, frame list, capture command, input command, Electron debug port, Appium/mobile launch settings, readiness timeout, engine bridge manifest, and references. Detection evidence remains in the result so the user can audit why an adapter was selected.
