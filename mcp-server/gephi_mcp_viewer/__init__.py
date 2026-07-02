"""Build a self-contained sigma.js HTML view from a Gephi GEXF export."""
import json
from importlib import resources

import defusedxml.ElementTree as ET  # noqa: N817 — stdlib-conventional alias


def _local(tag: str) -> str:
    """Strip any XML namespace: '{http://gexf.net/1.3}node' -> 'node'."""
    return tag.rsplit("}", 1)[-1]


def _children(elem, name):
    return [c for c in elem.iter() if _local(c.tag) == name]


def parse_gexf(path: str, max_nodes: int = 1500) -> dict:
    root = ET.parse(path).getroot()
    graph_el = _children(root, "graph")[0]
    directed = graph_el.get("defaultedgetype", "undirected") == "directed"

    # Attribute id -> title map (node attributes only).
    titles = {}
    for attrs_el in _children(graph_el, "attributes"):
        if attrs_el.get("class") == "node":
            for a in _children(attrs_el, "attribute"):
                titles[a.get("id")] = a.get("title", a.get("id"))

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
                node["color"] = f'rgb({c.get("r", 153)},{c.get("g", 153)},{c.get("b", 153)})'
            elif name == "size":
                node["size"] = float(c.get("value", 5))
            elif name == "attvalues":
                for av in c:
                    key = titles.get(av.get("for"), av.get("for"))
                    node["attributes"][key] = av.get("value")
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

    return {
        "nodes": nodes, "edges": edges, "directed": directed,
        "node_count_total": node_count_total,
        "edge_count_total": edge_count_total, "truncated": truncated,
    }


def build_html(graph: dict, title: str = "Network view") -> str:
    pkg = resources.files("gephi_mcp_viewer")
    template = (pkg / "template.html").read_text(encoding="utf-8")
    graphology_js = (pkg / "assets" / "graphology.umd.min.js").read_text(encoding="utf-8")
    sigma_js = (pkg / "assets" / "sigma.min.js").read_text(encoding="utf-8")

    safe_title = (title.replace("&", "&amp;").replace("<", "&lt;")
                  .replace(">", "&gt;").replace('"', "&quot;"))
    shown = len(graph["nodes"])
    if graph["truncated"]:
        meta = f'{shown} of {graph["node_count_total"]} nodes, {len(graph["edges"])} edges'
    else:
        meta = f'{graph["node_count_total"]} nodes, {graph["edge_count_total"]} edges'

    # str.replace, not str.format: the JS is full of braces.
    return (template
            .replace("__TITLE__", safe_title)
            .replace("__META__", meta)
            .replace("__GRAPHOLOGY_JS__", graphology_js)
            .replace("__SIGMA_JS__", sigma_js)
            .replace("__GRAPH_DATA__", json.dumps(graph)))
