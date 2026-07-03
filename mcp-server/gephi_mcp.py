"""
Gephi MCP Server - Model Context Protocol server for controlling Gephi Desktop

This MCP server enables LLMs to interact with a running Gephi Desktop instance
through the Gephi MCP Plugin's HTTP API.

Each tool exposes typed parameters, so MCP clients receive a precise JSON schema
per tool (field names, types, and which are optional) rather than an opaque blob.

Claude Code Skill:
    This server is paired with a Claude Code skill that provides workflows,
    best practices, and visualization guidelines for using these tools.
    See: claude-plugin/skills/gephi/SKILL.md

Developed by Matt Artz (https://www.mattartz.me)
"""

import asyncio
import contextlib
import json
import logging
import os
import tempfile
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent

import gephi_mcp_viewer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gephi_mcp")

# Both are overridable via environment so the server can target a non-default
# Gephi host/port or a slower machine without code changes.
GEPHI_API_URL = os.environ.get("GEPHI_API_URL", "http://127.0.0.1:8080")
REQUEST_TIMEOUT = float(os.environ.get("GEPHI_REQUEST_TIMEOUT", "60.0"))

mcp = FastMCP("gephi_mcp")


# ==================== HTTP Client ====================

class GephiClient:
    def __init__(self, base_url: str = GEPHI_API_URL):
        self.base_url = base_url.rstrip("/")
        self.timeout = REQUEST_TIMEOUT

    async def request(self, method: str, endpoint: str,
                      params: dict[str, Any] | None = None,
                      json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method=method, url=url, params=params, json=json_data)
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError:
            return {"success": False, "error": f"Cannot connect to Gephi at {self.base_url}. Ensure Gephi is running with the MCP plugin installed."}
        except httpx.TimeoutException:
            return {"success": False, "error": "Request timed out. The operation may still be running in Gephi."}
        except httpx.HTTPStatusError as e:
            try:
                return e.response.json()
            except Exception:
                return {"success": False, "error": f"HTTP {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            return {"success": False, "error": f"Request failed: {str(e)}"}

gephi = GephiClient()


# ==================== Helpers ====================

def fmt(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2)


def _body(**kwargs: Any) -> dict[str, Any]:
    """Build a request body, dropping any keys whose value is None so the Gephi
    plugin's own defaults apply for omitted optional parameters."""
    return {k: v for k, v in kwargs.items() if v is not None}


# ==================== MCP Tools ====================

# ─── Health ───────────────────────────────────────────────────

@mcp.tool(name="gephi_health_check")
async def gephi_health_check() -> str:
    """Check if Gephi Desktop is running and the MCP plugin is accessible."""
    return fmt(await gephi.request("GET", "/health"))


# ─── Project ─────────────────────────────────────────────────

@mcp.tool(name="gephi_create_project")
async def gephi_create_project(name: str = "New Project") -> str:
    """Create a new empty Gephi project/workspace."""
    return fmt(await gephi.request("POST", "/project/new", json_data={"name": name}))

@mcp.tool(name="gephi_open_project")
async def gephi_open_project(file: str) -> str:
    """Open an existing Gephi project file (.gephi). `file` is an absolute path."""
    return fmt(await gephi.request("POST", "/project/open", json_data={"file": file}))

@mcp.tool(name="gephi_save_project")
async def gephi_save_project(file: str) -> str:
    """Save the current Gephi project. `file` is the absolute destination path."""
    return fmt(await gephi.request("POST", "/project/save", json_data={"file": file}))

@mcp.tool(name="gephi_get_project_info")
async def gephi_get_project_info() -> str:
    """Get current project info: workspace status, node/edge counts, and graph type."""
    return fmt(await gephi.request("GET", "/project/info"))


# ─── Workspace ────────────────────────────────────────────────

@mcp.tool(name="gephi_new_workspace")
async def gephi_new_workspace() -> str:
    """Create a new workspace in the current project."""
    return fmt(await gephi.request("POST", "/workspace/new"))

@mcp.tool(name="gephi_list_workspaces")
async def gephi_list_workspaces() -> str:
    """List all workspaces in the current project."""
    return fmt(await gephi.request("GET", "/workspace/list"))

@mcp.tool(name="gephi_switch_workspace")
async def gephi_switch_workspace(index: int) -> str:
    """Switch to a different workspace by zero-based index."""
    return fmt(await gephi.request("POST", "/workspace/switch", json_data={"index": index}))

@mcp.tool(name="gephi_delete_workspace")
async def gephi_delete_workspace(index: int) -> str:
    """Delete a workspace by zero-based index."""
    return fmt(await gephi.request("DELETE", "/workspace/delete", params={"index": str(index)}))

@mcp.tool(name="gephi_duplicate_workspace")
async def gephi_duplicate_workspace(index: int) -> str:
    """Duplicate a workspace by index, copying graph data, statistics, and appearance."""
    return fmt(await gephi.request("POST", "/workspace/duplicate", json_data={"index": index}))

@mcp.tool(name="gephi_rename_workspace")
async def gephi_rename_workspace(index: int, name: str) -> str:
    """Rename the workspace at the given zero-based index."""
    return fmt(await gephi.request("POST", "/workspace/rename", json_data={"index": index, "name": name}))


# ─── Nodes ────────────────────────────────────────────────────

@mcp.tool(name="gephi_add_node")
async def gephi_add_node(id: str, label: str | None = None,
                         attributes: dict[str, Any] | None = None) -> str:
    """Add a single node. Placed at a random position; run a layout to reposition.

    attributes: optional {column: value} map; columns are created automatically.
    """
    return fmt(await gephi.request("POST", "/graph/node/add",
                                   json_data=_body(id=id, label=label, attributes=attributes)))

@mcp.tool(name="gephi_add_nodes")
async def gephi_add_nodes(nodes: list[dict[str, Any]]) -> str:
    """Add multiple nodes in one batch (efficient for large graphs).

    Each node: {id: str, label?: str, attributes?: {column: value}}.
    Duplicate IDs are skipped; per-node attributes are applied.
    """
    return fmt(await gephi.request("POST", "/graph/nodes/add", json_data={"nodes": nodes}))

@mcp.tool(name="gephi_remove_node")
async def gephi_remove_node(id: str) -> str:
    """Remove a node and all its connected edges. Destructive; cannot be undone."""
    return fmt(await gephi.request("DELETE", f"/graph/node/{id}"))

@mcp.tool(name="gephi_bulk_remove_nodes")
async def gephi_bulk_remove_nodes(ids: list[str]) -> str:
    """Remove multiple nodes (and their edges) by ID. Destructive."""
    return fmt(await gephi.request("POST", "/graph/nodes/remove", json_data={"ids": ids}))

@mcp.tool(name="gephi_query_nodes")
async def gephi_query_nodes(limit: int = 100, offset: int = 0) -> str:
    """Query nodes with pagination. Returns id, label, position, size, color, attributes."""
    return fmt(await gephi.request("GET", "/graph/nodes", params={"limit": limit, "offset": offset}))

@mcp.tool(name="gephi_get_node")
async def gephi_get_node(id: str) -> str:
    """Get full details for a single node: id, label, x/y, size, color, and attributes."""
    return fmt(await gephi.request("GET", f"/graph/node/get/{id}"))

@mcp.tool(name="gephi_set_node_label")
async def gephi_set_node_label(id: str, label: str) -> str:
    """Set or change the label of a node."""
    return fmt(await gephi.request("POST", "/graph/node/label", json_data={"id": id, "label": label}))

@mcp.tool(name="gephi_set_node_position")
async def gephi_set_node_position(id: str, x: float, y: float) -> str:
    """Set the X/Y position of a node."""
    return fmt(await gephi.request("POST", "/graph/node/position", json_data={"id": id, "x": x, "y": y}))

@mcp.tool(name="gephi_batch_set_positions")
async def gephi_batch_set_positions(positions: list[dict[str, Any]]) -> str:
    """Set positions of multiple nodes at once. Each entry: {id: str, x: float, y: float}."""
    return fmt(await gephi.request("POST", "/graph/nodes/positions", json_data={"positions": positions}))


# ─── Edges ────────────────────────────────────────────────────

@mcp.tool(name="gephi_add_edge")
async def gephi_add_edge(source: str, target: str, weight: float = 1.0, directed: bool = True) -> str:
    """Add an edge between two existing nodes."""
    return fmt(await gephi.request("POST", "/graph/edge/add",
                                   json_data={"source": source, "target": target,
                                              "weight": weight, "directed": directed}))

@mcp.tool(name="gephi_add_edges")
async def gephi_add_edges(edges: list[dict[str, Any]]) -> str:
    """Add multiple edges in one batch.

    Each edge: {source: str, target: str, weight?: float, directed?: bool,
    label?: str, attributes?: {column: value}}. Edges referencing missing nodes,
    or duplicates, are skipped.
    """
    return fmt(await gephi.request("POST", "/graph/edges/add", json_data={"edges": edges}))

@mcp.tool(name="gephi_remove_edge")
async def gephi_remove_edge(source: str, target: str) -> str:
    """Remove the edge between two nodes."""
    return fmt(await gephi.request("POST", "/graph/edge/remove",
                                   json_data={"source": source, "target": target}))

@mcp.tool(name="gephi_set_edge_weight")
async def gephi_set_edge_weight(source: str, target: str, weight: float) -> str:
    """Set the weight of an edge."""
    return fmt(await gephi.request("POST", "/graph/edge/weight",
                                   json_data={"source": source, "target": target, "weight": weight}))

@mcp.tool(name="gephi_set_edge_label")
async def gephi_set_edge_label(source: str, target: str, label: str) -> str:
    """Set or change the label of an edge."""
    return fmt(await gephi.request("POST", "/graph/edge/label",
                                   json_data={"source": source, "target": target, "label": label}))

@mcp.tool(name="gephi_query_edges")
async def gephi_query_edges(limit: int = 100, offset: int = 0) -> str:
    """Query edges with pagination. Returns source, target, weight, directed, attributes."""
    return fmt(await gephi.request("GET", "/graph/edges", params={"limit": limit, "offset": offset}))


# ─── Graph Stats & Type ──────────────────────────────────────

@mcp.tool(name="gephi_get_graph_stats")
async def gephi_get_graph_stats() -> str:
    """Get node count, edge count, density, average degree, and graph type."""
    return fmt(await gephi.request("GET", "/graph/stats"))

@mcp.tool(name="gephi_get_graph_type")
async def gephi_get_graph_type() -> str:
    """Get whether the graph is directed, undirected, or mixed."""
    return fmt(await gephi.request("GET", "/graph/type"))


# ─── Attributes / Columns ────────────────────────────────────

@mcp.tool(name="gephi_get_columns")
async def gephi_get_columns(target: str = "node") -> str:
    """List columns (attributes) in the node or edge table. target: "node" | "edge"."""
    return fmt(await gephi.request("GET", "/graph/columns", params={"target": target}))

@mcp.tool(name="gephi_add_column")
async def gephi_add_column(name: str, type: str, target: str = "node") -> str:
    """Add a column to the node or edge table.

    type: "string" | "integer" | "double" | "float" | "boolean" | "long".
    target: "node" | "edge".
    """
    return fmt(await gephi.request("POST", "/graph/columns/add",
                                   json_data={"name": name, "type": type, "target": target}))

@mcp.tool(name="gephi_set_node_attributes")
async def gephi_set_node_attributes(id: str, attributes: dict[str, Any]) -> str:
    """Set custom attributes on a node. Columns are created automatically if needed."""
    return fmt(await gephi.request("POST", "/graph/node/attributes",
                                   json_data={"id": id, "attributes": attributes}))

@mcp.tool(name="gephi_batch_set_node_attributes")
async def gephi_batch_set_node_attributes(updates: list[dict[str, Any]]) -> str:
    """Set attributes on multiple nodes. Each update: {id: str, attributes: {column: value}}."""
    return fmt(await gephi.request("POST", "/graph/nodes/attributes", json_data={"updates": updates}))

@mcp.tool(name="gephi_set_edge_attributes")
async def gephi_set_edge_attributes(source: str, target: str, attributes: dict[str, Any]) -> str:
    """Set custom attributes on an edge. Columns are created automatically if needed."""
    return fmt(await gephi.request("POST", "/graph/edge/attributes",
                                   json_data={"source": source, "target": target, "attributes": attributes}))


# ─── Appearance: Individual Styling ──────────────────────────

@mcp.tool(name="gephi_set_node_color")
async def gephi_set_node_color(id: str, r: int, g: int, b: int, a: int = 255) -> str:
    """Set the color of a single node. r/g/b/a are 0-255."""
    return fmt(await gephi.request("POST", "/appearance/node/color",
                                   json_data={"id": id, "r": r, "g": g, "b": b, "a": a}))

@mcp.tool(name="gephi_set_node_size")
async def gephi_set_node_size(id: str, size: float) -> str:
    """Set the size of a single node."""
    return fmt(await gephi.request("POST", "/appearance/node/size", json_data={"id": id, "size": size}))

@mcp.tool(name="gephi_set_edge_color")
async def gephi_set_edge_color(source: str, target: str, r: int, g: int, b: int, a: int = 255) -> str:
    """Set the color of a single edge. r/g/b/a are 0-255."""
    return fmt(await gephi.request("POST", "/appearance/edge/color",
                                   json_data={"source": source, "target": target,
                                              "r": r, "g": g, "b": b, "a": a}))

@mcp.tool(name="gephi_batch_set_node_colors")
async def gephi_batch_set_node_colors(nodes: list[dict[str, Any]]) -> str:
    """Set colors of multiple nodes. Each entry: {id: str, r: int, g: int, b: int, a?: int}."""
    return fmt(await gephi.request("POST", "/appearance/nodes/color", json_data={"nodes": nodes}))

@mcp.tool(name="gephi_reset_appearance")
async def gephi_reset_appearance(r: int = 153, g: int = 153, b: int = 153, size: float = 10) -> str:
    """Reset all nodes to a default color and size (defaults to grey / size 10)."""
    return fmt(await gephi.request("POST", "/appearance/reset",
                                   json_data={"r": r, "g": g, "b": b, "size": size}))


# ─── Appearance: Color/Size by Attribute ─────────────────────

@mcp.tool(name="gephi_color_by_partition")
async def gephi_color_by_partition(column: str, colors: dict[str, list[int]] | None = None) -> str:
    """Color nodes by a categorical attribute (e.g. modularity_class, type).

    colors: optional {value: [r, g, b]} map; otherwise a distinct palette is assigned.
    Recommended palette (validated for readability on white exports and colorblind
    separation; pale/pastel colors are near-invisible on white): {"0": [42,120,214],
    "1": [27,175,122], "2": [237,161,0], "3": [0,131,0], "4": [74,58,167],
    "5": [227,73,72], "6": [232,123,164], "7": [235,104,52]}. With more than 8
    categories, color the 8 largest and set the rest to gray [153,153,153].
    """
    return fmt(await gephi.request("POST", "/appearance/partition/color",
                                   json_data=_body(column=column, colors=colors)))

@mcp.tool(name="gephi_color_by_ranking")
async def gephi_color_by_ranking(column: str,
                                 r_min: int = 255, g_min: int = 255, b_min: int = 200,
                                 r_max: int = 255, g_max: int = 0, b_max: int = 0) -> str:
    """Color nodes by a numeric attribute using a gradient from (r/g/b)_min to (r/g/b)_max.

    Works with degree, betweenness, pagerank, etc.
    """
    return fmt(await gephi.request("POST", "/appearance/ranking/color",
                                   json_data={"column": column,
                                              "r_min": r_min, "g_min": g_min, "b_min": b_min,
                                              "r_max": r_max, "g_max": g_max, "b_max": b_max}))

@mcp.tool(name="gephi_size_by_ranking")
async def gephi_size_by_ranking(column: str, min_size: float = 10, max_size: float = 60) -> str:
    """Size nodes by a numeric attribute, mapping values between min_size and max_size.

    Always do this before exporting or viewing — unsized nodes render as invisible
    specks. Degree with min 10, max 60 is a good default; scale up for large canvases.
    """
    return fmt(await gephi.request("POST", "/appearance/ranking/size",
                                   json_data={"column": column, "min_size": min_size, "max_size": max_size}))


# ─── Layout ──────────────────────────────────────────────────

@mcp.tool(name="gephi_run_layout")
async def gephi_run_layout(algorithm: str, iterations: int = 1000,
                           properties: dict[str, Any] | None = None, sync: bool = False) -> str:
    """Run a layout algorithm to position nodes.

    For community readability with "ForceAtlas 2", start from the visual network
    analysis reference config: {"linLogMode": true, "gravity": 0, "scalingRatio": 2.0}
    (Venturini, Jacomy, and Jensen 2021). Gravity only keeps disconnected components
    in frame (use 0.5-1.0 then); raising it packs nodes into an unreadable central
    blob. To tighten or spread the layout, adjust scalingRatio, not gravity. After
    the run, visually inspect a small export and iterate: central blob = lower
    gravity; hairball = linLogMode on and raise scalingRatio; clusters too dense
    inside = raise scalingRatio. Change one parameter per rerun.

    properties: optional {name: value} tuning map (gravity, scalingRatio, linLogMode,
    barnesHutOptimization, ...). sync=True waits until the layout finishes before
    returning; otherwise it returns immediately with status "running" (poll
    gephi_get_layout_status for completion).
    """
    result = await gephi.request("POST", "/layout/run",
                                 json_data=_body(algorithm=algorithm, iterations=iterations,
                                                 properties=properties))
    if not sync or not result.get("success"):
        return fmt(result)
    # Poll until layout stops
    for _ in range(300):  # max ~5 minutes at 1s intervals
        await asyncio.sleep(1)
        status = await gephi.request("GET", "/layout/status")
        if not status.get("running", True):
            result["status"] = "completed"
            result["message"] = "Layout finished after polling"
            return fmt(result)
    result["status"] = "timeout"
    result["message"] = "Layout still running after 5 minutes"
    return fmt(result)

@mcp.tool(name="gephi_stop_layout")
async def gephi_stop_layout() -> str:
    """Stop a currently running layout algorithm."""
    return fmt(await gephi.request("POST", "/layout/stop"))

@mcp.tool(name="gephi_get_layout_status")
async def gephi_get_layout_status() -> str:
    """Check whether a layout algorithm is currently running."""
    return fmt(await gephi.request("GET", "/layout/status"))

@mcp.tool(name="gephi_get_available_layouts")
async def gephi_get_available_layouts() -> str:
    """Get the list of available layout algorithms."""
    return fmt(await gephi.request("GET", "/layout/available"))

@mcp.tool(name="gephi_get_layout_properties")
async def gephi_get_layout_properties(algorithm: str) -> str:
    """Get tunable properties (gravity, scaling, speed, ...) for a layout algorithm."""
    return fmt(await gephi.request("GET", "/layout/properties", params={"algorithm": algorithm}))

@mcp.tool(name="gephi_set_layout_properties")
async def gephi_set_layout_properties(algorithm: str, properties: dict[str, Any],
                                      iterations: int = 1000) -> str:
    """Run a layout with custom property values (gravity, scaling, speed, ...)."""
    return fmt(await gephi.request("POST", "/layout/properties",
                                   json_data={"algorithm": algorithm, "properties": properties,
                                              "iterations": iterations}))


# ─── Statistics ──────────────────────────────────────────────

@mcp.tool(name="gephi_compute_modularity")
async def gephi_compute_modularity(resolution: float = 1.0) -> str:
    """Run modularity (Louvain) community detection. Stores 'modularity_class' on nodes.

    Higher resolution yields fewer, larger communities.
    """
    return fmt(await gephi.request("POST", "/statistics/modularity", json_data={"resolution": resolution}))

@mcp.tool(name="gephi_compute_degree")
async def gephi_compute_degree() -> str:
    """Compute degree, in-degree, and out-degree for all nodes."""
    return fmt(await gephi.request("POST", "/statistics/degree"))

@mcp.tool(name="gephi_compute_betweenness")
async def gephi_compute_betweenness() -> str:
    """Compute betweenness/closeness centrality, eccentricity, diameter, radius, avg path length."""
    return fmt(await gephi.request("POST", "/statistics/betweenness"))

@mcp.tool(name="gephi_compute_pagerank")
async def gephi_compute_pagerank() -> str:
    """Compute PageRank for all nodes. Stores 'pageranks' on nodes."""
    return fmt(await gephi.request("POST", "/statistics/pagerank"))

@mcp.tool(name="gephi_compute_connected_components")
async def gephi_compute_connected_components() -> str:
    """Compute connected components. Stores 'componentnumber' on nodes."""
    return fmt(await gephi.request("POST", "/statistics/connected-components"))

@mcp.tool(name="gephi_compute_clustering_coefficient")
async def gephi_compute_clustering_coefficient() -> str:
    """Compute the clustering coefficient for all nodes. Stores 'clustering' on nodes."""
    return fmt(await gephi.request("POST", "/statistics/clustering-coefficient"))

@mcp.tool(name="gephi_compute_avg_path_length")
async def gephi_compute_avg_path_length() -> str:
    """Compute the average shortest path length across all node pairs."""
    return fmt(await gephi.request("POST", "/statistics/avg-path-length"))

@mcp.tool(name="gephi_compute_hits")
async def gephi_compute_hits() -> str:
    """Compute HITS hub and authority scores. Stores 'Authority' and 'Hub' on nodes."""
    return fmt(await gephi.request("POST", "/statistics/hits"))

@mcp.tool(name="gephi_compute_eigenvector")
async def gephi_compute_eigenvector() -> str:
    """Compute eigenvector centrality. Stores 'eigencentrality' on nodes."""
    return fmt(await gephi.request("POST", "/statistics/eigenvector"))


# ─── Filters ─────────────────────────────────────────────────

@mcp.tool(name="gephi_filter_by_degree")
async def gephi_filter_by_degree(min: int = 0, max: int = 0, dry_run: bool = False) -> str:
    """Filter the graph by node degree range, removing nodes outside it. Destructive.

    max=0 means no upper limit. dry_run=True reports how many nodes would be removed.
    """
    return fmt(await gephi.request("POST", "/filter/degree",
                                   json_data={"min": min, "max": max, "dry_run": dry_run}))

@mcp.tool(name="gephi_filter_by_edge_weight")
async def gephi_filter_by_edge_weight(min: float = 0, max: float = 0, dry_run: bool = False) -> str:
    """Filter the graph by edge weight range, removing edges outside it. Destructive.

    max=0 means no upper limit. dry_run=True reports how many edges would be removed.
    """
    return fmt(await gephi.request("POST", "/filter/edge-weight",
                                   json_data={"min": min, "max": max, "dry_run": dry_run}))

@mcp.tool(name="gephi_remove_isolates")
async def gephi_remove_isolates() -> str:
    """Remove all isolated nodes (degree 0). Destructive."""
    return fmt(await gephi.request("POST", "/filter/remove-isolates"))

@mcp.tool(name="gephi_extract_ego_network")
async def gephi_extract_ego_network(node_id: str, depth: int = 1) -> str:
    """Keep only a node and its neighbors within `depth`; remove everything else. Destructive."""
    return fmt(await gephi.request("POST", "/filter/ego-network",
                                   json_data={"node_id": node_id, "depth": depth}))

@mcp.tool(name="gephi_extract_giant_component")
async def gephi_extract_giant_component() -> str:
    """Keep only the largest connected component; remove all smaller ones. Destructive."""
    return fmt(await gephi.request("POST", "/filter/giant-component"))

@mcp.tool(name="gephi_reset_filters")
async def gephi_reset_filters() -> str:
    """Reset non-destructive filters and restore the full graph view."""
    return fmt(await gephi.request("POST", "/filter/reset"))

@mcp.tool(name="gephi_clear_graph")
async def gephi_clear_graph() -> str:
    """Remove all nodes and edges. The project/workspace stay open. Destructive."""
    return fmt(await gephi.request("POST", "/graph/clear"))

@mcp.tool(name="gephi_edge_thickness_by_weight")
async def gephi_edge_thickness_by_weight(min_thickness: float = 1, max_thickness: float = 5) -> str:
    """Scale rendered edge thickness proportionally to edge weight."""
    return fmt(await gephi.request("POST", "/appearance/edge/thickness-by-weight",
                                   json_data={"min_thickness": min_thickness, "max_thickness": max_thickness}))


# ─── Preview ─────────────────────────────────────────────────

@mcp.tool(name="gephi_get_preview_settings")
async def gephi_get_preview_settings() -> str:
    """Get current preview/rendering settings (background, labels, edge style, opacity, ...)."""
    return fmt(await gephi.request("GET", "/preview/settings"))

@mcp.tool(name="gephi_set_preview_settings")
async def gephi_set_preview_settings(settings: dict[str, Any]) -> str:
    """Set preview/rendering settings used for export (PNG/PDF/SVG).

    settings is a {property: value} map, e.g. {"background.color": "#ffffff",
    "node.label.show": true, "edge.thickness": 2}. Valid property names are the
    keys returned by gephi_get_preview_settings.
    """
    result = await gephi.request("POST", "/preview/settings", json_data=settings)
    applied = result.get("properties_set")
    if result.get("success") and applied is not None and applied < len(settings):
        result["warning"] = (
            f"only {applied} of {len(settings)} properties matched — check the "
            "property names against gephi_get_preview_settings (unknown names are "
            "silently ignored)")
    return fmt(result)


# ─── Export ──────────────────────────────────────────────────

@mcp.tool(name="gephi_export_gexf")
async def gephi_export_gexf(file: str) -> str:
    """Export the graph to GEXF (preserves attributes, positions, and viz properties)."""
    return fmt(await gephi.request("POST", "/export/gexf", json_data={"file": file}))

@mcp.tool(name="gephi_export_png")
async def gephi_export_png(file: str, width: int = 1920, height: int = 1080) -> str:
    """Export the graph visualization as PNG. Run a layout first to position nodes.

    Default rendering yields near-invisible output; before exporting: (1) size nodes
    with gephi_size_by_ranking (e.g. degree, 10-60); (2) color with the validated
    palette (see gephi_color_by_partition); (3) call gephi_set_preview_settings with
    {"edge.opacity": 25, "edge.thickness": 2.0, "node.opacity": 100,
    "node.border.width": 0.3, "arrow.size": 0}. Then export, look at the image, and
    fix what is unreadable before declaring done.
    """
    return fmt(await gephi.request("POST", "/export/png",
                                   json_data={"file": file, "width": width, "height": height}))

@mcp.tool(name="gephi_export_pdf")
async def gephi_export_pdf(file: str, width: int | None = None, height: int | None = None) -> str:
    """Export the graph visualization as PDF (page size auto-detected if omitted)."""
    return fmt(await gephi.request("POST", "/export/pdf",
                                   json_data=_body(file=file, width=width, height=height)))

@mcp.tool(name="gephi_export_svg")
async def gephi_export_svg(file: str) -> str:
    """Export the graph visualization as SVG (scalable vector graphics)."""
    return fmt(await gephi.request("POST", "/export/svg", json_data={"file": file}))

@mcp.tool(name="gephi_export_graphml")
async def gephi_export_graphml(file: str) -> str:
    """Export the graph to GraphML (widely supported XML format)."""
    return fmt(await gephi.request("POST", "/export/graphml", json_data={"file": file}))

@mcp.tool(name="gephi_export_csv")
async def gephi_export_csv(file: str, separator: str = ",", target: str = "nodes") -> str:
    """Export the graph to CSV. target: "nodes" | "edges" | "both"."""
    return fmt(await gephi.request("POST", "/export/csv",
                                   json_data={"file": file, "separator": separator, "target": target}))

@mcp.tool(name="gephi_visual_qa")
async def gephi_visual_qa(partition_column: str | None = None) -> str:
    """Run visual-design diagnostics on the current graph. Cheap; use it often.

    Call BEFORE styling with partition_column set (e.g. "group", "modularity_class")
    to verify a claimed grouping is topologically real — if the verdict is "none",
    coloring by it would mislead; compute real communities instead. Call again AFTER
    styling/layout to catch invisible node sizes, near-white colors, gradient color
    schemes, and to get the export dimensions that match the layout's shape
    (extent.suggested_export). Fix every warning before the final export.
    """
    fd, path = tempfile.mkstemp(suffix=".gexf")
    os.close(fd)
    try:
        result = await gephi.request("POST", "/export/gexf", json_data={"file": path})
        if not result.get("success", False):
            return fmt(result)
        graph = gephi_mcp_viewer.parse_gexf(path, max_nodes=1000000)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)
    return fmt(gephi_mcp_viewer.analyze_graph(graph, partition_column=partition_column))


