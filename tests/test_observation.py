from pathlib import Path

from PIL import Image, ImageDraw

from witness_qa.observation import analyze_image


def test_visual_metrics_detect_change_and_edges(tmp_path: Path) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    Image.new("RGB", (200, 120), "white").save(first)
    image = Image.new("RGB", (200, 120), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((150, 0, 210, 80), fill="black")
    image.save(second)
    metrics = analyze_image(second, first)
    assert metrics.change_ratio > 0.05
    assert metrics.edge_density > 0
    assert metrics.perceptual_hash
