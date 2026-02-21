---
name: gephi
description: |
  When the user wants to analyze, visualize, or explore network graphs using Gephi,
  this skill provides workflows and best practices for the 73 Gephi MCP tools.
  Triggered when the user mentions Gephi, network analysis, graph visualization,
  community detection, social network analysis, or graph metrics.
  Requires Gephi Desktop 0.10+ running with the Gephi MCP Plugin installed, and the gephi-mcp MCP server connected.
---

# Gephi Network Analysis Skill

You have access to 73 MCP tools for controlling Gephi Desktop. Use them to build, analyze, style, and export network graphs for researchers.

## Standard Workflow

Follow this sequence for any network analysis task:

1. **Create/Open Project** - `gephi_create_project` or `gephi_import_file`
2. **Build or Import Graph** - `gephi_add_nodes`/`gephi_add_edges` or `gephi_import_gexf`/`gephi_import_graphml`
3. **Compute Statistics** - Run relevant metrics (modularity, centrality, etc.)
4. **Apply Layout** - `gephi_run_layout` to spatialize the graph
5. **Style by Attributes** - Color/size nodes by computed metrics
6. **Filter** (optional) - Remove isolates, extract giant component, filter by degree
7. **Configure Preview** - `gephi_set_preview_settings` for export appearance
8. **Export** - `gephi_export_png`, `gephi_export_pdf`, `gephi_export_gexf`, etc.

Always check `gephi_health_check` first to confirm Gephi is running.

## Tool Categories Quick Reference

### Project & Workspace
- `gephi_create_project` - New empty project
- `gephi_open_project` - Open .gephi file
- `gephi_save_project` - Save to .gephi file
- `gephi_get_project_info` - Node/edge counts, graph type
- `gephi_new_workspace` / `gephi_list_workspaces` / `gephi_switch_workspace` / `gephi_delete_workspace`

### Graph Construction
- `gephi_add_node` / `gephi_add_nodes` - Add node(s) with ID, label, attributes
- `gephi_add_edge` / `gephi_add_edges` - Add edge(s) with source, target, weight
- `gephi_remove_node` / `gephi_bulk_remove_nodes` - Remove node(s)
- `gephi_remove_edge` - Remove an edge
- `gephi_clear_graph` - Remove all nodes and edges
- `gephi_set_node_label` / `gephi_set_edge_label` - Set labels
- `gephi_set_node_position` / `gephi_batch_set_positions` - Set coordinates
- `gephi_set_edge_weight` - Set edge weight
- `gephi_query_nodes` / `gephi_query_edges` - Query with pagination

### Statistics (run before styling)
- `gephi_compute_modularity` - Community detection (creates `modularity_class`)
- `gephi_compute_degree` - Degree distribution (creates `degree`, `indegree`, `outdegree`)
- `gephi_compute_betweenness` - Betweenness/closeness centrality, diameter
- `gephi_compute_pagerank` - PageRank importance (creates `pageranks`)
- `gephi_compute_eigenvector` - Eigenvector centrality (creates `eigencentrality`)
- `gephi_compute_connected_components` - Connected components (creates `componentnumber`)
- `gephi_compute_clustering_coefficient` - Local clustering (creates `clustering`)
- `gephi_compute_avg_path_length` - Average path length, diameter
- `gephi_compute_hits` - Hub/authority scores (creates `Authority`, `Hub`)

### Appearance
- `gephi_color_by_partition` - Color by categorical attribute (e.g., `modularity_class`)
- `gephi_color_by_ranking` - Color gradient by numeric attribute (e.g., `degree`)
- `gephi_size_by_ranking` - Size by numeric attribute (e.g., `pageranks`)
- `gephi_set_node_color` / `gephi_set_node_size` - Individual node styling
- `gephi_set_edge_color` - Individual edge styling
- `gephi_edge_thickness_by_weight` - Scale edge thickness by weight
- `gephi_batch_set_node_colors` - Batch color multiple nodes
- `gephi_reset_appearance` - Reset all to defaults

### Layout
- `gephi_run_layout` - Run algorithm (forceatlas2, yifanhu, fruchterman, circular, random)
- `gephi_stop_layout` - Stop running layout
- `gephi_get_layout_status` - Check if layout is running
- `gephi_get_available_layouts` - List all layout algorithms
- `gephi_get_layout_properties` / `gephi_set_layout_properties` - Get/set layout parameters

