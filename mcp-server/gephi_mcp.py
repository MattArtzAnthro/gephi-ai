"""
Gephi MCP Server - Model Context Protocol server for controlling Gephi Desktop

This MCP server enables LLMs to interact with a running Gephi Desktop instance
through the Gephi MCP Plugin's HTTP API.

Each tool exposes typed parameters, so MCP clients receive a precise JSON schema
per tool (field names, types, and which are optional) rather than an opaque blob.

Claude Code Skill:
    This server is paired with a Claude Code skill that provides workflows,
    best practices, and visualization guidelines for using these tools.
    See: plugins/claude-code/skills/gephi/SKILL.md

Developed by Matt Artz (https://www.mattartz.me)
"""

import asyncio
import contextlib
import importlib.metadata
import json
import logging
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import httpx
from mcp.server import CacheHint, MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations

import gephi_mcp_viewer
import text_network
from bipartite import bipartite_positions, project_bipartite, split_modes
from community_stability import consensus
from graph_diff import diff_graphs
from legend import legend_document
from session_ledger import Ledger
from stats_integrity import (
    GraphFacts,
    caveats_for,
    mutates_graph,
    needs_graph_facts,
    replaces_graph,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gephi_mcp")

# Both are overridable via environment so the server can target a non-default
# Gephi host/port or a slower machine without code changes.
GEPHI_API_URL = os.environ.get("GEPHI_API_URL", "http://127.0.0.1:8080")
REQUEST_TIMEOUT = float(os.environ.get("GEPHI_REQUEST_TIMEOUT", "60.0"))
# Some statistics are O(n*m) (betweenness, average path length) or run an
# unbounded plugin algorithm (run_statistic). On large graphs these legitimately
# run well past the default timeout — the computation is fine, the client just
# needs to wait longer. These tools pass SLOW_REQUEST_TIMEOUT explicitly.
SLOW_REQUEST_TIMEOUT = float(os.environ.get("GEPHI_SLOW_TIMEOUT", "600.0"))

# ── Undo snapshots ─────────────────────────────────────────────────────────
# A rolling one-level undo: before each destructive tool runs, the current
# workspace is duplicated into a "[undo] ..." workspace (then we switch straight
# back), so gephi_undo can restore the pre-operation graph. One snapshot exists
# at a time — taking a new one deletes the old — so memory stays bounded at
# roughly 2x the working graph.
AUTO_SNAPSHOT = os.environ.get("GEPHI_AUTO_SNAPSHOT", "1") != "0"
# Above this node count the automatic snapshot is skipped (duplicating a huge
# graph before every destructive call costs real time and memory). Manual
# gephi_snapshot ignores the cap — calling it is the explicit choice to pay.
SNAPSHOT_MAX_NODES = int(os.environ.get("GEPHI_SNAPSHOT_MAX_NODES", "200000"))
UNDO_PREFIX = "[undo] "

# ── Version freshness (checked once per session in health_check) ──────────
try:
    # version() can RETURN None rather than raise when a site-packages directory holds
    # more than one dist-info for this package (an orphaned one from an earlier install
    # is enough). Treating a falsy return as "unknown" keeps a null out of the session
    # receipt, which is meant to be pasted into a methods section.
    # The distribution is "gephi-ai"; it was "gephi-mcp" before the rename. The import
    # module stays gephi_mcp, so do not "correct" this back to match the module name.
    __version__ = importlib.metadata.version("gephi-ai") or None
except Exception:  # running from source, not an installed dist
    __version__ = None  # source run: no version to compare, server-freshness check skips
# One canonical version file on main; a raw file is not GitHub-API-rate-limited.
LATEST_URL = ("https://raw.githubusercontent.com/MattArtzAnthro/gephi-ai/"
              "main/latest.json")
_freshness_cache: dict[str, Any] = {}  # checked once per process


def _semver(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:3])


def _is_behind(installed: str, latest: str) -> bool:
    if not installed or not latest:
        return False
    try:
        return _semver(installed) < _semver(latest)
    except Exception:
        return False


async def _check_freshness(health: dict[str, Any]) -> dict[str, Any] | None:
    """Compare the running server + Gephi plugin against the latest published
    versions. Fail-silent, 2s timeout, cached once per process, opt-out via
    GEPHI_SKIP_UPDATE_CHECK. Returns an 'update' dict when something is behind."""
    if os.environ.get("GEPHI_SKIP_UPDATE_CHECK"):
        return None
    if "result" in _freshness_cache:
        return _freshness_cache["result"]
    result = None
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            latest = (await client.get(LATEST_URL)).json()
        behind = []
        if _is_behind(__version__, latest.get("server")):
            behind.append({"component": "gephi-ai plugin + server",
                           "installed": __version__, "latest": latest["server"]})
        nbm = health.get("version")  # Gephi plugin version from /health
        if _is_behind(nbm, latest.get("nbm")):
            behind.append({"component": "Gephi Desktop plugin (.nbm)",
                           "installed": nbm, "latest": latest["nbm"]})
        if behind:
            result = {
                "available": True,
                "behind": behind,
                "how_to_update": (
                    "Claude Code: run `claude plugin update "
                    "gephi-network-analysis@gephi-ai`, then restart. "
                    "Claude Desktop: download the newest .mcpb from the Releases "
                    "page. Gephi plugin: install the newest .nbm from Releases via "
                    "Tools > Plugins > Downloaded, then restart Gephi."),
            }
        else:
            result = {"available": False}  # checked and current (distinct from None)
    except Exception:
        result = None  # check couldn't run (offline/error) — status unknown, stay silent
    _freshness_cache["result"] = result
    return result

# tools/list and resources/list are static for the life of a release: 106 schemas
# (~77k chars) that a host can cache instead of re-fetching per session.
def _package_version() -> str:
    try:
        # See the note on __version__: this can return None instead of raising.
        return importlib.metadata.version("gephi-ai") or "0.0.0"
    except importlib.metadata.PackageNotFoundError:  # running from a bare checkout
        return "0.0.0"


mcp = MCPServer(
    "gephi_mcp",
    version=_package_version(),
    cache_hints={
        "tools/list": CacheHint(ttl_ms=3_600_000, scope="public"),
        "resources/list": CacheHint(ttl_ms=3_600_000, scope="public"),
    },
)

# ==================== Tool annotations ====================
# Hints for hosts (confirmation prompts, read-only fast paths). Classified by
# effect on the Gephi workspace, not on the filesystem: exports write files but
# never change the graph, so they are neither read-only nor destructive.
#   read-only:   reads state, writes nothing to the graph
#   destructive: removes nodes/edges/workspaces or replaces the current graph
#                (each auto-snapshots first, so gephi_undo reverses it)
#   everything else: adds or restyles without removing (columns, colors, layout)
_READ_ONLY = {
    "gephi_health_check", "gephi_get_project_info", "gephi_list_workspaces",
    "gephi_query_nodes", "gephi_get_node", "gephi_query_edges",
    "gephi_get_graph_stats", "gephi_get_graph_type", "gephi_get_columns",
    "gephi_get_layout_status", "gephi_get_available_layouts",
    "gephi_get_layout_properties", "gephi_profile_graph", "gephi_list_statistics",
    "gephi_list_filters", "gephi_get_timeline", "gephi_column_value_frequencies",
    "gephi_detect_duplicates", "gephi_get_preview_settings", "gephi_get_perspective",
    "gephi_get_selection", "gephi_view_graph", "gephi_whatif", "gephi_compare_nodes",
}
_DESTRUCTIVE = {
    "gephi_create_project", "gephi_open_project", "gephi_delete_workspace",
    "gephi_undo", "gephi_remove_node", "gephi_bulk_remove_nodes",
    "gephi_remove_edge", "gephi_filter_by_degree", "gephi_filter_by_edge_weight",
    "gephi_remove_isolates", "gephi_extract_ego_network",
    "gephi_extract_giant_component", "gephi_extract_backbone",
    "gephi_merge_nodes", "gephi_clear_graph", "gephi_reset_appearance",
    "gephi_reset_filters", "gephi_apply_filter",
}
# Reaches beyond Gephi: the health check fetches latest.json from GitHub.
_OPEN_WORLD = {"gephi_health_check"}


def _annotations_for(name: str) -> ToolAnnotations:
    read_only = name in _READ_ONLY
    return ToolAnnotations(
        read_only_hint=read_only,
        destructive_hint=name in _DESTRUCTIVE,
        idempotent_hint=read_only,
        open_world_hint=name in _OPEN_WORLD,
    )


def _tool(name: str, **kwargs: Any):
    """mcp.tool() with the annotation table applied. Every tool registers through
    this so a new tool cannot ship unclassified."""
    return mcp.tool(name=name, annotations=_annotations_for(name), **kwargs)


# ==================== HTTP Client ====================