@mcp.tool(name="gephi_label_clusters")
async def gephi_label_clusters(partition_column: str,
                               names: dict[str, str] | None = None,
                               restore: bool = False) -> str:
    """Caption each cluster by labeling only its most salient (top-degree) node.

    The visual network analysis move for naming regions: every other label is
    blanked, each cluster's hub gets the cluster's name (from `names`, keyed by
    the partition value, e.g. {"1.0": "Engineering"}) or keeps its own label if
    no name is given, and preview switches to labeled mode with a white outline.
    Hubs sit near their cluster's center of gravity, so the caption lands on the
    region. Original labels are saved to a `label_backup` node attribute;
    restore=True puts everything back and hides labels again.
    """
    fd, path = tempfile.mkstemp(suffix=".gexf")
    os.close(fd)
    try:
        result = await gephi.request("POST", "/export/gexf", json_data={"file": path})
        if not result.get("success", False):
            return fmt(result)
        graph = gephi_mcp_viewer.parse_gexf(path, max_nodes=1000000)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)

    if restore:
        restored = 0
        for n in graph["nodes"]:
            original = n["attributes"].get("label_backup")
            if original is not None:
                await gephi.request("POST", "/graph/node/label",
                                    json_data={"id": n["key"], "label": original})
                restored += 1
        await gephi.request("POST", "/preview/settings",
                            json_data={"node.label.show": False})
        return fmt({"success": True, "restored": restored})

    hubs = gephi_mcp_viewer.pick_cluster_hubs(graph, partition_column)
    if not hubs:
        return fmt({"success": False,
                    "error": f"no nodes carry the attribute '{partition_column}'"})
    hub_keys = set(hubs.values())

    await gephi.request("POST", "/graph/nodes/attributes", json_data={"updates": [
        {"id": n["key"], "attributes": {"label_backup": n["label"]}}
        for n in graph["nodes"]]})

    labeled, blanked = {}, 0
    label_by_key = {n["key"]: n["label"] for n in graph["nodes"]}
    for n in graph["nodes"]:
        if n["key"] in hub_keys:
            continue
        await gephi.request("POST", "/graph/node/label",
                            json_data={"id": n["key"], "label": ""})
        blanked += 1
    for group, key in hubs.items():
        caption = (names or {}).get(str(group), label_by_key[key])
        await gephi.request("POST", "/graph/node/label",
                            json_data={"id": key, "label": caption})
        labeled[str(group)] = {"node": key, "label": caption}

    await gephi.request("POST", "/preview/settings", json_data={
        "node.label.show": True, "node.label.proportinalSize": False,
        "node.label.font": "Arial 16 Bold", "node.label.outline.size": 4.0,
        "node.label.outline.opacity": 95.0, "node.label.avoidOverlap": True})
    return fmt({"success": True, "labeled": labeled, "blanked": blanked})


