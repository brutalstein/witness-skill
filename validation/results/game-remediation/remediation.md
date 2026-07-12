# Witness Remediation Report

- **Workspace:** `validation/results/game-remediation/workspace`
- **Verified:** yes
- **Applied to source:** no
- **Patch:** `validation/results/game-remediation/remediation.patch`

## Changed files

- `frames/frame_01.png`
- `frames/frame_02.png`
- `frames/frame_03.png`
- `generate_frames.py`

## Verification

### PASS — `python generate_frames.py`

Exit code: `0` · Duration: `1.34s`

```text

```

### PASS — `python verify_frames.py`

Exit code: `0` · Duration: `1.48s`

```text
frame_01.png: changed_ratio=0.000000
frame_02.png: changed_ratio=0.000000
frame_03.png: changed_ratio=0.000000
All gameplay frames match the approved references.
```

## Safety model

Witness edits a persistent copy by default. Applying changes back to the source requires `--apply` and a completely passing verification set.
