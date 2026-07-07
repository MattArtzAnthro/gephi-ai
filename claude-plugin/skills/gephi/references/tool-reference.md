# Gephi MCP Tool Reference

Complete catalog of all MCP tools for controlling Gephi Desktop.

## Health

### gephi_health_check
- **Method**: GET `/health`
- **Params**: None
- **Returns**: `{success, service, version, status}`
- **Usage**: Call first to verify Gephi is running

### gephi_visual_qa
- **Method**: GEXF export (internal temp file), analyzed server-side
- **Params**: `{partition_column?: str}`
- **Returns**: `{nodes, edges, sizes, colors, extent (with suggested_export), partition?, warnings[]}`
- **Usage**: Visual-design diagnostics. Call BEFORE styling with `partition_column`
  to verify a claimed grouping is topologically real (verdict "none" means coloring
  by it would mislead — compute modularity instead), and AFTER styling/layout to
  catch invisible node sizes, near-white colors, and gradient color schemes, and to
  get export dimensions matching the layout shape. Fix every warning before the
  final export.

### gephi_focus_view
- **Method**: POST `/view/focus`
- **Params**: `{mode: "graph"|"zero"|"node"|"edge"|"region", id?, source?, target?, x?, y?, w?, h?, zoom?: float, select?: [node ids]}`
- **Returns**: `{success, mode, selected?}`
- **Usage**: Camera/attention control for the Gephi Desktop window: fit the graph,
  center on a node/edge/region, visually select nodes (empty select clears), set
  zoom. Desktop only — errors politely when headless. Use in teaching mode so the
  viewer always sees what you're describing.

### gephi_set_selection_mode
- **Method**: POST `/view/selection`
- **Params**: `{mode: "rectangle"|"direct"|"disable"}` (default `rectangle`)
- **Returns**: `{success, mode}`
- **Usage**: sets how the human's mouse selects on the canvas, via the same VisualizationController focusView uses. `rectangle` enables the box-drag gesture that `gephi_get_selection` reads — call it at the start of a teaching session so pointing works without the human clicking the toolbar's dashed-square icon first. Desktop only.

### gephi_get_perspective
- **Method**: GET `/perspective`
- **Returns**: `{success, selected, perspectives: [{name, display_name, selected}]}`
- **Usage**: lists the top-level tabs (Overview / Data Laboratory / Preview) and which is active. Desktop only.

### gephi_switch_perspective
- **Method**: POST `/perspective/switch`
- **Params**: `{name}` — matches a perspective's `name` or `display_name` (case-insensitive), e.g. "Overview", "Data Laboratory", "Preview"
- **Returns**: `{success, selected}`
- **Usage**: moves the human's view to a tab before discussing it (e.g. switch to Data Laboratory before walking through the attribute table). Runs on the EDT. Desktop only.

### gephi_get_selection
- **Method**: GET `/selection?clear=true|false`
- **Returns**: `{success, selected_now: [{id, label?}], selected_count, selected_truncated?, clicks: [{time_ms, nodes}], click_count, listener_active}`
- **Usage**: What the human has selected in the Gephi window. selected_now is
  the persistent selection (made with the rectangle-selection tool — the
  pointing gesture; capped at 200, selected_count is the true total). Read it
  whenever they use deictic words ("these", "the ones I selected") and answer
  about those exact nodes. clicks is a secondary click journal, usually empty
  (hover highlighting is transient and does not register). clear=true empties
  the click journal only. Desktop only.

## Project Management

### gephi_create_project
- **Method**: POST `/project/new`
- **Params**: `{name?: str}` - optional project name
- **Returns**: `{success, workspace_id}`

### gephi_open_project
- **Method**: POST `/project/open`
- **Params**: `{file: str}` - absolute path to .gephi file
- **Returns**: `{success, message}`

### gephi_save_project
- **Method**: POST `/project/save`
- **Params**: `{file: str}` - absolute path to save to
- **Returns**: `{success, message}`

### gephi_get_project_info
- **Method**: GET `/project/info`
- **Params**: None
- **Returns**: `{success, has_project, workspace_id, node_count, edge_count, is_directed, is_mixed}`

## Workspace Management

### gephi_new_workspace
- **Method**: POST `/workspace/new`
- **Params**: `{}` (empty)
- **Returns**: `{success, workspace_id}`

