"""gephi_export_figure end to end against a stand-in Gephi.

The stand-in answers the two requests the tool makes: it renders a PNG the way Gephi's exporter
does (node centres fitted inside a margin, y counting downwards) and returns the same graph as
inline GEXF. That is enough to drive the whole tool, including the detail page whose crop boxes
must line up with the drawn nodes.
"""

from __future__ import annotations

import json
import math

import pytest
from PIL import Image, ImageDraw

import gephi_mcp

BLUE = (0, 114, 178)
AMBER = (230, 159, 0)


def _nodes():
    out = []
    for i in range(40):
        angle = i / 40 * 2 * math.pi
        side = "left" if i % 2 == 0 else "right"
        cx = -100 if side == "left" else 100
        out.append({"id": f"n{i}", "x": cx + 30 * math.cos(angle), "y": 30 * math.sin(angle),
                    "size": 4.0, "side": side, "rgb": BLUE if side == "left" else AMBER})
    return out


def _gexf(nodes):
    body = "".join(
        f'<node id="{n["id"]}" label="{n["id"]}"><attvalues>'
        f'<attvalue for="0" value="{n["side"]}"/></attvalues>'
        f'<viz:color r="{n["rgb"][0]}" g="{n["rgb"][1]}" b="{n["rgb"][2]}"/>'
        f'<viz:position x="{n["x"]}" y="{n["y"]}" z="0.0"/><viz:size value="{n["size"]}"/></node>'
        for n in nodes)
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<gexf xmlns="http://gexf.net/1.3" xmlns:viz="http://gexf.net/1.3/viz" version="1.3">'
            '<graph defaultedgetype="undirected">'
            '<attributes class="node"><attribute id="0" title="side" type="string"/></attributes>'
            f'<nodes>{body}</nodes><edges/></graph></gexf>')


def _render(nodes, path, size=(800, 800), margin=40):
    img = Image.new("RGB", size, (255, 255, 255))
    draw = ImageDraw.Draw(img)
    xs = [n["x"] for n in nodes]
    ys = [n["y"] for n in nodes]
    w, h = size[0] - 2 * margin, size[1] - 2 * margin
    scale = (w / (max(xs) - min(xs)) + h / (max(ys) - min(ys))) / 2
    for n in nodes:
        px = margin + (n["x"] - min(xs)) / (max(xs) - min(xs)) * w
        py = margin + (max(ys) - n["y"]) / (max(ys) - min(ys)) * h
        r = n["size"] / 2 * scale
        draw.ellipse([px - r, py - r, px + r, py + r], fill=n["rgb"])
    img.save(path)


class FakeGephi:
    """Answers /export/png by drawing the graph and /export/gexf with the same graph."""

    def __init__(self, nodes, png_ok=True, write_png=True, gexf_ok=True):
        self.nodes = nodes
        self.png_ok = png_ok
        self.write_png = write_png
        self.gexf_ok = gexf_ok
        self.calls = []

    async def __call__(self, method, endpoint, params=None, json_data=None, timeout=None):
        self.calls.append(endpoint)
        if endpoint == "/export/png":
            if not self.png_ok:
                return {"success": False, "error": "Preview export failed"}
            if self.write_png:
                _render(self.nodes, json_data["file"])
            return {"success": True}
        if endpoint == "/export/gexf":
            if not self.gexf_ok:
                return {"success": False, "error": "no project"}
            return {"success": True, "content": _gexf(self.nodes), "view": "visible"}
        return {"success": True}


@pytest.fixture
def gephi(monkeypatch):
    fake = FakeGephi(_nodes())
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)
    gephi_mcp.LEDGER.reset()
    return fake


async def figure(**kwargs):
    return json.loads(await gephi_mcp.gephi_export_figure(**kwargs))


async def test_a_figure_with_a_partition_key_and_a_detail_page_is_written(gephi, tmp_path):
    out = await figure(file=str(tmp_path / "fig.pdf"), title="Two sides",
                       partition_column="side", detail_column="side",
                       notes=["Disc placement within a side means nothing."])

    assert out["success"], out
    assert out["pages"] == 2, out
    assert (tmp_path / "fig.pdf").exists() and (tmp_path / "fig.png").exists()
    colour = out["channels"][0]
    assert colour["column"] == "side"
    assert colour["groups"] == {"left": "#0072b2", "right": "#e69f00"}
    assert "reminder" not in out


