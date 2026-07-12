# Game visual review example

This fixture contains three intentionally defective gameplay frames and three approved reference frames.

```bash
witness run --project examples/game_visual_review/frames \
  --adapter game \
  --persona game-visual-director \
  --provider command \
  --agent-command './your-model-wrapper'
```

Use `witness.yaml` to connect a running Godot/Unity/Unreal build through engine-specific `capture_command` and `input_command` bridges. Browser games can be tested directly with `WebAdapter`.