### gephi_list_workspaces
- **Method**: GET `/workspace/list`
- **Params**: `{}` (empty)
- **Returns**: `{success, workspaces: [{id, current}]}`

### gephi_switch_workspace
- **Method**: POST `/workspace/switch`
- **Params**: `{index: int}` - zero-based index
- **Returns**: `{success, message}`

### gephi_delete_workspace
- **Method**: DELETE `/workspace/delete`
- **Params**: `{index: int}` - zero-based index
- **Returns**: `{success, message}`

### gephi_duplicate_workspace
- **Method**: POST `/workspace/duplicate`
- **Params**: `{index: int}` - zero-based index to duplicate
- **Returns**: `{success, workspace_id}`
- **Notes**: Copies all graph data, statistics, and appearance settings into a new workspace.

### gephi_rename_workspace
- **Method**: POST `/workspace/rename`
- **Params**: `{index: int, name: str}`
- **Returns**: `{success, message}`

## Node Operations

### gephi_add_node
- **Method**: POST `/graph/node/add`
- **Params**: `{id: str, label?: str, attributes?: {key: value}}`
- **Returns**: `{success, node_id}`
- **Notes**: Label defaults to ID. Attributes auto-create columns.

### gephi_add_nodes
- **Method**: POST `/graph/nodes/add`
- **Params**: `{nodes: [{id: str, label?: str}, ...]}`
- **Returns**: `{success, added, skipped}`
- **Notes**: Skips duplicate IDs. Use for bulk loading.

### gephi_remove_node
- **Method**: DELETE `/graph/node/{id}`
- **Params**: `{id: str}`
- **Returns**: `{success, edges_removed}`
- **Notes**: Also removes all connected edges.

### gephi_bulk_remove_nodes
- **Method**: POST `/graph/nodes/remove`
- **Params**: `{ids: [str]}`
- **Returns**: `{success, removed, not_found}`

### gephi_query_nodes
- **Method**: GET `/graph/nodes`
- **Params**: `{limit?: int (100), offset?: int (0)}`
- **Returns**: `{success, total, count, nodes: [{id, label, x, y, size, degree, r, g, b, a, attributes}]}`
- **Notes**: Includes all custom attributes per node.

### gephi_get_node
- **Method**: GET `/graph/node/get/{id}`
- **Params**: `{id: str}`
- **Returns**: `{success, node: {id, label, x, y, size, r, g, b, attributes}}`
- **Notes**: Full detail for a single node by ID.

### gephi_set_node_label
- **Method**: POST `/graph/node/label`
- **Params**: `{id: str, label: str}`

### gephi_set_node_position
- **Method**: POST `/graph/node/position`
- **Params**: `{id: str, x: float, y: float}`

### gephi_batch_set_positions
- **Method**: POST `/graph/nodes/positions`
- **Params**: `{positions: [{id: str, x: float, y: float}, ...]}`
- **Returns**: `{success, set, not_found}`

## Edge Operations

### gephi_add_edge
- **Method**: POST `/graph/edge/add`
- **Params**: `{source: str, target: str, weight?: float (1.0), directed?: bool (true)}`
- **Returns**: `{success, message}`

### gephi_add_edges
- **Method**: POST `/graph/edges/add`
- **Params**: `{edges: [{source: str, target: str, weight?: float}, ...]}`
- **Returns**: `{success, added, skipped}`

### gephi_remove_edge
- **Method**: POST `/graph/edge/remove`
- **Params**: `{source: str, target: str}`

### gephi_set_edge_weight
- **Method**: POST `/graph/edge/weight`
- **Params**: `{source: str, target: str, weight: float}`

### gephi_set_edge_label
- **Method**: POST `/graph/edge/label`
- **Params**: `{source: str, target: str, label: str}`

### gephi_query_edges
- **Method**: GET `/graph/edges`
- **Params**: `{limit?: int (100), offset?: int (0)}`
- **Returns**: `{success, total, count, edges: [{source, target, weight, directed, label, r, g, b, attributes}]}`

## Graph Stats & Type

### gephi_get_graph_stats
- **Method**: GET `/graph/stats`
- **Returns**: `{success, node_count, edge_count, density, average_degree, is_directed}`

### gephi_get_graph_type
- **Method**: GET `/graph/type`
- **Returns**: `{success, directed, undirected, mixed}`

