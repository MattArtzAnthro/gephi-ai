---
name: gephi
description: |
  When the user wants to analyze, visualize, or explore network graphs using Gephi,
  this skill provides workflows and best practices for the 76 Gephi MCP tools.
  Triggered when the user mentions Gephi, network analysis, graph visualization,
  community detection, social network analysis, or graph metrics.
compatibility: Requires Gephi Desktop 0.11.1+ running with the Gephi MCP Plugin v1.0.0-beta installed, and the gephi-mcp MCP server connected.
metadata:
  author: Matt Artz
  version: "1.4"
---

# Gephi Network Analysis Skill

You have access to 76 MCP tools (prefixed `mcp__gephi-mcp__`) for controlling Gephi Desktop. Use them to build, analyze, style, and export network graphs.

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
- **`sync: true` in `gephi_run_layout`** — makes the call block until layout finishes. Always use this so Noverlap and Label Adjust don't start on a still-moving graph.

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
`gephi_create_project`, `gephi_open_project`, `gephi_save_project`, `gephi_get_project_info`, `gephi_new_workspace`, `gephi_list_workspaces`, `gephi_switch_workspace`, `gephi_delete_workspace`, `gephi_duplicate_workspace`, `gephi_rename_workspace`

### Graph Construction
`gephi_add_node`/`gephi_add_nodes`, `gephi_add_edge`/`gephi_add_edges`, `gephi_remove_node`/`gephi_bulk_remove_nodes`, `gephi_remove_edge`, `gephi_clear_graph`, `gephi_set_node_label`/`gephi_set_edge_label`, `gephi_set_node_position`/`gephi_batch_set_positions`, `gephi_set_edge_weight`, `gephi_query_nodes`, `gephi_get_node`, `gephi_query_edges`

### Statistics (run before styling)
- `gephi_compute_modularity` → creates `modularity_class`
- `gephi_compute_degree` → creates `degree`, `indegree`, `outdegree`
- `gephi_compute_betweenness` → creates `betweenesscentrality`, `closnesscentrality`, `eccentricity`, `harmonicclosnesscentrality` (0.11.1+)
- `gephi_compute_pagerank` → creates `pageranks`
- `gephi_compute_eigenvector` → creates `eigencentrality`
- `gephi_compute_connected_components` → creates `componentnumber`
- `gephi_compute_clustering_coefficient` → creates `clustering`
- `gephi_compute_avg_path_length` → avg path length, diameter
- `gephi_compute_hits` → creates `authority`, `hub` (lowercase column names)

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

New in 0.11.1: `"node.label.avoidOverlap": true` prevents label collisions; `"node.label.overlapGridSize": 50` controls grid granularity. Both can be combined with existing label settings.

### Layout
- ForceAtlas 2 for most graphs: `{"scalingRatio": 15, "linLogMode": true, "gravity": 1.0, "sync": true}`, 1000-1500 iterations — scale `scalingRatio` up with node count (see Beautiful Graph Recipe table)
- Follow with Noverlap: `{"algorithm": "Noverlap", "iterations": 500, "properties": {"margin": 5.0}, "sync": true}`
- Follow with Label Adjust (500 iterations, sync: true) if labels are enabled
- **`barnesHutOptimize` is wrong** — the correct key is `barnesHutOptimization`

## Key Gotchas

- **Filters are destructive** — they permanently remove nodes/edges. Save project first.
- **High gravity (>3) compresses nodes** into a ball. Fix: run Random Layout (1 iteration), then re-run ForceAtlas 2.
- **Workspace switching can deadlock** — if API hangs after workspace switch, Gephi needs restart.
- **Press Ctrl+Shift+H in Gephi** to center the view on the graph after API operations — the API modifies data but doesn't move the viewport camera.

## Beautiful Graph Recipe

Bad-looking graphs almost always come from one of three problems: layout parameters ignored (the most common), no overlap prevention, or wrong edge/label settings. Follow this recipe for publication-quality output.

### scalingRatio by graph size

`scalingRatio` must be calibrated to node count — too high and communities fly to the canvas edges:

| Nodes | scalingRatio | barnesHutOptimization | distributedAttraction |
|-------|-------------|----------------------|----------------------|
| ≤ 50  | 10–20       | false                | false                |
| 50–300 | 30–80      | true                 | false                |
| 300–1000 | 100–150  | true                 | true                 |
| 1000+ | 200–300     | true                 | true                 |

### Phase 1 — Community layout (1000–1500 iterations)
```json
{
  "algorithm": "ForceAtlas 2",
  "iterations": 1200,
  "sync": true,
  "properties": {
    "scalingRatio": 15,
    "linLogMode": true,
    "gravity": 1.0,
    "barnesHutOptimization": false
  }
}
```
- `linLogMode: true` is the single most important setting — it makes communities pull together as tight clusters with open space between them
- `scalingRatio` default (10) is fine for small graphs; scale up with node count per the table above
- `distributedAttraction` (Dissuade Hubs) helps large graphs but pushes communities apart on small ones — avoid for < 300 nodes
- `barnesHutOptimization` is only needed for large graphs (300+); skip it for small graphs to avoid approximation artifacts
- Always use `sync: true` so Phase 2 doesn't start on a still-moving graph

### Phase 2 — Overlap prevention (200 iterations)
```json
{
  "algorithm": "ForceAtlas 2",
  "iterations": 200,
  "sync": true,
  "properties": {
    "scalingRatio": 15,
    "linLogMode": true,
    "gravity": 1.0,
    "adjustSizes": true
  }
}
```
- `adjustSizes: true` (Prevent Overlap) runs FA2 while accounting for node sizes — nodes physically push each other apart
- Keep the same `scalingRatio` as Phase 1 so community structure is preserved

### Phase 3 — Fine-grained separation
```json
{"algorithm": "Noverlap", "iterations": 300, "sync": true, "properties": {"margin": 3.0}}
```

### Phase 4 — Label positioning (only if showing labels)
```json
{"algorithm": "Label Adjust", "iterations": 300, "sync": true}
```

### Preview settings for community graphs
```json
{
  "node.label.show": false,
  "edge.color": "source",
  "edge.opacity": 20,
  "edge.curved": true,
  "edge.thickness": 1.5,
  "node.opacity": 100,
  "node.border.width": 0.5,
  "node.label.avoidOverlap": true,
  "arrow.size": 0
}
```
- `edge.color: "source"` creates the watercolor halo effect where edges fade into their source community color
- `edge.opacity: 20` keeps edges from overwhelming the community structure
- `node.label.avoidOverlap: true` (0.11.1+) prevents label collisions without needing Label Adjust

### Troubleshooting
- **Nodes in a ball**: gravity is too high OR layout parameters weren't applied (check you're using correct key names). Fix: run Random Layout (1 iteration), then re-run Phase 1.
- **Communities not separating**: `linLogMode` is off, or `scalingRatio` is too low. Verify properties are accepted.
- **Nodes still overlapping after Phase 2**: run Noverlap with higher margin (5–8).
- **Labels colliding**: run Label Adjust, or enable `node.label.avoidOverlap: true` in preview settings.

For detailed tool parameters, see [references/tool-reference.md](references/tool-reference.md).
For layout algorithm details, see [references/layout-guide.md](references/layout-guide.md).
For statistics interpretation, see [references/statistics-guide.md](references/statistics-guide.md).
