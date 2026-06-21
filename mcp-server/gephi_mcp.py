"""
Gephi MCP Server - Model Context Protocol server for controlling Gephi Desktop

This MCP server enables LLMs to interact with a running Gephi Desktop instance
through the Gephi MCP Plugin's HTTP API.

Claude Code Skill:
    This server is paired with a Claude Code skill that provides workflows,
    best practices, and visualization guidelines for using these tools.
    See: .claude/skills/gephi-network-analysis/SKILL.md

Developed by Matt Artz (https://www.mattartz.me)
"""

import asyncio
import json
import logging
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

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


# ==================== Response Formatting ====================

def fmt(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2)


# ==================== MCP Tools ====================

# ─── Health ───────────────────────────────────────────────────

@mcp.tool(name="gephi_health_check")
async def gephi_health_check() -> str:
    """Check if Gephi Desktop is running and the MCP plugin is accessible."""
    return fmt(await gephi.request("GET", "/health"))


# ─── Project ─────────────────────────────────────────────────

@mcp.tool(name="gephi_create_project")
async def gephi_create_project(params: dict) -> str:
    """Create a new empty Gephi project/workspace.

    Args:
        params: {name: str (optional)} - project name, defaults to "New Project"
    """
    return fmt(await gephi.request("POST", "/project/new", json_data=params or {}))

@mcp.tool(name="gephi_open_project")
async def gephi_open_project(params: dict) -> str:
    """Open an existing Gephi project file (.gephi).

    Args:
        params: {file: str} - absolute path to the .gephi file
    """
    return fmt(await gephi.request("POST", "/project/open", json_data=params))

@mcp.tool(name="gephi_save_project")
async def gephi_save_project(params: dict) -> str:
    """Save the current Gephi project to a file.

    Args:
        params: {file: str} - absolute destination path for the .gephi file
    """
    return fmt(await gephi.request("POST", "/project/save", json_data=params))

@mcp.tool(name="gephi_get_project_info")
async def gephi_get_project_info(params: dict) -> str:
    """Get information about the current Gephi project.

    Returns workspace status, node/edge counts, and graph type information.

    Args:
        params: {} - no parameters
    """
    return fmt(await gephi.request("GET", "/project/info"))


# ─── Workspace ────────────────────────────────────────────────

@mcp.tool(name="gephi_new_workspace")
async def gephi_new_workspace(params: dict) -> str:
    """Create a new workspace in the current project.

    Args:
        params: Empty dict
    """
    return fmt(await gephi.request("POST", "/workspace/new"))

@mcp.tool(name="gephi_list_workspaces")
async def gephi_list_workspaces(params: dict) -> str:
    """List all workspaces in the current project.

    Args:
        params: Empty dict
    """
    return fmt(await gephi.request("GET", "/workspace/list"))

@mcp.tool(name="gephi_switch_workspace")
async def gephi_switch_workspace(params: dict) -> str:
    """Switch to a different workspace by index.

    Args:
        params: {index: int} - zero-based workspace index
    """
    return fmt(await gephi.request("POST", "/workspace/switch", json_data=params))

@mcp.tool(name="gephi_delete_workspace")
async def gephi_delete_workspace(params: dict) -> str:
    """Delete a workspace by index.

    Args:
        params: {index: int} - zero-based workspace index
    """
    return fmt(await gephi.request("DELETE", "/workspace/delete", params={"index": str(params.get("index", 0))}))

@mcp.tool(name="gephi_duplicate_workspace")
async def gephi_duplicate_workspace(params: dict) -> str:
    """Duplicate a workspace by index. Creates a copy with all graph data, statistics, and appearance settings.

    Args:
        params: {index: int} - zero-based workspace index to duplicate
    """
    return fmt(await gephi.request("POST", "/workspace/duplicate", json_data=params))

@mcp.tool(name="gephi_rename_workspace")
async def gephi_rename_workspace(params: dict) -> str:
    """Rename a workspace by index.

    Args:
        params: {index: int, name: str}
    """
    return fmt(await gephi.request("POST", "/workspace/rename", json_data=params))


# ─── Nodes ────────────────────────────────────────────────────