### Filtering
- `gephi_filter_by_degree` - Remove nodes outside degree range
- `gephi_filter_by_edge_weight` - Remove edges outside weight range
- `gephi_remove_isolates` - Remove degree-0 nodes
- `gephi_extract_ego_network` - Keep only a node's neighborhood
- `gephi_extract_giant_component` - Keep only the largest connected component
- `gephi_reset_filters` - Restore full graph view

### Attributes
- `gephi_get_columns` - List all columns in node/edge table
- `gephi_add_column` - Add a new column
- `gephi_set_node_attributes` / `gephi_batch_set_node_attributes` - Set node attributes
- `gephi_set_edge_attributes` - Set edge attributes

### Preview & Export
- `gephi_get_preview_settings` / `gephi_set_preview_settings` - Control rendering
- `gephi_export_png` / `gephi_export_pdf` / `gephi_export_svg` - Image exports
- `gephi_export_gexf` / `gephi_export_graphml` / `gephi_export_csv` - Data exports

### Import
- `gephi_import_file` - Auto-detect format import
- `gephi_import_gexf` / `gephi_import_graphml` / `gephi_import_csv` - Format-specific

## Common Researcher Workflows

### Community Detection & Visualization
1. Import or build graph
2. `gephi_compute_modularity` with resolution 1.0
3. `gephi_run_layout` with "forceatlas2" (500-1000 iterations)
4. `gephi_color_by_partition` with column "modularity_class"
5. `gephi_size_by_ranking` with column "degree" (min_size: 5, max_size: 40)
6. `gephi_export_png`

### Centrality Analysis (Find Important Nodes)
1. Import or build graph
2. `gephi_compute_betweenness` (calculates betweenness, closeness, eccentricity)
3. `gephi_compute_pagerank`
4. `gephi_run_layout` with "forceatlas2"
5. `gephi_color_by_ranking` with column "betweenesscentrality" (light to dark)
6. `gephi_size_by_ranking` with column "pageranks"
7. `gephi_query_nodes` to find top-ranked nodes
8. `gephi_export_png`

### Structural Analysis
1. `gephi_compute_connected_components`
2. `gephi_compute_avg_path_length`
3. `gephi_compute_clustering_coefficient`
4. `gephi_get_graph_stats` for density, average degree
5. `gephi_extract_giant_component` if multiple components exist
6. Report results to user

### Publication-Ready Export
1. Complete analysis and styling
2. `gephi_set_preview_settings`:
   - Background: white (`"node.label.show": true`)
   - Edge opacity reduced for clarity
   - Node labels visible for key nodes
3. `gephi_export_png` at high resolution (width: 3840, height: 2160)
4. `gephi_export_pdf` for vector output
5. `gephi_export_svg` for editable vector graphics

## Layout Selection Guide

| Algorithm | Best For | Nodes | Speed |
|-----------|----------|-------|-------|
| ForceAtlas2 | Most networks, community structure | <50k | Medium |
| Yifan Hu | Large graphs, fast overview | >10k | Fast |
| Fruchterman-Reingold | Small networks, even spacing | <5k | Slow |
| Circular | Ring visualization, ordered | Any | Instant |
| Random | Reset positions | Any | Instant |

**ForceAtlas2 tips**: Start with 500 iterations. Use `gephi_set_layout_properties` to tune:
- `scalingRatio` (higher = more spread out)
- `gravity` (higher = more compact)
- `linLogMode` (true for community structure emphasis)
- `barnesHutOptimize` (true for large graphs)

## Coloring Strategy

- **Partition coloring** for categorical data: modularity_class, type, category, componentnumber
  - Always override with pastel palette (see Visualization Design Guidelines above)
  - Use `gephi_color_by_partition` with custom `colors` map for each community value
- **Ranking coloring** for numeric data: degree, pageranks, betweenesscentrality, eigencentrality
  - Good gradient: light blue (200,220,255) to dark red (180,0,0) for centrality
  - Good gradient: light yellow (255,255,200) to dark red (180,0,0) for degree
- **Pre-computed colors**: If node data includes r/g/b attributes, apply them directly via `gephi_batch_set_node_colors`

## Visualization Design Guidelines

Follow these principles to produce publication-quality network visualizations.

### Color Palette: Use Soft Pastels

Default Gephi partition colors are harsh. Always override with a curated pastel palette:

| Community | Color Name | RGB | Hex |
|-----------|-----------|-----|-----|
| 0 | Soft Lime | (212, 222, 99) | #D4DE63 |
| 1 | Dusty Mauve | (227, 185, 216) | #E3B9D8 |
| 2 | Mint Teal | (89, 238, 200) | #59EEC8 |
| 3 | Sky Blue | (154, 226, 255) | #9AE2FF |
| 4 | Warm Peach | (255, 171, 125) | #FFAB7D |
| 5 | Rose Pink | (255, 173, 203) | #FFADCB |
| 6 | Soft Gold | (255, 220, 130) | #FFDC82 |
| 7 | Lavender | (190, 170, 230) | #BEAAE6 |

