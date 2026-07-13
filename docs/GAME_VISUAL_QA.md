# Game Visual QA

Witness treats a game or simulator frame as product evidence, not decoration. The model receives the screenshot together with deterministic visual metrics, reference differences, prior-frame deltas, recent inputs, and a checklist tailored to game and simulation visual consistency.

## Supported workflows

### Screenshot review

Point Witness at a PNG/JPEG/WebP file or a directory of ordered frames:

```bash
witness run --project captures/ --adapter game --persona game-visual-director
```

### Reference regression

Configure one reference per frame. Witness records a pixel-change ratio while the model judges whether the change is an intended art update or a visible regression.

### Running builds

A native build needs two safe bridges:

- `capture_command`: writes the current frame to `{output}`.
- `input_command`: accepts `{kind}`, `{key}`, `{target}`, `{x}`, and `{y}`.

Commands should connect to a test-only engine plugin, debug socket, automation driver, or platform capture utility. Do not expose them in production builds.

## Engine guidance

### Godot

Use a test autoload or editor plugin that accepts JSON commands on localhost, calls `Input.parse_input_event`, and saves the viewport through `get_viewport().get_texture().get_image().save_png(path)`.

### Unity

Use a development-build-only MonoBehaviour that accepts local commands, invokes an Input System test bridge, and captures through `ScreenCapture.CaptureScreenshot`. Run at fixed resolutions and include safe-area telemetry in structured state when possible.

### Unreal Engine

Use the automation test framework or a development-only console bridge. Capture high-resolution screenshots through an automation screenshot command and route input through Enhanced Input or test hooks. Export viewport size, DPI scale, active widget tree, and safe-zone data when available.

For Unreal-based simulators such as CARLA, prefer annotating `witness-game.json` with a simulation profile and tags so Witness can elevate simulator-specific checks:

```json
{
  "version": 1,
  "engine": "unreal",
  "profile": "carla",
  "tags": ["simulator", "driving", "telemetry"],
  "bridge": {"type": "file", "directory": ".witness/bridge"}
}
```

Use the `simulator-visual-director` persona or `carla-visual-director` alias when the session should prioritize world plausibility, overlay conflicts, and temporal stability.

### Custom engines

Keep the bridge deliberately small:

```json
{"action":"press","key":"Enter"}
{"action":"click","x":640,"y":360}
{"action":"capture","output":"/tmp/frame.png"}
```

Return only when the frame is stable. Include build version, resolution, locale, graphics preset, and scene/state identifier in output metadata.

## Visual defect taxonomy

Witness reviews:

- **Layout:** anchor errors, inconsistent gaps, baseline drift, wrong alignment, and unsafe edge placement.
- **Typography:** clipping, wrapping, tiny text, wrong weight, inconsistent casing, and missing glyphs.
- **Contrast:** unreadable foreground/background combinations, color-only status, and weak focus or selection.
- **Assets:** wrong scale, stretching, blur, aliasing, compression artifacts, and inconsistent icon style.
- **Composition:** hierarchy failures, focal competition, occlusion, z-order issues, and unintended seams or empty space.
- **State:** stale overlays, wrong selected state, disabled-state ambiguity, and missing feedback.
- **Temporal:** flicker, popping, animation discontinuity, transition residue, and frame-to-frame jitter.
- **Resolution:** safe areas, letterboxing, aspect-ratio adaptation, and ultrawide/mobile clipping.
- **Simulation plausibility:** vehicle/world clipping, actor intersections, route-overlay conflicts, lane/sign readability, sensor-feed occlusion, debug residue, and weather/visibility failures.

## Fix verification loop

Reports separate:

1. Observed visual fact.
2. User or operator impact.
3. Black-box hypothesis.
4. Suggested investigation or likely fix direction.

Witness does not claim an engine/source root cause from pixels alone.

After black-box evidence exists, `witness remediate` can delegate a fix in an isolated copy, preserve the generated patch, run engine/build/image verification commands, and rerun the same visual journey before anything is applied to source:

```bash
witness remediate game-run/result.json \
  --agent-command './tools/fix-with-coding-agent' \
  --verify './tools/build-development-player' \
  --verify './tools/capture-and-compare-frames'
```

For shipped builds, combine fixed-resolution captures with ultrawide, reduced-width, locale, DPI, color-scheme, weather, time-of-day, and accessibility variants. A model judgment should complement, not replace, deterministic safe-area, reference, and release-overlay assertions.