async def test_a_figure_without_notes_carries_a_reminder(gephi, tmp_path):
    out = await figure(file=str(tmp_path / "fig"), title="Two sides", partition_column="side")

    assert out["success"], out
    assert "No notes were given" in out["reminder"]


async def test_nothing_to_key_is_refused_rather_than_drawn_with_an_empty_legend(gephi, tmp_path):
    out = await figure(file=str(tmp_path / "fig"), title="Two sides")

    assert out["success"] is False
    assert "Nothing to put in a legend" in out["error"]
    assert not list(tmp_path.iterdir())


async def test_a_partition_that_carries_no_colours_is_left_out_with_a_warning(gephi, tmp_path):
    extra = [{"channel": "shape", "column": "side",
              "items": [{"label": "left", "glyph": "square"}]}]
    out = await figure(file=str(tmp_path / "fig"), title="t", partition_column="missing",
                       extra_channels=extra)

    assert out["success"], out
    assert any("missing" in w for w in out["warnings"])
    assert [c["channel"] for c in out["channels"]] == ["shape"]


async def test_an_unknown_glyph_is_refused(gephi, tmp_path):
    extra = [{"channel": "shape", "items": [{"label": "x", "glyph": "blob"}]}]
    out = await figure(file=str(tmp_path / "fig"), title="t", extra_channels=extra)

    assert out["success"] is False
    assert "blob" in out["error"]


async def test_a_detail_column_that_does_not_exist_drops_the_page_and_says_so(gephi, tmp_path):
    out = await figure(file=str(tmp_path / "fig"), title="t", partition_column="side",
                       detail_column="region")

    assert out["success"], out
    assert out["pages"] == 1
    assert any("no node column named 'region'" in w for w in out["warnings"])


async def test_a_failed_map_export_is_reported_with_gephis_answer(gephi, tmp_path):
    gephi.png_ok = False
    out = await figure(file=str(tmp_path / "fig"), title="t", partition_column="side")

    assert out["success"] is False
    assert out["detail"]["error"] == "Preview export failed"


async def test_a_success_with_no_file_is_not_trusted(gephi, tmp_path):
    gephi.write_png = False
    out = await figure(file=str(tmp_path / "fig"), title="t", partition_column="side")

    assert out["success"] is False
    assert "wrote no file" in out["error"]


async def test_without_the_graph_the_detail_page_is_skipped(gephi, tmp_path):
    gephi.gexf_ok = False
    extra = [{"channel": "shape", "items": [{"label": "x", "glyph": "circle"}]}]
    out = await figure(file=str(tmp_path / "fig"), title="t", extra_channels=extra,
                       detail_column="side")

    assert out["success"], out
    assert any("could not be read back" in w for w in out["warnings"])


def test_a_misaligned_map_drops_the_detail_page():
    nodes = _nodes()
    graph = _parsed(nodes)
    blank = Image.new("RGB", (800, 800), (255, 255, 255))
    ImageDraw.Draw(blank).rectangle([10, 10, 790, 790], outline=(0, 0, 0))

    page, problem = gephi_mcp._detail_page(blank, graph, "side")

    assert page is None
    assert "could not be trusted" in problem


def test_a_layout_with_no_extent_has_no_detail_page():
    nodes = [dict(n, x=0.0, y=0.0) for n in _nodes()]
    graph = _parsed(nodes)
    image = Image.new("RGB", (800, 800), (255, 255, 255))
    ImageDraw.Draw(image).ellipse([390, 390, 410, 410], fill=BLUE)

    page, problem = gephi_mcp._detail_page(image, graph, "side")

    assert page is None
    assert "no extent" in problem


def _parsed(nodes):
    from gephi_mcp_viewer import parse_gexf

    return parse_gexf(_gexf(nodes), max_nodes=10**9)
