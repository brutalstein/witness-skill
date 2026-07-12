from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).parent
failures: list[str] = []
for actual_path in sorted((ROOT / "frames").glob("frame_*.png")):
    reference_path = ROOT / "references" / actual_path.name
    if not reference_path.is_file():
        failures.append(f"missing reference: {reference_path.name}")
        continue
    with (
        Image.open(actual_path).convert("RGB") as actual,
        Image.open(reference_path).convert("RGB") as reference,
    ):
        if actual.size != reference.size:
            failures.append(f"size mismatch: {actual_path.name}")
            continue
        difference = ImageChops.difference(actual, reference)
        histogram = difference.histogram()
        changed_channels = sum(
            sum(histogram[channel * 256 + 1 : (channel + 1) * 256]) for channel in range(3)
        )
        ratio = changed_channels / max(1, actual.width * actual.height * 3)
        print(f"{actual_path.name}: changed_ratio={ratio:.6f}")
        if ratio > 0.0001:
            failures.append(f"visual mismatch: {actual_path.name} ({ratio:.6f})")

if failures:
    raise SystemExit("\n".join(failures))
print("All gameplay frames match the approved references.")