Apply via `gephi_color_by_partition` with custom colors, or use `gephi_batch_set_node_colors` for precise control.

### Edge Styling: The Watercolor Effect

The key to beautiful network visualizations is edge treatment. Thousands of overlapping semi-transparent edges create an organic, cloud-like halo around each community.

**Critical settings** via `gephi_set_preview_settings`:
```
edge.opacity: 15-30        (lower = more ethereal; 20 is ideal for 1000+ edges)
edge.curved: true           (curved edges look more organic)
arrow.size: 0               (hide arrows even on directed graphs for cleaner look)
edge.rescale-weight: true   (vary thickness by weight for visual depth)
edge.rescale-weight.min: 0.1
edge.rescale-weight.max: 2.0
```

**Edge color by source node** (the key to community-colored halos):
Two approaches, both work:
1. **Via preview setting**: `gephi_set_preview_settings({"edge.color": "source"})` — sets all edges to render using their source node's color. This is the simplest approach.
2. **Per-edge coloring**: Use `gephi_set_edge_color` on each edge to set explicit colors (query nodes for colors, then apply to edges). This gives more control and lets you blend or customize individual edge colors.

**Opacity guidelines by edge count:**
- < 100 edges: opacity 60-80
- 100-500 edges: opacity 30-50
- 500-2000 edges: opacity 15-30
- 2000+ edges: opacity 5-15

### Node Styling

- **Size by a continuous metric** (degree, pagerank, weight) — use `gephi_size_by_ranking`
- **Keep size range reasonable**: `min_size: 3, max_size: 25` for 100+ nodes; `min_size: 5, max_size: 40` for < 50 nodes
- **Node opacity: 100%** — nodes should be solid against the soft edge clouds
- **Thin borders**: `node.border.width: 0.5-1.0`

### Label Strategy

- **Labels OFF for the main export** — the cleanest visualizations show only nodes and edges; color clusters speak for themselves
- **Create a second export WITH labels** for reference/annotation
- When labels are on:
  - `node.label.proportinalSize: false` — use fixed font size for readability
  - `node.label.font: "Arial 8 Plain"` — small, clean font
  - `node.label.outline.size: 2-3` — white outline for contrast against edges
  - `node.label.outline.opacity: 90`

### Layout Strategy (3-Phase)

**Phase 1 — Spatialization:**
```
ForceAtlas 2: 1000-2000 iterations
  scalingRatio: 100-300 (higher for more spread)
  gravity: 1.0
  linLogMode: true (emphasizes community structure)
  adjustSizes: true
  barnesHutOptimize: true
```

**Phase 2 — Overlap Removal:**
```
Noverlap: 300-500 iterations (pushes overlapping nodes apart)
```

**Phase 3 — Label Adjustment (if labels are on):**
```
Label Adjust: 200-500 iterations (moves nodes to reduce label collisions)
```

If the layout is too compressed after Phase 1, run `Expansion` (50-200 iterations) before Phase 2.

### Export Settings

**For publication/presentation (no labels):**
```json
{
  "node.label.show": false,
  "edge.opacity": 20,
  "edge.curved": true,
  "node.opacity": 100,
  "node.border.width": 0.5,
  "arrow.size": 0
}
```
Export at `width: 3840, height: 2160` (4K) for PNG, plus SVG for vector.

**For annotated reference (with labels):**
```json
{
  "node.label.show": true,
  "node.label.proportinalSize": false,
  "node.label.font": "Arial 8 Plain",
  "node.label.outline.size": 3,
  "node.label.outline.opacity": 90,
  "edge.opacity": 15,
  "edge.curved": true
}
```

### Complete Publication Workflow

1. Build/import graph
2. Run `gephi_compute_modularity` (resolution 1.0)
3. Run `gephi_compute_degree`
4. Color by partition with pastel palette: `gephi_color_by_partition` column "modularity_class" with custom colors
5. Size by degree: `gephi_size_by_ranking` column "degree", min_size 3, max_size 25
6. Layout Phase 1: ForceAtlas 2 (1500 iterations, scalingRatio 200, linLogMode true)
7. Layout Phase 2: Noverlap (500 iterations)
8. Set preview: edge.opacity 20, edge.curved true, arrow.size 0, node.label.show false, edge.color "source"
9. Export clean version: `gephi_export_png` at 3840x2160
10. Toggle labels on, export annotated version
11. Export SVG for vector editing