@mcp.tool(name="gephi_add_node")
async def gephi_add_node(params: dict) -> str:
    """Add a single node to the graph.

    Creates a new node with the specified ID, label, and optional attributes.
    The node will be placed at a random position and can be repositioned by
    running a layout algorithm.

    Args:
        params: {id: str, label: str (optional), attributes: {key: value, ...} (optional)}
    """
    return fmt(await gephi.request("POST", "/graph/node/add", json_data=params))

@mcp.tool(name="gephi_add_nodes")
async def gephi_add_nodes(params: dict) -> str:
    """Add multiple nodes to the graph in a single batch operation.

    More efficient than adding nodes one at a time for large datasets.
    Nodes with duplicate IDs will be skipped. Per-node `attributes` are applied
    just like gephi_add_node.

    Args:
        params: {nodes: [{id: str, label: str (optional), attributes: {key: value} (optional)}, ...]}
    """
    return fmt(await gephi.request("POST", "/graph/nodes/add", json_data=params))

@mcp.tool(name="gephi_remove_node")
async def gephi_remove_node(params: dict) -> str:
    """Remove a node and all its connected edges from the graph.

    This operation is destructive and cannot be undone. All edges
    connected to this node will also be removed.

    Args:
        params: {id: str}
    """
    node_id = params.get("id", "")
    return fmt(await gephi.request("DELETE", f"/graph/node/{node_id}"))

@mcp.tool(name="gephi_bulk_remove_nodes")
async def gephi_bulk_remove_nodes(params: dict) -> str:
    """Remove multiple nodes and their connected edges.

    Args:
        params: {ids: [str]} - list of node IDs to remove
    """
    return fmt(await gephi.request("POST", "/graph/nodes/remove", json_data=params))

@mcp.tool(name="gephi_query_nodes")
async def gephi_query_nodes(params: dict) -> str:
    """Query and filter nodes in the graph.

    Returns node data with optional filtering by attribute values.
    Supports pagination for large graphs.

    Args:
        params: {limit: int (default 100), offset: int (default 0)}
    """
    query_params = {"limit": params.get("limit", 100), "offset": params.get("offset", 0)}
    return fmt(await gephi.request("GET", "/graph/nodes", params=query_params))

@mcp.tool(name="gephi_get_node")
async def gephi_get_node(params: dict) -> str:
    """Get full details for a single node by ID.

    Returns id, label, x/y position, size, color (r/g/b), and all attributes.

    Args:
        params: {id: str}
    """
    node_id = params.get("id", "")
    return fmt(await gephi.request("GET", f"/graph/node/get/{node_id}"))

@mcp.tool(name="gephi_set_node_label")
async def gephi_set_node_label(params: dict) -> str:
    """Set or change the label of a node.

    Args:
        params: {id: str, label: str}
    """
    return fmt(await gephi.request("POST", "/graph/node/label", json_data=params))

@mcp.tool(name="gephi_set_node_position")
async def gephi_set_node_position(params: dict) -> str:
    """Set the X/Y position of a node.

    Args:
        params: {id: str, x: float, y: float}
    """
    return fmt(await gephi.request("POST", "/graph/node/position", json_data=params))

@mcp.tool(name="gephi_batch_set_positions")
async def gephi_batch_set_positions(params: dict) -> str:
    """Set positions of multiple nodes at once.

    Args:
        params: {positions: [{id, x, y}, ...]}
    """
    return fmt(await gephi.request("POST", "/graph/nodes/positions", json_data=params))


# ─── Edges ────────────────────────────────────────────────────

@mcp.tool(name="gephi_add_edge")
async def gephi_add_edge(params: dict) -> str:
    """Add an edge between two nodes.

    Creates a connection between source and target nodes. Both nodes
    must already exist in the graph.

    Args:
        params: {source: str, target: str, weight: float (optional, default 1.0), directed: bool (optional, default true)}
    """
    return fmt(await gephi.request("POST", "/graph/edge/add", json_data=params))

@mcp.tool(name="gephi_add_edges")
async def gephi_add_edges(params: dict) -> str:
    """Add multiple edges to the graph in a single batch operation.

    More efficient than adding edges one at a time. Edges referencing
    non-existent nodes (or duplicate edges) will be skipped. Per-edge
    `directed`, `label`, and `attributes` are honored like gephi_add_edge.

    Args:
        params: {edges: [{source: str, target: str, weight: float (optional), directed: bool (optional, default true), label: str (optional), attributes: {key: value} (optional)}, ...]}
    """
    return fmt(await gephi.request("POST", "/graph/edges/add", json_data=params))