### gephi_clear_graph
- **Method**: POST `/graph/clear`
- **Params**: `{}` (empty)
- **Returns**: `{success, nodes_removed, edges_removed}`
- **Notes**: Removes all nodes and edges. Project/workspace remain.

## Attributes & Columns

### gephi_get_columns
- **Method**: GET `/graph/columns`
- **Params**: `{target: "node"|"edge"}`
- **Returns**: `{success, columns: [{id, title, type, property}]}`

### gephi_add_column
- **Method**: POST `/graph/columns/add`
- **Params**: `{name: str, type: "string"|"integer"|"double"|"float"|"boolean"|"long", target?: "node"|"edge"}`

### gephi_set_node_attributes
- **Method**: POST `/graph/node/attributes`
- **Params**: `{id: str, attributes: {key: value}}`
- **Notes**: Auto-creates columns if they don't exist.

### gephi_batch_set_node_attributes
- **Method**: POST `/graph/nodes/attributes`
- **Params**: `{updates: [{id: str, attributes: {key: value}}, ...]}`

### gephi_set_edge_attributes
- **Method**: POST `/graph/edge/attributes`
- **Params**: `{source: str, target: str, attributes: {key: value}}`

## Appearance: Individual Styling

### gephi_set_node_color
- **Method**: POST `/appearance/node/color`
- **Params**: `{id: str, r: int, g: int, b: int, a?: int (255)}`

### gephi_set_node_size
- **Method**: POST `/appearance/node/size`
- **Params**: `{id: str, size: float}`

### gephi_set_edge_color
- **Method**: POST `/appearance/edge/color`
- **Params**: `{source: str, target: str, r: int, g: int, b: int, a?: int (255)}`

### gephi_batch_set_node_colors
- **Method**: POST `/appearance/nodes/color`
- **Params**: `{nodes: [{id: str, r: int, g: int, b: int, a?: int}, ...]}`

### gephi_reset_appearance
- **Method**: POST `/appearance/reset`
- **Params**: `{r?: int (153), g?: int (153), b?: int (153), size?: float (10)}`

## Appearance: By Attribute

### gephi_color_by_partition
- **Method**: POST `/appearance/partition/color`
- **Params**: `{column: str, colors?: {value: [r,g,b], ...}}`
- **Notes**: Auto-generates palette if colors not provided. Use for modularity_class, type, category.

### gephi_color_edges_by_partition
- **Method**: POST `/appearance/edge/partition-color`
- **Params**: `{column: str, colors?: {value: [r,g,b], ...}}`
- **Notes**: The edge twin of `gephi_color_by_partition` — colors edges by a categorical EDGE column (relationship type, period, weight tier). Auto-palette if colors omitted. Coloring by a few relationship TYPES is when edge color earns its keep (unlike per-source coloring on dense graphs — see text-network-analysis.md).

### gephi_color_by_ranking
- **Method**: POST `/appearance/ranking/color`
- **Params**: `{column: str, r_min?: int (255), g_min?: int (255), b_min?: int (200), r_max?: int (255), g_max?: int (0), b_max?: int (0)}`
- **Notes**: Creates gradient from min to max color. Use for degree, pageranks, centrality.

### gephi_size_by_ranking
- **Method**: POST `/appearance/ranking/size`
- **Params**: `{column: str, min_size?: float (5), max_size?: float (50)}`

### gephi_edge_thickness_by_weight
- **Method**: POST `/appearance/edge/thickness-by-weight`
- **Params**: `{min_thickness?: float (1), max_thickness?: float (5)}`
- **Notes**: Scales edge thickness proportionally to weight values.

## Layout

### gephi_run_layout
- **Method**: POST `/layout/run`
- **Params**: `{algorithm: str, iterations?: int (1000), properties?: {name: value}}`
- **Notes**: Runs asynchronously. Algorithm names: forceatlas2, yifanhu, fruchterman, circular, random.

### gephi_stop_layout
- **Method**: POST `/layout/stop`

### gephi_get_layout_status
- **Method**: GET `/layout/status`
- **Returns**: `{success, running, layout?}`

### gephi_get_available_layouts
- **Method**: GET `/layout/available`
- **Returns**: `{success, layouts: [{name}]}`

### gephi_get_layout_properties
- **Method**: GET `/layout/properties`
- **Params**: `{algorithm: str}`
- **Returns**: `{success, algorithm, properties: [{name, display_name, type, value, description}]}`

