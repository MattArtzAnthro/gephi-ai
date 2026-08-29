"""Tests for composing a map and its legend into one figure."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import figure  # noqa: E402


def _map_image(nodes, size=(800, 800), margin=40, background=(255, 255, 255)):
    """Render a stand-in export the way Gephi does it.

    Node centres are fitted inside the margin and each node is drawn with a
    radius derived from its own size, so the non-background area runs half a
    node past the outermost centre exactly as a real export does.
    """
    img = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(img)
    xs = [n["x"] for n in nodes]
    ys = [n["y"] for n in nodes]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    w = size[0] - 2 * margin
    h = size[1] - 2 * margin
    scale = (w / (max_x - min_x) + h / (max_y - min_y)) / 2
    for n in nodes:
        px = margin + (n["x"] - min_x) / (max_x - min_x) * w
        py = margin + (max_y - n["y"]) / (max_y - min_y) * h
        r = float(n.get("size", 0.0)) / 2 * scale
        draw.ellipse([px - r, py - r, px + r, py + r], fill=(40, 90, 180))
    return img


def _nodes():
    out = []
    for i in range(60):
        angle = i / 60 * 2 * math.pi
        group = "left" if i % 2 == 0 else "right"
        cx = -100 if group == "left" else 100
        out.append({"x": cx + 30 * math.cos(angle), "y": 30 * math.sin(angle),
                    "size": 4.0, "attributes": {"side": group}})
    return out


# ── glyphs ────────────────────────────────────────────────────────────────

def test_every_named_glyph_can_be_drawn():
    for name in figure.GLYPHS:
        points = figure.glyph_outline(name, 50, 50, 40)
        if name == "circle":
            assert points is None
        else:
            assert points and len(points) >= 3


def test_no_glyph_escapes_the_circle_it_stands_for():
    # A swatch wider than the node it represents misreports the encoding.
    for name in figure.GLYPHS:
        points = figure.glyph_outline(name, 0, 0, 40) or []
        for x, y in points:
            assert math.hypot(x, y) <= 20 + 1e-6, f"{name} vertex outside the circle"


def test_an_unknown_glyph_is_rejected_rather_than_silently_drawn_as_a_circle():
    with pytest.raises(ValueError) as exc:
        figure.glyph_outline("hexagram", 0, 0, 10)
    assert "hexagram" in str(exc.value)


# ── the coordinate transform, which is the risky part ─────────────────────

def test_the_transform_recovers_pixel_positions_from_graph_coordinates():
    nodes = _nodes()
    img = _map_image(nodes)
    to_pixel = figure.position_transform(nodes, figure.content_box(img))

    assert to_pixel is not None
    assert figure.transform_hit_rate(img, nodes, to_pixel) > 0.9


def test_the_transform_flips_y_because_gexf_counts_upwards_and_images_downwards():
    nodes = _nodes()
    img = _map_image(nodes)
    to_pixel = figure.position_transform(nodes, figure.content_box(img))

    top = max(nodes, key=lambda n: n["y"])
    bottom = min(nodes, key=lambda n: n["y"])
    assert to_pixel(top["x"], top["y"])[1] < to_pixel(bottom["x"], bottom["y"])[1]


def test_a_wrong_transform_is_caught_instead_of_producing_plausible_crops():
    # The guard exists because a misaligned crop still looks like a real one.
    nodes = _nodes()
    img = _map_image(nodes)
    shifted = lambda x, y: (10.0, 10.0)  # noqa: E731 — always the blank corner

    assert figure.transform_hit_rate(img, nodes, shifted) < 0.5


def test_a_degenerate_layout_yields_no_transform():
    flat = [{"x": 5.0, "y": 5.0, "size": 4.0, "attributes": {}} for _ in range(10)]
    assert figure.position_transform(flat, (0, 0, 100, 100)) is None
    assert figure.position_transform([], (0, 0, 100, 100)) is None


def test_group_boxes_separate_the_two_sides():
    nodes = _nodes()
    img = _map_image(nodes)
    to_pixel = figure.position_transform(nodes, figure.content_box(img))
    boxes = figure.group_boxes(nodes, "side", to_pixel, pad=0)

    assert set(boxes) == {"left", "right"}
    assert boxes["left"][2] < boxes["right"][0], "the two groups must not overlap"


def test_nodes_with_no_value_are_left_out_of_every_box():
    nodes = _nodes() + [{"x": 0.0, "y": 0.0, "size": 4.0, "attributes": {}}]
    img = _map_image(nodes)
    to_pixel = figure.position_transform(nodes, figure.content_box(img))
    boxes = figure.group_boxes(nodes, "side", to_pixel, pad=0)

    assert set(boxes) == {"left", "right"}


# ── composition ───────────────────────────────────────────────────────────

def test_the_composed_figure_is_wider_than_the_map_because_it_carries_a_legend():
    nodes = _nodes()
    img = _map_image(nodes)
    out = figure.compose(img, "A title", "a subtitle",
                         [{"channel": "node colour", "column": "side",
                           "groups": {"left": "#2a78d6", "right": "#e34948"}}],
                         ["disc placement means nothing"])

    assert out.width > out.height * 0.9
    assert out.width > 2200


def test_an_extra_channel_is_drawn_with_its_declared_glyphs():
    nodes = _nodes()
    img = _map_image(nodes)
    plain = figure.compose(img, "T", None,
                           [{"channel": "node colour", "groups": {"a": "#000000"}}], [])
    with_shapes = figure.compose(
        img, "T", None,
        [{"channel": "node colour", "groups": {"a": "#000000"}},
         {"channel": "shape", "column": "kind",
          "items": [{"label": "Person", "glyph": "circle"},
                    {"label": "Org", "glyph": "square"}]}], [])

    from PIL import ImageChops
    assert with_shapes.size == plain.size, "the map still sets the canvas size"
    assert ImageChops.difference(with_shapes, plain).getbbox() is not None, \
        "declaring a shape channel must actually draw glyphs into the key"


def test_writing_produces_both_a_png_and_a_pdf(tmp_path):
    nodes = _nodes()
    img = _map_image(nodes)
    page = figure.compose(img, "T", None,
                          [{"channel": "node colour", "groups": {"a": "#123456"}}], [])

    written = figure.write([page], tmp_path / "fig")

    assert Path(written["png"]).exists()
    assert Path(written["pdf"]).exists()
    assert written["pages"] == 1


def test_a_detail_page_becomes_a_second_pdf_page(tmp_path):
    nodes = _nodes()
    img = _map_image(nodes)
    to_pixel = figure.position_transform(nodes, figure.content_box(img))
    boxes = figure.group_boxes(nodes, "side", to_pixel)
    page1 = figure.compose(img, "T", None,
                           [{"channel": "node colour", "groups": {"a": "#123456"}}], [])
    page2 = figure.detail_page(img, boxes, "Detail")

    written = figure.write([page1, page2], tmp_path / "fig")

    assert written["pages"] == 2
    assert Path(written["pdf"]).stat().st_size > 0