@mcp.tool(name="gephi_remove_edge")
async def gephi_remove_edge(params: dict) -> str:
    """Remove an edge between two nodes.

    Args:
        params: {source: str, target: str}
    """
    return fmt(await gephi.request("POST", "/graph/edge/remove", json_data=params))

@mcp.tool(name="gephi_set_edge_weight")
async def gephi_set_edge_weight(params: dict) -> str:
    """Set the weight of an edge.

    Args:
        params: {source: str, target: str, weight: float}
    """
    return fmt(await gephi.request("POST", "/graph/edge/weight", json_data=params))

@mcp.tool(name="gephi_set_edge_label")
async def gephi_set_edge_label(params: dict) -> str:
    """Set or change the label of an edge.

    Args:
        params: {source: str, target: str, label: str}
    """
    return fmt(await gephi.request("POST", "/graph/edge/label", json_data=params))

@mcp.tool(name="gephi_query_edges")
async def gephi_query_edges(params: dict) -> str:
    """Query edges in the graph with pagination.

    Args:
        params: {limit: int, offset: int}
    """
    query_params = {"limit": params.get("limit", 100), "offset": params.get("offset", 0)}
    return fmt(await gephi.request("GET", "/graph/edges", params=query_params))


# ─── Graph Stats & Type ──────────────────────────────────────

@mcp.tool(name="gephi_get_graph_stats")
async def gephi_get_graph_stats(params: dict) -> str:
    """Get basic graph statistics.

    Returns node count, edge count, density, average degree, and graph type.

    Args:
        params: {} - no parameters
    """
    return fmt(await gephi.request("GET", "/graph/stats"))

@mcp.tool(name="gephi_get_graph_type")
async def gephi_get_graph_type(params: dict) -> str:
    """Get whether the graph is directed, undirected, or mixed.

    Args:
        params: Empty dict
    """
    return fmt(await gephi.request("GET", "/graph/type"))


# ─── Attributes / Columns ────────────────────────────────────

@mcp.tool(name="gephi_get_columns")
async def gephi_get_columns(params: dict) -> str:
    """List all columns (attributes) in node or edge table.

    Args:
        params: {target: "node"|"edge"} - which table to query
    """
    return fmt(await gephi.request("GET", "/graph/columns", params={"target": params.get("target", "node")}))

@mcp.tool(name="gephi_add_column")
async def gephi_add_column(params: dict) -> str:
    """Add a new column to the node or edge table.

    Args:
        params: {name: str, type: "string"|"integer"|"double"|"float"|"boolean"|"long", target: "node"|"edge"}
    """
    return fmt(await gephi.request("POST", "/graph/columns/add", json_data=params))

@mcp.tool(name="gephi_set_node_attributes")
async def gephi_set_node_attributes(params: dict) -> str:
    """Set custom attributes on a node. Creates columns automatically if needed.

    Args:
        params: {id: str, attributes: {key: value, ...}}
    """
    return fmt(await gephi.request("POST", "/graph/node/attributes", json_data=params))

@mcp.tool(name="gephi_batch_set_node_attributes")
async def gephi_batch_set_node_attributes(params: dict) -> str:
    """Set attributes on multiple nodes at once.

    Args:
        params: {updates: [{id: str, attributes: {key: value}}, ...]}
    """
    return fmt(await gephi.request("POST", "/graph/nodes/attributes", json_data=params))

@mcp.tool(name="gephi_set_edge_attributes")
async def gephi_set_edge_attributes(params: dict) -> str:
    """Set custom attributes on an edge. Creates columns automatically if needed.

    Args:
        params: {source: str, target: str, attributes: {key: value, ...}}
    """
    return fmt(await gephi.request("POST", "/graph/edge/attributes", json_data=params))


# ─── Appearance: Individual Styling ──────────────────────────