### gephi_set_layout_properties
- **Method**: POST `/layout/properties`
- **Params**: `{algorithm: str, properties: {name: value}, iterations?: int (1000)}`
- **Notes**: Sets properties then runs layout. Use for fine-tuning.

### gephi_similarity_layout
- **Method**: computed server-side (Python), positions pushed via POST `/graph/nodes/positions`
- **Params**: `{projection?: "auto"|"umap"|"tsne"|"spectral", dimensions?: int (8), finish_noverlap?: bool (true)}`
- **Notes**: Positions nodes by structural role (embedding), not springs. Proximity = similar role, NOT connection — state this when presenting.

### gephi_community_layout
- **Method**: computed server-side (Python), positions pushed via POST `/graph/nodes/positions`
- **Params**: `{partition_column?: str ("Modularity Class"), min_community_size?: int (6), finish_noverlap?: bool (true)}`
- **Returns**: includes `separation_before`/`separation_after` (1.0 = fully mixed, near 0 = tight discs)
- **Notes**: One radial fan per community, packed as discs. For tree-like networks (replies, retweets) where force layouts cannot separate communities. Reading rule: disc placement is legibility, not structure — say so.

## Statistics

### gephi_compute_modularity
- **Method**: POST `/statistics/modularity`
- **Params**: `{resolution?: float (1.0)}`
- **Creates**: `modularity_class` (Integer) on nodes
- **Returns**: `{success, modularity}`
- **Notes**: Higher resolution = more communities. Use `gephi_color_by_partition` with `modularity_class` afterwards.

### gephi_compute_degree
- **Method**: POST `/statistics/degree`
- **Creates**: `degree`, `indegree`, `outdegree` on nodes
- **Returns**: `{success, average_degree}`

### gephi_list_statistics
- **Method**: GET `/statistics/available`
- **Returns**: every statistic name available in this Gephi instance, including built-ins and any installed plugin metric (e.g. Leiden Algorithm from the Gephi plugin portal)
- **Notes**: run any listed name with `gephi_run_statistic`.

### gephi_run_statistic
- **Params**: `{name: str, params?: dict}` — `name` matches an entry from `gephi_list_statistics` (case-insensitive); `params` is an optional `{property: value}` map set on the statistic before it runs
- **Notes**: the plugin-ecosystem passthrough — install a metric plugin in Gephi (Tools > Plugins) and it's immediately runnable here. Plugin statistics configured by a UI dialog usually need `params` (their fields start null/zero). Results land in node/edge columns as usual.

### gephi_profile_graph
- **Method**: exports the graph (GEXF) and computes size, density, degree distribution, connectivity, weight signal, modularity, and clustering coefficient in one call
- **Params**: `{include_slow?: bool (false)}` — also computes average path length/diameter when true (expensive; only sensible under ~3k nodes)
- **Notes**: run this first, before analyzing anything else. Auto-raises flags (fragmentation, hub dominance, likely hairball) to guide layout/sizing/coloring choices downstream.

### gephi_compute_betweenness
- **Method**: POST `/statistics/betweenness`
- **Creates**: `betweenesscentrality`, `closnesscentrality`, `harmonicclosnesscentrality`, `eccentricity` on nodes
- **Returns**: `{success, average_path_length, diameter, radius}`
- **Notes**: Slow on large graphs (>10k nodes). Also computes closeness and eccentricity.

### gephi_compute_pagerank
- **Method**: POST `/statistics/pagerank`
- **Creates**: `pageranks` on nodes
- **Returns**: `{success, statistic}`

### gephi_compute_eigenvector
- **Method**: POST `/statistics/eigenvector`
- **Creates**: `eigencentrality` on nodes

### gephi_compute_connected_components
- **Method**: POST `/statistics/connected-components`
- **Creates**: `componentnumber` on nodes
- **Returns**: `{success, connected_components}`

### gephi_compute_clustering_coefficient
- **Method**: POST `/statistics/clustering-coefficient`
- **Creates**: `clustering` on nodes
- **Returns**: `{success, average_clustering_coefficient}`

### gephi_compute_avg_path_length
- **Method**: POST `/statistics/avg-path-length`
- **Returns**: `{success, average_path_length, diameter, radius}`

### gephi_compute_hits
- **Method**: POST `/statistics/hits`
- **Creates**: `Authority`, `Hub` on nodes

