"""Draw a legend for a map, from the mappings that produced it.

An exported Gephi image is a field of coloured circles with no key, so it cannot be read unless
its author is present to explain it. Gephi has never shipped a legend: gephi/gephi#511 asked for
one in 2012 and the request has been repeated in three other repositories since. The obstacle in
the application is that a legend has to be reconstructed from the appearance model after the fact,
and the intent behind a mapping is not stored anywhere.

That obstacle does not apply to a caller that made the mapping itself. Colouring by a partition is
a decision with a column and a palette in it, and once recorded a legend is a transcription of
choices rather than an inference from pixels.

Output is SVG. It is text, so no imaging dependency is needed, and it is the format a figure
destined for print wants. Both a spliceable fragment and a standalone document are produced from
the same drawing code.

Everything written here comes from user data: column names, group labels, and colours. Text is
escaped and colours are validated against a strict pattern, because an unescaped value does not
merely look wrong, it voids the whole document.
"""

from __future__ import annotations

import re
from typing import Any
from xml.sax.saxutils import escape, quoteattr

#: A colour is only ever written into an attribute if it looks exactly like one. Anything else is
#: replaced, since a rejected colour costs a grey swatch while an accepted one can void the SVG.
_COLOUR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$|^[a-zA-Z]{1,20}$")
_FALLBACK_COLOUR = "#999999"

_PAD = 12
_ROW = 20
_SWATCH = 12
_TITLE_GAP = 22
_BLOCK_GAP = 10
_WIDTH = 240
_FONT = "font-family=\"Helvetica,Arial,sans-serif\""


def _colour(value: Any) -> str:
    text = str(value or "")
    return text if _COLOUR.match(text) else _FALLBACK_COLOUR


def _text(x: float, y: float, body: Any, *, size: int = 11, weight: str = "normal") -> str:
    return (f'<text x="{x:g}" y="{y:g}" font-size="{size}" font-weight="{weight}" '
            f'{_FONT} fill="#222222">{escape(str(body))}</text>')


def _block_height(item: dict[str, Any]) -> float:
    if item.get("groups"):
        return _TITLE_GAP + _ROW * len(item["groups"])
    return _TITLE_GAP + _ROW


def _draw_block(item: dict[str, Any], y: float, gradient_id: str) -> tuple[str, str]:
    """Return the block's SVG and any <defs> content it needs."""
    parts = [_text(_PAD, y + 12, f'{item.get("column", "")}  ({item.get("channel", "")})',
                   size=12, weight="bold")]
    defs = ""
    row = y + _TITLE_GAP

    if item.get("groups"):
        for label, colour in item["groups"].items():
            parts.append(
                f'<rect x="{_PAD}" y="{row:g}" width="{_SWATCH}" height="{_SWATCH}" rx="2" '
                f'fill={quoteattr(_colour(colour))} stroke="#00000022"/>')
            parts.append(_text(_PAD + _SWATCH + 8, row + _SWATCH - 2, label))
            row += _ROW

    elif item.get("palette"):
        low, high = _colour(item["palette"][0]), _colour(item["palette"][-1])
        defs = (f'<linearGradient id="{gradient_id}" x1="0" x2="1">'
                f'<stop offset="0" stop-color={quoteattr(low)}/>'
                f'<stop offset="1" stop-color={quoteattr(high)}/></linearGradient>')
        parts.append(f'<rect x="{_PAD}" y="{row:g}" width="{_WIDTH - 2 * _PAD}" height="10" '
                     f'rx="2" fill="url(#{gradient_id})" stroke="#00000022"/>')
        parts.append(_text(_PAD, row + 24, "low"))
        parts.append(f'<text x="{_WIDTH - _PAD:g}" y="{row + 24:g}" font-size="11" '
                     f'text-anchor="end" {_FONT} fill="#222222">high</text>')

    elif item.get("range"):
        low, high = item["range"]
        parts.append(f'<circle cx="{_PAD + 5}" cy="{row + 7:g}" r="4" fill="#bbbbbb" '
                     f'stroke="#00000033"/>')
        parts.append(f'<circle cx="{_PAD + 34}" cy="{row + 7:g}" r="9" fill="#bbbbbb" '
                     f'stroke="#00000033"/>')
        parts.append(_text(_PAD + 50, row + 11, f"{low} to {high}"))

    return "\n".join(parts), defs


def _draw(items: list[dict[str, Any]]) -> tuple[str, float]:
    blocks, defs, y = [], [], float(_PAD)
    for index, item in enumerate(items):
        svg, gradient = _draw_block(item, y, f"gephiLegendGradient{index}")
        blocks.append(svg)
        if gradient:
            defs.append(gradient)
        y += _block_height(item) + _BLOCK_GAP
    body = ""
    if defs:
        body += "<defs>" + "".join(defs) + "</defs>\n"
    body += "\n".join(blocks)
    return body, y + _PAD - _BLOCK_GAP


def legend_fragment(items: list[dict[str, Any]] | None) -> str | None:
    """A `<g>` element ready to splice into an exported SVG, or None if there is nothing to say.

    Returning None rather than an empty box matters: a legend with no entries tells a reader the
    map encodes nothing, which is a stronger and usually false claim than saying nothing at all.
    """
    if not items:
        return None
    body, height = _draw(items)
    return (f'<g class="gephi-ai-legend" transform="translate(0,0)">\n'
            f'<rect x="0" y="0" width="{_WIDTH}" height="{height:g}" rx="4" '
            f'fill="#ffffffcc" stroke="#00000022"/>\n{body}\n</g>')


def legend_document(items: list[dict[str, Any]] | None) -> str | None:
    """A standalone SVG holding just the legend, for pairing with a raster export."""
    if not items:
        return None
    body, height = _draw(items)
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH}" height="{height:g}" '
            f'viewBox="0 0 {_WIDTH} {height:g}">\n'
            f'<rect x="0" y="0" width="{_WIDTH}" height="{height:g}" fill="#ffffff"/>\n'
            f'{body}\n</svg>\n')