@mcp.tool(name="gephi_set_node_color")
async def gephi_set_node_color(params: dict) -> str:
    """Set the color of a single node.

    Args:
        params: {id: str, r: int (0-255), g: int (0-255), b: int (0-255), a: int (0-255, optional)}
    """
    return fmt(await gephi.request("POST", "/appearance/node/color", json_data=params))

@mcp.tool(name="gephi_set_node_size")
async def gephi_set_node_size(params: dict) -> str:
    """Set the size of a single node.

    Args:
        params: {id: str, size: float}
    """
    return fmt(await gephi.request("POST", "/appearance/node/size", json_data=params))

@mcp.tool(name="gephi_set_edge_color")
async def gephi_set_edge_color(params: dict) -> str:
    """Set the color of a single edge.

    Args:
        params: {source: str, target: str, r: int, g: int, b: int, a: int (optional)}
    """
    return fmt(await gephi.request("POST", "/appearance/edge/color", json_data=params))

@mcp.tool(name="gephi_batch_set_node_colors")
async def gephi_batch_set_node_colors(params: dict) -> str:
    """Set colors of multiple nodes at once.

    Args:
        params: {nodes: [{id: str, r: int, g: int, b: int, a: int (optional)}, ...]}
    """
    return fmt(await gephi.request("POST", "/appearance/nodes/color", json_data=params))

@mcp.tool(name="gephi_reset_appearance")
async def gephi_reset_appearance(params: dict) -> str:
    """Reset all nodes to default color and size.

    Args:
        params: {r: int, g: int, b: int, size: float} - all optional, defaults to grey/10
    """
    return fmt(await gephi.request("POST", "/appearance/reset", json_data=params or {}))


# ─── Appearance: Color/Size by Attribute ─────────────────────

@mcp.tool(name="gephi_color_by_partition")
async def gephi_color_by_partition(params: dict) -> str:
    """Color nodes by a categorical attribute (partition coloring).

    Each unique value gets a distinct color. Works well with modularity_class,
    type, category, etc. Optionally provide a custom color map.

    Args:
        params: {column: str, colors: {value: [r,g,b], ...} (optional)}
    """
    return fmt(await gephi.request("POST", "/appearance/partition/color", json_data=params))

@mcp.tool(name="gephi_color_by_ranking")
async def gephi_color_by_ranking(params: dict) -> str:
    """Color nodes by a numeric attribute using a gradient (ranking coloring).

    Maps numeric values to a color gradient from color_min to color_max.
    Works well with degree, betweenness, pagerank, etc.

    Args:
        params: {column: str, r_min: int, g_min: int, b_min: int, r_max: int, g_max: int, b_max: int}
    """
    return fmt(await gephi.request("POST", "/appearance/ranking/color", json_data=params))

@mcp.tool(name="gephi_size_by_ranking")
async def gephi_size_by_ranking(params: dict) -> str:
    """Size nodes by a numeric attribute (ranking sizing).

    Maps numeric values to node sizes between min_size and max_size.
    Works well with degree, betweenness, pagerank, etc.

    Args:
        params: {column: str, min_size: float, max_size: float}
    """
    return fmt(await gephi.request("POST", "/appearance/ranking/size", json_data=params))


# ─── Layout ──────────────────────────────────────────────────

@mcp.tool(name="gephi_run_layout")
async def gephi_run_layout(params: dict) -> str:
    """Run a layout algorithm to position nodes.

    Pass `sync: true` to wait until the layout finishes before returning.
    Without sync, returns immediately with status "running" — use
    gephi_get_layout_status to poll for completion.

    Args:
        params: {algorithm: str, iterations: int, properties: dict (optional), sync: bool (optional)}
    """
    sync = params.pop("sync", False)
    result = await gephi.request("POST", "/layout/run", json_data=params)
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
async def gephi_stop_layout(params: dict) -> str:
    """Stop a currently running layout algorithm.

    Args:
        params: {} - no parameters
    """
    return fmt(await gephi.request("POST", "/layout/stop"))

@mcp.tool(name="gephi_get_layout_status")
async def gephi_get_layout_status(params: dict) -> str:
    """Check if a layout algorithm is currently running.

    Args:
        params: {} - no parameters
    """
    return fmt(await gephi.request("GET", "/layout/status"))

