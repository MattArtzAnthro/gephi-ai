"""Parse Gephi GEXF exports and serve the sigma.js MCP App viewer.

GEXF spec coverage (gephi/gexf): namespace-agnostic, viz position/size/color
(with alpha), node attributes including attribute-level <default> values.
Consciously unsupported for now: per-edge type overrides in mixed graphs,
viz:shape, hierarchical (nested) nodes, and dynamic graphs (spells/timestamps
— a time-aware viewer is a candidate future feature).
"""
from importlib import resources

import defusedxml.ElementTree as ET  # noqa: N817 — stdlib-conventional alias


def _local(tag: str) -> str:
    """Strip any XML namespace: '{http://gexf.net/1.3}node' -> 'node'."""
    return tag.rsplit("}", 1)[-1]


def _children(elem, name):
    return [c for c in elem.iter() if _local(c.tag) == name]


def _time(value):
    """Coerce a GEXF time value: float when possible, else the raw string."""
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return value


def _spells(elem):
    """GEXF dynamics: [[start, end], ...] from start/end attrs or <spells>, else None."""
    spells = []
    for c in elem:
        if _local(c.tag) == "spells":
            for sp in c:
                if _local(sp.tag) == "spell":
                    spells.append([_time(sp.get("start")), _time(sp.get("end"))])
    if not spells and (elem.get("start") is not None or elem.get("end") is not None):
        spells.append([_time(elem.get("start")), _time(elem.get("end"))])
    return spells or None


def parse_gexf(path: str, max_nodes: int = 1500) -> dict:
    root = ET.parse(path).getroot()
    graph_el = _children(root, "graph")[0]
    directed = graph_el.get("defaultedgetype", "undirected") == "directed"

    # Attribute id -> title map plus spec-mandated defaults (node attributes only).
    titles, defaults = {}, {}
    for attrs_el in _children(graph_el, "attributes"):
        if attrs_el.get("class") == "node":
            for a in _children(attrs_el, "attribute"):
                title = a.get("title", a.get("id"))
                titles[a.get("id")] = title
                for child in a:
                    if _local(child.tag) == "default" and child.text is not None:
                        defaults[title] = child.text

    nodes = []
    for n in _children(graph_el, "node"):
        node = {
            "key": n.get("id"),
            "label": n.get("label") or n.get("id"),
            "x": 0.0, "y": 0.0, "size": 5.0, "color": "#999999",
            "attributes": {},
        }
        for c in n:
            name = _local(c.tag)
            if name == "position":
                node["x"] = float(c.get("x", 0))
                # Both Gephi and sigma v3 render y-up, so GEXF y passes through
                # unchanged (verified against Gephi's own renders).
                node["y"] = float(c.get("y", 0))
            elif name == "color":
                r, g, b = c.get("r", 153), c.get("g", 153), c.get("b", 153)
                a = c.get("a")
                node["color"] = (f'rgba({r},{g},{b},{a})' if a is not None
                                 else f'rgb({r},{g},{b})')
            elif name == "size":
                node["size"] = float(c.get("value", 5))
            elif name == "attvalues":
                for av in c:
                    key = titles.get(av.get("for"), av.get("for"))
                    node["attributes"][key] = av.get("value")
        for title, value in defaults.items():
            node["attributes"].setdefault(title, value)
        node["spells"] = _spells(n)
        nodes.append(node)

    edges = []
    for e in _children(graph_el, "edge"):
        color = None
        for c in e:
            if _local(c.tag) == "color":
                color = f'rgb({c.get("r", 153)},{c.get("g", 153)},{c.get("b", 153)})'
        edges.append({
            "source": e.get("source"), "target": e.get("target"),
            "size": float(e.get("weight", 1)), "color": color,
            "spells": _spells(e),
        })

    node_count_total, edge_count_total = len(nodes), len(edges)
    truncated = len(nodes) > max_nodes
    if truncated:
        degree: dict[str, int] = {}
        for e in edges:
            degree[e["source"]] = degree.get(e["source"], 0) + 1
            degree[e["target"]] = degree.get(e["target"], 0) + 1
        nodes.sort(key=lambda n: degree.get(n["key"], 0), reverse=True)
        nodes = nodes[:max_nodes]
        kept = {n["key"] for n in nodes}
        edges = [e for e in edges if e["source"] in kept and e["target"] in kept]

    times = [t for item in nodes + edges for sp in (item.get("spells") or [])
             for t in sp if isinstance(t, (int, float))]
    return {
        "nodes": nodes, "edges": edges, "directed": directed,
        "node_count_total": node_count_total,
        "edge_count_total": edge_count_total, "truncated": truncated,
        "dynamic": any(item.get("spells") for item in nodes + edges),
        "time_min": min(times) if times else None,
        "time_max": max(times) if times else None,
    }


def build_app_html() -> str:
    """The static MCP App page (ui://gephi/graph-view).

    Fully self-contained: vendored graphology + sigma.js are inlined so the
    sandboxed iframe needs no network. Graph data arrives at runtime via the
    host's ui/notifications/tool-result message, never baked into the HTML.
    """
    pkg = resources.files("gephi_mcp_viewer")
    template = (pkg / "template.html").read_text(encoding="utf-8")
    graphology_js = (pkg / "assets" / "graphology.umd.min.js").read_text(encoding="utf-8")
    sigma_js = (pkg / "assets" / "sigma.min.js").read_text(encoding="utf-8")
    return (template
            .replace("__GRAPHOLOGY_JS__", graphology_js)
            .replace("__SIGMA_JS__", sigma_js))