@mcp.resource("ui://gephi/graph-view", name="gephi-graph-view",
              mime_type="text/html;profile=mcp-app")
def gephi_graph_view_app() -> str:
    """Static MCP App page that renders graph data pushed by the host."""
    return gephi_mcp_viewer.build_app_html()

@mcp.tool(name="gephi_view_graph",
          meta={"ui": {"resourceUri": "ui://gephi/graph-view"}})
async def gephi_view_graph(max_nodes: int = 1500, title: str = "Network view") -> CallToolResult:
    """Render the current graph as an interactive in-chat view (MCP App).

    In hosts that render MCP Apps (e.g. Claude Desktop chat) this displays an
    interactive visualization inline: pan, zoom, hover labels, click a node for
    its attributes. IMPORTANT — if your host did NOT render a visual (you only
    see this result as text/data), build an interactive visualization yourself
    from the result's structuredContent using the host's native visual surface
    (widget, canvas, artifact): every node carries x, y, color, size, label, and
    attributes, so no recomputation is needed. Prefer that over showing a PNG;
    inline PNGs render small. Run a layout first so nodes are positioned.
    Graphs larger than max_nodes are trimmed to the highest-degree nodes.
    """
    fd, path = tempfile.mkstemp(suffix=".gexf")
    os.close(fd)
    try:
        result = await gephi.request("POST", "/export/gexf", json_data={"file": path})
        if not result.get("success", False):
            return CallToolResult(
                content=[TextContent(type="text", text=fmt(result))], isError=True)
        graph = gephi_mcp_viewer.parse_gexf(path, max_nodes=max_nodes)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(path)

    if graph["truncated"]:
        summary = (f"Interactive view rendered with the {len(graph['nodes'])} highest-degree of "
                   f"{graph['node_count_total']} nodes ({len(graph['edges'])} edges shown). "
                   f"Raise max_nodes to show more.")
    else:
        summary = (f"Interactive view rendered: {graph['node_count_total']} nodes and "
                   f"{graph['edge_count_total']} edges.")
    summary += (" If no visual appeared in this client, render structuredContent yourself "
                "as an interactive visualization (native widget/canvas/artifact — nodes "
                "have x, y, color, size); avoid falling back to a static PNG.")
    return CallToolResult(
        content=[TextContent(type="text", text=summary)],
        structuredContent={**graph, "title": title},
    )