@mcp.tool(name="gephi_get_available_layouts")
async def gephi_get_available_layouts(params: dict) -> str:
    """Get list of available layout algorithms.

    Args:
        params: {} - no parameters
    """
    return fmt(await gephi.request("GET", "/layout/available"))

@mcp.tool(name="gephi_get_layout_properties")
async def gephi_get_layout_properties(params: dict) -> str:
    """Get tunable properties for a layout algorithm.

    Returns all configurable parameters (gravity, scaling, speed, etc.)
    with their current values and types.

    Args:
        params: {algorithm: str}
    """
    return fmt(await gephi.request("GET", "/layout/properties", params={"algorithm": params.get("algorithm", "")}))

@mcp.tool(name="gephi_set_layout_properties")
async def gephi_set_layout_properties(params: dict) -> str:
    """Run a layout with custom property values.

    Allows fine-tuning layout parameters like gravity, scaling, speed, etc.

    Args:
        params: {algorithm: str, properties: {name: value, ...}, iterations: int}
    """
    return fmt(await gephi.request("POST", "/layout/properties", json_data=params))


# ─── Statistics ──────────────────────────────────────────────

@mcp.tool(name="gephi_compute_modularity")
async def gephi_compute_modularity(params: dict) -> str:
    """Run modularity algorithm for community detection.

    Identifies communities/clusters in the graph using the Louvain method.
    Results are stored in node attribute 'modularity_class'.

    Args:
        params: {resolution: float (optional, default 1.0)} - higher values yield fewer, larger communities
    """
    return fmt(await gephi.request("POST", "/statistics/modularity", json_data=params or {}))

@mcp.tool(name="gephi_compute_degree")
async def gephi_compute_degree(params: dict) -> str:
    """Compute degree statistics for all nodes.

    Calculates in-degree, out-degree, and total degree for each node.
    Results are stored in node attributes 'degree', 'indegree', 'outdegree'.

    Args:
        params: {} - no parameters
    """
    return fmt(await gephi.request("POST", "/statistics/degree"))

@mcp.tool(name="gephi_compute_betweenness")
async def gephi_compute_betweenness(params: dict) -> str:
    """Compute betweenness centrality and graph distance metrics.

    Calculates betweenness centrality, closeness centrality, eccentricity,
    diameter, radius, and average path length for all nodes.
    Results stored in node attributes.

    Args:
        params: Empty dict
    """
    return fmt(await gephi.request("POST", "/statistics/betweenness"))

@mcp.tool(name="gephi_compute_pagerank")
async def gephi_compute_pagerank(params: dict) -> str:
    """Compute PageRank for all nodes.

    Calculates the PageRank score measuring node importance based on
    incoming connections. Results stored in node attribute 'pageranks'.

    Args:
        params: Empty dict
    """
    return fmt(await gephi.request("POST", "/statistics/pagerank"))

@mcp.tool(name="gephi_compute_connected_components")
async def gephi_compute_connected_components(params: dict) -> str:
    """Compute connected components of the graph.

    Identifies which nodes belong to the same connected component.
    Results stored in node attribute 'componentnumber'.

    Args:
        params: Empty dict
    """
    return fmt(await gephi.request("POST", "/statistics/connected-components"))

@mcp.tool(name="gephi_compute_clustering_coefficient")
async def gephi_compute_clustering_coefficient(params: dict) -> str:
    """Compute clustering coefficient for all nodes.

    Measures how connected a node's neighbors are to each other.
    Results stored in node attribute 'clustering'.

    Args:
        params: Empty dict
    """
    return fmt(await gephi.request("POST", "/statistics/clustering-coefficient"))

@mcp.tool(name="gephi_compute_avg_path_length")
async def gephi_compute_avg_path_length(params: dict) -> str:
    """Compute average path length of the graph.

    Calculates the average shortest path between all pairs of nodes.

    Args:
        params: Empty dict
    """
    return fmt(await gephi.request("POST", "/statistics/avg-path-length"))

@mcp.tool(name="gephi_compute_hits")
async def gephi_compute_hits(params: dict) -> str:
    """Compute HITS (Hyperlink-Induced Topic Search) algorithm.

    Calculates hub and authority scores for all nodes.
    Results stored in node attributes 'Authority' and 'Hub'.

    Args:
        params: Empty dict
    """
    return fmt(await gephi.request("POST", "/statistics/hits"))

