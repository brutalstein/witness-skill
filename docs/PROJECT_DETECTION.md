# Project Detection

Detection produces a scored `ProjectProfile`; it does not launch the target. Explicit CLI/config overrides always win.

## Signals

Witness inspects, within bounded limits:

- README commands and project description
- package/lock/build manifests and scripts
- framework and dependency markers
- executable/CLI entry points
- OpenAPI/Swagger documents and API server patterns
- Electron package/main-process markers
- Godot, Unity, Unreal, custom game-engine markers and `witness-game.json`
- screenshot/frame sequences and reference directories
- static HTML, dev-server configuration, and common ports
- an already-running URL supplied by the user

Each signal records source, candidate type, weight, and human-readable detail. Candidates are sorted by score and converted to high/medium/low confidence.

## Supported profiles

- `web`: reachable URL or inferred server/static entry point
- `desktop`: Electron launch command and CDP connection policy
- `cli`: executable/script command and project root
- `api`: start command, base URL, and optional OpenAPI metadata
- `game`: frame list and/or capture/input/start commands

Mobile remains a reserved profile value. Electron desktop projects are supported directly. Low-confidence/unknown targets require an explicit `--adapter` rather than silently guessing.

## Configuration

`witness.yaml` can override type, root, start command, URL, frame list, capture command, input command, Electron debug port, readiness timeout, engine bridge manifest, and references. Detection evidence remains in the result so the user can audit why an adapter was selected.