class GephiClient:
    def __init__(self, base_url: str = GEPHI_API_URL):
        self.base_url = base_url.rstrip("/")
        self.timeout = REQUEST_TIMEOUT

    async def request(self, method: str, endpoint: str,
                      params: dict[str, Any] | None = None,
                      json_data: dict[str, Any] | None = None,
                      timeout: float | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        # Cached graph facts describe a particular graph. Any call that could change which graph
        # we are looking at, or its shape, retires them before it runs.
        if mutates_graph(method, endpoint):
            invalidate_graph_facts()
            if replaces_graph(method, endpoint):
                LEDGER.reset()
        try:
            async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
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


# ── Undo snapshot machinery ────────────────────────────────────────────────
# The workspace API is index-based and indices shift whenever a workspace is
# added or deleted, so every step below re-resolves workspaces from a fresh
# /workspace/list (matching by the stable workspace id, or by the "[undo] "
# name prefix for the snapshot itself). Also: /workspace/duplicate switches the
# current workspace TO the copy, which is why a snapshot ends by switching back.

async def _workspaces() -> list[dict[str, Any]] | None:
    r = await gephi.request("GET", "/workspace/list")
    if isinstance(r, dict) and r.get("success") and isinstance(r.get("workspaces"), list):
        return r["workspaces"]
    return None


def _is_snapshot(w: dict[str, Any]) -> bool:
    return str(w.get("name", "")).startswith(UNDO_PREFIX)


def _index_of(wss: list[dict[str, Any]], workspace_id: Any) -> int | None:
    return next((i for i, w in enumerate(wss) if w.get("id") == workspace_id), None)


def _original_name(snapshot_name: str) -> str:
    """Recover the workspace's pre-snapshot name from '[undo] <name> (before <op>)'."""
    base = snapshot_name
    if base.startswith(UNDO_PREFIX):
        base = base[len(UNDO_PREFIX):]
    if " (before " in base and base.endswith(")"):
        base = base.rsplit(" (before ", 1)[0]
    return base


async def _snapshot_current(op: str, enforce_cap: bool = False) -> dict[str, Any]:
    """Duplicate the current workspace into the rolling '[undo] ...' snapshot.

    Returns {"ok": True, "snapshot": name} or {"ok": False, "reason": ...}.
    Replaces any existing snapshot (deleted before duplicating, so peak memory
    stays bounded). enforce_cap applies SNAPSHOT_MAX_NODES (auto-snapshots
    only; manual snapshots pay whatever the graph costs).
    """
    wss = await _workspaces()
    if wss is None:
        return {"ok": False, "reason": "workspace list unavailable"}
    cur = next((w for w in wss if w.get("current")), None)
    if cur is None:
        return {"ok": False, "reason": "no current workspace"}
    if _is_snapshot(cur):
        return {"ok": False, "reason": "the current workspace is itself an undo "
                "snapshot; switch to a working workspace before snapshotting"}
    if enforce_cap and cur.get("node_count", 0) > SNAPSHOT_MAX_NODES:
        return {"ok": False, "reason": f"graph exceeds GEPHI_SNAPSHOT_MAX_NODES "
                f"({SNAPSHOT_MAX_NODES}); use gephi_snapshot to snapshot explicitly"}

    old_i = next((i for i, w in enumerate(wss) if _is_snapshot(w)), None)
    if old_i is not None:  # rolling: one snapshot at a time
        await gephi.request("DELETE", "/workspace/delete", params={"index": str(old_i)})
        wss = await _workspaces()  # indices shifted
        if wss is None:
            return {"ok": False, "reason": "workspace list unavailable"}

    cur_i = _index_of(wss, cur.get("id"))
    if cur_i is None:
        return {"ok": False, "reason": "current workspace disappeared mid-snapshot"}
    dup = await gephi.request("POST", "/workspace/duplicate", json_data={"index": cur_i})
    if not dup.get("success", False):
        return {"ok": False, "reason": dup.get("error", "duplicate failed")}

    wss = await _workspaces()
    if wss is None:
        return {"ok": False, "reason": "workspace list unavailable after duplicate"}
    copy_i = next((i for i, w in enumerate(wss)
                   if w.get("current") and w.get("id") != cur.get("id")), None)
    if copy_i is None:
        return {"ok": False, "reason": "duplicate did not switch to the copy"}
    snap_name = f"{UNDO_PREFIX}{cur['name']} (before {op})"
    await gephi.request("POST", "/workspace/rename",
                        json_data={"index": copy_i, "name": snap_name})
    orig_i = _index_of(wss, cur.get("id"))
    sw = await gephi.request("POST", "/workspace/switch", json_data={"index": orig_i})
    if not sw.get("success", False):
        return {"ok": False, "reason": "could not switch back to the original workspace"}
    return {"ok": True, "snapshot": snap_name}


async def _auto_snapshot(op: str) -> bool:
    """Best-effort rolling snapshot before a destructive op.

    Never raises and never blocks the operation — a failed snapshot just means
    the op's result reports undo_available: false.
    """
    if not AUTO_SNAPSHOT:
        return False
    try:
        result = await _snapshot_current(op, enforce_cap=True)
        return bool(result.get("ok"))
    except Exception:
        return False


def _with_undo(result: Any, undo_ok: bool) -> Any:
    if isinstance(result, dict):
        result["undo_available"] = undo_ok
    return result


# ==================== MCP Tools ====================

# ─── Health ───────────────────────────────────────────────────

@_tool(name="gephi_health_check")
async def gephi_health_check() -> str:
    """Check if Gephi Desktop is running and the MCP plugin is accessible.

    The response's graph_lock field is a wedge detector: "ok" is healthy; a
    persistent "busy" means Gephi's graph lock is unavailable and the app needs a
    full restart (known macOS renderer issue). graph_lock_stats gives the live
    lock counters: a nonzero "readers" while Gephi is idle means a leaked read
    hold (writes will fail until restart); "queued" > 0 for long means a writer
    is starving.

    Also reports `server_version` (the MCP server) alongside `version` (the Gephi
    plugin), plus a freshness signal checked once per session: `update` when the
    install is behind the latest release (tell the user once, plainly, with the
    how_to_update step), or `up_to_date: true` when it is current. Neither appears
    if the check can't reach the network (then say nothing about versions).
    """
    health = await gephi.request("GET", "/health")
    if isinstance(health, dict) and health.get("success"):
        # Surface the MCP server version alongside the Gephi plugin version (the
        # response's "version" field) so what's installed is always visible, not
        # inferred from silence.
        health["server_version"] = __version__ or "unknown (running from source)"
        fresh = await _check_freshness(health)
        if fresh and fresh.get("available"):
            health["update"] = fresh          # something is behind
        elif fresh is not None:
            health["up_to_date"] = True       # checked and current
        # fresh is None -> couldn't check (offline/opt-out); say nothing
    return fmt(health)


# ─── Project ─────────────────────────────────────────────────

@_tool(name="gephi_create_project")
async def gephi_create_project(name: str = "New Project") -> str:
    """Create a new empty Gephi project/workspace."""
    return fmt(await gephi.request("POST", "/project/new", json_data={"name": name}))

@_tool(name="gephi_open_project")
async def gephi_open_project(file: str) -> str:
    """Open an existing Gephi project file (.gephi). `file` is an absolute path.

    WARNING: this closes the current project first, DISCARDING any unsaved changes
    in it without prompting (unlike Gephi's own File > Open). If the current graph
    has unsaved work the person might want, `gephi_save_project` it (or confirm with
    them) BEFORE opening another file.

    It then loads and returns node_count/edge_count so you can confirm the graph came
    back (a 0 count means the file was empty). For a reversible experiment (a
    what-if, a teaching demo), prefer an in-memory undo
    over a save/reopen round-trip: `gephi_duplicate_workspace` a copy and run the
    destructive step on the copy, so "undo" is just switching back — instant, no disk.
    If you must snapshot to disk, `gephi_export_gexf` + `gephi_import_file` also
    round-trips reliably."""
    return fmt(await gephi.request("POST", "/project/open", json_data={"file": file}))

@_tool(name="gephi_save_project")
async def gephi_save_project(file: str) -> str:
    """Save the current Gephi project. `file` is the absolute destination path."""
    return fmt(await gephi.request("POST", "/project/save", json_data={"file": file}))

@_tool(name="gephi_get_project_info")
async def gephi_get_project_info() -> str:
    """Get current project info: workspace status, node/edge counts, and graph type."""
    return fmt(await gephi.request("GET", "/project/info"))


# ─── Workspace ────────────────────────────────────────────────

@_tool(name="gephi_new_workspace")
async def gephi_new_workspace() -> str:
    """Create a new workspace in the current project."""
    return fmt(await gephi.request("POST", "/workspace/new"))

@_tool(name="gephi_list_workspaces")
async def gephi_list_workspaces() -> str:
    """List all workspaces in the current project."""
    return fmt(await gephi.request("GET", "/workspace/list"))

@_tool(name="gephi_switch_workspace")
async def gephi_switch_workspace(index: int) -> str:
    """Switch to a different workspace by zero-based index."""
    return fmt(await gephi.request("POST", "/workspace/switch", json_data={"index": index}))

@_tool(name="gephi_delete_workspace")
async def gephi_delete_workspace(index: int) -> str:
    """Delete a workspace by zero-based index."""
    return fmt(await gephi.request("DELETE", "/workspace/delete", params={"index": str(index)}))

@_tool(name="gephi_duplicate_workspace")
async def gephi_duplicate_workspace(index: int) -> str:
    """Duplicate a workspace by index, copying graph data, statistics, and appearance."""
    return fmt(await gephi.request("POST", "/workspace/duplicate", json_data={"index": index}))

@_tool(name="gephi_rename_workspace")
async def gephi_rename_workspace(index: int, name: str) -> str:
    """Rename the workspace at the given zero-based index."""
    return fmt(await gephi.request("POST", "/workspace/rename", json_data={"index": index, "name": name}))


# ─── Undo ─────────────────────────────────────────────────────

@_tool(name="gephi_snapshot")
async def gephi_snapshot(label: str = "") -> str:
    """Save an undo point: copy the current workspace so gephi_undo can restore it.

    The copy appears as a "[undo] ..." workspace in Gephi's tab bar and replaces
    any previous snapshot — one undo point exists at a time, so this is a
    one-level undo (no redo). Destructive tools (clear_graph, merge_nodes, the
    filter/extract family) already take this snapshot automatically before they
    run; call this explicitly before a risky sequence of SMALL edits (per-node
    removals, attribute rewrites) that aren't auto-snapshotted, or to move the
    undo point forward after work you want to keep.

    label: optional note recorded in the snapshot's name, e.g.
    label="manual cleanup" -> "[undo] MyGraph (before manual cleanup)".
    """
    result = await _snapshot_current(label or "snapshot", enforce_cap=False)
    if result.get("ok"):
        return fmt({"success": True, "snapshot": result["snapshot"],
                    "message": "Undo point saved. gephi_undo restores the graph to this state."})
    return fmt({"success": False, "error": result.get("reason", "snapshot failed")})


@_tool(name="gephi_undo")
async def gephi_undo() -> str:
    """Restore the graph to the last undo snapshot, discarding changes since.

    Switches to the "[undo] ..." snapshot workspace, deletes the modified
    workspace, and renames the snapshot back to its original name — so the graph
    (nodes, edges, attributes, positions, appearance) is exactly as it was when
    the snapshot was taken. One level only: after undoing there is no snapshot
    left until the next destructive tool (or gephi_snapshot) creates one, and
    there is no redo — to compare before/after instead of reverting, use
    gephi_whatif or duplicate the workspace yourself before editing.

    Errors with "nothing to undo" if no snapshot exists (none taken yet, already
    undone, or the graph was above GEPHI_SNAPSHOT_MAX_NODES when the destructive
    tool ran — its result would have said undo_available: false).
    """
    wss = await _workspaces()
    if wss is None:
        return fmt({"success": False, "error": "workspace list unavailable"})
    snap = next((w for w in wss if _is_snapshot(w)), None)
    if snap is None:
        return fmt({"success": False, "error":
                    "Nothing to undo: no undo snapshot exists. Snapshots are taken "
                    "automatically before destructive tools, or explicitly with "
                    "gephi_snapshot."})
    restored = _original_name(str(snap.get("name", "")))
    cur = next((w for w in wss if w.get("current")), None)

    if cur is not None and cur.get("id") == snap.get("id"):
        # Already sitting on the snapshot (e.g. the person switched to it by
        # hand): just give it back its working name.
        snap_i = _index_of(wss, snap.get("id"))
        rn = await gephi.request("POST", "/workspace/rename",
                                 json_data={"index": snap_i, "name": restored})
        if not rn.get("success", False):
            return fmt(rn)
        return fmt({"success": True, "restored": restored,
                    "node_count": snap.get("node_count"),
                    "edge_count": snap.get("edge_count")})

    snap_i = _index_of(wss, snap.get("id"))
    sw = await gephi.request("POST", "/workspace/switch", json_data={"index": snap_i})
    if not sw.get("success", False):
        return fmt(sw)
    if cur is not None:
        fresh = await _workspaces()  # indices may differ from the first list
        if fresh is not None:
            damaged_i = _index_of(fresh, cur.get("id"))
            if damaged_i is not None:
                await gephi.request("DELETE", "/workspace/delete",
                                    params={"index": str(damaged_i)})
    fresh = await _workspaces()
    if fresh is None:
        return fmt({"success": False, "error": "workspace list unavailable after undo"})
    snap_i = _index_of(fresh, snap.get("id"))
    if snap_i is None:
        return fmt({"success": False, "error": "snapshot workspace lost during undo"})
    rn = await gephi.request("POST", "/workspace/rename",
                             json_data={"index": snap_i, "name": restored})
    if not rn.get("success", False):
        return fmt(rn)
    entry = fresh[snap_i]
    return fmt({"success": True, "restored": restored,
                "node_count": entry.get("node_count"),
                "edge_count": entry.get("edge_count")})


# ─── Nodes ────────────────────────────────────────────────────

@_tool(name="gephi_add_node")
async def gephi_add_node(id: str, label: str | None = None,
                         attributes: dict[str, Any] | None = None) -> str:
    """Add a single node. Placed at a random position; run a layout to reposition.

    attributes: optional {column: value} map; columns are created automatically.
    """
    return fmt(await gephi.request("POST", "/graph/node/add",
                                   json_data=_body(id=id, label=label, attributes=attributes)))

@_tool(name="gephi_add_nodes")
async def gephi_add_nodes(nodes: list[dict[str, Any]]) -> str:
    """Add multiple nodes in one batch (efficient for large graphs).

    Each node: {id: str, label?: str, attributes?: {column: value}}.
    Duplicate IDs are skipped; per-node attributes are applied.
    """
    return fmt(await gephi.request("POST", "/graph/nodes/add", json_data={"nodes": nodes}))

@_tool(name="gephi_remove_node")
async def gephi_remove_node(id: str) -> str:
    """Remove a node and all its connected edges. Destructive.

    Single-node removals are NOT auto-snapshotted (a snapshot per node would
    thrash on bulk cleanups) — call gephi_snapshot first if this might need
    undoing, or use gephi_bulk_remove_nodes, which is.
    """
    return fmt(await gephi.request("DELETE", f"/graph/node/{id}"))

@_tool(name="gephi_bulk_remove_nodes")
async def gephi_bulk_remove_nodes(ids: list[str]) -> str:
    """Remove multiple nodes (and their edges) by ID. Destructive; an undo
    snapshot is taken automatically first (gephi_undo reverses it)."""
    undo = await _auto_snapshot("bulk_remove_nodes")
    return fmt(_with_undo(await gephi.request("POST", "/graph/nodes/remove",
                                              json_data={"ids": ids}), undo))

@_tool(name="gephi_query_nodes")
async def gephi_query_nodes(limit: int = 100, offset: int = 0) -> str:
    """List nodes with their attributes, positions, sizes, colors, and computed
    metrics, paginated. Use it to read values (a centrality column, a community
    id, a label) for many nodes at once; gephi_get_node reads one."""
    return fmt(await gephi.request("GET", "/graph/nodes", params={"limit": limit, "offset": offset}))

@_tool(name="gephi_get_node")
async def gephi_get_node(id: str) -> str:
    """Get full details for a single node: id, label, x/y, size, color, and attributes."""
    return fmt(await gephi.request("GET", f"/graph/node/get/{id}"))

@_tool(name="gephi_set_node_label")
async def gephi_set_node_label(id: str, label: str) -> str:
    """Set or change the label of a node."""
    return fmt(await gephi.request("POST", "/graph/node/label", json_data={"id": id, "label": label}))

@_tool(name="gephi_set_node_position")
async def gephi_set_node_position(id: str, x: float, y: float) -> str:
    """Set the X/Y position of a node."""
    return fmt(await gephi.request("POST", "/graph/node/position", json_data={"id": id, "x": x, "y": y}))

@_tool(name="gephi_batch_set_positions")
async def gephi_batch_set_positions(positions: list[dict[str, Any]]) -> str:
    """Set positions of multiple nodes at once. Each entry: {id: str, x: float, y: float}."""
    return fmt(await gephi.request("POST", "/graph/nodes/positions", json_data={"positions": positions}))


# ─── Edges ────────────────────────────────────────────────────

@_tool(name="gephi_add_edge")
async def gephi_add_edge(source: str, target: str, weight: float = 1.0, directed: bool = True,
                         edge_type: str | None = None) -> str:
    """Add an edge between two existing nodes.

    edge_type: an optional relationship-type label. Normally a pair of nodes can
    hold only one edge; giving a type lets the same pair carry several parallel
    edges of different types (e.g. a "cites" edge and a "coauthor" edge between
    the same two authors) — a multiplex/multilayer graph. A second edge of the
    SAME type between the same pair is still rejected as a duplicate. Omit it for
    ordinary single-edge behavior.
    """
    return fmt(await gephi.request("POST", "/graph/edge/add",
                                   json_data=_body(source=source, target=target,
                                                   weight=weight, directed=directed,
                                                   edge_type=edge_type)))

@_tool(name="gephi_add_edges")
async def gephi_add_edges(edges: list[dict[str, Any]]) -> str:
    """Add multiple edges in one batch.

    Each edge: {source: str, target: str, weight?: float, directed?: bool,
    label?: str, edge_type?: str, attributes?: {column: value}}. Edges
    referencing missing nodes, or duplicates, are skipped. `edge_type` gives the
    pair a named relationship type so several parallel typed edges can coexist
    between the same two nodes (multiplex graph); a duplicate is only skipped
    within the same type.
    """
    return fmt(await gephi.request("POST", "/graph/edges/add", json_data={"edges": edges}))

@_tool(name="gephi_remove_edge")
async def gephi_remove_edge(source: str, target: str) -> str:
    """Remove the edge between two nodes."""
    return fmt(await gephi.request("POST", "/graph/edge/remove",
                                   json_data={"source": source, "target": target}))

@_tool(name="gephi_set_edge_weight")
async def gephi_set_edge_weight(source: str, target: str, weight: float) -> str:
    """Set the weight of an edge."""
    return fmt(await gephi.request("POST", "/graph/edge/weight",
                                   json_data={"source": source, "target": target, "weight": weight}))

@_tool(name="gephi_set_edge_label")
async def gephi_set_edge_label(source: str, target: str, label: str) -> str:
    """Set or change the label of an edge."""
    return fmt(await gephi.request("POST", "/graph/edge/label",
                                   json_data={"source": source, "target": target, "label": label}))

@_tool(name="gephi_query_edges")
async def gephi_query_edges(limit: int = 100, offset: int = 0) -> str:
    """List edges with source, target, weight, direction, and attributes,
    paginated. Use it to read relationship values for many edges at once."""
    return fmt(await gephi.request("GET", "/graph/edges", params={"limit": limit, "offset": offset}))


# ─── Graph Stats & Type ──────────────────────────────────────

@_tool(name="gephi_get_graph_stats")
async def gephi_get_graph_stats() -> str:
    """Get node count, edge count, density, average degree, and graph type."""
    return fmt(await gephi.request("GET", "/graph/stats"))

@_tool(name="gephi_get_graph_type")
async def gephi_get_graph_type() -> str:
    """Get whether the graph is directed, undirected, or mixed."""
    return fmt(await gephi.request("GET", "/graph/type"))


# ─── Attributes / Columns ────────────────────────────────────

@_tool(name="gephi_get_columns")
async def gephi_get_columns(target: str = "node") -> str:
    """List columns (attributes) in the node or edge table. target: "node" | "edge"."""
    return fmt(await gephi.request("GET", "/graph/columns", params={"target": target}))

@_tool(name="gephi_add_column")
async def gephi_add_column(name: str, type: str, target: str = "node") -> str:
    """Add a column to the node or edge table.

    type: "string" | "integer" | "double" | "float" | "boolean" | "long".
    target: "node" | "edge".
    """
    return fmt(await gephi.request("POST", "/graph/columns/add",
                                   json_data={"name": name, "type": type, "target": target}))

@_tool(name="gephi_set_node_attributes")
async def gephi_set_node_attributes(id: str, attributes: dict[str, Any]) -> str:
    """Set custom attributes on a node. Columns are created automatically if needed."""
    return fmt(await gephi.request("POST", "/graph/node/attributes",
                                   json_data={"id": id, "attributes": attributes}))

@_tool(name="gephi_batch_set_node_attributes")
async def gephi_batch_set_node_attributes(updates: list[dict[str, Any]]) -> str:
    """Set attributes on multiple nodes. Each update: {id: str, attributes: {column: value}}."""
    return fmt(await gephi.request("POST", "/graph/nodes/attributes", json_data={"updates": updates}))

@_tool(name="gephi_set_edge_attributes")
async def gephi_set_edge_attributes(source: str, target: str, attributes: dict[str, Any]) -> str:
    """Set custom attributes on an edge. Columns are created automatically if needed."""
    return fmt(await gephi.request("POST", "/graph/edge/attributes",
                                   json_data={"source": source, "target": target, "attributes": attributes}))


# ─── Appearance: Individual Styling ──────────────────────────

def _fmt_styled(resp: dict[str, Any], operation: str, **detail: Any) -> str:
    """Format a styling result, noting it in the ledger when Gephi accepted it.

    Only a call the application actually applied belongs in the record: a refused one changed
    nothing, and a legend describing it would name an encoding the map does not carry.
    """
    if isinstance(resp, dict) and resp.get("success"):
        LEDGER.record(operation, **detail)
    return fmt(resp)



@_tool(name="gephi_set_node_color")
async def gephi_set_node_color(id: str, r: int, g: int, b: int, a: int = 255) -> str:
    """Set the color of a single node. r/g/b/a are 0-255."""
    return fmt(await gephi.request("POST", "/appearance/node/color",
                                   json_data={"id": id, "r": r, "g": g, "b": b, "a": a}))

@_tool(name="gephi_set_node_size")
async def gephi_set_node_size(id: str, size: float) -> str:
    """Set the size of a single node."""
    return fmt(await gephi.request("POST", "/appearance/node/size", json_data={"id": id, "size": size}))

@_tool(name="gephi_set_edge_color")
async def gephi_set_edge_color(source: str, target: str, r: int, g: int, b: int, a: int = 255) -> str:
    """Set the color of a single edge. r/g/b/a are 0-255."""
    return fmt(await gephi.request("POST", "/appearance/edge/color",
                                   json_data={"source": source, "target": target,
                                              "r": r, "g": g, "b": b, "a": a}))

@_tool(name="gephi_batch_set_node_colors")
async def gephi_batch_set_node_colors(nodes: list[dict[str, Any]]) -> str:
    """Set colors of multiple nodes. Each entry: {id: str, r: int, g: int, b: int, a?: int}."""
    return fmt(await gephi.request("POST", "/appearance/nodes/color", json_data={"nodes": nodes}))

@_tool(name="gephi_reset_appearance")
async def gephi_reset_appearance(r: int = 153, g: int = 153, b: int = 153, size: float = 10) -> str:
    """Reset all nodes to a default color and size (defaults to grey / size 10)."""
    return fmt(await gephi.request("POST", "/appearance/reset",
                                   json_data={"r": r, "g": g, "b": b, "size": size}))


# ─── Appearance: Color/Size by Attribute ─────────────────────

@_tool(name="gephi_color_by_partition")
async def gephi_color_by_partition(column: str, colors: dict[str, list[int]] | None = None) -> str:
    """Color nodes by a categorical attribute (e.g. modularity_class, type).

    colors: optional {value: [r, g, b]} map; otherwise a distinct palette is assigned.
    Recommended palette (validated for readability on white exports and colorblind
    separation; pale/pastel colors are near-invisible on white): {"0": [42,120,214],
    "1": [27,175,122], "2": [237,161,0], "3": [0,131,0], "4": [74,58,167],
    "5": [227,73,72], "6": [232,123,164], "7": [235,104,52]}. With more than 8
    categories, color the 8 largest and set the rest to gray [153,153,153].
    """
    return _fmt_styled(await gephi.request("POST", "/appearance/partition/color",
                                           json_data=_body(column=column, colors=colors)),
                       "color_by_partition", column=column)

@_tool(name="gephi_color_edges_by_partition")
async def gephi_color_edges_by_partition(column: str,
                                         colors: dict[str, list[int]] | None = None) -> str:
    """Color edges by a categorical EDGE attribute (relationship type, period, tier).

    The edge counterpart to gephi_color_by_partition. Use it when edges carry a
    type worth seeing — co-authorship vs. citation, time period, weight tier — so
    the relationship kind reads at a glance. colors is an optional {value:
    [r, g, b]} map; otherwise a distinct palette is assigned. Note the different
    default edge-styling advice: on a dense graph, per-source edge coloring
    usually reads as noise (see the text-network guidance), but coloring by a
    small set of relationship TYPES is exactly when edge color earns its keep.
    """
    return fmt(await gephi.request("POST", "/appearance/edge/partition-color",
                                   json_data=_body(column=column, colors=colors)))

@_tool(name="gephi_color_by_ranking")
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

@_tool(name="gephi_size_by_ranking")
async def gephi_size_by_ranking(column: str, min_size: float = 10, max_size: float = 60) -> str:
    """Size nodes by a numeric attribute, mapping values between min_size and max_size.

    Always do this before exporting or viewing — unsized nodes render as invisible
    specks. Degree with min 10, max 60 is a good default; scale up for large canvases.
    """
    return _fmt_styled(await gephi.request("POST", "/appearance/ranking/size",
                                           json_data={"column": column, "min_size": min_size,
                                                      "max_size": max_size}),
                       "size_by_ranking", column=column,
                       min_size=min_size, max_size=max_size)


# ─── Reading the graph ───────────────────────────────────────

async def _export_gexf_inline() -> dict:
    """Export the graph inline as GEXF, with the filter state made explicit.

    This path exports the VISIBLE graph. When a filter is active in Gephi it
    returns a subgraph, while ``/graph/stats`` reports the full graph, and until
    the plugin declared the difference every tool built on this call could reason
    over a subset while believing it had the whole network.

    The plugin now returns ``view``, ``filter_active``, and both node and edge
    counts. This is the single place that reads them, so every caller reports the
    discrepancy the same way and none can quietly drift out of step.
    """
    exported = await gephi.request(
        "POST", "/export/gexf", json_data={"inline": True}
    )
    if not isinstance(exported, dict):
        return exported
    if exported.get("filter_active") and exported.get("view") == "visible":
        full_n = exported.get("full_node_count")
        vis_n = exported.get("visible_node_count")
        if isinstance(full_n, int) and isinstance(vis_n, int) and full_n != vis_n:
            exported["filter_warning"] = (
                f"A filter is active in Gephi. This result was computed from the "
                f"{vis_n} visible nodes, not the {full_n} nodes in the full graph. "
                f"Reset the filter first if you meant to analyse the whole network."
            )
    return exported


def _carry_filter_warning(source: Any, result: Any) -> Any:
    """Propagate a filter warning from an inline export onto a tool's own result."""
    if isinstance(source, dict) and isinstance(result, dict):
        warning = source.get("filter_warning")
        if warning:
            result.setdefault("filter_warning", warning)
    return result


# ─── Layout ──────────────────────────────────────────────────

async def _check_layout_positions() -> dict | None:
    """Detect a numerically exploded layout: non-finite or absurd coordinates.

    ForceAtlas 2 can blow up silently (observed live: coordinates at 1e37 and
    Infinity on a weighted graph with a strong hub) while still reporting
    success. Returns an explosion report dict, or None when positions are sane
    or the check itself can't run (never blocks the layout result).
    """
    exported = await _export_gexf_inline()
    if not exported.get("success") or "content" not in exported:
        return None
    try:
        graph = gephi_mcp_viewer.parse_gexf(exported["content"], max_nodes=10**9)
    except Exception:
        return None
    bad = [n["key"] for n in graph["nodes"]
           if not (math.isfinite(n["x"]) and math.isfinite(n["y"])
                   and abs(n["x"]) < 1e12 and abs(n["y"]) < 1e12)]
    if not bad:
        return None
    return {
        "non_finite_nodes": len(bad),
        "sample": bad[:5],
        "fix": ("the layout exploded numerically — do NOT export or trust these "
                "positions; reset with Random Layout (1 iteration), then rerun "
                "(on weighted graphs, log-transform weights or lower "
                "edgeWeightInfluence first)"),
    }


@_tool(name="gephi_run_layout")
async def gephi_run_layout(algorithm: str, iterations: int = 1000,
                           properties: dict[str, Any] | None = None, sync: bool = False) -> str:
    """Run a layout algorithm to position nodes.

    For community readability with "ForceAtlas 2", start from the visual network
    analysis reference config: {"linLogMode": true, "gravity": 0, "scalingRatio": <by
    size>} (Venturini, Jacomy, and Jensen 2021). Pick the starting scalingRatio by
    node count and expand only if cramped — starting high over-spreads (nodes render
    as specks): under ~1k nodes start at 1-2; 1k-10k start at 2-4; above 10k start
    at 4-8. Gravity only keeps disconnected components in frame (use 0.5-1.0 then);
    raising it packs nodes into an unreadable central blob. To tighten or spread the
    layout, adjust scalingRatio, not gravity. After the run, check gephi_visual_qa
    (it flags over-spread) and iterate: central blob = lower gravity; hairball =
    linLogMode on and raise scalingRatio; clusters too dense inside = raise
    scalingRatio; over-spread warning = lower scalingRatio. One parameter per rerun.

    properties: optional {name: value} tuning map (gravity, scalingRatio, linLogMode,
    barnesHutOptimization, ...). sync=True waits until the layout finishes before
    returning; otherwise it returns immediately with status "running" (poll
    gephi_get_layout_status for completion).

    Sync runs end with a finite-positions check: if the layout exploded
    numerically (non-finite or absurd coordinates — FA2 can do this silently,
    especially on weighted graphs with a strong hub), the result carries a
    layout_exploded block with the affected nodes and the fix. When present,
    do NOT export or style — follow the fix first.
    """
    result = await gephi.request("POST", "/layout/run",
                                 json_data=_body(algorithm=algorithm, iterations=iterations,
                                                 properties=properties))
    if isinstance(result, dict) and result.get("success"):
        LEDGER.record("run_layout", algorithm=algorithm, iterations=iterations,
                      **({"properties": properties} if properties else {}))
    if not sync or not result.get("success"):
        return fmt(result)
    # Poll until layout stops
    for _ in range(300):  # max ~5 minutes at 1s intervals
        await asyncio.sleep(1)
        status = await gephi.request("GET", "/layout/status")
        if not status.get("running", True):
            result["status"] = "completed"
            result["message"] = "Layout finished after polling"
            exploded = await _check_layout_positions()
            if exploded:
                result["layout_exploded"] = exploded
                result["message"] = ("Layout finished but positions exploded "
                                     "numerically — see layout_exploded")
            return fmt(result)
    result["status"] = "timeout"
    result["message"] = "Layout still running after 5 minutes"
    return fmt(result)

@_tool(name="gephi_similarity_layout")
async def gephi_similarity_layout(projection: str = "auto", dimensions: int = 8,
                                  finish_noverlap: bool = True) -> str:
    """Position nodes by structural similarity instead of springs — a layout no
    Gephi plugin offers.

    Nodes end up near each other when they play a similar ROLE in the network,
    even if they are not directly connected. Use when someone asks "who is
    similar / who plays the same role / are there groups beyond the obvious
    clusters". Complements (does not replace) ForceAtlas 2: run both and compare.

    IMPORTANT when presenting the result: proximity here means similar role,
    NOT "connected" — say so plainly, because readers of force layouts assume
    the opposite. Nodes a community metric groups together but this layout
    separates (or vice versa) are the interesting finding: they are boundary
    or bridge actors. For cluster captions on this layout prefer the
    interactive graph view (centroid captions); hub-anchored labels
    (gephi_label_clusters) assume force-layout geometry.

    projection: "auto" (best available), "umap", "tsne", or "spectral"
    (the always-available base). dimensions: embedding depth (default 8).
    finish_noverlap: run a Noverlap pass afterward so nodes stay readable.
    Needs numpy+scipy; "umap"/"tsne" use umap-learn/scikit-learn when installed.
    """

    from gephi_mcp_viewer import parse_gexf
    from gephi_mcp_viewer.similarity import compute_similarity_positions

    exported = await _export_gexf_inline()
    if not exported.get("success"):
        return fmt(exported)
    try:
        graph = parse_gexf(exported["content"])
        positions, method = compute_similarity_positions(
            graph, dims=dimensions, projection=projection)
    except ImportError as e:
        return fmt({"success": False, "error": f"projection '{projection}' needs an optional package ({e.name}); use projection='spectral' which always works, or install the package"})
    except ValueError as e:
        return fmt({"success": False, "error": str(e)})
    pushed = await gephi.request("POST", "/graph/nodes/positions", json_data={"positions": positions})
    if not pushed.get("success"):
        return fmt(pushed)
    if finish_noverlap:
        await gephi.request("POST", "/layout/run", json_data={"algorithm": "noverlap", "iterations": 60})
        for _ in range(120):
            status = await gephi.request("GET", "/layout/status")
            if not status.get("running"):
                break
            await asyncio.sleep(0.5)
    await gephi.request("POST", "/view/focus", json_data={"mode": "graph"})
    return fmt(_carry_filter_warning(exported, {"success": True, "layout": "similarity", "projection_used": method,
                "nodes_positioned": len(positions),
                "reading_note": "proximity = similar structural role, not direct connection"}))

@_tool(name="gephi_community_layout")
async def gephi_community_layout(partition_column: str = "Modularity Class",
                                 min_community_size: int = 6,
                                 finish_noverlap: bool = True) -> str:
    """Lay the graph out as one radial fan per community, packed as discs —
    the layout for networks where force layouts stay mixed no matter how long
    they run.

    Use on tree-like networks (replies, retweets, mentions, citations from a
    seed — anything the profile flags as leaf-majority or tree-like): their
    communities are stars fanning out from hubs, interleaved star-arms have no
    ties pulling them together, so ForceAtlas 2 leaves real communities
    visually interpenetrating. This layout takes the DETECTED partition and
    draws each community as its own disc: hub at center, members ringed by
    graph distance from the hub, branch angles sized by subtree.

    IMPORTANT when presenting the result — the reading rules change: grouping
    and within-disc distances come from the data; disc placement relative to
    other discs is arranged for legibility and means NOTHING. Say so plainly
    (a caption like "disc placement arranged for legibility; grouping comes
    from the data" is the honest minimum).

    The result includes separation_before/after: mean intra-community pair
    distance over mean random pair distance (1.0 = fully mixed, near 0 = tight
    discs). Quote it when explaining why the layout was switched.

    partition_column: node attribute holding the community (default the
    modularity result; run gephi_run_modularity first if absent).
    min_community_size: smaller communities scatter on the outer rim instead
    of getting a disc.
    """
    from gephi_mcp_viewer import parse_gexf
    from gephi_mcp_viewer.community_layout import compute_community_positions, separation_score

    exported = await _export_gexf_inline()
    if not exported.get("success"):
        return fmt(exported)
    graph = parse_gexf(exported["content"], max_nodes=10**9)
    before = separation_score(
        graph, {n["key"]: (n["x"], n["y"]) for n in graph["nodes"]},
        partition_column)
    try:
        positions, info = compute_community_positions(
            graph, partition=partition_column, min_disc=min_community_size)
    except ValueError as e:
        return fmt({"success": False, "error": str(e)})
    pushed = await gephi.request("POST", "/graph/nodes/positions",
                                 json_data={"positions": positions})
    if not pushed.get("success"):
        return fmt(pushed)
    if finish_noverlap:
        await gephi.request("POST", "/layout/run",
                            json_data={"algorithm": "noverlap", "iterations": 60})
        for _ in range(120):
            status = await gephi.request("GET", "/layout/status")
            if not status.get("running"):
                break
            await asyncio.sleep(0.5)
    await gephi.request("POST", "/view/focus", json_data={"mode": "graph"})
    after = separation_score(graph, positions, partition_column)
    return fmt(_carry_filter_warning(exported, {"success": True, "layout": "community-discs", **info,
                "nodes_positioned": len(positions),
                "separation_before": before, "separation_after": after,
                "reading_note": ("grouping and within-disc distances come from "
                                 "the data; disc placement is arranged for "
                                 "legibility and means nothing")}))

@_tool(name="gephi_stop_layout")
async def gephi_stop_layout() -> str:
    """Stop a currently running layout algorithm."""
    return fmt(await gephi.request("POST", "/layout/stop"))

@_tool(name="gephi_get_layout_status")
async def gephi_get_layout_status() -> str:
    """Check whether a layout algorithm is currently running."""
    return fmt(await gephi.request("GET", "/layout/status"))

@_tool(name="gephi_get_available_layouts")
async def gephi_get_available_layouts() -> str:
    """Get the list of available layout algorithms."""
    return fmt(await gephi.request("GET", "/layout/available"))

@_tool(name="gephi_get_layout_properties")
async def gephi_get_layout_properties(algorithm: str) -> str:
    """Get tunable properties (gravity, scaling, speed, ...) for a layout algorithm."""
    return fmt(await gephi.request("GET", "/layout/properties", params={"algorithm": algorithm}))

@_tool(name="gephi_set_layout_properties")
async def gephi_set_layout_properties(algorithm: str, properties: dict[str, Any],
                                      iterations: int = 1000) -> str:
    """Run a layout with custom property values (gravity, scaling, speed, ...)."""
    return fmt(await gephi.request("POST", "/layout/properties",
                                   json_data={"algorithm": algorithm, "properties": properties,
                                              "iterations": iterations}))


# ─── Statistics integrity ────────────────────────────────────
# Gephi's own statistics carry long-open defects the interface never surfaces (a resolution
# parameter applied as the reciprocal of the convention it cites, a closeness measure normalised
# whatever the checkbox said). gephi-ai reports those numbers into research claims, so every
# statistic leaves through fmt_stat, which attaches what is known about the number it carries.

_graph_facts: GraphFacts | None = None

#: What this session applied to the current graph. A legend and a methods note both need it, and
#: neither can be recovered from the graph afterwards: Gephi keeps the pixels, not the decision
#: that produced them. Reset whenever the graph changes, since it describes one graph.
LEDGER = Ledger()


def invalidate_graph_facts() -> None:
    """Forget cached facts about the graph. Called whenever the graph may have changed."""
    global _graph_facts
    _graph_facts = None


def note_weights_vary(weights_vary: bool) -> None:
    """Record whether this graph's edge weights vary, learned from work already done.

    Establishing this needs the full GEXF export, which is far too expensive to run on every
    statistic, so the statistics path leaves it unknown and the weight caveats stay silent. Any
    code that has already parsed the graph can hand the answer over here instead.
    """
    global _graph_facts
    current = _graph_facts or GraphFacts()
    _graph_facts = GraphFacts(directed=current.directed, weights_vary=weights_vary)


async def _fetch_graph_facts() -> GraphFacts:
    """Establish the cheap facts a conditional caveat needs. Never raises.

    Only `directed` is cheap enough to fetch on the statistics path; `weights_vary` needs the
    full GEXF export and is left unknown here, which keeps the weight caveats quiet rather than
    guessing. An unknown fact never satisfies a predicate.
    """
    global _graph_facts
    if _graph_facts is not None and _graph_facts.directed is not None:
        return _graph_facts
    known_weights = _graph_facts.weights_vary if _graph_facts else None
    directed = None
    try:
        stats = await gephi.request("GET", "/graph/stats")
        if isinstance(stats, dict) and stats.get("success"):
            gtype = str(stats.get("graph_type", "")).strip().lower()
            if gtype in ("directed", "undirected"):
                directed = gtype == "directed"
    except Exception:
        directed = None
    _graph_facts = GraphFacts(directed=directed, weights_vary=known_weights)
    return _graph_facts


async def fmt_stat(metric: str, resp: dict[str, Any], **params: Any) -> str:
    """Format a statistic result, attaching any known defect that applies to it.

    Adds a `caveats` key only when the list is non-empty, so a call with nothing to warn about is
    byte-identical to what it returned before. Failure anywhere in this layer returns the
    statistic unchanged: a bug here must never fail a measurement that otherwise succeeded.
    """
    try:
        if not (isinstance(resp, dict) and resp.get("success", True)):
            return fmt(resp)
        LEDGER.record("statistic", metric=metric, params=dict(params))
        facts = await _fetch_graph_facts() if needs_graph_facts(metric) else GraphFacts()
        found = caveats_for(metric, params=params, facts=facts)
        if found:
            resp = {**resp, "caveats": [
                {"id": c["id"], "severity": c["severity"], "says": c["says"],
                 "issues": c["issues"], "verification": c["verification"]["status"]}
                for c in found]}
    except Exception:
        pass
    return fmt(resp)


# ─── Statistics ──────────────────────────────────────────────

@_tool(name="gephi_compute_modularity")
async def gephi_compute_modularity(resolution: float = 1.0) -> str:
    """Run modularity (Louvain) community detection. Stores 'modularity_class' on nodes.

    Higher resolution yields fewer, larger communities.
    """
    return await fmt_stat("modularity",
                          await gephi.request("POST", "/statistics/modularity",
                                              json_data={"resolution": resolution}),
                          resolution=resolution)

#: Gephi titles the community column "Modularity Class" and gives it the id "modularity_class".
#: Which of the two a GEXF parser surfaces varies, so the read-back matches on a normalised form
#: rather than one exact spelling. Getting this wrong is silent: the lookup finds nothing, every
#: partition comes back empty, and a graph that was never measured reports as perfectly stable.
_PARTITION_KEYS = {"modularityclass", "modularity"}


def _partition_value(attributes: dict[str, Any]) -> Any:
    """The community id on a node, however this Gephi build spelled the column."""
    for key, value in (attributes or {}).items():
        if str(key).replace("_", "").replace(" ", "").lower() in _PARTITION_KEYS:
            return value
    return None


@_tool(name="gephi_community_stability")
async def gephi_community_stability(runs: int = 20, resolution: float = 1.0,
                                    consensus_column: str = "consensus_community") -> str:
    """Run community detection repeatedly and report which groups actually hold up.

    Gephi reports one partition as though it were the answer. It is one draw: the same graph run
    again can give different communities, and the result shifts with the order the tables were
    imported and even after a layout has run. So a partition on its own cannot support a claim
    that a group exists. This runs detection `runs` times and measures how often each pair of
    nodes lands together.

    Returns the number of genuinely distinct partitions seen (relabellings do not count as
    different), a stability score per node, the least stable nodes by name, and a consensus
    partition built from the pairs that agreed more often than not. A node's stability is the
    average decisiveness of its co-membership relations: 1.0 means every relation came out the
    same way every time, 0.5 means its membership is undetermined.

    The consensus partition is written to its own column rather than overwriting
    `modularity_class`, so the run you already had survives (gephi#2590).

    Use this before describing communities as a finding. Answers gephi#2968, which Gephi closed
    as not planned, so nothing else in this ecosystem can tell you whether your groups are real.
    """
    if runs < 2:
        return fmt({"success": False,
                    "error": ("runs must be at least 2: a single run is the thing you already "
                              "have, and says nothing about whether it is reproducible.")})

    from gephi_mcp_viewer import parse_gexf

    partitions: list[dict[str, Any]] = []
    for _ in range(runs):
        mod = await gephi.request("POST", "/statistics/modularity",
                                  json_data={"resolution": resolution})
        if not (isinstance(mod, dict) and mod.get("success")):
            return fmt(mod)
        exported = await _export_gexf_inline()
        if not (isinstance(exported, dict) and exported.get("success")):
            return fmt(exported)
        graph = parse_gexf(exported["content"], max_nodes=10**9)
        partition = {
            n["key"]: value
            for n in graph["nodes"]
            if (value := _partition_value(n.get("attributes", {}))) is not None
        }
        if not partition:
            return fmt({"success": False,
                        "error": ("Ran community detection but could not read any partition back "
                                  "from the graph. Gephi titles the column 'Modularity Class'; if "
                                  "this build names it something else, the read-back needs "
                                  "updating. Reporting nothing rather than an empty result, "
                                  "because an empty result looks exactly like a stable one.")})
        partitions.append(partition)

    result: dict[str, Any] = {"success": True, "resolution": resolution}
    result.update(consensus(partitions))

    groups = result.get("consensus_groups") or []
    if groups:
        added = await gephi.request("POST", "/graph/columns/add",
                                    json_data={"name": consensus_column, "type": "integer",
                                               "target": "node"})
        updates = [{"id": node, "attributes": {consensus_column: index}}
                   for index, group in enumerate(groups) for node in group]
        written = await gephi.request("POST", "/graph/nodes/attributes",
                                      json_data={"updates": updates})
        # Both responses used to be discarded, so a failed write was reported as a successful
        # one and the caller was told a column existed that did not. Report what happened.
        if added.get("success", True) and written.get("success", True):
            result["consensus_column"] = consensus_column
            result["consensus_communities"] = len(groups)
        else:
            result["consensus_column"] = None
            result["consensus_write_failed"] = (
                "The consensus partition was computed but could not be written to the graph. "
                "The stability numbers above are unaffected; the column is absent.")
            result["consensus_write_detail"] = added if not added.get("success", True) else written

    return await fmt_stat("modularity", result, resolution=resolution)


async def _compute_profile(include_slow: bool = False) -> dict:
    """Compute the structural profile panel on the CURRENT workspace.

    Shared by gephi_profile_graph and gephi_whatif so metric computation lives
    in exactly one place. Returns the profile dict (nodes, edges, density,
    degree, components, isolates, weighted, flags, plus modularity/clustering
    and — when include_slow — distance). On a failed GEXF export it returns
    that failed response verbatim (it carries "success": False); a successful
    profile dict has no "success" key, so callers test
    `profile.get("success", True)` to tell them apart.
    """
    exported = await _export_gexf_inline()
    if not exported.get("success"):
        return exported
    from gephi_mcp_viewer import parse_gexf
    from gephi_mcp_viewer.profile import structural_profile

    graph = parse_gexf(exported["content"], max_nodes=10**9)
    profile = structural_profile(graph)
    # The profile establishes, in passing, the one fact the caveat layer cannot afford to fetch
    # on the statistics path. Keeping it is what lets the edge-weight caveats ever fire.
    note_weights_vary(bool(profile.get("weighted")))

    mod = await gephi.request("POST", "/statistics/modularity", json_data={})
    if mod.get("success"):
        profile["modularity"] = {k: mod[k] for k in ("modularity", "communities") if k in mod}
    cc = await gephi.request("POST", "/statistics/clustering-coefficient", json_data={})
    if cc.get("success"):
        for k in ("average_clustering_coefficient", "clustering_coefficient", "average"):
            if k in cc:
                profile["clustering_coefficient"] = cc[k]
                break
    # Observed / configuration-model expectation: the baseline-relative verdict.
    expected = profile.get("clustering_expected_random", 0)
    observed = profile.get("clustering_coefficient")
    if observed is not None and expected:
        profile["clustering_vs_random"] = round(float(observed) / expected, 2)
    if include_slow and profile["nodes"] <= 3000:
        dist = await gephi.request("POST", "/statistics/avg-path-length", json_data={})
        if dist.get("success"):
            profile["distance"] = {k: dist[k] for k in ("avg_path_length", "diameter", "radius") if k in dist}
    return _carry_filter_warning(exported, profile)


@_tool(name="gephi_profile_graph")
async def gephi_profile_graph(include_slow: bool = False) -> str:
    """Profile the whole graph in ONE call — run this first, before analyzing.

    Returns a compact quantitative picture: size, density, degree distribution
    (including gini — degree inequality, 0 equal to 1 winner-take-all — and
    assortativity — negative means hub-and-spoke wiring), connectivity
    (components, isolates), weight distribution when weights carry signal
    (weights.heavy_tailed means the strongest ties will dominate a force
    layout: log-transform weights or lower edgeWeightInfluence before laying
    out), plus Gephi-computed modularity (community count and strength) and
    clustering coefficient with its random-graph expectation
    (clustering_vs_random is the verdict: observed/expected for this exact
    degree sequence — quote the ratio, never the raw coefficient alone).
    Auto-raised flags (fragmentation, hub dominance, likely hairball,
    heavy-tailed weights, strong disassortativity) each name their fix — act
    on them before choosing layout parameters. One call = one approval prompt
    instead of six.

    USE IT TO GUIDE EVERYTHING DOWNSTREAM, together with the person's own
    description of their data: their description supplies meaning (what nodes
    and ties are, what they want to learn); this profile supplies measurement.
    Read both before choosing a layout (purpose table), a sizing metric, or a
    coloring — and turn the person's expectations into hypothesis tests (if
    they expect X to organize the network, check it against the partition
    baseline instead of assuming). Present a short plain-language first
    reading, then ask the two or three questions the numbers raise (the flags
    are candidates). THE FIRST READING IS PROVISIONAL: present impressions as
    things to check together, never findings; pair each pattern with a rival
    explanation; close with 2-3 places to look and let the person choose; no
    verdict language before a check has run with them. The goal is to help
    people explore their data, not to hand them conclusions.

    include_slow: also compute average path length / diameter (skipped by
    default; expensive on large graphs — only sensible under ~3k nodes).
    """
    profile = await _compute_profile(include_slow)
    if not profile.get("success", True):
        return fmt(profile)  # GEXF export failed
    profile["success"] = True
    return fmt(profile)

@_tool(name="gephi_list_statistics")
async def gephi_list_statistics() -> str:
    """List every statistic available in this Gephi instance, by name.

    Includes Gephi's built-ins AND any installed plugin that provides a metric
    (e.g. the Leiden Algorithm plugin from the Gephi plugin portal). Run any of
    them with gephi_run_statistic.
    """
    return fmt(await gephi.request("GET", "/statistics/available"))

@_tool(name="gephi_run_statistic")
async def gephi_run_statistic(name: str, params: dict[str, Any] | None = None) -> str:
    """Run any available statistic by name — including installed plugin metrics.

    `name` matches an entry from gephi_list_statistics (case-insensitive).
    `params`: optional {property: value} map set on the statistic before it runs
    (setters, bare fields, and enums-by-name all work). Results land in
    node/edge columns as usual (check gephi_list_columns, then size or color by
    the new column). This is the plugin-ecosystem passthrough: install a metric
    plugin in Gephi (Tools > Plugins) and it is immediately runnable here.

    Plugin statistics configured by a UI dialog usually NEED params (their
    fields start null/zero). Verified example, the CWTS Leiden plugin:
    name="Leiden algorithm", params={"algorithm": "Leiden", "qualityFunction":
    "Modularity", "resolution": 1.0, "nIterations": 10, "nRestarts": 5}.
    If a run errors mid-execution, check gephi_health_check: a statistic that
    crashes while holding the graph lock can freeze Gephi's own UI (restart
    Gephi if graph_lock_stats shows readers stuck above zero).
    """
    return fmt(await gephi.request("POST", "/statistics/run",
                                   json_data=_body(name=name, params=params),
                                   timeout=SLOW_REQUEST_TIMEOUT))

@_tool(name="gephi_compute_degree")
async def gephi_compute_degree() -> str:
    """Compute degree, in-degree, and out-degree for all nodes."""
    return await fmt_stat("degree", await gephi.request("POST", "/statistics/degree"))

@_tool(name="gephi_compute_betweenness")
async def gephi_compute_betweenness() -> str:
    """Compute betweenness/closeness centrality, eccentricity, diameter, radius, avg path length.

    This is all-pairs shortest paths (O(n*m)) — it is the slowest built-in metric
    and scales steeply: near-instant at 1k nodes, ~15s at 5k, ~1min at 10k. It runs
    with an extended timeout; on very large graphs (tens of thousands of nodes)
    expect a wait, and consider whether degree or PageRank answers the question more
    cheaply."""
    return await fmt_stat("betweenness",
                          await gephi.request("POST", "/statistics/betweenness",
                                              timeout=SLOW_REQUEST_TIMEOUT))

@_tool(name="gephi_compute_pagerank")
async def gephi_compute_pagerank() -> str:
    """Compute PageRank for all nodes. Stores 'pageranks' on nodes."""
    return await fmt_stat("pagerank", await gephi.request("POST", "/statistics/pagerank"))

@_tool(name="gephi_compute_connected_components")
async def gephi_compute_connected_components() -> str:
    """Compute connected components. Stores 'componentnumber' on nodes."""
    return fmt(await gephi.request("POST", "/statistics/connected-components"))

@_tool(name="gephi_compute_clustering_coefficient")
async def gephi_compute_clustering_coefficient() -> str:
    """Compute the clustering coefficient for all nodes. Stores 'clustering' on nodes."""
    return await fmt_stat("clustering_coefficient",
                          await gephi.request("POST", "/statistics/clustering-coefficient"))

@_tool(name="gephi_compute_avg_path_length")
async def gephi_compute_avg_path_length() -> str:
    """Compute the average shortest path length across all node pairs.

    All-pairs shortest paths (O(n*m)), as slow as betweenness on large graphs; runs
    with an extended timeout."""
    return await fmt_stat("avg_path_length",
                          await gephi.request("POST", "/statistics/avg-path-length",
                                              timeout=SLOW_REQUEST_TIMEOUT))

@_tool(name="gephi_compute_hits")
async def gephi_compute_hits() -> str:
    """Compute HITS hub and authority scores. Stores 'Authority' and 'Hub' on nodes."""
    return fmt(await gephi.request("POST", "/statistics/hits"))

@_tool(name="gephi_compute_eigenvector")
async def gephi_compute_eigenvector() -> str:
    """Compute eigenvector centrality. Stores 'eigencentrality' on nodes."""
    return await fmt_stat("eigenvector", await gephi.request("POST", "/statistics/eigenvector"))


# ─── Filters ─────────────────────────────────────────────────

@_tool(name="gephi_filter_by_degree")
async def gephi_filter_by_degree(min: int = 0, max: int = 0, dry_run: bool = False) -> str:
    """Filter the graph by node degree range, removing nodes outside it. Destructive.

    max=0 means no upper limit. dry_run=True reports how many nodes would be removed.
    Removal is permanent (reset_filters does not restore deleted nodes), but an undo
    snapshot is taken automatically before a real run — gephi_undo restores the graph
    as it was. For a scoped, non-destructive filter instead, `gephi_apply_filter` with
    action="select" (visible-only) or "new_workspace" (subgraph copy) leaves the
    original intact.
    """
    undo = await _auto_snapshot("filter_by_degree") if not dry_run else False
    result = await gephi.request("POST", "/filter/degree",
                                 json_data={"min": min, "max": max, "dry_run": dry_run})
    return fmt(_with_undo(result, undo) if not dry_run else result)

@_tool(name="gephi_filter_by_edge_weight")
async def gephi_filter_by_edge_weight(min: float = 0, max: float = 0, dry_run: bool = False) -> str:
    """Filter the graph by edge weight range, removing edges outside it. Destructive.

    max=0 means no upper limit. dry_run=True reports how many edges would be removed.
    A real run auto-snapshots first; gephi_undo reverses it.
    """
    undo = await _auto_snapshot("filter_by_edge_weight") if not dry_run else False
    result = await gephi.request("POST", "/filter/edge-weight",
                                 json_data={"min": min, "max": max, "dry_run": dry_run})
    return fmt(_with_undo(result, undo) if not dry_run else result)

@_tool(name="gephi_remove_isolates")
async def gephi_remove_isolates() -> str:
    """Remove all isolated nodes (degree 0). Destructive; auto-snapshots first
    (gephi_undo reverses it)."""
    undo = await _auto_snapshot("remove_isolates")
    return fmt(_with_undo(await gephi.request("POST", "/filter/remove-isolates"), undo))

@_tool(name="gephi_extract_ego_network")
async def gephi_extract_ego_network(node_id: str, depth: int = 1) -> str:
    """Keep only a node and its neighbors within `depth`; remove everything else.
    Destructive; auto-snapshots first (gephi_undo reverses it)."""
    undo = await _auto_snapshot("extract_ego_network")
    return fmt(_with_undo(await gephi.request("POST", "/filter/ego-network",
                                              json_data={"node_id": node_id, "depth": depth}),
                          undo))

@_tool(name="gephi_extract_giant_component")
async def gephi_extract_giant_component() -> str:
    """Keep only the largest connected component; remove all smaller ones.
    Destructive; auto-snapshots first (gephi_undo reverses it)."""
    undo = await _auto_snapshot("extract_giant_component")
    return fmt(_with_undo(await gephi.request("POST", "/filter/giant-component"), undo))

@_tool(name="gephi_reset_filters")
async def gephi_reset_filters() -> str:
    """Reset non-destructive filters and restore the full graph view."""
    return fmt(await gephi.request("POST", "/filter/reset"))


@_tool(name="gephi_list_filters")
async def gephi_list_filters() -> str:
    """List every filter available in this Gephi instance, with its settable properties.

    Covers the built-in topology filters (Degree Range, K-core, Giant Component,
    Ego Network, Neighbors, Edge Weight, …) AND a per-column attribute filter for
    each node/edge column currently in the graph (Attribute Equal / Range /
    Non-null on that column) — so the exact set depends on what columns exist.
    Each entry gives name, category, description, and `properties` (name + type)
    so you know what to pass to gephi_apply_filter. Range-typed properties take a
    [low, high] pair. This is the discovery step before applying an arbitrary
    filter, the same way gephi_list_statistics precedes gephi_run_statistic.
    """
    return fmt(await gephi.request("GET", "/filter/list"))


@_tool(name="gephi_apply_filter")
async def gephi_apply_filter(name: str, params: dict[str, Any] | None = None,
                             action: str = "select", column: str | None = None) -> str:
    """Apply a filter by name — the general-purpose filter tool.

    name matches an entry from gephi_list_filters (case-insensitive). params is a
    {property: value} map for that filter's properties (see the filter's
    `properties` in gephi_list_filters); a Range property takes a [low, high]
    pair, e.g. params={"Degree Range": [2, 10]}. If a property name doesn't
    match, the error lists the valid ones.

    action decides what happens with the matches:
    - "select" (default): filter the visible graph non-destructively (a
      GraphView — the underlying data is untouched; reset with
      gephi_reset_filters). Returns node/edge counts before and after.
    - "new_workspace": materialize the filtered subgraph into a new workspace.
      Prefer this when filtering repeatedly on a large graph — a visible-only
      filter keeps the hidden elements resident in memory, so chained filters
      can grow memory unbounded; exporting to a fresh workspace and working
      there avoids that.
    - "column": write filter membership into a boolean column named `column`
      (required for this action) instead of hiding anything — useful for
      marking "matches" to color or size by afterward.

    This compiles a plain-language filtering intent ("nodes with degree ≥ 5 in
    the giant component", "only where type = X") into the right Gephi filter:
    pick the filter from gephi_list_filters, set its properties, choose the
    action. For AND/OR of several conditions, apply them in sequence with
    action="select" (each narrows the visible graph).
    """
    return fmt(await gephi.request("POST", "/filter/apply",
                                   json_data=_body(name=name, params=params,
                                                   action=action, column=column)))


@_tool(name="gephi_get_timeline")
async def gephi_get_timeline() -> str:
    """Report the graph's dynamic/timeline state (read-only).

    Returns graph_is_dynamic (does the data carry a time attribute), the time
    bounds (time_min/time_max) and format, the dynamic_columns the timeline
    recognizes, and the timeline's enabled/interval state. Use it to check
    whether an imported graph is dynamic and over what time range.

    To reason about change over time, read this plus the node/edge start/end
    values (e.g. via gephi_query_nodes / the exported GEXF) — there is no
    programmatic "restrict the graph to a time window" tool: driving Gephi's
    timeline from outside destabilizes its render thread in this architecture
    (both the data-view swap and the timeline-UI toggle proved unsafe), so it's
    deliberately not exposed. Slice by time in the Gephi timeline UI directly if
    you need the live view filtered.
    """
    return fmt(await gephi.request("GET", "/timeline"))


@_tool(name="gephi_column_value_frequencies")
async def gephi_column_value_frequencies(column: str, target: str = "node") -> str:
    """Count how often each value appears in a column — the value distribution.

    Returns {value: count} for the given column, plus distinct_values and total.
    Use it to understand a categorical column before coloring/partitioning by it
    (how many groups, how skewed), to spot data-entry variants (the same place
    spelled three ways shows as three near-identical keys), or to sanity-check a
    computed column. target is "node" (default) or "edge".
    """
    return fmt(await gephi.request("POST", "/datalab/frequencies",
                                   json_data={"target": target, "column": column}))


@_tool(name="gephi_detect_duplicates")
async def gephi_detect_duplicates(column: str, target: str = "node",
                                  case_sensitive: bool = False) -> str:
    """Find groups of nodes (or edges) that share a value in one column.

    Returns duplicate_groups — a list of id-lists, one per value held by two or
    more elements — and group_count. The classic use is deduplication: find the
    nodes that are really the same entity (same email, same normalized name),
    then merge them with gephi_merge_nodes. case_sensitive=False (default)
    treats "Alice"/"alice" as the same; set True to keep them distinct. This
    only reports; it changes nothing.
    """
    return fmt(await gephi.request("POST", "/datalab/duplicates",
                                   json_data={"target": target, "column": column,
                                              "case_sensitive": case_sensitive}))


@_tool(name="gephi_merge_nodes")
async def gephi_merge_nodes(ids: list[str], into: str | None = None) -> str:
    """Merge several nodes into one, reassigning their edges. Destructive.

    Combines the given node ids into a single node (their edges are reattached
    to it; per-column values are merged with Gephi's default strategies), then
    deletes the others. `into` picks which id survives as the merged node
    (default: the first in `ids`). Pair with gephi_detect_duplicates: detect the
    groups, then merge each group. An undo snapshot is taken automatically first,
    so gephi_undo reverses a bad merge — but only the most recent one (one-level
    undo), so verify each merge before doing the next.
    """
    undo = await _auto_snapshot("merge_nodes")
    return fmt(_with_undo(await gephi.request("POST", "/datalab/merge-nodes",
                                              json_data=_body(ids=ids, into=into)), undo))


@_tool(name="gephi_create_regex_column")
async def gephi_create_regex_column(column: str, new_column: str, regex: str,
                                    target: str = "node") -> str:
    """Add a boolean column flagging rows whose value matches a regex.

    For each node/edge, tests `column`'s value against `regex` and writes
    True/False into a new column named `new_column` — without hiding anything.
    Use it to mark a subset for later coloring/sizing/filtering (e.g. flag every
    label starting "Dept-", or every id matching an email pattern). target is
    "node" (default) or "edge". Errors on an invalid regex.
    """
    return fmt(await gephi.request("POST", "/datalab/regex-column",
                                   json_data={"target": target, "column": column,
                                              "new_column": new_column, "regex": regex}))

@_tool(name="gephi_clear_graph")
async def gephi_clear_graph() -> str:
    """Remove all nodes and edges. The project/workspace stay open. Destructive;
    auto-snapshots first (gephi_undo brings the graph back)."""
    undo = await _auto_snapshot("clear_graph")
    return fmt(_with_undo(await gephi.request("POST", "/graph/clear"), undo))

@_tool(name="gephi_edge_thickness_by_weight")
async def gephi_edge_thickness_by_weight(min_thickness: float = 1, max_thickness: float = 5) -> str:
    """Scale rendered edge thickness proportionally to edge weight."""
    return fmt(await gephi.request("POST", "/appearance/edge/thickness-by-weight",
                                   json_data={"min_thickness": min_thickness, "max_thickness": max_thickness}))


# ─── Preview ─────────────────────────────────────────────────

@_tool(name="gephi_get_preview_settings")
async def gephi_get_preview_settings() -> str:
    """Get current preview/rendering settings (background, labels, edge style, opacity, ...)."""
    return fmt(await gephi.request("GET", "/preview/settings"))

@_tool(name="gephi_set_preview_settings")
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

async def _derive_partition_colours(column: str) -> dict[str, str] | None:
    """Read the colour each group actually carries, from the graph rather than from assumption.

    When no palette is passed, Gephi assigns one and never reports it back, so the mapping is
    known but its colours are not. Reading them off the nodes is the only way a swatch can be
    trusted; inventing one would produce a legend that confidently mislabels the map.
    """
    exported = await _export_gexf_inline()
    if not (isinstance(exported, dict) and exported.get("success") and exported.get("content")):
        return None
    from gephi_mcp_viewer import parse_gexf
    graph = parse_gexf(exported["content"], max_nodes=10**9)
    wanted = column.replace("_", "").replace(" ", "").lower()
    groups: dict[str, str] = {}
    for node in graph["nodes"]:
        value = next((v for k, v in (node.get("attributes") or {}).items()
                      if k.replace("_", "").replace(" ", "").lower() == wanted), None)
        if value is None or str(value) in groups:
            continue
        match = re.match(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", str(node.get("color") or ""))
        if match:
            r, g, b = (int(v) for v in match.groups())
            groups[str(value)] = f"#{r:02x}{g:02x}{b:02x}"
    return groups or None


@_tool(name="gephi_export_legend")
async def gephi_export_legend(file: str) -> str:
    """Write a legend for the current map as SVG, so an export can be read without you present.

    A Gephi export is coloured circles with no key. This draws the key from the mappings applied
    in this session: which column each visual channel encodes, the groups and their swatches, and
    the range a size mapping spans. Swatch colours are read back from the graph, because Gephi
    assigns a palette itself when none is given and never reports which one.

    Refuses when nothing was mapped through these tools. Styling done by hand in the Gephi window
    is invisible here, and a legend guessed from an unknown appearance would be confidently wrong,
    which is worse for a published figure than having no legend at all.

    Pair it with a PNG or PDF export, or splice it into an SVG one. Answers gephi/gephi#511.
    """
    items = LEDGER.legend_items()
    if not items:
        return fmt({"success": False,
                    "error": ("Nothing to put in a legend: no colour, size, or width mapping has "
                              "been applied through these tools in this session. Anything styled "
                              "by hand in the Gephi window is not visible here, so a legend would "
                              "be a guess. Apply a mapping (gephi_color_by_partition, "
                              "gephi_size_by_ranking) and try again.")})

    resolved = []
    for item in items:
        if item.get("groups") or not (item["channel"].endswith("colour") and item.get("column")):
            resolved.append(item)
            continue
        groups = await _derive_partition_colours(item["column"])
        resolved.append({**item, "groups": groups} if groups else item)

    document = legend_document(resolved)
    try:
        Path(file).write_text(document, encoding="utf-8")
    except OSError as exc:
        return fmt({"success": False, "error": f"Could not write {file}: {exc}"})
    return fmt({"success": True, "file": file, "items": resolved})


@_tool(name="gephi_export_figure")
async def gephi_export_figure(
    file: str,
    title: str,
    subtitle: str | None = None,
    partition_column: str | None = None,
    extra_channels: list[dict] | None = None,
    notes: list[str] | None = None,
    detail_column: str | None = None,
    width: int = 2400,
    height: int = 2400,
) -> str:
    """Write the map and its legend as one figure, as a PDF and a PNG at 300 dpi.

    gephi_export_png writes a map with no key and gephi_export_legend writes a key with no
    map; joining them has been left to whoever is driving, so the caveats that make a figure
    honest get remembered or not. This does the joining and keeps them attached.

    What it will not do is invent the parts only you can supply. `title` is a claim about the
    world and `notes` are the reading rules a stranger needs ("disc placement means nothing",
    "absent from the harvest is not the same as silent"); both are written down, never
    generated. That is the same refusal gephi_export_legend already makes about swatches.

    Colour and size come from the mappings made through these tools. `partition_column` also
    reads the colour each group actually carries off the graph, so a reopened project or a
    palette Gephi chose itself still gets a correct key.

    `extra_channels` carries a channel this server does not own, such as a shape mapping added
    by a plugin. Give it {"channel": "shape", "column": "...", "items": [{"label": ...,
    "glyph": "circle|square|triangle|diamond|star|pentagon|hexagon|cross", "note": ...,
    "stat": ...}]}. Naming a glyph rather than a plugin keeps this coupled to nothing.

    `detail_column` adds a second page of magnified crops, one per value of that column, cut
    at the export's own resolution. The mapping from graph coordinates to pixels is derived
    from the image and then checked against it; if the check fails the page is dropped and the
    result says so, because a crop that is subtly misaligned still looks plausible.
    """
    from PIL import Image as _Image

    import figure as _figure
    from gephi_mcp_viewer import parse_gexf

    base = Path(file)
    if base.suffix.lower() in (".pdf", ".png"):
        base = base.with_suffix("")
    notes = list(notes or [])
    warnings: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "map.png"
        exported = await gephi.request("POST", "/export/png",
                                       json_data={"file": str(raw), "width": width,
                                                  "height": height})
        if not (isinstance(exported, dict) and exported.get("success")):
            return fmt({"success": False, "error": "Map export failed", "detail": exported})
        if not raw.exists():
            return fmt({"success": False,
                        "error": f"Gephi reported success but wrote no file at {raw}"})
        map_image = _Image.open(raw)
        map_image.load()

    # One read of the graph serves the swatches, the diagnostics and the crops.
    graph = None
    gexf = await _export_gexf_inline()
    if isinstance(gexf, dict) and gexf.get("success") and gexf.get("content"):
        graph = parse_gexf(gexf["content"], max_nodes=10**9)

    def colours_for(column: str) -> dict[str, str] | None:
        if not graph:
            return None
        wanted = column.replace("_", "").replace(" ", "").lower()
        found: dict[str, str] = {}
        for node in graph["nodes"]:
            value = next((v for k, v in (node.get("attributes") or {}).items()
                          if k.replace("_", "").replace(" ", "").lower() == wanted), None)
            if value is None or str(value) in found:
                continue
            match = re.match(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", str(node.get("color") or ""))
            if match:
                r, g, b = (int(v) for v in match.groups())
                found[str(value)] = f"#{r:02x}{g:02x}{b:02x}"
        return found or None

    channels: list[dict] = []
    for item in LEDGER.legend_items():
        entry = dict(item)
        if (entry["channel"].endswith("colour") and entry.get("column")
                and not entry.get("groups")):
            derived = colours_for(entry["column"])
            if derived:
                entry["groups"] = derived
        channels.append(entry)

    if partition_column:
        derived = colours_for(partition_column)
        if derived:
            known = next((c for c in channels if c.get("column") == partition_column), None)
            if known is not None:
                known["groups"] = derived
            else:
                channels.insert(0, {"channel": "node colour", "column": partition_column,
                                    "groups": derived})
        else:
            warnings.append(
                f"No colours could be read back for '{partition_column}'; the column may not "
                "exist or its nodes may be uncoloured. The legend omits that channel rather "
                "than guessing one.")

    for extra in (extra_channels or []):
        for item in extra.get("items") or []:
            glyph = str(item.get("glyph", "circle")).lower()
            if glyph not in _figure.GLYPHS:
                return fmt({"success": False,
                            "error": f"Unknown glyph {glyph!r} in extra_channels; expected one "
                                     f"of {', '.join(_figure.GLYPHS)}"})
        channels.append(extra)

    if not channels:
        return fmt({"success": False,
                    "error": ("Nothing to put in a legend: no colour or size mapping has been "
                              "applied through these tools, no partition_column was given to "
                              "read colours back from the graph, and no extra_channels were "
                              "declared. A figure with an empty key is worse than none.")})

    # The composer draws whatever Gephi currently renders, so an unstyled map
    # becomes an unreadable figure without complaint. Run the same diagnostics
    # gephi_visual_qa runs and hand back what they say.
    if graph:
        try:
            diagnosis = gephi_mcp_viewer.analyze_graph(graph, partition_column=partition_column)
            for problem in diagnosis.get("warnings") or []:
                warnings.append(f"map: {problem}")
        except Exception as exc:  # diagnostics must never block the figure
            logging.getLogger(__name__).debug("figure diagnostics failed: %s", exc)

    pages = [_figure.compose(map_image, title, subtitle, channels, notes)]

    if detail_column:
        page, problem = _detail_page(map_image, graph, detail_column)
        if page is not None:
            pages.append(page)
        else:
            warnings.append(problem)

    try:
        written = _figure.write(pages, base)
    except OSError as exc:
        return fmt({"success": False, "error": f"Could not write {base}: {exc}"})

    result = {"success": True, **written,
              "channels": [{k: v for k, v in c.items() if k != "palette"} for c in channels],
              "notes": notes}
    if warnings:
        result["warnings"] = warnings
    if not notes:
        result["reminder"] = ("No notes were given. A figure that leaves its reading rules "
                              "unstated invites the reader to over-read it; pass `notes` with "
                              "what the layout does and does not mean.")
    return fmt(result)


def _detail_page(map_image: Any, graph: dict | None, column: str):
    """Build the magnified-crops page, or explain why it cannot be trusted."""
    import figure as _figure

    if not graph:
        return None, "Detail page skipped: the graph could not be read back to locate groups."
    nodes = graph["nodes"]

    to_pixel = _figure.position_transform(nodes, _figure.content_box(map_image))
    if to_pixel is None:
        return None, "Detail page skipped: node positions have no extent to map onto the image."

    hit = _figure.transform_hit_rate(map_image, nodes, to_pixel)
    if hit < 0.5:
        return None, (f"Detail page skipped: only {hit:.0%} of sampled nodes landed on drawn "
                      "pixels, so the crop boxes could not be trusted. A misaligned crop still "
                      "looks plausible, which is why it is dropped rather than shipped.")

    wanted = column.replace("_", "").replace(" ", "").lower()
    resolved = next((k for node in nodes for k in (node.get("attributes") or {})
                     if k.replace("_", "").replace(" ", "").lower() == wanted), None)
    if resolved is None:
        return None, f"Detail page skipped: no node column named '{column}'."

    boxes = _figure.group_boxes(nodes, resolved, to_pixel)
    if not boxes:
        return None, f"Detail page skipped: column '{column}' held no values."
    boxes = dict(sorted(boxes.items(),
                        key=lambda kv: -((kv[1][2] - kv[1][0]) * (kv[1][3] - kv[1][1])))[:6])
    return _figure.detail_page(
        map_image, boxes, f"Detail: {column}",
        "Same map, magnified at the export's own resolution."), ""


@_tool(name="gephi_session_receipt")
async def gephi_session_receipt(file: str | None = None) -> str:
    """Report how the current figure was made, ready to paste into a methods section.

    Gephi does not record which layout ran with which settings, or which statistics produced which
    columns, so six months later a figure cannot be explained or reproduced. This returns that
    record: the visual mappings in force, the statistics run and the parameters they ran under,
    the layout and its settings, and the plugin and server versions.

    The record covers what went through these tools. Work done by hand in the Gephi window is not
    visible here, and the receipt says so rather than letting silence read as completeness.
    """
    receipt: dict[str, Any] = {"success": True}
    receipt.update(LEDGER.receipt())
    health = await gephi.request("GET", "/health")
    receipt["versions"] = {
        # Never null: a receipt is provenance, and a blank version reads as though the
        # question was never asked rather than as though the answer was unavailable.
        "server": __version__ or "unknown (not an installed distribution)",
        "plugin": health.get("version") if isinstance(health, dict) else None,
    }
    if file:
        try:
            Path(file).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
            receipt["file"] = file
        except OSError as exc:
            return fmt({"success": False, "error": f"Could not write {file}: {exc}"})
    return fmt(receipt)




@_tool(name="gephi_export_gexf")
async def gephi_export_gexf(file: str | None = None) -> str:
    """Export the graph to GEXF (preserves attributes, positions, and viz properties).

    With a file path, writes to disk. Without one, returns the GEXF document
    inline in the response's "content" field (plugin 1.2.1+) — no file round-trip.
    """
    payload = {"file": file} if file else {"inline": True}
    return fmt(await gephi.request("POST", "/export/gexf", json_data=payload))

@_tool(name="gephi_export")
async def gephi_export(file: str, format: str) -> str:
    """Export the graph in any format Gephi supports, by name — the general exporter.

    format is the exporter name: `vna`, `pajek`, `dl` (UCINET interchange),
    `spreadsheet` (for non-technical readers), `gdf`, `json`, plus
    `gexf`/`graphml`/`csv`. (Note: `gml` is import-only in this Gephi build — no
    exporter — despite appearing in some format lists.) The common visual/graph
    formats keep their dedicated tools (gephi_export_gexf, gephi_export_png,
    gephi_export_csv, …); reach for this when you need one of the interchange
    formats they don't cover, e.g. handing the network to UCINET (`vna`/`dl`) or
    Pajek (`pajek`), or giving a collaborator a spreadsheet. Errors listing the
    known formats if the name isn't recognized.
    """
    return fmt(await gephi.request("POST", "/export/format",
                                   json_data={"file": file, "format": format}))

@_tool(name="gephi_export_png")
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

@_tool(name="gephi_export_screenshot")
async def gephi_export_screenshot(file: str, scale: int = 2, transparent_background: bool = False) -> str:
    """Screenshot the live Gephi canvas as the analyst sees it, selection and
    camera included. Captures selection highlighting, hover state, and current
    camera framing through Gephi's own screenshot feature. Use this instead of gephi_export_png whenever the
    figure needs to show what the analyst is currently looking at, most importantly
    an active selection: gephi_export_png renders the graph's stored data through
    Gephi's Preview pipeline, which has no concept of selection at all and can only
    fake it by recoloring nodes (the rest of the map stays at full strength instead
    of dimming). This tool captures the real rendered frame, so a box-drag selection
    shows dimmed-unselected / vivid-selected exactly as the person sees it.

    Tradeoff: this is the interactive Overview renderer, not the publication-quality
    Preview renderer gephi_export_png uses (no edge bundling, plainer typography), so
    a screenshot may look visually rougher than Preview-based exports. Use
    gephi_export_png for clean data-driven figures; use this specifically when
    selection state (or exactly what's on screen) needs to be in the image.

    scale: an integer multiplier on the current on-screen canvas size (Gephi's
    screenshot API takes a scale factor, not literal width/height like
    gephi_export_png). 2 is a reasonable default for print-quality output.
    transparent_background: if true, exports with a transparent background instead
    of Gephi's current canvas background.

    Desktop only; the Overview window must be visible (not minimized) since this
    reads the actual rendered pixels.
    """
    return fmt(await gephi.request("POST", "/export/screenshot",
                                   json_data={"file": file, "scale": scale,
                                              "transparent_background": transparent_background}))

@_tool(name="gephi_export_pdf")
async def gephi_export_pdf(file: str, width: int | None = None, height: int | None = None) -> str:
    """Export the graph visualization as PDF (page size auto-detected if omitted)."""
    return fmt(await gephi.request("POST", "/export/pdf",
                                   json_data=_body(file=file, width=width, height=height)))

@_tool(name="gephi_export_svg")
async def gephi_export_svg(file: str) -> str:
    """Export the graph visualization as SVG (scalable vector graphics)."""
    return fmt(await gephi.request("POST", "/export/svg", json_data={"file": file}))

@_tool(name="gephi_export_graphml")
async def gephi_export_graphml(file: str) -> str:
    """Export the graph to GraphML (widely supported XML format)."""
    return fmt(await gephi.request("POST", "/export/graphml", json_data={"file": file}))

@_tool(name="gephi_export_csv")
async def gephi_export_csv(file: str, separator: str = ",", target: str = "nodes") -> str:
    """Export the graph to CSV. target: "nodes" | "edges" | "both"."""
    return fmt(await gephi.request("POST", "/export/csv",
                                   json_data={"file": file, "separator": separator, "target": target}))

@_tool(name="gephi_focus_view")
async def gephi_focus_view(mode: str = "graph", id: str | None = None,
                           source: str | None = None, target: str | None = None,
                           x: float | None = None, y: float | None = None,
                           w: float | None = None, h: float | None = None,
                           zoom: float | None = None,
                           select: list[str] | None = None) -> str:
    """Move Gephi Desktop's camera to direct the human viewer's attention.

    Use this in teaching/demo sessions so the person watching Gephi sees what you
    are working on: mode "graph" fits the whole graph, "node" centers on a node
    (id), "edge" on an edge (source+target), "region" on a rectangle (x, y, w, h in
    graph coordinates). Optional select highlights nodes visually (empty list
    clears the selection); zoom sets the zoom level. Call it after layouts, before
    narrating a cluster, or when saying "watch this part". Desktop only; returns an
    error when no visualization is available (headless).

    `select` is for VISUAL HIGHLIGHTING only (drawing the viewer's eye), not for
    setting up a selection you will read back. It switches Gephi's engine into
    "custom selection" mode, a separate mode from the rectangle box-drag the
    person uses to point, and confirmed unreliable to read back afterward via
    gephi_get_selection (Gephi's own selection-mode bookkeeping does not clean up
    the switch symmetrically). The response's `selected` count is verified at
    the moment of this call, but do not rely on it still being readable in a
    later call. For anything you need to read back, rely on the human's real
    box-drag selection (gephi_get_selection), not this parameter.
    """
    return fmt(await gephi.request("POST", "/view/focus",
                                   json_data=_body(mode=mode, id=id, source=source,
                                                   target=target, x=x, y=y, w=w, h=h,
                                                   zoom=zoom, select=select)))


@_tool(name="gephi_set_selection_mode")
async def gephi_set_selection_mode(mode: str = "rectangle") -> str:
    """Set how the human's mouse selects nodes in the Gephi window.

    This removes the one manual step the pointing feature (gephi_get_selection)
    otherwise requires: normally the person has to click the dashed-square
    rectangle-selection icon before they can box-select nodes. Call this with
    mode="rectangle" at the START of a teaching/watch-along session so pointing
    just works — they can immediately drag a box and gephi_get_selection reads
    it.

    mode: "rectangle" (drag a box to select — the persistent mode that pointing
    relies on), "direct" (click/mouse-radius selection), or "disable" (turn
    selection off). Desktop only; errors when no visualization is available
    (headless).
    """
    return fmt(await gephi.request("POST", "/view/selection", json_data={"mode": mode}))


@_tool(name="gephi_get_perspective")
async def gephi_get_perspective() -> str:
    """List Gephi Desktop's perspectives (tabs) and which one is active.

    Perspectives are the top-level tabs: Overview (the graph canvas), Data
    Laboratory (the node/edge tables), and Preview (the export-styling view).
    Returns the selected perspective plus the full list, each with name and
    display_name. Pair with gephi_switch_perspective to move the human's view
    to the right tab before discussing it. Desktop only.
    """
    return fmt(await gephi.request("GET", "/perspective"))


@_tool(name="gephi_switch_perspective")
async def gephi_switch_perspective(name: str) -> str:
    """Switch Gephi Desktop to a different perspective (tab) by name.

    name matches a perspective's name or display_name from gephi_get_perspective
    (case-insensitive) — typically "Overview", "Data Laboratory", or "Preview".
    Use in teaching mode to bring the human to the view you're about to talk
    about (e.g. switch to Data Laboratory before walking through the attribute
    table). Desktop only.
    """
    return fmt(await gephi.request("POST", "/perspective/switch", json_data={"name": name}))


@_tool(name="gephi_get_selection")
async def gephi_get_selection(clear: bool = False) -> str:
    """Read the nodes the human has SELECTED in the Gephi window — pointing,
    made legible.

    Call this whenever the person uses deictic words about the canvas: "these",
    "this group", "the ones I selected", "what did I grab?". Their selection is
    the answer; do not ask them to type node names.

    How the human points: box-drag selection is turned ON automatically at the
    start of the session, so they can just drag a box around nodes on the
    Overview canvas and the selection persists until they box elsewhere — no need
    to hunt for a toolbar tool. (If they switched to another mouse mode, the
    dashed-square rectangle icon in the thin left toolbar turns it back on; plain
    hover highlighting is transient and does not register.)

    Returns selected_now (the current persistent selection, capped at 200 with
    selected_count giving the true total), plus canvas state — rectangle_selection
    (is box-drag active), selection_enabled, and zoom — so an empty selection can
    be explained rather than left silent. Also returns clicks, a journal of node
    clicks (usually empty; selected_now is the primary channel). clear=True empties
    the click journal only; the live selection always reflects the canvas. Desktop only.

    Only reliably reads back the human's real box-drag (rectangle) selection.
    A selection set programmatically via gephi_focus_view's `select` parameter
    is NOT guaranteed to still be here — that parameter switches Gephi into a
    separate "custom selection" engine mode that does not interoperate cleanly
    with this read path (confirmed unreliable; do not chain the two).
    """
    return fmt(await gephi.request(
        "GET", f"/selection?clear={'true' if clear else 'false'}"))


@_tool(name="gephi_visual_qa")
async def gephi_visual_qa(partition_column: str | None = None) -> str:
    """Run visual-design diagnostics on the current graph. Cheap; use it often.

    Call BEFORE styling with partition_column set (e.g. "group", "modularity_class")
    to verify a claimed grouping is topologically real — if the verdict is "none",
    coloring by it would mislead; compute real communities instead. Call again AFTER
    styling/layout — always with partition_column when the graph has communities —
    to catch invisible node sizes, near-white colors, gradient color schemes, and
    to get the export dimensions that match the layout's shape
    (extent.suggested_export). Fix every warning before the final export.

    Layout-quality outputs: partition.separation measures how spatially mixed the
    partition is in the CURRENT layout (mean intra-community pair distance over
    mean random pair distance; 1.0 = fully mixed, near 0 = tight distinct
    clusters) — compare it across parameter changes instead of eyeballing PNGs,
    and quote the before/after when explaining an adjustment. extent.outliers
    lists nodes far outside the main cloud (the hub-and-spoke bounding-box
    blowout); when present, suggested_export already frames the main cloud, so
    export with it rather than hand-cropping. Non-finite positions (an exploded
    layout) are warned about and excluded from all extent math.
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


@_tool(name="gephi_label_clusters")
async def gephi_label_clusters(partition_column: str,
                               names: dict[str, str] | None = None,
                               caption_scale: float = 1.0,
                               prefer: str = "degree",
                               restore: bool = False) -> str:
    """Caption each cluster by labeling only its most salient (top-degree) node.

    The visual network analysis move for naming regions: every other label is
    blanked, each cluster's hub gets the cluster's name (from `names`, keyed by
    the partition value, e.g. {"1.0": "Engineering"}) or keeps its own label if
    no name is given, and preview switches to labeled mode with a white outline.
    Hubs sit near their cluster's center of gravity, so the caption lands on the
    region. caption_scale multiplies the auto-computed caption size (1.5-2 for
    louder, map-style captions); prefer="size" anchors captions on the visually
    largest node instead of the highest-degree one. Original labels are saved to
    a `label_backup` node attribute (never overwritten on repeat runs);
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

    hubs = gephi_mcp_viewer.pick_cluster_hubs(graph, partition_column, prefer=prefer)
    if not hubs:
        return fmt({"success": False,
                    "error": f"no nodes carry the attribute '{partition_column}'"})
    hub_keys = set(hubs.values())

    backups = [{"id": n["key"], "attributes": {"label_backup": n["label"]}}
               for n in graph["nodes"]
               if n["attributes"].get("label_backup") is None]
    if backups:
        await gephi.request("POST", "/graph/nodes/attributes",
                            json_data={"updates": backups})

    labeled, blanked = {}, 0
    label_by_key = {n["key"]: n["attributes"].get("label_backup") or n["label"]
                    for n in graph["nodes"]}
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

    # Two Gephi label facts drive this recipe: with proportional size OFF the
    # renderer clamps labels to the node's bounds (captions can never outgrow
    # the hub), and with it ON the font multiplies by node size — which works in
    # our favor, since caption hosts are the biggest hubs. Base font still
    # scales with layout extent (fonts render in graph-coordinate space).
    xs = [n["x"] for n in graph["nodes"]] or [0.0]
    ys = [n["y"] for n in graph["nodes"]] or [0.0]
    extent_long = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    font_size = max(12, int(extent_long / 200 * caption_scale))
    await gephi.request("POST", "/preview/settings", json_data={
        "node.label.show": True, "node.label.proportinalSize": True,
        "node.label.font": f"Arial {font_size} Bold",
        "node.label.outline.size": max(4.0, font_size / 5),
        "node.label.outline.opacity": 95.0, "node.label.avoidOverlap": True})
    return fmt({"success": True, "labeled": labeled, "blanked": blanked,
                "caption_font": font_size})


@mcp.resource("ui://gephi/graph-view", name="gephi-graph-view",
              mime_type="text/html;profile=mcp-app")
def gephi_graph_view_app() -> str:
    """Static MCP App page that renders graph data pushed by the host."""
    return gephi_mcp_viewer.build_app_html()

def _preview_for_view(result: dict) -> dict | None:
    """Normalize Gephi's preview settings for the in-chat view so it draws the
    way Gephi's own export would (opacities as 0-1, the edge color mode as-is).
    Returns None when the settings could not be read; the app then uses defaults."""
    if not result.get("success", True):
        return None
    st = result.get("settings") or result
    if "edge.opacity" not in st:
        return None
    return {
        "edge_opacity": float(st.get("edge.opacity", 100.0)) / 100.0,
        "edge_curved": bool(st.get("edge.curved", False)),
        "edge_color": st.get("edge.color", "mixed"),
        "edge_thickness": float(st.get("edge.thickness", 1.0)),
        "node_border_width": float(st.get("node.border.width", 1.0)),
        "node_opacity": float(st.get("node.opacity", 100.0)) / 100.0,
        "label_show": bool(st.get("node.label.show", False)),
        "arrow_size": float(st.get("arrow.size", 3.0)),
    }


@_tool(name="gephi_view_graph",
          meta={"ui": {"resourceUri": "ui://gephi/graph-view"}})
async def gephi_view_graph(max_nodes: int = 1500, title: str = "Network view",
                           caption_column: str | None = None,
                           caption_names: dict[str, str] | None = None) -> CallToolResult:
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
                content=[TextContent(type="text", text=fmt(result))], is_error=True)
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
    structured = {**graph, "title": title}
    if caption_column:
        # Callers pass a column id (modularity_class); node attributes are keyed
        # by title (Modularity Class). Hand the app the key that is actually there.
        structured["captions"] = {
            "column": gephi_mcp_viewer.resolve_column_key(graph, caption_column),
            "names": caption_names or {}}
    preview = _preview_for_view(await gephi.request("GET", "/preview/settings"))
    if preview:
        structured["preview"] = preview
    return CallToolResult(
        content=[TextContent(type="text", text=summary)],
        structured_content=structured,
    )


# ─── Text ─────────────────────────────────────────────────────

@_tool(name="gephi_text_to_network")
async def gephi_text_to_network(text: str | list[str], window_size: int = 4,
                                min_edge_weight: float = 0.0,
                                extra_stopwords: list[str] | None = None,
                                pos_filter: str | None = None,
                                min_word_frequency: int = 1,
                                merge_phrases: bool = False,
                                self_referential_threshold: float = 0.5,
                                exclude_self_referential: bool = False,
                                context_snippets: int = 0,
                                clear_existing: bool = False) -> str:
    """Convert free text into a word co-occurrence network and load it into Gephi.

    Words are lemmatized and stopwords removed; an edge connects two words
    that appear within `window_size` tokens of each other, weighted by
    proximity (closer words get a stronger edge). The result is a normal
    Gephi graph, so every other tool here (layout, community detection,
    gephi_visual_qa, teachback) applies to it exactly as it would to any
    other network, with no special-casing needed.

    Pass a list of strings, not one concatenated string, whenever the input
    is naturally many separate units — article titles, survey responses,
    transcript turns, tweets. The co-occurrence window resets at each list
    item; it never bridges from the end of one document into the start of
    the next. Concatenating first and passing a single string will silently
    manufacture edges between the last word of one document and the first
    word of the next.

    Before trusting the result, check stats.self_referential_candidates —
    words appearing in an unusually large share of documents (the corpus's
    own subject name, or generic prose scaffolding in full-text corpora)
    will dominate the graph as a hub without discriminating anything, and
    raw frequency rank alone is not a reliable way to catch this: a word can
    be edged out of a top-N-by-count list by rarer, more topical words and
    still be the single most universal word in the corpus. Add any flagged
    candidate to extra_stopwords and rebuild rather than reporting it as a
    finding.

    Do not assume every high document-frequency word is generic scaffolding
    though — on real data, a word appearing in ~40-50% of documents is
    genuinely ambiguous: a legitimate topical hub word and a truly generic
    one can land at nearly the same document ratio, and graph-structural
    signals (degree, edge-weight concentration) don't reliably separate them
    either. A word can also be a genuine but minor sub-topic hiding inside
    what looks like scaffolding overall — on one real corpus, a word read as
    filler from two arbitrary example sentences, but its single
    highest-count document used it 184 times and turned out to be a genuine
    article specifically about that word's own subject; a blanket exclusion
    would have discarded that real sub-topic along with the actual noise.
    This has to be read, not computed: rebuild with context_snippets=2-3 (excerpts
    come from each word's highest-count documents first, precisely to catch
    concentration like this) and check each candidate's peak_document_count
    too — scaffolding words rarely repeat more than a dozen times even in
    their heaviest document, while a real topic spikes much higher in the
    documents actually about it. Neither signal is a substitute for reading
    the excerpts; a word that's generic scaffolding on one corpus can be
    exactly the topic on another, so treat both as evidence to weigh, not a
    rule to apply blindly.

    Suggested next steps: gephi_profile_network for structural stats, then a
    layout, then betweenness centrality — high-betweenness words are bridge
    concepts between topic clusters, a different signal from high-degree
    words (frequency). Two dense clusters with few or no connecting edges (a
    structural gap) is a candidate for insight, but verify it's a real
    pattern rather than an artifact of a small or skewed sample before
    treating it as a finding — run gephi_visual_qa with the partition set to
    confirm it's topologically real first. Before naming a detected
    community from its top words, read the source documents behind at least
    2-3 of them (not just the highest one) — a shared high-degree word can be
    a theoretical frame or stock phrase reused across otherwise-unrelated
    documents rather than a real shared topic; see
    references/text-network-analysis.md for how to tell the difference.

    extra_stopwords: additional words to filter beyond the built-in English
    stopword list (e.g. a recurring interviewer name in transcript data, or
    the corpus's own subject terms).
    pos_filter: None (default) keeps every part of speech. "nouns" restricts
    the graph to noun tokens only — nouns carry the concept-level structure
    of a discourse (Rule, Cointet, and Bearman 2015); a noun-only graph is
    sparser and more topically legible, at the cost of losing the relational/
    qualitative information verbs and adjectives carry. Falls back to no
    filtering (disclosed via stats.pos_filter_applied) if the POS tagger
    isn't installed.
    min_edge_weight: drop weak co-occurrence edges after aggregation. For a
    more principled alternative that doesn't apply one flat cutoff to every
    node regardless of its own degree, build with min_edge_weight=0 and run
    gephi_extract_backbone afterward instead.
    min_word_frequency: drop words appearing fewer than this many times in
    the whole corpus before building any edges (default 1 keeps everything).
    Most unique words in natural text occur once or twice and contribute
    long-tail node clutter rather than repeatable structure — raising this
    to 2 or 3 is standard practice for reducing that clutter without
    touching the edge-weight logic at all.
    merge_phrases: if True, cohesive two-word phrases ("machine learning")
    are detected corpus-wide and merged into one node instead of remaining
    two separately co-occurring unigrams — qualifies only if both the POS
    pattern (adjective+noun or noun+noun) and pointwise mutual information
    clear a threshold, so frequent-but-unrelated adjacent words don't merge.
    Disclosed via stats.phrases_detected. Default off (pure unigrams).
    self_referential_threshold: flags any word appearing in at least this
    fraction of documents (default 0.5) as a candidate self-referential/
    generic hub, via stats.self_referential_candidates (each entry:
    {"word", "document_frequency", "document_ratio", "peak_document_count"})
    and each node's document_frequency attribute. Lower it (e.g. 0.3) for a
    stricter check on a large or noisy corpus.
    exclude_self_referential: if True, flagged words are actually dropped
    from the graph, not just reported. Worth turning on for large multi-
    document corpora specifically: a high min_word_frequency floor on its
    own can select FOR generic words rather than against them there (a word
    needs sustained presence across many documents to rack up a large total
    count — on a real 255-document corpus, requiring 200+ occurrences left
    half the surviving vocabulary flagged as present in most documents).
    Default False since dropping a large share of the vocabulary is a real
    methodological choice, not a silent default.
    context_snippets: how many short excerpts of original surrounding text to
    attach to each self_referential_candidate (default 0, off). Turn this on
    when reviewing the gray zone (see above) — excerpts are pulled from each
    word's highest-count documents first, not just the first documents it
    happens to appear in, so a word concentrated as a real sub-topic in a
    handful of documents doesn't get missed by chance. Reading those
    excerpts is enough to tell "generic scaffolding" from "genuine topic
    hub" on any dataset, without hand-grepping the source text or guessing
    from a word list tuned on a different corpus.
    clear_existing: if True, clears the current graph before loading this one
    (an undo snapshot is taken automatically before the clear; gephi_undo
    restores the previous graph).
    """
    graph = text_network.build_cooccurrence_graph(
        text, window_size=window_size, min_edge_weight=min_edge_weight,
        extra_stopwords=extra_stopwords, pos_filter=pos_filter,
        min_word_frequency=min_word_frequency, merge_phrases=merge_phrases,
        self_referential_threshold=self_referential_threshold,
        exclude_self_referential=exclude_self_referential,
        context_snippets=context_snippets,
    )
    if not graph["nodes"]:
        return fmt({"success": False,
                    "error": "No words survived stopword filtering; nothing to build.",
                    "stats": graph["stats"]})

    undo = False
    if clear_existing:
        undo = await _auto_snapshot("text_to_network")
        clear_result = await gephi.request("POST", "/graph/clear")
        if not clear_result.get("success", True):
            return fmt(clear_result)

    node_result = await gephi.request("POST", "/graph/nodes/add", json_data={"nodes": graph["nodes"]})
    if not node_result.get("success", True):
        return fmt(node_result)

    edge_result = await gephi.request("POST", "/graph/edges/add", json_data={"edges": graph["edges"]})

    out = {
        "success": edge_result.get("success", True),
        "stats": graph["stats"],
        "nodes_result": node_result,
        "edges_result": edge_result,
    }
    if clear_existing:  # only then was anything destroyed
        out["undo_available"] = undo
    return fmt(out)

@_tool(name="gephi_extract_backbone")
async def gephi_extract_backbone(alpha: float = 0.05, max_edges: int = 20000) -> str:
    """Prune the current graph to its statistically significant backbone.

    Removes edges using the disparity filter (Serrano, Boguna, and
    Vespignani 2009) instead of a single global weight cutoff: for each node,
    an edge is judged significant relative to how that node's own total
    weight is split across its neighbors, so a low-degree node's one real
    connection survives even if its absolute weight is small, while a
    high-degree hub's genuinely insignificant edges still get pruned even if
    their absolute weight looks fine in isolation. This is the principled
    alternative to min_edge_weight on gephi_text_to_network (a flat
    threshold) or to visually rescaling edge thickness by weight (a display-
    only fix that leaves the underlying graph, and any statistics computed
    on it, unchanged).

    Works on any weighted graph already loaded in Gephi, not just text
    networks. Applies directly to the live graph: fetches all edges, computes
    the backbone, and removes every edge that doesn't survive. This changes
    the actual graph other tools see — recompute modularity/betweenness
    afterward if you need them to reflect the pruned structure, since values
    computed before pruning describe the pre-prune graph.

    alpha: significance threshold (lower keeps fewer edges, a stricter
    backbone); 0.05 and 0.01 are the values most commonly used in the
    disparity-filter literature. max_edges: safety cap on how many edges this
    will fetch/prune in one call — pruning removes edges one at a time
    (no bulk-remove endpoint exists), so very large graphs will be slow;
    raise the cap deliberately rather than by default.
    """
    edges_result = await gephi.request("GET", "/graph/edges", params={"limit": max_edges})
    if not edges_result.get("success", True):
        return fmt(edges_result)
    edges = edges_result.get("edges", [])
    if not edges:
        return fmt({"success": False, "error": "No edges found on the current graph."})

    backbone = text_network.extract_backbone(edges, alpha=alpha)
    kept_pairs = {(e["source"], e["target"]) for e in backbone["edges"]}
    to_remove = [e for e in edges if (e["source"], e["target"]) not in kept_pairs]

    # Snapshot after the (read-only) fetch + computation, right before pruning —
    # so a call that errors out or removes nothing doesn't roll away a useful
    # undo point.
    undo = await _auto_snapshot("extract_backbone")

    removed = 0
    for e in to_remove:
        result = await gephi.request("POST", "/graph/edge/remove",
                                     json_data={"source": e["source"], "target": e["target"]})
        if result.get("success", True):
            removed += 1

    return fmt({
        "success": True,
        "stats": backbone["stats"],
        "edges_removed_from_graph": removed,
        "edges_remaining": len(edges) - removed,
        "undo_available": undo,
    })


# ─── Counterfactual / comparison ─────────────────────────────

async def _read_graph(workspace: int | None = None) -> dict[str, Any] | None:
    """Parse the graph of a workspace, switching to it and back if one is named."""
    original = None
    if workspace is not None:
        listed = await gephi.request("GET", "/workspace/list")
        if not (isinstance(listed, dict) and listed.get("success")):
            return None
        # The list reports an id; every switch/rename call takes a zero-based INDEX. They are
        # different numbers, and using the id lands on the wrong workspace or on none at all.
        original = next((i for i, w in enumerate(listed.get("workspaces", []))
                         if w.get("current")), None)
        switched = await gephi.request("POST", "/workspace/switch", json_data={"index": workspace})
        if not (isinstance(switched, dict) and switched.get("success")):
            return None
    try:
        exported = await _export_gexf_inline()
        if not (isinstance(exported, dict) and exported.get("success") and exported.get("content")):
            return None
        from gephi_mcp_viewer import parse_gexf
        return parse_gexf(exported["content"], max_nodes=10**9)
    finally:
        if workspace is not None and original is not None:
            await gephi.request("POST", "/workspace/switch", json_data={"index": original})


@_tool(name="gephi_compare_workspaces")
async def gephi_compare_workspaces(before: int, after: int, compare: str | None = None,
                                   directed: bool = False) -> str:
    """Compare the same network at two points in time, held in two workspaces.

    Reports which nodes and edges arrived, which left, and — when `compare` names a numeric column
    such as Degree — which of the nodes present in both grew and which shrank. Answering this today
    means exporting both sides and comparing by hand.

    The comparison rests entirely on node identity: the two sides only diff meaningfully if the
    same id means the same thing in both. When they share no nodes at all the result says so
    rather than reporting total turnover, because a mismatched identifier looks identical to a
    network that replaced every member and is very much more common.

    Answers gephi/gephi#2013.
    """
    left = await _read_graph(before)
    if left is None:
        return fmt({"success": False, "error": f"Could not read workspace {before}."})
    right = await _read_graph(after)
    if right is None:
        return fmt({"success": False, "error": f"Could not read workspace {after}."})
    result = {"success": True, "before_workspace": before, "after_workspace": after}
    result.update(diff_graphs(left, right, compare=compare, directed=directed))
    return fmt(result)


@_tool(name="gephi_bipartite_layout")
async def gephi_bipartite_layout(mode_column: str, separation: float = 600.0,
                                 spacing: float = 60.0) -> str:
    """Lay a two-mode network out as two columns, one per mode.

    Two-mode data — people by events, authors by concepts, informants by sites — is drawn by Gephi
    as though every node were the same kind of thing, which misreads the data at a glance. This
    places each mode in its own column so the structure is visible.

    `mode_column` names the attribute separating the two kinds; Gephi has no notion of a node's
    mode, so it has to be told. A column holding more than two distinct values is refused rather
    than guessed at.

    Answers gephi/gephi#3131. Computed here and pushed as coordinates, so no layout plugin is
    involved.
    """
    graph = await _read_graph()
    if graph is None:
        return fmt({"success": False, "error": "Could not read the current graph."})
    try:
        positions = bipartite_positions(graph, mode_column,
                                        separation=separation, spacing=spacing)
    except ValueError as exc:
        return fmt({"success": False, "error": str(exc)})
    pushed = await gephi.request("POST", "/graph/nodes/positions",
                                 json_data={"positions": positions})
    if not (isinstance(pushed, dict) and pushed.get("success")):
        return fmt(pushed)
    left, right = split_modes(graph, mode_column)
    return fmt({"success": True, "positioned": len(positions),
                "modes": {"left": len(left), "right": len(right)},
                "mode_column": mode_column})


@_tool(name="gephi_bipartite_projection")
async def gephi_bipartite_projection(mode_column: str, keep: str,
                                     workspace_name: str | None = None) -> str:
    """Collapse a two-mode network onto one mode, in a new workspace.

    Two people who attended the same event become connected, weighted by how many events they
    shared. This is the standard way to analyse two-mode data as a social network, and Gephi
    cannot do it at all.

    Nodes sharing no partner are kept with no edges. Dropping them would quietly remove people
    from the network, which produces a different graph rather than a tidier one.

    The original is left untouched: the projection is built in a new workspace, so the two-mode
    data survives alongside the one-mode view of it.
    """
    graph = await _read_graph()
    if graph is None:
        return fmt({"success": False, "error": "Could not read the current graph."})
    try:
        projected = project_bipartite(graph, mode_column, keep=keep)
    except ValueError as exc:
        return fmt({"success": False, "error": str(exc)})

    created = await gephi.request("POST", "/workspace/new")
    if not (isinstance(created, dict) and created.get("success")):
        return fmt(created)
    if workspace_name:
        listed = await gephi.request("GET", "/workspace/list")
        if isinstance(listed, dict) and listed.get("success"):
            # Rename addresses a workspace by index, and the new one is current.
            index = next((i for i, w in enumerate(listed.get("workspaces", []))
                          if w.get("current")), None)
            if index is not None:
                await gephi.request("POST", "/workspace/rename",
                                    json_data={"index": index, "name": workspace_name})
    await gephi.request("POST", "/graph/nodes/add",
                        json_data={"nodes": [{"id": n} for n in projected["nodes"]]})
    if projected["edges"]:
        await gephi.request("POST", "/graph/edges/add",
                            json_data={"edges": [{"source": e["source"], "target": e["target"],
                                                  "weight": e["weight"], "directed": False}
                                                 for e in projected["edges"]]})
    result = {"success": True, "nodes": len(projected["nodes"]),
              "edges": len(projected["edges"]), "kept_mode": keep}
    if projected.get("warning"):
        result["warning"] = projected["warning"]
        result["within_mode_edges"] = projected["within_mode_edges"]
    return fmt(result)




# Scalar metrics worth diffing before/after a hypothetical edit, as
# (label, path-into-the-profile-dict). Curated rather than a blind recursive
# diff so the result reports only the numbers a counterfactual actually turns
# on, and skips bools/flags/lists that don't diff meaningfully.
_WHATIF_METRICS = [
    ("nodes", ("nodes",)),
    ("edges", ("edges",)),
    ("density", ("density",)),
    ("max_degree", ("degree", "max")),
    ("median_degree", ("degree", "median")),
    ("components", ("components", "count")),
    ("isolates", ("isolates",)),
    ("modularity", ("modularity", "modularity")),
    ("communities", ("modularity", "communities")),
    ("clustering_coefficient", ("clustering_coefficient",)),
    ("avg_path_length", ("distance", "avg_path_length")),
    ("diameter", ("distance", "diameter")),
]


def _dig(d: dict, path: tuple) -> Any:
    """Follow a key path into a nested dict; None if any hop is missing."""
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _diff_profiles(before: dict, after: dict) -> list[dict]:
    """Per-metric {before, after, delta} for the curated whatif metrics.

    Skips any metric absent from both profiles; computes delta only when both
    sides are numeric (so a metric present in one profile but not the other is
    still reported, just without a delta)."""
    diff = []
    for label, path in _WHATIF_METRICS:
        b, a = _dig(before, path), _dig(after, path)
        if b is None and a is None:
            continue
        entry = {"metric": label, "before": b, "after": a}
        if isinstance(b, (int, float)) and not isinstance(b, bool) \
                and isinstance(a, (int, float)) and not isinstance(a, bool):
            delta = a - b
            entry["delta"] = round(delta, 4) if isinstance(delta, float) else delta
        diff.append(entry)
    return diff


async def _apply_edit(edit: dict) -> dict:
    """Dispatch one whatif edit op to its existing graph endpoint."""
    op = edit.get("op")
    try:
        if op == "remove_node":
            return await gephi.request("DELETE", f"/graph/node/{edit['id']}")
        if op == "remove_nodes":
            return await gephi.request("POST", "/graph/nodes/remove", json_data={"ids": edit["ids"]})
        if op == "add_edge":
            e = {"source": edit["source"], "target": edit["target"]}
            if "weight" in edit:
                e["weight"] = edit["weight"]
            if "directed" in edit:
                e["directed"] = edit["directed"]
            return await gephi.request("POST", "/graph/edges/add", json_data={"edges": [e]})
        if op == "remove_edge":
            return await gephi.request("POST", "/graph/edge/remove",
                                       json_data={"source": edit["source"], "target": edit["target"]})
    except KeyError as missing:
        return {"success": False, "error": f"edit op {op!r} missing field {missing}"}
    return {"success": False, "error": f"unknown edit op: {op!r}"}


async def _cleanup_scratch(scratch_id: Any, orig_id: Any) -> dict:
    """Restore the original workspace and delete the scratch copy, by id.

    Switches to the original FIRST (so we are never deleting the current
    workspace), then deletes the scratch. Correlates by stable id and re-lists
    between steps because deleting a workspace shifts indices."""
    info: dict[str, Any] = {"scratch_deleted": False, "returned_to_workspace_id": None}
    ws = await gephi.request("GET", "/workspace/list")
    workspaces = ws.get("workspaces", []) if ws.get("success", True) else []
    orig_idx = next((i for i, w in enumerate(workspaces) if w.get("id") == orig_id), None)
    if orig_idx is not None:
        s = await gephi.request("POST", "/workspace/switch", json_data={"index": orig_idx})
        if s.get("success", True):
            info["returned_to_workspace_id"] = orig_id
    ws2 = await gephi.request("GET", "/workspace/list")
    workspaces2 = ws2.get("workspaces", []) if ws2.get("success", True) else []
    scratch_idx = next((i for i, w in enumerate(workspaces2) if w.get("id") == scratch_id), None)
    if scratch_idx is not None:
        d = await gephi.request("DELETE", "/workspace/delete", params={"index": str(scratch_idx)})
        info["scratch_deleted"] = bool(d.get("success", False))
    return info


@_tool(name="gephi_whatif")
async def gephi_whatif(edits: list[dict[str, Any]], include_slow: bool = False) -> str:
    """Test a hypothetical edit on a throwaway copy — never touches the real graph.

    Duplicates the current workspace, applies `edits` to the copy, measures the
    structural before/after, and returns the diff. The original workspace is
    never modified and the scratch copy is always deleted afterward (even if an
    edit fails), so this is safe to run repeatedly for scenario-testing:
    "what would removing this node do to path length and community structure?"

    edits: an ordered list of operations, each one of:
      - {"op": "remove_node", "id": str}
      - {"op": "remove_nodes", "ids": [str, ...]}
      - {"op": "add_edge", "source": str, "target": str, "weight"?: float, "directed"?: bool}
      - {"op": "remove_edge", "source": str, "target": str}
    include_slow: also diff average path length / diameter (expensive; only
    under ~3k nodes, same gate as gephi_profile_graph). Default off.

    Returns {success, edits_applied, diff, cleanup}. `diff` is a list of
    {metric, before, after, delta} for global structural metrics (nodes, edges,
    density, degree, components, isolates, modularity, communities, clustering,
    and path length/diameter when include_slow). The tool returns measurements,
    not conclusions — narrate the result yourself, and remember a counterfactual
    on a small or skewed graph can mislead the same way any single sample can.
    If an edit fails (e.g. add_edge on a pair that already has an edge), the
    run stops, no diff is produced, and the failure is reported — the scratch
    copy is still cleaned up.
    """
    # This tool duplicates a workspace, works on the copy, deletes it, and returns. Every one
    # of those calls hits /workspace/, which resets the ledger — correct for a real change of
    # graph, wrong here, because the caller is handed back the same graph with the same styling.
    # Without this the counterfactual silently empties the methods record for the figure being
    # prepared, and the next export ships with an incomplete legend.
    ledger_entries = list(LEDGER.entries)
    ws_list = await gephi.request("GET", "/workspace/list")
    if not ws_list.get("success", True):
        return fmt(ws_list)
    workspaces = ws_list.get("workspaces", [])
    orig = next((w for w in workspaces if w.get("current")), None)
    if orig is None:
        return fmt({"success": False, "error": "No current workspace to run a counterfactual on."})
    orig_id = orig.get("id")
    orig_index = workspaces.index(orig)

    dup = await gephi.request("POST", "/workspace/duplicate", json_data={"index": orig_index})
    if not dup.get("success", True):
        return fmt(dup)
    scratch_id = dup.get("workspace_id")

    outcome: dict[str, Any]
    try:
        before = await _compute_profile(include_slow)
        if not before.get("success", True):
            outcome = {"success": False, "stage": "baseline_profile", "detail": before}
        else:
            failed = None
            for i, edit in enumerate(edits):
                er = await _apply_edit(edit)
                if not er.get("success", True):
                    failed = {"success": False, "stage": "edit", "index": i, "edit": edit, "detail": er}
                    break
            if failed:
                outcome = failed
            else:
                after = await _compute_profile(include_slow)
                if not after.get("success", True):
                    outcome = {"success": False, "stage": "after_profile", "detail": after}
                else:
                    outcome = {"success": True, "edits_applied": edits,
                               "diff": _diff_profiles(before, after)}
    finally:
        cleanup = await _cleanup_scratch(scratch_id, orig_id)
        # The caller is back on their own graph with their own styling, so the record that
        # described it is valid again. Restored last, after every /workspace/ call has run.
        LEDGER.entries = ledger_entries

    outcome["cleanup"] = cleanup
    return fmt(outcome)


@_tool(name="gephi_compare_nodes")
async def gephi_compare_nodes(id_a: str, id_b: str, metric: str) -> str:
    """Compare two nodes on one metric — a deterministic answer to "which is more X?".

    Reads both nodes and reports each one's value for `metric` and which is
    higher. Turns a claim like "she is more central than he is" into a single
    checkable call instead of two reads plus manual arithmetic.

    metric: a node column that already exists — either a computed statistic in
    the node's attributes ("Betweenness Centrality", "Degree", "pageranks",
    "frequency") or a built-in field ("size"). If the column is absent, this
    errors and tells you to compute the relevant statistic first (e.g. run the
    betweenness statistic before comparing betweenness). Attributes are checked
    before top-level fields.

    Returns {success, metric, a, b, higher, difference}. `higher` is the id of
    the larger value, or null on a tie. `difference` is abs(a - b).
    """
    def _value(node: dict) -> Any:
        attrs = node.get("attributes") or {}
        if metric in attrs:
            return attrs[metric]
        if metric in node:
            return node[metric]
        return None

    ra = await gephi.request("GET", f"/graph/node/get/{id_a}")
    if not ra.get("success", True):
        return fmt(ra)
    rb = await gephi.request("GET", f"/graph/node/get/{id_b}")
    if not rb.get("success", True):
        return fmt(rb)

    va = _value(ra.get("node", {}))
    vb = _value(rb.get("node", {}))
    missing = [nid for nid, v in ((id_a, va), (id_b, vb)) if v is None]
    if missing:
        return fmt({"success": False,
                    "error": f"metric {metric!r} not found on node(s) {missing} — "
                             f"compute that statistic first, then compare."})
    if not isinstance(va, (int, float)) or not isinstance(vb, (int, float)):
        return fmt({"success": False,
                    "error": f"metric {metric!r} is not numeric (got {va!r}, {vb!r})."})

    higher = None if va == vb else (id_a if va > vb else id_b)
    return fmt({"success": True, "metric": metric, "a": va, "b": vb,
                "higher": higher, "difference": abs(va - vb)})


_VERDICTS = {"confirmed": "confirmed", "refuted": "refuted", "cant_tell": "cannot tell"}


@_tool(name="gephi_claim_record")
async def gephi_claim_record(claim: str, classification: str, verdict: str,
                             metric: str | None = None,
                             nodes: list[str] | None = None,
                             values: dict[str, float] | None = None,
                             numbers: dict[str, Any] | None = None,
                             caveat: str = "",
                             export: str | None = None) -> CallToolResult:
    """Record a verified claim with its receipts, checked against the live graph.

    Call this once a claim has been measured and a verdict reached, passing the
    node ids and numbers the verdict rests on. The tool re-reads every cited node
    from Gephi and compares each cited value with the live value of `metric`, so
    the record cannot restate numbers the graph does not hold. The result is a
    structured record a person can read, cite, or hand to a reviewer: claim,
    classification, metric, verdict, the evidence nodes with their labels and
    live values, any other cited numbers, the checks, and a caption sentence.

    classification: comparison | connectivity | centrality | robustness | grouping.
    verdict: confirmed | refuted | cant_tell. The tool never changes the verdict;
    `verified` reports only whether the receipts matched the graph. A cited node
    that does not exist, or a cited value that differs from the live value, makes
    `verified` false and is listed under `checks`.
    values: {node_id: cited value of `metric`}. numbers: other cited figures
    (a within-group edge share, a component count) kept as given.
    export: optional path; writes the record as JSON for a methods appendix.
    Writes nothing to the graph; the only side effect is that file, when asked.
    """
    if verdict not in _VERDICTS:
        return CallToolResult(
            content=[TextContent(type="text", text=fmt({
                "success": False,
                "error": f"verdict must be one of {sorted(_VERDICTS)}, got {verdict!r}"}))],
            is_error=True)
    nodes = nodes or []
    values = values or {}
    evidence = []
    missing: list[str] = []
    mismatches: list[dict[str, Any]] = []
    for nid in nodes:
        r = await gephi.request("GET", f"/graph/node/get/{nid}")
        if not r.get("success", True) or "node" not in r:
            missing.append(nid)
            continue
        node = r["node"]
        attrs = node.get("attributes") or {}
        live = None
        if metric is not None:
            live = attrs.get(metric, node.get(metric))
        entry: dict[str, Any] = {"id": nid, "label": node.get("label", nid)}
        if metric is not None:
            entry["value"] = live
        if nid in values:
            cited = values[nid]
            entry["cited"] = cited
            if not _close(cited, live):
                mismatches.append({"id": nid, "cited": cited, "live": live})
        evidence.append(entry)
    for nid in values:
        if nid not in nodes:
            missing.append(nid)
    verified = not missing and not mismatches
    record: dict[str, Any] = {
        "claim": claim, "classification": classification, "metric": metric,
        "verdict": verdict, "verified": verified,
        "evidence": {"nodes": evidence},
        "numbers": numbers or {},
        "caveat": caveat,
        "checks": {"nodes_checked": len(nodes) - len([m for m in missing if m in nodes]),
                   "nodes_missing": missing, "value_mismatches": mismatches},
    }
    record["caption"] = _claim_caption(record)
    if export:
        with open(os.path.expanduser(export), "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2)
        record["export"] = export
    text = record["caption"]
    if not verified:
        text += (" Receipts did not match the graph:"
                 + (f" missing nodes {missing};" if missing else "")
                 + (f" value mismatches {mismatches};" if mismatches else ""))
    return CallToolResult(content=[TextContent(type="text", text=text)],
                          structured_content=record)


def _close(a: Any, b: Any) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(float(a), float(b), rel_tol=1e-6, abs_tol=1e-9)
    return a == b


def _claim_caption(rec: dict[str, Any]) -> str:
    """One sentence a person can paste: claim, verdict, the numbers, the caveat."""
    parts = [f"Claim: {rec['claim'].rstrip('.')}", f"Verdict: {_VERDICTS[rec['verdict']]}"]
    if rec["metric"] and rec["evidence"]["nodes"]:
        vals = ", ".join(f"{n['label']} = {n.get('value')}" for n in rec["evidence"]["nodes"])
        parts.append(f"{rec['metric']}: {vals}")
    if rec["numbers"]:
        parts.append(", ".join(f"{k} = {v}" for k, v in rec["numbers"].items()))
    if not rec["verified"]:
        parts.append("receipts did not match the live graph")
    if rec["caveat"]:
        parts.append(f"Caveat: {rec['caveat'].rstrip('.')}")
    return ". ".join(parts) + "."


# ─── Import ──────────────────────────────────────────────────

@_tool(name="gephi_import_gexf")
async def gephi_import_gexf(file: str) -> str:
    """Import a graph from a GEXF file. Merged with any existing graph."""
    return fmt(await gephi.request("POST", "/import/gexf", json_data={"file": file}))

@_tool(name="gephi_import_graphml")
async def gephi_import_graphml(file: str) -> str:
    """Import a graph from a GraphML file."""
    return fmt(await gephi.request("POST", "/import/graphml", json_data={"file": file}))

@_tool(name="gephi_import_csv")
async def gephi_import_csv(file: str) -> str:
    """Import a graph from a CSV file."""
    return fmt(await gephi.request("POST", "/import/csv", json_data={"file": file}))

@_tool(name="gephi_import_file")
async def gephi_import_file(file: str, max_node_size: float | None = None) -> str:
    """Import a graph from any supported format (GEXF, GraphML, GML, CSV, DOT, Pajek, ...).

    Auto-detected by extension. Imported node sizes are capped at 30 so a viz:size
    from the source can't render nodes enormous; re-size with gephi_size_by_ranking.

    No file path? (e.g. the user attached a spreadsheet/CSV/JSON/RDF in chat):
    parse the content yourself and build the graph with gephi_add_nodes +
    gephi_add_edges in batches — that path handles ANY format you can read.
    Common shapes: edge list (source,target[,weight] rows) -> add directly;
    adjacency matrix -> one edge per nonzero cell; two-column co-occurrence
    (person,event) -> bipartite, or project it (edge when two rows share a
    value); rows-as-entities with attributes -> nodes with attributes, then
    edges from a relationship column or attribute similarity; RDF triples ->
    subject/object as nodes, predicate as edge label.

    `max_node_size` caps imported node sizes. Leave it unset and the file's own sizes are
    kept, so an import followed by an export round-trips unchanged. Set it (30 is a sensible
    value) when a GEXF carries `viz:size` values large enough that a few nodes cover the
    whole map; the reply then reports how many nodes were changed.
    """
    body: dict[str, Any] = {"file": file}
    if max_node_size is not None:
        body["max_node_size"] = max_node_size
    return fmt(await gephi.request("POST", "/import/file", json_data=body))


# ==================== Main Entry Point ====================

if __name__ == "__main__":
    mcp.run()
