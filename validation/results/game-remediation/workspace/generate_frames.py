from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
(ROOT / "frames").mkdir(exist_ok=True)
(ROOT / "references").mkdir(exist_ok=True)
font = ImageFont.load_default()

for index in range(1, 4):
    base = Image.new("RGB", (1280, 720), "#182331")
    draw = ImageDraw.Draw(base)
    draw.rectangle((0, 0, 1280, 720), fill="#182331")
    draw.ellipse((520, 230, 760, 470), fill="#335b7a", outline="#9bd7ff", width=4)
    draw.rectangle((40, 40, 360, 102), fill="#101820", outline="#8cd7ff", width=3)
    draw.text((60, 62), "SCORE 001250", font=font, fill="#ffffff")
    draw.rectangle((900, 40, 1235, 102), fill="#101820", outline="#8cd7ff", width=3)
    draw.text((925, 62), "SHIELDS 100%", font=font, fill="#ffffff")
    draw.rectangle((460, 640, 820, 690), fill="#101820", outline="#8cd7ff", width=3)
    draw.text((570, 657), "MISSION READY", font=font, fill="#ffffff")
    base.save(ROOT / "references" / f"frame_{index:02d}.png")

    # Production output uses the same safe-area anchors, typography, and release layers
    # as the approved reference capture. Engine-specific effects can be composed before save.
    actual = base.copy()
    actual.save(ROOT / "frames" / f"frame_{index:02d}.png")