@mcp.tool(name="gephi_compute_eigenvector")
async def gephi_compute_eigenvector(params: dict) -> str:
    """Compute eigenvector centrality for all nodes.

    Measures node importance based on connections to other important nodes.
    Results stored in node attribute 'eigencentrality'.

    Args:
        params: Empty dict
    """
    return fmt(await gephi.request("POST", "/statistics/eigenvector"))


# ─── Filters ─────────────────────────────────────────────────

@mcp.tool(name="gephi_filter_by_degree")
async def gephi_filter_by_degree(params: dict) -> str:
    """Filter graph by node degree range. Removes nodes outside the range.

    Warning: This is destructive - filtered nodes are permanently removed.

    Pass `dry_run: true` to see how many nodes would be removed without actually removing them.

    Args:
        params: {min: int, max: int (0 = no upper limit), dry_run: bool (optional)}
    """
    return fmt(await gephi.request("POST", "/filter/degree", json_data=params))

@mcp.tool(name="gephi_filter_by_edge_weight")
async def gephi_filter_by_edge_weight(params: dict) -> str:
    """Filter graph by edge weight range. Removes edges outside the range.

    Warning: This is destructive - filtered edges are permanently removed.

    Pass `dry_run: true` to see how many edges would be removed without actually removing them.

    Args:
        params: {min: float, max: float (0 = no upper limit), dry_run: bool (optional)}
    """
    return fmt(await gephi.request("POST", "/filter/edge-weight", json_data=params))

@mcp.tool(name="gephi_remove_isolates")
async def gephi_remove_isolates(params: dict) -> str:
    """Remove all isolated nodes (degree 0) from the graph.

    Warning: This is destructive - removed nodes cannot be recovered.

    Args:
        params: Empty dict
    """
    return fmt(await gephi.request("POST", "/filter/remove-isolates"))

@mcp.tool(name="gephi_extract_ego_network")
async def gephi_extract_ego_network(params: dict) -> str:
    """Extract the ego network around a specific node.

    Keeps only the specified node and its neighbors within the given depth.
    All other nodes and their edges are permanently removed.

    Args:
        params: {node_id: str, depth: int (default 1)}
    """
    return fmt(await gephi.request("POST", "/filter/ego-network", json_data=params))

@mcp.tool(name="gephi_extract_giant_component")
async def gephi_extract_giant_component(params: dict) -> str:
    """Extract the largest connected component from the graph.

    Runs connected components analysis and keeps only the largest one.
    All nodes in smaller components are permanently removed.

    Args:
        params: Empty dict
    """
    return fmt(await gephi.request("POST", "/filter/giant-component"))

@mcp.tool(name="gephi_reset_filters")
async def gephi_reset_filters(params: dict) -> str:
    """Reset filters and restore the full graph view.

    Only works for non-destructive filter operations.

    Args:
        params: Empty dict
    """
    return fmt(await gephi.request("POST", "/filter/reset"))

@mcp.tool(name="gephi_clear_graph")
async def gephi_clear_graph(params: dict) -> str:
    """Remove all nodes and edges from the graph.

    The project and workspace remain open but the graph becomes empty.
    This is destructive and cannot be undone.

    Args:
        params: Empty dict
    """
    return fmt(await gephi.request("POST", "/graph/clear"))

@mcp.tool(name="gephi_edge_thickness_by_weight")
async def gephi_edge_thickness_by_weight(params: dict) -> str:
    """Scale edge thickness proportionally to edge weight.

    Configures the preview to render edges with thickness based on their
    weight values, scaled between min and max thickness.

    Args:
        params: {min_thickness: float (default 1), max_thickness: float (default 5)}
    """
    return fmt(await gephi.request("POST", "/appearance/edge/thickness-by-weight", json_data=params or {}))


# ─── Preview ─────────────────────────────────────────────────

@mcp.tool(name="gephi_get_preview_settings")
async def gephi_get_preview_settings(params: dict) -> str:
    """Get current preview/rendering settings.

    Returns all configurable preview properties including background color,
    node labels, edge style, opacity, etc.

    Args:
        params: Empty dict
    """
    return fmt(await gephi.request("GET", "/preview/settings"))