def _luminance(color: str) -> float:
    """Approximate relative luminance (0-1) of 'rgb(r,g,b)' or '#rrggbb' strings."""
    try:
        if color.startswith("rgb"):
            r, g, b = (int(v) for v in color[color.index("(") + 1:color.index(")")].split(","))
        elif color.startswith("#") and len(color) >= 7:
            r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        else:
            return 0.5
    except ValueError:
        return 0.5
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


def analyze_graph(graph: dict, partition_column: str | None = None) -> dict:
    """Visual-design diagnostics over a parsed graph (see parse_gexf).

    Checks the things that make renders unreadable: invisible node sizes,
    near-white colors on white exports, gradient-instead-of-categorical color
    use, layout extent vs export aspect — and, when partition_column is given,
    whether that grouping is topologically real (within-group edge share vs
    the random baseline) or would mislead if used for coloring.
    """
    nodes, edges = graph["nodes"], graph["edges"]
    warnings = []

    sizes = sorted(n["size"] for n in nodes) or [0.0]
    size_info = {"min": sizes[0], "median": sizes[len(sizes) // 2], "max": sizes[-1],
                 "flat": sizes[0] == sizes[-1]}
    if size_info["min"] < 8:
        warnings.append(
            f"smallest node size is {size_info['min']:g}; sizes under 8 render as "
            "invisible specks — re-run gephi_size_by_ranking with min_size >= 10")
    if size_info["flat"] and len(nodes) > 1:
        warnings.append("all nodes are the same size; size by degree (or another "
                        "ranking) to create visual hierarchy")

    colors = {n["color"] for n in nodes}
    near_white = [c for c in colors if _luminance(c) > 0.85]
    color_info = {"distinct": len(colors), "near_white": len(near_white)}
    if near_white:
        warnings.append(
            f"{len(near_white)} node color(s) are near-white and will be invisible "
            "on white exports — use the validated palette (see gephi_color_by_partition)")
    if len(colors) > 12:
        warnings.append(
            f"{len(colors)} distinct node colors — this looks like a continuous "
            "gradient; if color should show categories, use a categorical palette "
            "(and never double-encode the variable already shown by size)")

    xs = [n["x"] for n in nodes] or [0.0]
    ys = [n["y"] for n in nodes] or [0.0]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    aspect = (w / h) if h else 1.0
    long_side = 2000
    if aspect >= 1:
        sug = {"width": long_side, "height": max(800, int(long_side / max(aspect, 0.1) / 10) * 10)}
    else:
        sug = {"width": max(800, int(long_side * aspect / 10) * 10), "height": long_side}
    extent = {"width": round(w, 1), "height": round(h, 1), "aspect": round(aspect, 2),
              "suggested_export": sug}
    # Node presence: when the biggest node is under ~1% of the extent's long
    # side, exports show specks in whitespace (found live: LinLog with a high
    # scalingRatio exploded a 500-node layout to 17k units against size-60 nodes).
    long_side = max(w, h, 1.0)
    if len(nodes) > 1 and sizes[-1] / long_side < 0.01:
        warnings.append(
            f"layout is over-spread: largest node ({sizes[-1]:g}) is under 1% of the "
            f"layout extent ({long_side:g}) — nodes will render as specks; lower "
            "scalingRatio and rerun the layout, or raise node sizes")

    result = {
        "nodes": len(nodes), "edges": len(edges),
        "directed": graph.get("directed", False),
        "sizes": size_info, "colors": color_info, "extent": extent,
        "warnings": warnings,
    }

    if partition_column:
        group = {n["key"]: n["attributes"].get(partition_column) for n in nodes}
        counted = [g for g in group.values() if g is not None]
        shares = {}
        for g in counted:
            shares[g] = shares.get(g, 0) + 1
        n_total = len(counted) or 1
        baseline = sum((c / n_total) ** 2 for c in shares.values())
        within = sum(1 for e in edges
                     if group.get(e["source"]) is not None
                     and group.get(e["source"]) == group.get(e["target"]))
        fraction = within / len(edges) if edges else 0.0
        ratio = fraction / baseline if baseline else 0.0
        if fraction >= 0.6 or ratio >= 3:
            verdict = "strong"
        elif ratio >= 1.5:
            verdict = "weak"
        else:
            verdict = "none"
            warnings.append(
                f"'{partition_column}' does not match the topology (within-group edge "
                f"share {fraction:.0%} vs random baseline {baseline:.0%}) — coloring by "
                "it would be misleading; compute real communities with "
                "gephi_compute_modularity instead")
        result["partition"] = {
            "column": partition_column, "groups": len(shares),
            "within_fraction": round(fraction, 3),
            "random_baseline": round(baseline, 3),
            "ratio_vs_random": round(ratio, 2), "verdict": verdict,
        }

    return result


def pick_cluster_hubs(graph: dict, partition_column: str, prefer: str = "degree") -> dict:
    """Most salient node per partition value: {group_value: node_key}.

    prefer="degree" ranks by degree then rendered size; prefer="size" ranks by
    rendered size then degree (use when captions should sit on the visually
    biggest circle). Lexicographic key breaks remaining ties, so the result is
    deterministic. Nodes without the attribute are ignored.
    """
    degree: dict[str, int] = {}
    for e in graph["edges"]:
        degree[e["source"]] = degree.get(e["source"], 0) + 1
        degree[e["target"]] = degree.get(e["target"], 0) + 1
    best: dict = {}
    for n in graph["nodes"]:
        g = n["attributes"].get(partition_column)
        if g is None:
            continue
        d, sz = degree.get(n["key"], 0), n["size"]
        score = (sz, d, n["key"]) if prefer == "size" else (d, sz, n["key"])
        if g not in best or score > best[g][0]:
            best[g] = (score, n["key"])
    return {g: key for g, (_, key) in best.items()}
