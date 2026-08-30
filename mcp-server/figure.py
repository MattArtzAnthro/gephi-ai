"""Compose a Gephi export and its legend into one figure a stranger can read.

Gephi writes a map with no key, and ``gephi_export_legend`` writes a key with no
map. Joining them has been left to whoever is driving, which means every figure
is assembled by hand and the caveats that make it honest are remembered or not.

This module does the joining. It draws only what it is given: swatch colours are
read off the graph by the caller, and the title, the notes and any channel this
server does not own are supplied rather than inferred. A figure that invented
its own caption would be confidently wrong in exactly the way the legend tool
already refuses to be.

Nothing here talks to Gephi, so it can be tested without one.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFont

# Font families to try in order. The first two cover macOS, the third most
# Linux distributions; the bitmap default keeps the composer working anywhere
# rather than failing on a missing font.
_FONT_CANDIDATES = {
    False: (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ),
    True: (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ),
}

INK = (20, 20, 24)
MUTED = (105, 105, 112)
FAINT = (140, 140, 148)
RULE = (215, 215, 219)
GLYPH_FILL = (78, 78, 82)
GLYPH_EDGE = (40, 40, 44)

#: Glyph names a caller may use for a channel this server does not own. The
#: names are shape words, not a plugin's vocabulary, so declaring a shape
#: channel couples the caller to nothing.
GLYPHS = ("circle", "square", "triangle", "diamond",
          "star", "pentagon", "hexagon", "cross")


def font(size: int, bold: bool = False) -> Any:
    """Returns a font of the requested size, falling back until one loads."""
    for path in _FONT_CANDIDATES[bold]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def glyph_outline(name: str, cx: float, cy: float, diameter: float) -> list[tuple[float, float]] | None:
    """Returns a glyph outline inscribed in the given circle.

    Inscribed rather than area-matched, so a key swatch has the same visual
    weight as the node it stands for. Returns None for a circle, which has no
    polygon form.

    :param name: one of :data:`GLYPHS`
    :param cx: centre on the x axis
    :param cy: centre on the y axis, increasing downwards
    :param diameter: the circle the glyph is inscribed in
    """
    key = name.strip().lower()
    if key not in GLYPHS:
        raise ValueError(f"Unknown glyph {name!r}; expected one of {', '.join(GLYPHS)}")
    r = diameter / 2.0
    up = math.pi / 2

    def regular(sides: int, start: float) -> list[tuple[float, float]]:
        step = 2 * math.pi / sides
        return [(cx + r * math.cos(start + i * step),
                 cy - r * math.sin(start + i * step)) for i in range(sides)]

    if key == "circle":
        return None
    if key == "square":
        return regular(4, math.pi / 4)
    if key == "diamond":
        return regular(4, up)
    if key == "triangle":
        return regular(3, up)
    if key == "pentagon":
        return regular(5, up)
    if key == "hexagon":
        return regular(6, 0.0)
    if key == "star":
        inner = r * 0.382
        pts = []
        for i in range(10):
            radius = r if i % 2 == 0 else inner
            angle = up + i * (math.pi / 5)
            pts.append((cx + radius * math.cos(angle), cy - radius * math.sin(angle)))
        return pts
    # cross: the arm corners are the outermost points, so the tip is pulled in
    # to keep every vertex on the circle.
    arm = r * 0.34
    tip = math.sqrt(max(r * r - arm * arm, 0.0))
    offsets = [(-arm, -tip), (arm, -tip), (arm, -arm), (tip, -arm),
               (tip, arm), (arm, arm), (arm, tip), (-arm, tip),
               (-arm, arm), (-tip, arm), (-tip, -arm), (-arm, -arm)]
    return [(cx + dx, cy + dy) for dx, dy in offsets]


def draw_glyph(draw: ImageDraw.ImageDraw, name: str, cx: float, cy: float,
               diameter: float, fill=GLYPH_FILL, outline=GLYPH_EDGE) -> None:
    """Draws one legend glyph."""
    points = glyph_outline(name, cx, cy, diameter)
    if points is None:
        r = diameter / 2.0
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=outline)
    else:
        draw.polygon(points, fill=fill, outline=outline)


def content_box(image: Image.Image, background=(255, 255, 255)) -> tuple[int, int, int, int]:
    """Returns the bounding box of everything that is not background."""
    plain = Image.new("RGB", image.size, background)
    return ImageChops.difference(image.convert("RGB"), plain).getbbox() or (0, 0, *image.size)


def position_transform(nodes: Sequence[dict], box: tuple[int, int, int, int]
                       ) -> Callable[[float, float], tuple[float, float]] | None:
    """Maps graph coordinates onto pixels in an export of that graph.

    Derived from the two bounding boxes rather than from Gephi's margin
    constant: the extent of the node positions must fill the non-background
    area of the image. That holds whatever margin or aspect the exporter chose,
    so it does not go stale when the exporter changes.

    Returns None when the positions have no extent to fit.
    """
    finite = [n for n in nodes
              if math.isfinite(n.get("x", math.nan)) and math.isfinite(n.get("y", math.nan))]
    if len(finite) < 2:
        return None
    xs = [n["x"] for n in finite]
    ys = [n["y"] for n in finite]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    span_x, span_y = max_x - min_x, max_y - min_y
    if span_x <= 0 or span_y <= 0:
        return None
    left, top, right, bottom = box

    # The drawn area runs half a node past the outermost centre on every side,
    # so fitting the centres to the full content box over-scales by that radius.
    # The radius in pixels depends on the scale and the scale depends on the
    # radius, so solve it by iterating; it settles in two or three passes.
    widest = max((float(n.get("size") or 0.0) for n in finite), default=0.0)
    inset = 0.0
    scale_x = scale_y = 0.0
    for _ in range(4):
        usable_w = (right - left) - 2 * inset
        usable_h = (bottom - top) - 2 * inset
        if usable_w <= 0 or usable_h <= 0:
            break
        scale_x, scale_y = usable_w / span_x, usable_h / span_y
        radius = widest / 2.0 * (scale_x + scale_y) / 2.0
        if abs(radius - inset) < 0.5:
            inset = radius
            break
        inset = radius
    if scale_x <= 0 or scale_y <= 0:
        return None

    origin_x, origin_y = left + inset, top + inset

    def to_pixel(x: float, y: float) -> tuple[float, float]:
        # GEXF y increases upwards; image y increases downwards.
        return (origin_x + (x - min_x) * scale_x,
                origin_y + (max_y - y) * scale_y)

    return to_pixel


def transform_hit_rate(image: Image.Image, nodes: Sequence[dict],
                       to_pixel: Callable[[float, float], tuple[float, float]],
                       sample: int = 200, background=(255, 255, 255)) -> float:
    """Fraction of sampled nodes whose projected pixel is not background.

    A derived transform that is subtly wrong still produces plausible crops, so
    it is checked against the image before anything is cut from it.
    """
    finite = [n for n in nodes if math.isfinite(n.get("x", math.nan))
              and math.isfinite(n.get("y", math.nan))]
    if not finite:
        return 0.0
    step = max(1, len(finite) // sample)
    picked = finite[::step]
    rgb = image.convert("RGB")
    hits = 0
    for node in picked:
        px, py = to_pixel(node["x"], node["y"])
        ix, iy = int(round(px)), int(round(py))
        if 0 <= ix < rgb.width and 0 <= iy < rgb.height:
            if rgb.getpixel((ix, iy)) != background:
                hits += 1
    return hits / len(picked)


def group_boxes(nodes: Sequence[dict], column: str,
                to_pixel: Callable[[float, float], tuple[float, float]],
                pad: float = 30.0) -> dict[str, tuple[int, int, int, int]]:
    """Bounding box in pixels for each value of a node column."""
    boxes: dict[str, list[float]] = {}
    for node in nodes:
        value = (node.get("attributes") or {}).get(column)
        if value is None:
            continue
        if not (math.isfinite(node.get("x", math.nan)) and math.isfinite(node.get("y", math.nan))):
            continue
        px, py = to_pixel(node["x"], node["y"])
        box = boxes.get(str(value))
        if box is None:
            boxes[str(value)] = [px, py, px, py]
        else:
            box[0] = min(box[0], px)
            box[1] = min(box[1], py)
            box[2] = max(box[2], px)
            box[3] = max(box[3], py)
    return {k: (int(v[0] - pad), int(v[1] - pad), int(v[2] + pad), int(v[3] + pad))
            for k, v in boxes.items()}


def _wrap(text: str, width: int) -> list[str]:
    words, lines, line = text.split(), [], ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if len(candidate) > width and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def _legend_height(channels: Sequence[dict], notes: Sequence[str]) -> int:
    height = 0
    for channel in channels:
        height += 100
        height += 50 * len(channel.get("groups") or {})
        height += 78 * len(channel.get("items") or [])
        if channel.get("range"):
            height += 50
    if notes:
        height += 60 + 30 * sum(len(_wrap(n, 58)) for n in notes)
    return height


def _draw_legend(canvas: Image.Image, x: int, y: int, width: int,
                 channels: Sequence[dict], notes: Sequence[str]) -> None:
    draw = ImageDraw.Draw(canvas)
    head, body, small, tiny = font(30, True), font(27), font(23), font(21)
    for channel in channels:
        label = channel.get("channel", "channel")
        column = channel.get("column")
        draw.text((x, y), label.title() if label.islower() else label, font=head, fill=INK)
        y += 46
        if column:
            draw.text((x, y), f"encodes {column}", font=small, fill=FAINT)
            y += 40
        stats = channel.get("stats") or {}
        for name, colour in (channel.get("groups") or {}).items():
            draw.ellipse([x, y, x + 32, y + 32], fill=colour, outline=(90, 90, 94))
            draw.text((x + 48, y + 1), str(name), font=body, fill=(30, 30, 34))
            if name in stats:
                draw.text((x + width - 240, y + 3), str(stats[name]), font=small, fill=FAINT)
            y += 50
        for item in channel.get("items") or []:
            draw_glyph(draw, item.get("glyph", "circle"), x + 26, y + 26, 46)
            draw.text((x + 72, y + 2), str(item.get("label", "")), font=body, fill=(30, 30, 34))
            if item.get("note"):
                draw.text((x + 72, y + 34), str(item["note"]), font=tiny, fill=FAINT)
            if item.get("stat"):
                draw.text((x + width - 240, y + 14), str(item["stat"]), font=small, fill=FAINT)
            y += 78
        span = channel.get("range")
        if span:
            draw.text((x, y), f"{span[0]:g} to {span[1]:g}", font=small, fill=FAINT)
            y += 50
        y += 26
    if notes:
        draw.line([x, y, x + width - 40, y], fill=RULE, width=2)
        y += 28
        for note in notes:
            for line in _wrap(note, 58):
                draw.text((x, y), line, font=tiny, fill=MUTED)
                y += 30
            y += 6


def compose(map_image: Image.Image, title: str, subtitle: str | None,
            channels: Sequence[dict], notes: Sequence[str],
            map_width: int = 2200, pad: int = 70, legend_width: int = 860) -> Image.Image:
    """Lays out title, map and legend on one canvas and trims the surplus."""
    scaled = map_image.convert("RGB")
    scaled = scaled.resize((map_width, max(1, int(scaled.height * map_width / scaled.width))),
                           Image.LANCZOS)
    top = 215 if subtitle else 165
    height = max(scaled.height + top, _legend_height(channels, notes) + top) + pad
    width = pad + map_width + 50 + legend_width + pad
    canvas = Image.new("RGB", (width, height), "white")
    canvas.paste(scaled, (pad, top))
    draw = ImageDraw.Draw(canvas)
    draw.text((pad, 56), title, font=font(54, True), fill=INK)
    if subtitle:
        for i, line in enumerate(_wrap(subtitle, 150)):
            draw.text((pad, 126 + i * 34), line, font=font(26), fill=(95, 95, 103))
    _draw_legend(canvas, pad + map_width + 50, top + 35, legend_width, channels, notes)

    box = content_box(canvas)
    margin = 55
    return canvas.crop((max(0, box[0] - margin), max(0, box[1] - margin),
                        min(canvas.width, box[2] + margin), min(canvas.height, box[3] + margin)))


def detail_page(map_image: Image.Image, boxes: dict[str, tuple[int, int, int, int]],
                title: str, subtitle: str | None = None,
                columns: int = 2, cell: int = 1020, pad: int = 70) -> Image.Image:
    """Lays out one magnified crop per group, at the export's own resolution."""
    items = list(boxes.items())
    rows = max(1, math.ceil(len(items) / columns))
    width = pad + columns * (cell + 50) + pad
    top = 250 if subtitle else 190
    canvas = Image.new("RGB", (width, top + rows * (cell + 90) + pad), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((pad, 56), title, font=font(52, True), fill=INK)
    if subtitle:
        for i, line in enumerate(_wrap(subtitle, 150)):
            draw.text((pad, 124 + i * 34), line, font=font(26), fill=(95, 95, 103))
    source = map_image.convert("RGB")
    for i, (name, box) in enumerate(items):
        left, top_, right, bottom = box
        crop = source.crop((max(0, left), max(0, top_),
                            min(source.width, right), min(source.height, bottom)))
        if crop.width < 2 or crop.height < 2:
            continue
        scale = min(cell / crop.width, cell / crop.height)
        crop = crop.resize((max(1, int(crop.width * scale)), max(1, int(crop.height * scale))),
                           Image.LANCZOS)
        cx = pad + (i % columns) * (cell + 50)
        cy = top + (i // columns) * (cell + 90)
        tile = Image.new("RGB", (cell, cell), "white")
        tile.paste(crop, ((cell - crop.width) // 2, (cell - crop.height) // 2))
        canvas.paste(tile, (cx, cy))
        draw.rectangle([cx, cy, cx + cell, cy + cell], outline=RULE, width=2)
        draw.text((cx, cy + cell + 16), str(name), font=font(30, True), fill=(30, 30, 34))
    return canvas


def write(pages: Iterable[Image.Image], base: Path, dpi: int = 300) -> dict[str, str]:
    """Writes the first page as PNG and every page into one PDF."""
    pages = list(pages)
    png = base.with_suffix(".png")
    pdf = base.with_suffix(".pdf")
    pages[0].save(png, dpi=(dpi, dpi))
    pages[0].save(pdf, "PDF", resolution=float(dpi),
                  save_all=len(pages) > 1, append_images=pages[1:])
    return {"png": str(png), "pdf": str(pdf), "pages": len(pages)}