# ─── Import ──────────────────────────────────────────────────

@mcp.tool(name="gephi_import_gexf")
async def gephi_import_gexf(file: str) -> str:
    """Import a graph from a GEXF file. Merged with any existing graph."""
    return fmt(await gephi.request("POST", "/import/gexf", json_data={"file": file}))

@mcp.tool(name="gephi_import_graphml")
async def gephi_import_graphml(file: str) -> str:
    """Import a graph from a GraphML file."""
    return fmt(await gephi.request("POST", "/import/graphml", json_data={"file": file}))

@mcp.tool(name="gephi_import_csv")
async def gephi_import_csv(file: str) -> str:
    """Import a graph from a CSV file."""
    return fmt(await gephi.request("POST", "/import/csv", json_data={"file": file}))

@mcp.tool(name="gephi_import_file")
async def gephi_import_file(file: str) -> str:
    """Import a graph from any supported format (GEXF, GraphML, GML, CSV, DOT, Pajek, ...).

    Auto-detected by extension. Imported node sizes are capped at 30 so a viz:size
    from the source can't render nodes enormous; re-size with gephi_size_by_ranking.
    """
    return fmt(await gephi.request("POST", "/import/file", json_data={"file": file}))


# ==================== Main Entry Point ====================

if __name__ == "__main__":
    mcp.run()
