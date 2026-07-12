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

    actual = base.copy()
    draw = ImageDraw.Draw(actual)
    if index == 1:
        draw.rectangle((900, 40, 1295, 102), fill="#101820", outline="#ff6b6b", width=3)
        draw.text((1135, 62), "SHIELDS 100%", font=font, fill="#777777")
    elif index == 2:
        draw.rectangle((430, 648, 820, 698), fill="#101820", outline="#ff6b6b", width=3)
        draw.text((445, 665), "MISSION READY", font=font, fill="#ffffff")
        draw.rectangle((40, 47, 360, 109), fill="#101820", outline="#ff6b6b", width=3)
        draw.text((60, 69), "SCORE 001250", font=font, fill="#ffffff")
    else:
        draw.rectangle((500, 210, 780, 490), outline="#ff00ff", width=8)
        draw.text((510, 205), "STALE DEBUG BOUNDS", font=font, fill="#ff00ff")
    actual.save(ROOT / "frames" / f"frame_{index:02d}.png")