### gephi_label_clusters
- **Method**: GEXF export + per-node label writes + preview settings
- **Params**: `{partition_column: str, names?: {group_value: caption}, restore?: bool}`
- **Returns**: `{labeled: {group: {node, label}}, blanked}` or `{restored}`
- **Usage**: Caption clusters the VNA way — blanks all labels, names each cluster's
  top-degree hub (hubs sit near their region's center), labeled preview with white
  outline. Originals saved to `label_backup`; `restore: true` reverses everything.

## Analysis & Counterfactual

### gephi_whatif
- **Method**: duplicates the current workspace (auto-opens the copy), computes a baseline profile, applies the edits to the copy, recomputes the profile, diffs them, then deletes the scratch copy and switches back to the original — all in one call. The real graph is never modified.
- **Params**: `{edits: [op...], include_slow?: bool (false)}` where each op is one of `{"op":"remove_node","id"}`, `{"op":"remove_nodes","ids":[...]}`, `{"op":"add_edge","source","target","weight"?,"directed"?}`, `{"op":"remove_edge","source","target"}`. `include_slow` also diffs avg path length/diameter.
- **Returns**: `{success, edits_applied, diff: [{metric, before, after, delta}], cleanup: {scratch_deleted, returned_to_workspace_id}}`. `diff` covers nodes, edges, density, degree, components, isolates, modularity, communities, clustering (+ path length/diameter when `include_slow`).
- **Notes**: for robustness / "what would happen if we removed X" claims. Cleanup is guaranteed even if an edit fails (the scratch copy is always deleted); on a failed edit the run stops and reports the failure with no diff. Returns measurements, not conclusions — narrate them, and treat a counterfactual on a small/skewed graph with the same caution as any single sample. See references/claim-verification.md.

### gephi_compare_nodes
- **Method**: reads both nodes (`GET /graph/node/get/{id}`) and compares one metric
- **Params**: `{id_a: str, id_b: str, metric: str}` — `metric` is a node attribute (`"Betweenness Centrality"`, `"Degree"`, `"pageranks"`, `"frequency"`) or a built-in field (`"size"`); attributes are checked before top-level fields
- **Returns**: `{success, metric, a, b, higher, difference}` — `higher` is the id of the larger value (null on a tie); `difference` is `abs(a-b)`. Errors clearly if the metric column is absent from a node (compute that statistic first).
- **Notes**: the deterministic answer to "is X more [central/connected] than Y". See references/claim-verification.md.

## Filters

### gephi_filter_by_degree
- **Method**: POST `/filter/degree`
- **Params**: `{min: int, max: int}` (max=0 for no upper limit)
- **Returns**: `{success, removed, remaining_nodes}`
- **Warning**: Destructive. Permanently removes nodes.

### gephi_filter_by_edge_weight
- **Method**: POST `/filter/edge-weight`
- **Params**: `{min: float, max: float}` (max=0 for no upper limit)
- **Returns**: `{success, removed, remaining_edges}`
- **Warning**: Destructive. Permanently removes edges.

### gephi_remove_isolates
- **Method**: POST `/filter/remove-isolates`
- **Params**: `{}` (empty)
- **Returns**: `{success, removed, remaining_nodes}`
- **Notes**: Removes all nodes with degree 0.

### gephi_extract_ego_network
- **Method**: POST `/filter/ego-network`
- **Params**: `{node_id: str, depth?: int (1)}`
- **Returns**: `{success, kept_nodes, removed_nodes}`
- **Notes**: Keeps only the specified node and neighbors within depth. Destructive.

### gephi_extract_giant_component
- **Method**: POST `/filter/giant-component`
- **Params**: `{}` (empty)
- **Returns**: `{success, kept_nodes, removed_nodes, component_count}`
- **Notes**: Runs connected components, keeps only the largest. Destructive.

### gephi_reset_filters
- **Method**: POST `/filter/reset`
- **Params**: `{}` (empty)
- **Notes**: Restores graph to full view (only works for non-destructive filters).

### gephi_extract_backbone
- **Method**: fetches all edges (GET `/graph/edges`), computes the disparity filter (Serrano, Boguna, and Vespignani 2009) client-side, removes every non-surviving edge one at a time (POST `/graph/edge/remove`)
- **Params**: `{alpha?: float (0.05), max_edges?: int (20000)}` — lower alpha keeps fewer edges (stricter backbone); max_edges is a safety cap on how many edges this fetches/prunes in one call
- **Returns**: `{success, stats: {edges_kept, edges_removed, alpha}, edges_removed_from_graph}`
- **Warning**: Destructive. Works on any weighted graph, not just text networks — a principled alternative to a flat `min_edge_weight` cutoff (edge significance is judged per-node, relative to that node's own weight distribution, not one global threshold). Recompute modularity/betweenness afterward if needed; existing values describe the pre-prune graph.

### gephi_list_filters
- **Method**: GET `/filter/list`
- **Returns**: `{success, filters: [{name, category, description, properties: [{name, type}]}]}`
- **Usage**: discover every filter — built-in topology filters plus a per-column attribute filter for each column in the current graph. Read each filter's `properties` (a Range-typed property takes a `[low, high]` pair) before applying. The discover step before `gephi_apply_filter`. See references/filtering.md.

### gephi_apply_filter
- **Method**: POST `/filter/apply`
- **Params**: `{name, params?: {property: value}, action?: "select"|"new_workspace"|"column", column?}`
- **Returns**: for `select`, `{success, filter, nodes_before, edges_before, nodes_after, edges_after}`; for `new_workspace`/`column`, a success message
- **Usage**: apply any filter by name. `select` (default) narrows the visible graph non-destructively; `new_workspace` materializes the filtered subgraph (use for repeated filtering on large graphs — avoids unbounded hidden-element memory); `column` writes membership to a boolean column. Stack `select` calls for AND. See references/filtering.md.

## Data Laboratory

### gephi_column_value_frequencies
- **Method**: POST `/datalab/frequencies`
- **Params**: `{column, target?: "node"|"edge"}`
- **Returns**: `{success, column, target, total, distinct_values, frequencies: {value: count}}`
- **Usage**: value distribution for a column — check group counts/skew before partitioning, or spot data-entry variants. Read-only.

### gephi_detect_duplicates
- **Method**: POST `/datalab/duplicates`
- **Params**: `{column, target?: "node"|"edge", case_sensitive?: bool}`
- **Returns**: `{success, column, group_count, duplicate_groups: [[id, ...], ...]}`
- **Usage**: find nodes/edges sharing a column value (same email, same normalized name). Pair with `gephi_merge_nodes` to dedupe. Read-only.

### gephi_merge_nodes
- **Method**: POST `/datalab/merge-nodes`
- **Params**: `{ids: [str, ...], into?: str}`
- **Returns**: `{success, into, merged_count}`
- **Warning**: Destructive. Merges the given nodes into one (edges reassigned, values merged by Gephi defaults), deletes the rest. `into` picks the survivor (default: first id).

### gephi_create_regex_column
- **Method**: POST `/datalab/regex-column`
- **Params**: `{column, new_column, regex, target?: "node"|"edge"}`
- **Returns**: `{success, column}`
- **Usage**: adds a boolean column flagging rows whose `column` value matches `regex` — mark a subset to color/size/filter by later, without hiding anything. Errors on invalid regex.

## Timeline

### gephi_get_timeline
- **Method**: GET `/timeline`
- **Returns**: `{success, graph_is_dynamic, time_min?, time_max?, time_format, dynamic_columns: [...], timeline_enabled?, has_valid_bounds?, interval_start?, interval_end?}`
- **Usage**: report a graph's dynamic/timeline state — is it dynamic, what time range, which dynamic columns the timeline sees, current interval. Read-only; reason over node/edge start/end values to narrate change over time. There is intentionally **no** programmatic time-window tool — driving Gephi's timeline from outside destabilizes its render thread in this architecture (both the data-view swap and the timeline-UI toggle proved unsafe in testing); slice by time in the Gephi timeline UI directly if you need the live view filtered.

## Preview Settings

### gephi_get_preview_settings
- **Method**: GET `/preview/settings`
- **Returns**: `{success, settings: {property_name: value}}`

### gephi_set_preview_settings
- **Method**: POST `/preview/settings`
- **Params**: Dictionary of property name to value pairs
- **Common properties**:
  - `"node.label.show"`: true/false
  - `"edge.thickness"`: float
  - `"edge.curved"`: true/false
  - `"node.opacity"`: float (0-100)
  - `"edge.opacity"`: float (0-100)
  - `"background.color"`: "#rrggbb"

## Export

### gephi_export_png
- **Method**: POST `/export/png`
- **Params**: `{file: str, width?: int (1920), height?: int (1080)}`
- **Notes**: Automatically refreshes preview before export.

### gephi_export_pdf
- **Method**: POST `/export/pdf`
- **Params**: `{file: str, width?: int, height?: int}`

### gephi_export_svg
- **Method**: POST `/export/svg`
- **Params**: `{file: str}`

### gephi_export_gexf
- **Method**: POST `/export/gexf`
- **Params**: `{file: str}`

### gephi_export
- **Method**: POST `/export/format`
- **Params**: `{file: str, format: str}` — format is the exporter name: `vna`, `pajek`, `dl`, `spreadsheet`, `gdf`, `json`, plus `gexf`/`graphml`/`csv` (`gml` is import-only in this build — no exporter)
- **Notes**: the general export-by-format passthrough for interchange formats the dedicated tools don't cover (UCINET via `vna`/`dl`, Pajek, a spreadsheet for non-technical readers). Errors listing known formats if unrecognized.

### gephi_export_graphml
- **Method**: POST `/export/graphml`
- **Params**: `{file: str}`

### gephi_export_csv
- **Method**: POST `/export/csv`
- **Params**: `{file: str, separator?: str (","), target?: "nodes"|"edges"|"both"}`

### gephi_view_graph
- **Method**: POST `/export/gexf` (internal temp file), rendered client-side
- **Params**: `{max_nodes?: int (1500), title?: str ("Network view"), caption_column?: str, caption_names?: {group: name}}`
- **Notes**: MCP App tool. In hosts that support MCP Apps (claude.ai, Claude Desktop)
  it renders an interactive sigma.js view inline in the chat (pan, zoom, hover labels,
  click a node for attributes); graph data travels in the result's structuredContent.
  The app is a two-way instrument: per-node "Highlight connections" and "Ask Claude"
  buttons, a Refresh button that re-fetches from Gephi via an app-initiated tools/call,
  floating cluster captions when `caption_column` is set (size-weighted community
  centroids, toggleable), and a time slider when the GEXF is dynamic (spells).
  Hosts without MCP Apps get a text summary only, so use `gephi_export_png` there.
  Run a layout first so nodes are positioned. Graphs over `max_nodes` are trimmed to
  the highest-degree nodes (the summary says so).

## Import

### gephi_import_file
- **Method**: POST `/import/file`
- **Params**: `{file: str}`
- **Notes**: Auto-detects format by extension. Supports GEXF, GraphML, GML, CSV, DOT, Pajek.

### gephi_import_gexf
- **Method**: POST `/import/gexf`
- **Params**: `{file: str}`

### gephi_import_graphml
- **Method**: POST `/import/graphml`
- **Params**: `{file: str}`

### gephi_import_csv
- **Method**: POST `/import/csv`
- **Params**: `{file: str}`

## Text Network Analysis

### gephi_text_to_network
- **Method**: builds a word co-occurrence graph from free text client-side, loads it via `/graph/nodes/add` and `/graph/edges/add`
- **Params**: `{text: str | list[str], window_size?: int (4), min_edge_weight?: float (0.0), extra_stopwords?: list[str], pos_filter?: "nouns", min_word_frequency?: int (1), merge_phrases?: bool (false), self_referential_threshold?: float (0.5), exclude_self_referential?: bool (false), context_snippets?: int (0), clear_existing?: bool (false)}`
- **Returns**: `{success, stats: {raw_word_count, kept_word_count, unique_words, words_filtered, edge_count, document_count, lemmatization, pos_filter_applied, phrases_detected, self_referential_candidates}, nodes_result, edges_result}`
- **Notes**: pass a list of strings, not one concatenated string, whenever the input is naturally many separate documents — the co-occurrence window resets at each list item rather than bridging between unrelated documents. Every node also carries a `document_frequency` attribute. Before trusting the result, check `stats.self_referential_candidates` (each entry: `word`, `document_frequency`, `document_ratio`, `peak_document_count`, plus `context` when `context_snippets > 0`) — a word appearing in an unusually large share of documents can dominate the graph without discriminating anything, and raw frequency rank alone won't reliably catch it. See references/text-network-analysis.md for the full craft knowledge on stopword handling, window size, and reading community structure.