## Known Limitations & Gotchas

These were discovered through extensive testing — avoid these pitfalls:

### Preview Settings
- **`edge.color` supports string values** — set to `"source"`, `"target"`, `"mixed"`, `"original"`, or a hex color like `"#FF0000"`. The plugin converts these to proper `EdgeColor` objects.
- **`node.border.color` and `node.label.color` support string values** — set to `"parent"`, `"darker"`, `"original"`, or a hex color like `"#333333"`. The plugin converts these to proper `DependantColor`/`DependantOriginalColor` objects.
- **`node.label.font` must be a string like `"Arial 12 Bold"`** — the plugin parses this into a `java.awt.Font` object. Passing anything else (or null) will corrupt the preview model, causing blank exports. If this happens, you must restart Gephi and rebuild the graph.
- **`node.label.proportinalSize`** — note the typo in Gephi's property name (missing 'o'). Use this exact key to toggle proportional label sizing.
- **Null values in preview settings corrupt the preview model** — never pass null. The plugin skips nulls, but be careful with missing values.
- **Unknown property types are safely skipped** — the plugin only sets properties whose types it can handle (Color, Boolean, Float, Integer, Font, DependantColor, DependantOriginalColor, EdgeColor). Other types are silently skipped to prevent corruption.

### Layout Traps
- **High gravity → compressed cluster trap**: If you run ForceAtlas2 with gravity > 3, nodes can compress into a tight ball that is very hard to un-compress. Even running with high scalingRatio afterwards may not separate them. **Fix**: Run `Random Layout` (1 iteration) to reset positions, then re-run ForceAtlas2.
- **Node size affects layout**: ForceAtlas2 with `adjustSizes: true` considers node sizes. If nodes are very large (max_size > 30), they push each other out and create unnatural gaps. Size nodes AFTER layout, or use small sizes during layout.
- **Expansion layout is multiplicative**: Each iteration multiplies positions by ~1.2x. Running 200+ iterations can send nodes to extreme coordinates. Use 20-50 iterations for mild expansion, check, then repeat.

### Workspace Issues
- **Workspace switching can deadlock Gephi** — switching workspaces via API sometimes causes the next graph operation to hang indefinitely. If API calls start timing out after a workspace switch, restart Gephi.
- **`gephi_list_workspaces` may return empty** even when workspaces exist — this is a known Gephi API limitation.

### Edge Operations on Directed Graphs
- Directed edges are created with edge type 1. The `findEdge()` helper checks types 1, 0, and default. This was fixed in the plugin but be aware that duplicate edges (same source/target but different type) can exist.

### Statistics
- **Always run `gephi_compute_modularity` BEFORE `gephi_color_by_partition`** — the `Modularity Class` column doesn't exist until modularity is computed. This is a common mistake.
- **Always run `gephi_compute_degree` BEFORE `gephi_size_by_ranking` with column "degree"** — same reason.

### Deployment
- Gephi plugins must be installed from `.nbm` files, not standalone JARs
- After updating the plugin, clear the cache: `rm ~/Library/Caches/gephi/0.10/*.dat`
- Then restart Gephi

## Best Practices

1. **Always create a project first** before adding nodes/edges
2. **Run statistics before styling** - you need computed attributes to color/size by
3. **Run layout before export** - nodes need positions for meaningful visualization
4. **Use batch operations** (`gephi_add_nodes`, `gephi_add_edges`) for efficiency
5. **Check layout status** before running a new layout
6. **Refresh preview** before export (done automatically by export tools)
7. **Filters are destructive** - they permanently remove nodes/edges from the graph
8. **Save project** before destructive operations (filtering, clearing)
9. **Use gephi_query_nodes** to verify results after operations
10. **ForceAtlas2 is the default choice** for most network types
11. **Use pastel colors** — never use default Gephi partition colors for publication
12. **Edge opacity is the #1 aesthetic lever** — lower opacity = more professional look
13. **Color edges by source node** — use `edge.color: "source"` in preview settings, or per-edge coloring for custom control
14. **Export twice** — once clean (no labels), once annotated (with labels) for reference
15. **3-phase layout** — ForceAtlas2 → Noverlap → Label Adjust for best results

For detailed tool parameters, see [references/tool-reference.md](references/tool-reference.md).
For layout algorithm details, see [references/layout-guide.md](references/layout-guide.md).
For statistics interpretation, see [references/statistics-guide.md](references/statistics-guide.md).
