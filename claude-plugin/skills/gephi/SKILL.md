---
name: gephi
description: |
  When the user wants to analyze, visualize, or explore network graphs using Gephi,
  this skill provides workflows and best practices for the 73 Gephi MCP tools.
  Triggered when the user mentions Gephi, network analysis, graph visualization,
  community detection, social network analysis, or graph metrics.
compatibility: Requires Gephi Desktop 0.10+ running with the Gephi MCP Plugin installed, and the gephi-mcp MCP server connected.
metadata:
  author: Matt Artz
  version: "1.1"
---

# Gephi Network Analysis Skill

You have access to 73 MCP tools (prefixed `mcp__gephi-mcp__`) for controlling Gephi Desktop. Use them to build, analyze, style, and export network graphs.

## Communication

**Always narrate what you're doing.** Before each major tool call, tell the user what's about to happen in a short sentence (e.g., "Computing modularity...", "Running ForceAtlas 2 layout..."). This prevents the user from wondering what's happening during long operations.

## Critical Things To Know

These prevent the most common failures:

- **Layout algorithm name**: Use `"ForceAtlas 2"` (with space and capitals), not `"forceatlas2"`
- **Export file parameter**: Export tools use `file` as the key, not `path`
- **Never set `node.label.font` via preview settings** — this corrupts Gephi's preview model, causing all subsequent exports to fail with a Font casting error. Use Gephi's default font.
- **Run statistics before styling** — `modularity_class` and `degree` columns don't exist until you compute them
- **`node.label.proportinalSize`** — note the typo (missing 'o'). This is Gephi's actual property name.
- **Always call `project/new` before importing** — stale workspace state from prior operations causes edge rendering to silently fail. A fresh project prevents this.
- **GEXF viz:size makes nodes huge** — imported GEXF files with `viz:size` attributes can produce nodes with size 60-100, which cover all edges. Always run `size_by_ranking` immediately after import to resize nodes to a reasonable range (e.g., min 4, max 20).
- **Never restyle after layout** — calling `color_by_partition` or `size_by_ranking` after a layout has run can corrupt the preview edge cache, causing all edges to vanish from exports. The correct order is always: stats → style → layout → export.
- **Filters break edge rendering** — `remove_isolates`, `giant_component`, and `filter_by_degree` can corrupt the preview model so edges no longer render. If you need to filter, do it externally (Python/networkx) and reimport the filtered GEXF.
- **NEVER set `edge.color` via preview settings** — setting `edge.color` to ANY value (`"source"`, `"original"`, `"#hex"`) permanently corrupts the preview edge renderer, causing ALL edges to vanish from exports. This corruption is irreversible — you must create a new project and reimport. To get community-colored edges, pre-color them in the GEXF file using `<viz:color>` on each `<edge>` element before importing. Gephi will use these colors by default without needing the `edge.color` preview setting.

## Standard Workflow

**This order is strict — do not restyle after layout or edges will vanish:**

1. **Health check** — `gephi_health_check` (stop if Gephi isn't running)
2. **Fresh project** — always call `gephi_create_project` (or `project/new`) before importing
3. **Import** — `gephi_import_file` or build with `gephi_add_nodes`/`gephi_add_edges`
4. **Resize immediately** — if importing GEXF with viz:size, call `gephi_size_by_ranking` right after import to prevent oversized nodes hiding edges
5. **Statistics** — compute degree, modularity, etc.
6. **Style** — color by partition, size by ranking (BEFORE layout)
7. **Layout** — `gephi_run_layout` with `"ForceAtlas 2"`, then optionally `"Noverlap"`
8. **Preview** — `gephi_set_preview_settings` (this is OK after layout — only appearance operations break edges)
9. **Export** — `gephi_export_png` (use `file` param), `gephi_export_svg`, etc.

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
Clean (no labels): `{"node.label.show": false, "edge.opacity": 20, "edge.curved": true, "edge.color": "source", "node.opacity": 100, "node.border.width": 0.5, "arrow.size": 0}`

Labeled: `{"node.label.show": true, "node.label.proportinalSize": false, "node.label.outline.size": 3, "node.label.outline.opacity": 90, "edge.opacity": 15}`

**Do NOT include `node.label.font`** — it corrupts the preview model.

### Layout
- ForceAtlas 2 for most graphs: `{"scalingRatio": 200, "linLogMode": true, "gravity": 1.0, "barnesHutOptimize": true}`, 1000-1500 iterations
- Size nodes AFTER layout to avoid spacing artifacts

## Key Gotchas

- **Filters are destructive** — they permanently remove nodes/edges. Save project first.
- **High gravity (>3) compresses nodes** into a ball. Fix: run Random Layout (1 iteration), then re-run ForceAtlas 2.
- **Workspace switching can deadlock** — if API hangs after workspace switch, Gephi needs restart.
- **Export at 4K**: width 3840, height 2160. Always export clean + labeled versions.

For detailed tool parameters, see [references/tool-reference.md](references/tool-reference.md).
For layout algorithm details, see [references/layout-guide.md](references/layout-guide.md).
For statistics interpretation, see [references/statistics-guide.md](references/statistics-guide.md).
