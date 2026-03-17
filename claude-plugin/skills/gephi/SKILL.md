---
name: gephi
description: |
  When the user wants to analyze, visualize, or explore network graphs using Gephi,
  this skill provides workflows and best practices for the 73 Gephi MCP tools.
  Triggered when the user mentions Gephi, network analysis, graph visualization,
  community detection, social network analysis, or graph metrics.
compatibility: Requires Gephi Desktop 0.10+ running with the Gephi MCP Plugin v1.1+ installed, and the gephi-mcp MCP server connected.
metadata:
  author: Matt Artz
  version: "1.2"
---

# Gephi Network Analysis Skill

You have access to 73 MCP tools (prefixed `mcp__gephi-mcp__`) for controlling Gephi Desktop. Use them to build, analyze, style, and export network graphs.

## Communication

**Always narrate what you're doing.** Before each major tool call, tell the user what's about to happen in a short sentence (e.g., "Computing modularity...", "Running ForceAtlas 2 layout..."). This prevents the user from wondering what's happening during long operations.

## Critical Things To Know

- **Layout algorithm name**: Use `"ForceAtlas 2"` (with space and capitals), not `"forceatlas2"`
- **Export file parameter**: Export tools use `file` as the key, not `path`
- **Run statistics before styling** — `modularity_class` and `degree` columns don't exist until you compute them
- **`node.label.proportinalSize`** — note the typo (missing 'o'). This is Gephi's actual property name.
- **Always call `project/new` before importing** — stale workspace state from prior operations can cause issues. A fresh project prevents this.
- **`edge.color: "source"` colors edges individually** — the plugin automatically colors each edge to match its source node's color and sets mode to ORIGINAL. This is safe and produces the watercolor halo effect.
- **`node.label.font` supports multi-word names** — e.g., `"Courier New 12 Bold"`. The plugin parses everything before the first digit as the font name.
- **Imported node sizes are auto-capped at 30** — GEXF files with large `viz:size` values are automatically capped during import to prevent oversized nodes from hiding edges.
- **Filters refresh the preview automatically** — `remove_isolates`, `giant_component`, `filter_by_degree` now properly refresh the preview model after modifying the graph.

## Standard Workflow

1. **Health check** — `gephi_health_check` (stop if Gephi isn't running)
2. **Fresh project** — call `gephi_create_project` before importing
3. **Import** — `gephi_import_file` or build with `gephi_add_nodes`/`gephi_add_edges`
4. **Statistics** — compute degree, modularity, etc.
5. **Style** — color by partition, size by ranking
6. **Layout** — `gephi_run_layout` with `"ForceAtlas 2"`, then optionally `"Noverlap"` and `"Label Adjust"`
7. **Preview** — `gephi_set_preview_settings` for export appearance
8. **Export** — `gephi_export_png` (use `file` param), `gephi_export_svg`, etc.

## Tool Quick Reference

### Project & Workspace
`gephi_create_project`, `gephi_open_project`, `gephi_save_project`, `gephi_get_project_info`, `gephi_new_workspace`, `gephi_list_workspaces`, `gephi_switch_workspace`, `gephi_delete_workspace`

### Graph Construction
`gephi_add_node`/`gephi_add_nodes`, `gephi_add_edge`/`gephi_add_edges`, `gephi_remove_node`/`gephi_bulk_remove_nodes`, `gephi_remove_edge`, `gephi_clear_graph`, `gephi_set_node_label`/`gephi_set_edge_label`, `gephi_set_node_position`/`gephi_batch_set_positions`, `gephi_set_edge_weight`, `gephi_query_nodes`/`gephi_query_edges`

### Statistics (run before styling)
- `gephi_compute_modularity` → creates `modularity_class`
- `gephi_compute_degree` → creates `degree`, `indegree`, `outdegree`
- `gephi_compute_betweenness` → creates `betweenesscentrality`, closeness, eccentricity
- `gephi_compute_pagerank` → creates `pageranks`
- `gephi_compute_eigenvector` → creates `eigencentrality`
- `gephi_compute_connected_components` → creates `componentnumber`
- `gephi_compute_clustering_coefficient` → creates `clustering`
- `gephi_compute_avg_path_length` → avg path length, diameter
- `gephi_compute_hits` → creates `Authority`, `Hub`

### Appearance
`gephi_color_by_partition`, `gephi_color_by_ranking`, `gephi_size_by_ranking`, `gephi_set_node_color`/`gephi_set_node_size`, `gephi_set_edge_color`, `gephi_edge_thickness_by_weight`, `gephi_batch_set_node_colors`, `gephi_reset_appearance`

### Layout
`gephi_run_layout` (use `"ForceAtlas 2"`, `"Yifan Hu"`, `"Fruchterman Reingold"`, `"Circular"`, `"Random Layout"`), `gephi_stop_layout`, `gephi_get_layout_status`, `gephi_get_available_layouts`, `gephi_get_layout_properties`/`gephi_set_layout_properties`

### Filtering
`gephi_filter_by_degree`, `gephi_filter_by_edge_weight`, `gephi_remove_isolates`, `gephi_extract_ego_network`, `gephi_extract_giant_component`, `gephi_reset_filters`

### Preview & Export
`gephi_get_preview_settings`/`gephi_set_preview_settings`, `gephi_export_png`/`gephi_export_pdf`/`gephi_export_svg` (use `file` param), `gephi_export_gexf`/`gephi_export_graphml`/`gephi_export_csv`

### Import
`gephi_import_file`, `gephi_import_gexf`/`gephi_import_graphml`/`gephi_import_csv`

## Styling Defaults

### Pastel Community Colors
Always override default Gephi colors with this palette for `gephi_color_by_partition`:
```json
{"0": [212,222,99], "1": [227,185,216], "2": [89,238,200], "3": [154,226,255], "4": [255,171,125], "5": [255,173,203], "6": [255,220,130], "7": [190,170,230]}
```

### Publication Export Settings
Clean (no labels):
```json
{"node.label.show": false, "edge.opacity": 25, "edge.curved": true, "edge.color": "source", "edge.thickness": 2.0, "node.opacity": 100, "node.border.width": 0.3, "arrow.size": 0}
```

Labeled:
```json
{"node.label.show": true, "node.label.proportinalSize": false, "node.label.font": "Arial 10 Plain", "node.label.outline.size": 4, "node.label.outline.opacity": 95, "edge.opacity": 15}
```

### Layout
- ForceAtlas 2 for most graphs: `{"scalingRatio": 200, "linLogMode": true, "gravity": 1.0, "barnesHutOptimize": true}`, 1000-1500 iterations
- Follow with Noverlap (500 iterations, margin 5.0) to push overlapping nodes apart
- Follow with Label Adjust (500 iterations) if labels are enabled

## Key Gotchas

- **Filters are destructive** — they permanently remove nodes/edges. Save project first.
- **High gravity (>3) compresses nodes** into a ball. Fix: run Random Layout (1 iteration), then re-run ForceAtlas 2.
- **Workspace switching can deadlock** — if API hangs after workspace switch, Gephi needs restart.
- **Press Ctrl+Shift+H in Gephi** to center the view on the graph after API operations — the API modifies data but doesn't move the viewport camera.

For detailed tool parameters, see [references/tool-reference.md](references/tool-reference.md).
For layout algorithm details, see [references/layout-guide.md](references/layout-guide.md).
For statistics interpretation, see [references/statistics-guide.md](references/statistics-guide.md).
