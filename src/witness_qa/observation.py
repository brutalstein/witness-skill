from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageFilter, ImageStat

from .models import Observation, ObservationDelta, VisualMetrics


def _hex_color(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _pixel_data(image: Image.Image):
    getter = getattr(image, "get_flattened_data", None)
    return getter() if getter else image.getdata()


def _average_hash(image: Image.Image, size: int = 8) -> str:
    gray = image.convert("L").resize((size, size))
    values = list(_pixel_data(gray))
    average = sum(values) / max(1, len(values))
    bits = "".join("1" if value >= average else "0" for value in values)
    return f"{int(bits, 2):0{size * size // 4}x}"


def _entropy(image: Image.Image) -> float:
    histogram = image.convert("L").histogram()
    total = sum(histogram)
    if not total:
        return 0.0
    return -sum((count / total) * math.log2(count / total) for count in histogram if count)


def _edge_density(image: Image.Image) -> float:
    edge = image.convert("L").filter(ImageFilter.FIND_EDGES)
    stat = ImageStat.Stat(edge)
    mean = stat.mean[0] if stat.mean else 0.0
    return round(mean / 255.0, 5)


def _blank_ratio(image: Image.Image) -> float:
    thumb = image.convert("RGB").resize((min(256, image.width), min(256, image.height)))
    pixels = list(_pixel_data(thumb))
    if not pixels:
        return 1.0
    common = Counter(pixels).most_common(1)[0][1]
    return round(common / len(pixels), 5)


def _dominant_colors(image: Image.Image, count: int = 6) -> list[str]:
    thumb = image.convert("RGB").resize((96, 96)).quantize(colors=count).convert("RGB")
    return [_hex_color(color) for color, _ in Counter(_pixel_data(thumb)).most_common(count)]


def _border_warnings(image: Image.Image) -> list[str]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    if width < 4 or height < 4:
        return []
    border_width = max(1, min(width, height) // 100)
    regions = {
        "left": (0, 0, border_width, height),
        "right": (width - border_width, 0, width, height),
        "top": (0, 0, width, border_width),
        "bottom": (0, height - border_width, width, height),
    }
    warnings: list[str] = []
    center = rgb.crop((width // 4, height // 4, 3 * width // 4, 3 * height // 4))
    center_std = sum(ImageStat.Stat(center).stddev) / 3
    for name, box in regions.items():
        region = rgb.crop(box)
        std = sum(ImageStat.Stat(region).stddev) / 3
        if center_std > 12 and std > 28:
            warnings.append(f"High-detail content touches the {name} edge; inspect for clipping.")
    return warnings


def _alignment_warnings(image: Image.Image) -> list[str]:
    gray = image.convert("L").resize((min(image.width, 512), min(image.height, 512)))
    edges = gray.filter(ImageFilter.FIND_EDGES)
    threshold = edges.point(lambda value: 255 if value > 48 else 0)
    bbox = threshold.getbbox()
    if not bbox:
        return []
    left, top, right, bottom = bbox
    width, height = gray.size
    margins = (left, width - right, top, height - bottom)
    warnings: list[str] = []
    horizontal_difference = abs(margins[0] - margins[1]) / max(1, width)
    vertical_difference = abs(margins[2] - margins[3]) / max(1, height)
    if horizontal_difference > 0.18:
        warnings.append("Visible composition is strongly horizontally unbalanced.")
    if vertical_difference > 0.30:
        warnings.append("Visible composition is strongly vertically unbalanced.")
    return warnings


def _contrast_warnings(image: Image.Image) -> list[str]:
    gray = image.convert("L").resize((128, 128))
    stat = ImageStat.Stat(gray)
    warnings: list[str] = []
    if stat.stddev and stat.stddev[0] < 18:
        warnings.append("The frame has very low global luminance contrast.")
    if stat.mean and (stat.mean[0] < 12 or stat.mean[0] > 244):
        warnings.append("The frame is close to uniformly black or white.")
    return warnings


def analyze_image(path: Path, previous_path: Path | None = None) -> VisualMetrics:
    with Image.open(path) as opened:
        image = opened.convert("RGB")
        change_ratio = 0.0
        if previous_path and previous_path.is_file():
            try:
                with Image.open(previous_path) as previous_opened:
                    previous = previous_opened.convert("RGB").resize(image.size)
                    diff = ImageChops.difference(image, previous).convert("L")
                    histogram = diff.histogram()
                    changed = sum(count for value, count in enumerate(histogram) if value > 12)
                    change_ratio = changed / max(1, image.width * image.height)
            except OSError:
                change_ratio = 0.0
        return VisualMetrics(
            width=image.width,
            height=image.height,
            entropy=round(_entropy(image), 5),
            edge_density=_edge_density(image),
            blank_ratio=_blank_ratio(image),
            dominant_colors=_dominant_colors(image),
            perceptual_hash=_average_hash(image),
            change_ratio=round(change_ratio, 5),
            likely_clipping=_border_warnings(image),
            alignment_warnings=_alignment_warnings(image),
            contrast_warnings=_contrast_warnings(image),
        )


def compare_observations(previous: Observation | None, current: Observation) -> ObservationDelta:
    if previous is None:
        return ObservationDelta(
            changed_text=[line for line in current.text.splitlines()[:20] if line.strip()],
            new_errors=current.errors,
            visual_change_ratio=current.visual_metrics.change_ratio
            if current.visual_metrics
            else 0.0,
        )
    previous_lines = {line.strip() for line in previous.text.splitlines() if line.strip()}
    current_lines = {line.strip() for line in current.text.splitlines() if line.strip()}
    previous_errors = set(previous.errors)
    current_errors = set(current.errors)
    return ObservationDelta(
        changed_text=sorted(current_lines - previous_lines)[:80],
        new_errors=sorted(current_errors - previous_errors),
        resolved_errors=sorted(previous_errors - current_errors),
        visual_change_ratio=current.visual_metrics.change_ratio if current.visual_metrics else 0.0,
    )


def dom_visual_heuristics(
    elements: list[dict[str, Any]], viewport: dict[str, int]
) -> dict[str, list[str]]:
    width = max(1, int(viewport.get("width", 1)))
    height = max(1, int(viewport.get("height", 1)))
    clipping: list[str] = []
    alignment: list[str] = []
    contrast: list[str] = []
    rows: dict[int, list[dict[str, Any]]] = {}
    for element in elements:
        box = element.get("box") or {}
        x = float(box.get("x", 0))
        y = float(box.get("y", 0))
        w = float(box.get("width", 0))
        h = float(box.get("height", 0))
        name = str(element.get("name") or element.get("tag") or "element")[:80]
        if x < -1 or y < -1 or x + w > width + 1 or y + h > height + 1:
            clipping.append(f"'{name}' extends outside the viewport.")
        row_key = int(y // 12)
        rows.setdefault(row_key, []).append(element)
        ratio = element.get("contrast_ratio")
        if isinstance(ratio, (int, float)) and ratio < 3:
            contrast.append(f"'{name}' has estimated contrast ratio {ratio:.2f}:1.")
    for row in rows.values():
        if len(row) >= 3:
            tops = [round(float((item.get("box") or {}).get("y", 0)), 1) for item in row]
            if max(tops) - min(tops) > 8:
                names = ", ".join(str(item.get("name") or item.get("tag"))[:30] for item in row[:4])
                alignment.append(f"Elements on one visual row are vertically misaligned: {names}.")
    return {
        "likely_clipping": clipping[:30],
        "alignment_warnings": alignment[:30],
        "contrast_warnings": contrast[:30],
    }