@mcp.tool(name="gephi_set_preview_settings")
async def gephi_set_preview_settings(params: dict) -> str:
    """Set preview/rendering settings for export.

    Controls how the graph is rendered in exports (PNG, PDF, SVG).
    Properties include background color, label visibility, edge thickness, etc.

    Args:
        params: Dict of preview property names to values
    """
    return fmt(await gephi.request("POST", "/preview/settings", json_data=params))


# ─── Export ──────────────────────────────────────────────────

@mcp.tool(name="gephi_export_gexf")
async def gephi_export_gexf(params: dict) -> str:
    """Export the graph to GEXF format.

    GEXF is an XML-based format that preserves all graph data including
    node/edge attributes, positions, and visualization properties.

    Args:
        params: {file: str} - absolute output path
    """
    return fmt(await gephi.request("POST", "/export/gexf", json_data=params))

@mcp.tool(name="gephi_export_png")
async def gephi_export_png(params: dict) -> str:
    """Export the graph visualization as a PNG image.

    Renders the current graph visualization to an image file.
    Run a layout algorithm first to position nodes meaningfully.

    Args:
        params: {file: str, width: int (optional, default 1920), height: int (optional, default 1080)}
    """
    return fmt(await gephi.request("POST", "/export/png", json_data=params))

@mcp.tool(name="gephi_export_pdf")
async def gephi_export_pdf(params: dict) -> str:
    """Export the graph visualization as a PDF.

    Args:
        params: {file: str, width: int (optional), height: int (optional)}
    """
    return fmt(await gephi.request("POST", "/export/pdf", json_data=params))

@mcp.tool(name="gephi_export_svg")
async def gephi_export_svg(params: dict) -> str:
    """Export the graph visualization as SVG (Scalable Vector Graphics).

    Args:
        params: {file: str}
    """
    return fmt(await gephi.request("POST", "/export/svg", json_data=params))

@mcp.tool(name="gephi_export_graphml")
async def gephi_export_graphml(params: dict) -> str:
    """Export the graph to GraphML format.

    GraphML is an XML-based format widely supported by graph tools.

    Args:
        params: {file: str}
    """
    return fmt(await gephi.request("POST", "/export/graphml", json_data=params))

@mcp.tool(name="gephi_export_csv")
async def gephi_export_csv(params: dict) -> str:
    """Export the graph to CSV format.

    Args:
        params: {file: str, separator: str (optional, default ','), target: 'nodes'|'edges'|'both'}
    """
    return fmt(await gephi.request("POST", "/export/csv", json_data=params))


# ─── Import ──────────────────────────────────────────────────

@mcp.tool(name="gephi_import_gexf")
async def gephi_import_gexf(params: dict) -> str:
    """Import a graph from a GEXF file.

    Loads graph data from a GEXF file into the current workspace.
    The imported data is merged with any existing graph.

    Args:
        params: {file: str} - absolute path to the GEXF file
    """
    return fmt(await gephi.request("POST", "/import/gexf", json_data=params))

@mcp.tool(name="gephi_import_graphml")
async def gephi_import_graphml(params: dict) -> str:
    """Import a graph from a GraphML file.

    Args:
        params: {file: str}
    """
    return fmt(await gephi.request("POST", "/import/graphml", json_data=params))

@mcp.tool(name="gephi_import_csv")
async def gephi_import_csv(params: dict) -> str:
    """Import a graph from a CSV file.

    Args:
        params: {file: str}
    """
    return fmt(await gephi.request("POST", "/import/csv", json_data=params))

@mcp.tool(name="gephi_import_file")
async def gephi_import_file(params: dict) -> str:
    """Import a graph from any supported file format (auto-detected by extension).

    Supports: GEXF, GraphML, GML, CSV, DOT, Pajek, and more. Imported node sizes
    are capped at 30 so a viz:size from the source file can't render nodes
    enormous; re-size afterward with gephi_size_by_ranking if needed.

    Args:
        params: {file: str}
    """
    return fmt(await gephi.request("POST", "/import/file", json_data=params))


# ==================== Main Entry Point ====================

if __name__ == "__main__":
    mcp.run()
