# Gephi AI Tool Reference

Complete catalog of all MCP tools for controlling Gephi Desktop.

Start with `gephi_health_check`. Then check which workspace is open (`gephi_list_workspaces`) and whether a filter is active (`filter_active` in replies): a filter from an earlier conversation stays on, and exports and checks then see only what it shows.

## Health

### gephi_health_check
- **Method**: GET `/health`
- **Params**: None
- **Returns**: `{success, service, version, status}`
- **Usage**: Call first to verify Gephi is running

### gephi_visual_qa
- **Method**: GEXF export (internal temp file), analyzed server-side
- **Params**: `{partition_column?: str}`
- **Returns**: `{nodes, edges, sizes, colors, extent (with suggested_export), partition?, warnings[]}`. With `partition_column`, `partition` holds `within_fraction` (share of ties inside a group), `random_baseline` (the share expected by chance), `ratio_vs_random`, `verdict`, and `separation` (how mixed the groups are in the current layout; 1.0 fully mixed). It counts ties, not weight, and reads only the visible graph when a filter is on.
- **Usage**: Visual-design diagnostics. Call BEFORE styling with `partition_column`
  to verify a claimed grouping is topologically real (verdict "none" means coloring
  by it would mislead; compute modularity instead), and AFTER styling/layout to
  catch invisible node sizes, near-white colors, and gradient color schemes, and to
  get export dimensions matching the layout shape. Fix every warning before the
  final export.

### gephi_focus_view
- **Method**: POST `/view/focus`
- **Params**: `{mode: "graph"|"zero"|"node"|"edge"|"region", id?, source?, target?, x?, y?, w?, h?, zoom?: float, select?: [node ids]}`
- **Returns**: `{success, mode, selected?}`. `selected` is the count actually applied
  (checked for up to one second), not an echo of the request size.
- **Usage**: Camera/attention control for the Gephi Desktop window: fit the graph,
  center on a node/edge/region, visually select nodes (empty select clears), set
  zoom. Desktop only; errors politely when headless. Use in teaching mode so the
  viewer always sees what you are describing.
- **Note**: `select` is for visual highlighting only, not for setting up a
  selection to read back later: it switches Gephi into "custom selection"
  mode, which `gephi_get_selection` does not read reliably. Only a real box-drag
  selection is guaranteed readable via `gephi_get_selection`.

### gephi_set_selection_mode
- **Method**: POST `/view/selection`
- **Params**: `{mode: "rectangle"|"direct"|"disable"}` (default `rectangle`)
- **Returns**: `{success, mode}`
- **Usage**: sets how the human's mouse selects on the canvas, via the same VisualizationController focusView uses. `rectangle` enables the box-drag gesture that `gephi_get_selection` reads. Call it at the start of a teaching session so pointing works without the human clicking the toolbar's dashed-square icon first. Desktop only.

### gephi_get_perspective
- **Method**: GET `/perspective`
- **Returns**: `{success, selected, perspectives: [{name, display_name, selected}]}`
- **Usage**: lists the top-level tabs (Overview / Data Laboratory / Preview) and which is active. Desktop only.

### gephi_switch_perspective
- **Method**: POST `/perspective/switch`
- **Params**: `{name}`, matching a perspective's `name` or `display_name` (case-insensitive), e.g. "Overview", "Data Laboratory", "Preview"
- **Returns**: `{success, selected}`
- **Usage**: moves the human's view to a tab before discussing it (e.g. switch to Data Laboratory before walking through the attribute table). Runs on the EDT. Desktop only.

### gephi_get_selection
- **Method**: GET `/selection?clear=true|false`
- **Params**: `{clear?: bool (false)}`
- **Returns**: `{success, selected_now: [{id, label?}], selected_count, selected_truncated?, clicks: [{time_ms, nodes}], click_count, listener_active}`
- **Usage**: What the human has selected in the Gephi window. selected_now is
  the persistent selection (made with the rectangle-selection tool, the
  pointing gesture; capped at 200, selected_count is the true total). Read it
  whenever they use deictic words ("these", "the ones I selected") and answer
  about those exact nodes. Only reliably reads back a real box-drag selection;
  a selection set via `gephi_focus_view`'s `select` is not guaranteed to still
  be here (see that tool's note). clicks is a secondary click journal, usually empty
  (hover highlighting is transient and does not register). clear=true empties
  the click journal only. Desktop only.

## Project Management

### gephi_create_project
- **Method**: POST `/project/new`
- **Params**: `{name?: str ("New Project")}` - optional project name
- **Returns**: `{success, workspace_id}`
- **Notes**: Gives no warning about unsaved work in the open project. Imports open in their own workspace, so no new project is needed. Never create or open a project over unsaved work; save it first or ask.

### gephi_open_project
- **Method**: POST `/project/open`
- **Params**: `{file: str}` - absolute path to .gephi file
- **Returns**: `{success, message}`

### gephi_save_project
- **Method**: POST `/project/save`
- **Params**: `{file: str}` - absolute path to save to
- **Returns**: `{success, message, file, bytes}`
- **Notes**: Reports success only once the file is on disk; a save that failed or was cancelled returns an error.

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

### gephi_snapshot
- **Method**: composite (Python-side; workspace list + duplicate + rename + switch)
- **Params**: `{label?: str}` - optional note recorded in the snapshot's name
- **Returns**: `{success, snapshot, message}`
- **Notes**: Saves a one-level undo point by copying the current workspace to a
  `[undo] …` workspace and switching straight back. Replaces any previous
  snapshot (one exists at a time). Destructive tools take this snapshot
  automatically; call it explicitly before risky per-node edits, which are not
  auto-snapshotted. Ignores `GEPHI_SNAPSHOT_MAX_NODES` (that cap only limits
  automatic snapshots; env `GEPHI_AUTO_SNAPSHOT=0` disables those entirely).

### gephi_undo
- **Method**: composite (Python-side; workspace list + switch + delete + rename)
- **Params**: `{}` (empty)
- **Returns**: `{success, restored, node_count, edge_count}`
- **Notes**: Restores the last `[undo] …` snapshot: switches to it, deletes the
  modified workspace, renames the snapshot back to its working name. One level,
  no redo. Errors with "nothing to undo" when no snapshot exists. Destructive
  tools report `undo_available: true/false` so you know whether this will work.

## Node Operations

### gephi_add_node
- **Method**: POST `/graph/node/add`
- **Params**: `{id: str, label?: str, attributes?: {key: value}}`
- **Returns**: `{success, node_id}`
- **Notes**: Label defaults to ID. Attributes auto-create columns.

### gephi_add_nodes
- **Method**: POST `/graph/nodes/add`
- **Params**: `{nodes: [{id: str, label?: str, attributes?: {column: value}}, ...]}`
- **Returns**: `{success, added, skipped}`
- **Notes**: Skips duplicate IDs; per-node attributes are applied. Use for bulk loading.

### gephi_remove_node
- **Method**: DELETE `/graph/node/{id}`
- **Params**: `{id: str}`
- **Returns**: `{success, edges_removed}`
- **Notes**: Also removes all connected edges. Destructive, and not auto-snapshotted: call `gephi_snapshot` first if it may need undoing, or use `gephi_bulk_remove_nodes`, which snapshots.

### gephi_bulk_remove_nodes
- **Method**: POST `/graph/nodes/remove`
- **Params**: `{ids: [str]}`
- **Returns**: `{success, removed, not_found}`
- **Notes**: Destructive; takes an undo snapshot first (`gephi_undo` reverses it, one level).

### gephi_query_nodes
- **Method**: GET `/graph/nodes`
- **Params**: `{limit?: int (100), offset?: int (0), column?: str, value?: str, contains?: str, min?: float, max?: float}`
- **Returns**: `{success, total, matches?, count, nodes: [{id, label, x, y, size, degree, r, g, b, a, attributes}]}`
- **Notes**: Pages in id order and has no sort. Every node comes back with all its columns, keyed by column title, so a large `limit` can overflow. To rank nodes on a metric, call `gephi_query_nodes` with `column` set to the metric and `min` set to a cutoff, with `limit` 20 or less, and raise or lower the cutoff until about ten nodes match (`matches` gives the total). To find nodes by value, name a `column` (id or title) with `value` (whole value; text ignores case), `contains` (part of the text), and/or `min`/`max` (inclusive numeric range); `matches` counts every match, not just the page.

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
- **Params**: `{source: str, target: str, weight?: float (1.0), directed?: bool (true), edge_type?: str}`
- **Returns**: `{success, message}`
- **Notes**: A pair of nodes normally holds one edge. `edge_type` names a relationship type, so the same pair can carry several parallel edges of different types (a multiplex graph); a second edge of the same type is rejected as a duplicate.

### gephi_add_edges
- **Method**: POST `/graph/edges/add`
- **Params**: `{edges: [{source: str, target: str, weight?: float, directed?: bool, label?: str, edge_type?: str, attributes?: {column: value}}, ...]}`
- **Returns**: `{success, added, skipped}`
- **Notes**: Edges naming missing nodes, and duplicates within the same `edge_type`, are skipped. For one edge row per pair per period, give each row `edge_type` set to its period and the period in `attributes` (for example `{"year": 2021}`): importing such rows as a CSV instead merges repeated pairs, summing weights and keeping only one row's other values. See references/change-over-time.md.

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
- **Notes**: Removes all nodes and edges. Project and workspace remain. Destructive; takes an undo snapshot first (`gephi_undo` brings the graph back).

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
- **Notes**: Auto-creates columns that do not exist yet.

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
- **Notes**: On a light background, leave `colors` unset: the plugin gives the largest group the first of eight colours validated for readability, the next largest the second, and so on, in an order that keeps the five largest groups distinguishable wherever they touch, even for colour-blind readers; past five groups, label the groups as well. On a dark background, pass the dark-surface palette. Colour must never be the only way to tell groups apart: label the largest nodes or the groups. Past eight groups the rest get generated distinct colours and the reply adds `palette_note`. Use for modularity_class, type, category.
- **Dark-surface palette** (pass explicitly, keyed largest group first): `{"0":[57,135,229],"1":[201,133,0],"2":[0,131,0],"3":[213,81,129],"4":[144,133,233],"5":[230,103,103],"6":[25,158,112],"7":[217,89,38]}`

### gephi_color_edges_by_partition
- **Method**: POST `/appearance/edge/partition-color`
- **Params**: `{column: str, colors?: {value: [r,g,b], ...}}`
- **Notes**: The edge twin of `gephi_color_by_partition`: colors edges by a categorical EDGE column (relationship type, period, weight tier). Auto-palette if colors omitted. Coloring by a few relationship TYPES is when edge color earns its keep (unlike per-source coloring on dense graphs; see text-network-analysis.md).

### gephi_color_by_ranking
- **Method**: POST `/appearance/ranking/color`
- **Params**: `{column: str, r_min?: int (255), g_min?: int (255), b_min?: int (200), r_max?: int (255), g_max?: int (0), b_max?: int (0)}`
- **Notes**: Creates gradient from min to max color. Use for degree, pageranks, centrality.

### gephi_size_by_ranking
- **Method**: POST `/appearance/ranking/size`
- **Params**: `{column: str, min_size?: float (10), max_size?: float (100), cap?: float}`
- **Notes**: Size nodes at about one to ten on screen (the `gephi_size_by_ranking` default, 10 to 100); widen the range for a large print. Unsized nodes render as invisible specks. `cap` gives every node at or above that value the largest size, so a few outliers do not shrink the rest; the reply gives `nodes_at_cap`, the legend records the cap, and Gephi's Appearance panel is left unchanged because it has no cap.

### gephi_edge_thickness_by_weight
- **Method**: POST `/appearance/edge/thickness-by-weight`
- **Params**: `{min_thickness?: float (1), max_thickness?: float (5)}`
- **Notes**: Scales edge thickness proportionally to weight values.

## Layout

### gephi_run_layout
- **Method**: POST `/layout/run`
- **Params**: `{algorithm: str, iterations?: int (1000), properties?: {name: value}, sync?: bool (false)}`
- **Returns**: any setting name that matches no property of the layout is listed in `unapplied_params` with a `warning`; it was not applied, so fix the name and rerun. A `sync` run ends with a positions check: if the layout exploded numerically (coordinates that are not finite or absurdly large, which ForceAtlas 2 can produce on weighted graphs with a strong hub), the reply carries `layout_exploded` with the affected nodes and the fix. When it is present, do not export or style; follow the fix first.
- **Notes**: Without `sync`, returns at once with status "running" (poll `gephi_get_layout_status`); with `sync: true`, waits until the layout finishes. Use `sync: true` for passes run one after another, so the next pass does not start on a moving graph. Algorithm names: forceatlas2, yifanhu, openord, fruchterman, circular, random (plus any layout plugin installed in Gephi; `gephi_get_available_layouts` lists what is present). Check property spelling against `gephi_get_layout_properties`: OpenOrd takes display names (`"Edge Cut"`, `"Layout Size"`), ForceAtlas 2 and Yifan Hu take camelCase. See references/layout-guide.md.
- **Developer note**: when calling the HTTP API directly, `/layout/run` takes tuning values under the key `properties`; values sent under `params` are ignored and the layout runs on its defaults.

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
- **Notes**: `value` is the layout's default, not a setting made earlier: each call builds a fresh layout instance, so it never reflects a previous `gephi_run_layout`. The `description` field also states the default in prose.

### gephi_set_layout_properties
- **Method**: POST `/layout/properties`
- **Params**: `{algorithm: str, properties: {name: value}, iterations?: int (1000)}`
- **Notes**: Sets properties then runs layout. Use for fine-tuning.

### gephi_similarity_layout
- **Method**: computed server-side (Python), positions pushed via POST `/graph/nodes/positions`
- **Params**: `{projection?: "auto"|"umap"|"tsne"|"spectral", dimensions?: int (8), finish_noverlap?: bool (true)}`
- **Notes**: Positions nodes by structural role (embedding), not springs. Proximity = similar role, NOT connection; state this when presenting.

### gephi_community_layout
- **Method**: computed server-side (Python), positions pushed via POST `/graph/nodes/positions`
- **Params**: `{partition_column?: str ("Modularity Class"), min_community_size?: int (6), finish_noverlap?: bool (true)}`
- **Returns**: includes `separation_before`/`separation_after` (1.0 = fully mixed, near 0 = tight discs)
- **Notes**: One radial fan per community, packed as discs. For tree-like networks (replies, retweets) where force layouts cannot separate communities. Reading rule: disc placement is legibility, not structure; say so.

## Statistics

### gephi_compute_modularity
- **Method**: POST `/statistics/modularity`
- **Params**: `{resolution?: float (1.0)}`
- **Creates**: `modularity_class` (Integer) on nodes
- **Returns**: `{success, modularity}`
- **Notes**: Higher resolution = fewer, larger communities (Gephi merges as the value rises, the reverse of the literature's convention). Use `gephi_color_by_partition` with `modularity_class` afterwards. Gephi's modularity occasionally never converges (gephi#1630); such a run is stopped after 45 s (`GEPHI_MODULARITY_DEADLINE`) and repeated once, and `reruns_after_nonconvergence` says so.

### gephi_community_stability
- **Method**: runs community detection `runs` times on the unchanged graph, reading the partition back between runs, and measures how often each pair of nodes lands together. Writes its results to their own columns so the run already on the graph survives.
- **Params**: `{runs: int (20), resolution: float (1.0), consensus_column: str ("consensus_community"), core_column: str ("stable_core")}`.
- **Returns**: `{success, runs, distinct_partitions, mean_stability, unstable_nodes: [{node, stability}], stable_cores: {threshold, cores, share_of_nodes, largest}, consensus_warning?, consensus_column, core_column, stability_column, reruns_after_nonconvergence?, caveats?}`. Graphs of 50 nodes or fewer also return `node_stability: {id: 0-1}` and `consensus_groups`; larger graphs return `consensus_group_sizes` and keep per-node values on the graph.
- **Writes**: `stable_core` (core id, -1 for nodes in no core), `consensus_community`, `community_stability` (per node, 0-1).
- **Notes**: use this BEFORE describing communities as a finding. Gephi reports one partition as though it were the answer; it is one draw. A node's stability is the chance that a node grouped with it in one run is grouped with it in another: 1.0 when its community-mates never change, 0.5 when half of them do. Stable cores are groups held together in at least 90% of runs. Small stable cores appear even in a randomly wired network, so their number or coverage is not evidence of communities: judge by `mean_stability` and by how large the biggest cores are. The consensus keeps pairs that agreed more often than not; on large sparse graphs those pairs chain into one giant group, and `consensus_warning` then says to read the stable cores instead. A run Gephi fails to finish is stopped and repeated (`reruns_after_nonconvergence`). Fewer than 2 runs is refused, and a partition that cannot be read back is an error rather than an empty result, because empty is indistinguishable from stable.

### gephi_compute_degree
- **Method**: POST `/statistics/degree`
- **Creates**: `degree`, `indegree`, `outdegree` on nodes
- **Returns**: `{success, average_degree}`

### gephi_list_statistics
- **Method**: GET `/statistics/available`
- **Returns**: every statistic name available in this Gephi instance, including built-ins and any installed plugin metric (e.g. Leiden Algorithm from the Gephi plugin portal)
- **Notes**: run any listed name with `gephi_run_statistic`.

### gephi_run_statistic
- **Params**: `{name: str, params?: dict}`. `name` matches an entry from `gephi_list_statistics` (case-insensitive); `params` is an optional `{property: value}` map set on the statistic before it runs
- **Notes**: the passthrough to Gephi's plugin ecosystem: install a metric plugin in Gephi (Tools > Plugins) and it is immediately runnable here. `gephi_run_statistic("Weighted Degree")` writes a "Weighted Degree" column, the sum of each node's edge weights. Plugin statistics configured by a UI dialog usually need `params` (their fields start null/zero). Results land in node/edge columns as usual.

### gephi_stop_statistic
- **Method**: POST `/statistics/stop`
- **Returns**: `{success, message, stopped: [name], cannot_stop?: [name]}`
- **Notes**: Stops a statistic still running in Gephi; the stopped run writes nothing, so columns keep their earlier values. Interrupting a statistic's call from the chat stops it in Gephi too. Runs even while another tool is working.

### gephi_find_shortest_path
- **Method**: POST `/graph/shortest-path`
- **Params**: `{source: str, target: str, weighting?: "none"|"distance"|"strength", follow_direction?: bool (true), mark_column?: str}`
- **Returns**: `{success, found, steps, length?, weighting, equally_short_paths, path: [{id, label}], mark_column?}`
- **Notes**: "none" counts steps; "distance" reads weight as length; "strength" reads a heavier edge as a closer tie (length 1/weight). When `equally_short_paths` is above 1 the path is one of several, so its middle nodes are not the only link. `mark_column` writes true/false on nodes and edges for colouring.

### gephi_profile_graph
- **Method**: exports the graph (GEXF) and computes size, density, degree distribution, connectivity, weight signal, modularity, and clustering coefficient in one call
- **Params**: `{include_slow?: bool (false)}`: also computes average path length/diameter when true (expensive; only sensible under ~3k nodes)
- **Notes**: run this first, before analyzing anything else. Its `degree` block gives `min`, `median`, `max`, `gini` (degree inequality, 0 equal to 1 one node holding every tie), and `top_5pct_edge_share`, which describe a heavy tail without fitting a curve. Auto-raises flags (fragmentation, hub dominance, likely hairball) to guide layout/sizing/coloring choices downstream.

### gephi_compute_betweenness
- **Method**: POST `/statistics/betweenness`
- **Creates**: `betweenesscentrality`, `closnesscentrality`, `harmonicclosnesscentrality`, `eccentricity` on nodes
- **Returns**: `{success, average_path_length, diameter, radius}`
- **Notes**: Slow on large graphs (>10k nodes). Also computes closeness and eccentricity. Gephi's closeness carries a known caveat, listed in the reply's `caveats`; PageRank is the safer read for "central to the whole network".

### gephi_compute_pagerank
- **Method**: POST `/statistics/pagerank`
- **Creates**: `pageranks` on nodes
- **Returns**: `{success, statistic}`

### gephi_compute_eigenvector
- **Method**: POST `/statistics/run` (Eigenvector Centrality)
- **Params**: `{iterations?: int (1000)}`
- **Creates**: `eigencentrality` on nodes
- **Notes**: Gephi's own default of 100 iterations stops before the values settle on some networks and can put the wrong node first; the tool runs 1,000. Values can still differ from an exact calculation by up to about a tenth, so do not rank on small differences; compare with PageRank and say so when they disagree.

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
- **Params**: `{partition_column: str, names?: {group_value: caption}, caption_scale?: float (1.0), prefer?: "degree"|"size" ("degree"), restore?: bool (false)}`
- **Returns**: `{labeled: {group: {node, label}}, blanked}` or `{restored}`
- **Usage**: Caption clusters the way visual network analysis does: blanks all labels,
  names each cluster's top-degree hub (hubs sit near their region's center), and turns
  on a labeled preview with a white outline. `caption_scale` multiplies the computed
  caption size (1.5 to 2 for louder, map-style captions); `prefer: "size"` anchors each
  caption on the visually largest node instead, useful when a hub is buried in a dense
  core. Originals are saved to `label_backup`; `restore: true` reverses everything.

## Analysis & Counterfactual

### gephi_whatif
- **Method**: duplicates the current workspace (auto-opens the copy), computes a baseline profile, applies the edits to the copy, recomputes the profile, diffs them, then deletes the scratch copy and switches back to the original, all in one call. The real graph is never modified.
- **Params**: `{edits: [op...], include_slow?: bool (false)}` where each op is one of `{"op":"remove_node","id"}`, `{"op":"remove_nodes","ids":[...]}`, `{"op":"add_edge","source","target","weight"?,"directed"?}`, `{"op":"remove_edge","source","target"}`. `include_slow` also diffs avg path length/diameter.
- **Returns**: `{success, edits_applied, diff: [{metric, before, after, delta}], cleanup: {scratch_deleted, returned_to_workspace_id}}`. `diff` covers nodes, edges, density, degree, components, the share of nodes in the largest component, isolates, modularity, clustering (+ path length/diameter when `include_slow`).
- **Notes**: for robustness / "what would happen if X were removed" claims. Cleanup is guaranteed even if an edit fails (the scratch copy is always deleted); on a failed edit the run stops and reports the failure with no diff. Returns measurements, not conclusions: narrate them, and treat a counterfactual on a small/skewed graph with the same caution as any single sample. See references/claim-verification.md.

### gephi_compare_nodes
- **Method**: reads both nodes (`GET /graph/node/get/{id}`) and compares one metric
- **Params**: `{id_a: str, id_b: str, metric: str}`. `metric` is a node attribute (`"Betweenness Centrality"`, `"Degree"`, `"pageranks"`, `"frequency"`) or a built-in field (`"size"`); attributes are checked before top-level fields
- **Returns**: `{success, metric, a, b, higher, difference}`. `higher` is the id of the larger value (null on a tie); `difference` is `abs(a-b)`. Errors clearly if the metric column is absent from a node (compute that statistic first).
- **Notes**: the deterministic answer to "is X more [central/connected] than Y". See references/claim-verification.md.

### gephi_claim_record
- **Method**: re-reads every cited node (`GET /graph/node/get/{id}`) and checks the cited values against the live graph; writes nothing to the graph
- **Params**: `{claim: str, classification: str, verdict: "confirmed"|"refuted"|"cant_tell", metric?: str, nodes?: [id], values?: {id: number}, numbers?: {name: value}, caveat?: str, export?: path}`
- **Returns**: a structured record (also as `structuredContent`): `{claim, classification, metric, verdict, verified, evidence: {nodes: [{id, label, value, cited}]}, numbers, caveat, checks: {nodes_checked, nodes_missing, value_mismatches}, caption, export?}`. `verified` is false when a cited node does not exist or a cited value differs from the live one; the verdict itself is never changed by the tool.
- **Notes**: the receipt behind a verified claim. Call it after measuring, with the ids and numbers the verdict rests on; `caption` is one sentence ready for a figure caption or methods appendix, and `export` writes the record as JSON. See references/claim-verification.md.

### gephi_compare_workspaces
- **Method**: reads both workspaces (switching to each and back), diffs node and edge sets, and, when `compare` names a numeric column, tracks it across the nodes present in both.
- **Params**: `{before: int, after: int, compare?: str, directed?: bool (false)}`. Workspace arguments are zero-based indices, not the ids the workspace list reports.
- **Returns**: `{success, nodes: {added, removed, shared, before, after}, edges: {added, removed, shared, directed}, changed: {column, comparable, grew, shrank, unchanged}|null, warning?}`.
- **Notes**: the comparison rests on node identity. Two graphs sharing no nodes carry a warning, because a mismatched identifier looks exactly like a network that replaced every member and is much more common. Omitting `compare` returns `changed: null` rather than an empty section, since an empty one reads as a finding that nothing moved.

### gephi_bipartite_layout
- **Method**: reads the graph, computes two columns of coordinates in Python, and pushes them as positions. No Gephi layout plugin is involved.
- **Params**: `{mode_column: str, separation?: float (600), spacing?: float (60)}`.
- **Returns**: `{success, positioned, modes: {left, right}, mode_column}`.
- **Notes**: `mode_column` names the attribute separating the two kinds of node: Gephi has no concept of a mode, so it must be told. A column holding more than two distinct values is refused rather than guessed at.

### gephi_bipartite_projection
- **Method**: collapses a two-mode network onto one mode, joining nodes that share a partner and weighting by how many they share, then builds the result in a NEW workspace. The original is untouched.
- **Params**: `{mode_column: str, keep: str, workspace_name?: str}`.
- **Returns**: `{success, nodes, edges, kept_mode, warning?, within_mode_edges?}`.
- **Notes**: the standard way to analyse two-mode data (people by events, authors by concepts) as a social network; Gephi cannot do it at all. Nodes sharing no partner are kept with no edges, because dropping them would quietly remove people from the network. An edge joining two nodes of the same mode means the data is not bipartite; those edges are ignored and reported.

## Filters

### gephi_filter_by_degree
- **Method**: POST `/filter/degree`
- **Params**: `{min: int (0), max: int (0), dry_run?: bool (false)}` (max=0 for no upper limit)
- **Returns**: `{success, removed, remaining_nodes}`
- **Warning**: Destructive: deletes the nodes outside the range (`gephi_reset_filters` does not bring them back). `dry_run: true` counts what would be removed and changes nothing. A real run takes an undo snapshot first; `gephi_undo` restores the graph (one level, no redo). To hide instead, use `gephi_apply_filter`.

### gephi_filter_by_edge_weight
- **Method**: POST `/filter/edge-weight`
- **Params**: `{min: float (0), max: float (0), dry_run?: bool (false)}` (max=0 for no upper limit)
- **Returns**: `{success, removed, remaining_edges}`
- **Warning**: Destructive: deletes the edges outside the range. `dry_run: true` counts first and changes nothing. A real run takes an undo snapshot first; `gephi_undo` reverses it (one level).

### gephi_remove_isolates
- **Method**: POST `/filter/remove-isolates`
- **Params**: `{}` (empty)
- **Returns**: `{success, removed, remaining_nodes}`
- **Notes**: Removes all nodes with degree 0. Destructive, with no `dry_run`; takes an undo snapshot first (`gephi_undo` reverses it). To count isolates first, compute degree and call `gephi_query_nodes(column="degree", max=0, limit=1)`; `matches` gives the count.

### gephi_extract_ego_network
- **Method**: POST `/filter/ego-network`
- **Params**: `{node_id: str, depth?: int (1)}`
- **Returns**: `{success, kept_nodes, removed_nodes}`
- **Notes**: Keeps only the specified node and neighbors within depth. Destructive; takes an undo snapshot first (`gephi_undo` reverses it).

### gephi_extract_giant_component
- **Method**: POST `/filter/giant-component`
- **Params**: `{}` (empty)
- **Returns**: `{success, kept_nodes, removed_nodes, component_count}`
- **Notes**: Runs connected components, keeps only the largest. Destructive; takes an undo snapshot first (`gephi_undo` reverses it).

### gephi_reset_filters
- **Method**: POST `/filter/reset`
- **Params**: `{}` (empty)
- **Notes**: Shows the whole graph again after `gephi_apply_filter` or `gephi_apply_filters`. It does not restore anything a remove, extract, or `filter_by_*` tool deleted; use `gephi_undo` for that.

### gephi_extract_backbone
- **Method**: fetches all edges (GET `/graph/edges`), computes the disparity filter (Serrano, Boguna, and Vespignani 2009) client-side, removes every non-surviving edge one at a time (POST `/graph/edge/remove`)
- **Params**: `{alpha?: float (0.05), max_edges?: int (20000)}`. Lower alpha keeps fewer edges (stricter backbone); max_edges is a safety cap on how many edges this fetches/prunes in one call
- **Returns**: `{success, stats: {edges_kept, edges_removed, alpha}, edges_removed_from_graph}`
- **Warning**: Destructive; takes an undo snapshot first (`gephi_undo` reverses it). Works on any weighted graph, not just text networks: a principled alternative to a flat `min_edge_weight` cutoff (edge significance is judged per-node, relative to that node's own weight distribution, not one global threshold). Recompute modularity/betweenness afterward if needed; existing values describe the pre-prune graph.

### gephi_list_filters
- **Method**: GET `/filter/list`
- **Returns**: `{success, filters: [{name, category, description, properties: [{name, type}]}]}`
- **Usage**: discover every filter: built-in topology filters plus a per-column attribute filter for each column in the current graph. Read each filter's `properties` (a Range-typed property takes a `[low, high]` pair) before applying. The discover step before `gephi_apply_filter`. See references/filtering.md.

### gephi_apply_filter
- **Method**: POST `/filter/apply`
- **Params**: `{name, params?: {property: value}, action?: "select"|"new_workspace"|"column", column?, dry_run?: bool (false)}`
- **Returns**: dry run: counts of what would stay and go (`nodes_kept`, `nodes_removed`, and the edge equivalents); for `select`, `{success, filter, nodes_before, edges_before, nodes_after, edges_after}`; for `new_workspace`/`column`, a success message
- **Usage**: apply any filter by name. `select` (default) hides what the filter excludes and changes no data; `gephi_reset_filters` shows it again. `new_workspace` copies the filtered subgraph into a new workspace (use for repeated filtering on large graphs, since hidden elements stay in memory); `column` writes membership to a true/false column. `dry_run: true` counts what would stay and go and changes nothing. A `select` filter stays on, into later conversations, and exports and checks then read only the visible graph. For AND, OR or NOT across filters use `gephi_apply_filters`. See references/filtering.md.

### gephi_apply_filters
- **Method**: POST `/filter/combine`
- **Params**: `{filters: [{name, params?, exclude?: bool}], combine?: "all"|"any", action?: "select"|"new_workspace"|"column", column?, dry_run?: bool}`
- **Returns**: dry run `{success, nodes_kept, edges_kept, nodes_removed, edges_removed, combine, filters}`; otherwise as `gephi_apply_filter`, plus `combine` and `filters`
- **Usage**: several filters at once. `combine` "all" keeps what every filter keeps (AND), "any" what at least one keeps (OR); `exclude` inverts one filter (NOT). Run `dry_run` first and say what will be hidden. The combined query shows in Gephi's Filters panel, and a `select` filter stays on until `gephi_reset_filters`.

## Data Laboratory

### gephi_column_value_frequencies
- **Method**: POST `/datalab/frequencies`
- **Params**: `{column, target?: "node"|"edge"}`
- **Returns**: `{success, column, target, total, distinct_values, frequencies: {value: count}}`
- **Usage**: value distribution for a column: check group counts and skew before partitioning, or spot data-entry variants. Read-only.

### gephi_detect_duplicates
- **Method**: POST `/datalab/duplicates`
- **Params**: `{column, target?: "node"|"edge", case_sensitive?: bool}`
- **Returns**: `{success, column, group_count, duplicate_groups: [[id, ...], ...]}`
- **Usage**: find nodes or edges sharing a column value (same email, same normalized name). Pair with `gephi_merge_nodes` to dedupe. Read-only.
- **Limit**: matches whole values only, ignoring case unless `case_sensitive` is true. Variants such as "J. Smith" and "John Smith" do not match; write a normalised column first (`gephi_add_column`, then `gephi_batch_set_node_attributes`) and detect on that.

### gephi_merge_nodes
- **Method**: POST `/datalab/merge-nodes`
- **Params**: `{ids: [str, ...], into?: str}`
- **Returns**: `{success, into, merged_count}`
- **Warning**: Destructive. Merges the given nodes into one (edges reassigned, values merged by Gephi defaults), deletes the rest. `into` picks the survivor (default: first id). Takes an undo snapshot first; `gephi_undo` reverses only the most recent merge, so check each merge before the next.

### gephi_create_regex_column
- **Method**: POST `/datalab/regex-column`
- **Params**: `{column, new_column, regex, target?: "node"|"edge"}`
- **Returns**: `{success, column}`
- **Usage**: adds a boolean column flagging rows whose `column` value matches `regex`: mark a subset to color/size/filter by later, without hiding anything. Errors on invalid regex.

### gephi_edit_column
- **Method**: POST `/datalab/column/edit`
- **Params**: `{column, action: "delete"|"rename"|"convert"|"fill_empty"|"clear", target?: "node"|"edge", value?, type?, new_name?}`
- **Returns**: `{success, message, column?, values_lost?, filled?}`
- **Usage**: tidy one column. `convert` changes its type (`type`: string, integer, long, float, double, boolean) and reports `values_lost` for values that could not convert; `fill_empty` writes `value` only into empty cells. Gephi's own columns cannot be deleted, renamed or converted. Auto-snapshots first; `gephi_undo` reverses it.

## Timeline

### gephi_get_timeline
- **Method**: GET `/timeline`
- **Returns**: `{success, graph_is_dynamic, time_min?, time_max?, time_format, dynamic_columns: [...], timeline_enabled?, has_valid_bounds?, interval_start?, interval_end?}`
- **Usage**: report a graph's time data: whether it has any, its range, which columns vary over time, and the timeline's current interval. Read-only. Gephi's timeline itself is left to the user; to study one period, use `gephi_time_slice`.

### gephi_set_time_from_columns
- **Method**: POST `/time/from-columns`
- **Params**: `{start?: str, end?: str, target?: "node"|"edge", date_format?: str}`
- **Returns**: `{success, with_time, time_min?, time_max?}`
- **Usage**: gives nodes or edges their time from a start and/or end column, so the timeline, time slices and dynamic statistics work. Number columns (years) are used as they are; text dates need `date_format`, a Java date pattern such as "yyyy-MM-dd". Auto-snapshots first; `gephi_undo` reverses it.

### gephi_time_slice
- **Method**: POST `/time/slice`
- **Params**: `{start: float, end: float}`
- **Returns**: `{success, workspace_id, workspace_name, node_count, edge_count, source_node_count, source_edge_count}`
- **Usage**: opens the network as it was between `start` and `end` in a new workspace: nodes present at some moment in the window, and edges present then between them. Elements without time data count as always present. The source network and Gephi's timeline are unchanged. Slice each period, run the same statistics in each, and compare with `gephi_compare_workspaces`.

## Preview Settings

### gephi_get_preview_settings
- **Method**: GET `/preview/settings`
- **Returns**: `{success, settings: {property_name: value}}`

### gephi_set_preview_settings
- **Method**: POST `/preview/settings`
- **Params**: `{settings: {property: value}}`
- **Light-background edge default**: `{"edge.color": "#D0D0D0", "edge.opacity": 90, "edge.thickness": 1.0, "edge.curved": false}`. Label settings change labels only; they never reset edge values.
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
- **Notes**: Automatically refreshes preview before export. Renders through Gephi's Preview pipeline (the graph's stored data), which has no concept of live selection; use gephi_export_screenshot when the figure needs to show what is currently selected.

### gephi_export_screenshot
- **Method**: POST `/export/screenshot`
- **Params**: `{file: str, scale?: int (2), transparent_background?: bool (false)}`
- **Notes**: Captures the LIVE Overview canvas via Gephi's own built-in screenshot feature (`org.gephi.visualization.api.ScreenshotController`): selection highlighting, hover state, and current camera framing all show up exactly as rendered on screen, unlike gephi_export_png. `scale` is a multiplier on the current on-screen canvas size, not literal pixel dimensions. Visually rougher than Preview-based exports (no edge bundling, plainer typography), so prefer gephi_export_png for clean data-driven figures and this tool specifically when selection/on-screen state needs to be captured. Desktop only; the Overview window must be visible.

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
- **Params**: `{file: str, format: str}`. `format` is the exporter name: `vna`, `pajek`, `dl`, `spreadsheet`, `gdf`, `json`, plus `gexf`/`graphml`/`csv` (`gml` is import-only; there is no exporter)
- **Notes**: the general export-by-format passthrough for interchange formats the dedicated tools do not cover (UCINET via `vna`/`dl`, Pajek, a spreadsheet for non-technical readers). Errors listing known formats if unrecognized.

### gephi_export_graphml
- **Method**: POST `/export/graphml`
- **Params**: `{file: str}`

### gephi_export_csv
- **Method**: POST `/export/csv`
- **Params**: `{file: str, separator?: str (","), target?: "nodes"|"edges"|"both"}`

### gephi_view_graph
- **Method**: POST `/export/gexf` (internal temp file), rendered client-side
- **Params**: `{max_nodes?: int (1500), title?: str ("Network view"), caption_column?: str, caption_names?: {group: name}}`
- **Notes**: MCP App tool. In hosts that support MCP Apps
  it renders an interactive sigma.js view inline in the chat (pan, zoom, hover labels,
  click a node for attributes); graph data travels in the result's structuredContent.
  The app is a two-way instrument: per-node "Highlight connections" and assistant-question
  buttons, a Refresh button that re-fetches from Gephi via an app-initiated tools/call,
  floating cluster captions when `caption_column` is set (size-weighted community
  centroids, toggleable), and a time slider when the GEXF is dynamic (spells).
  Hosts without MCP Apps get a text summary only, so use `gephi_export_png` there.
  Run a layout first so nodes are positioned. Graphs over `max_nodes` are trimmed to
  the highest-degree nodes (the summary says so).

### gephi_export_legend
- **Method**: draws an SVG key from the mappings applied in this session. Swatch colours for a partition are read back from the graph, because Gephi assigns a palette itself when none is given and never reports which one.
- **Params**: `{file: str}` (an `.svg` path).
- **Returns**: `{success, file, items}` or `{success: false, error}` when nothing has been mapped.
- **Notes**: answers gephi/gephi#511: Gephi has never shipped a legend. It describes only what was applied through these tools; styling done by hand in the Gephi window is invisible to it, so it REFUSES rather than guessing. A legend guessed from an unknown appearance is worse in a published figure than no legend. Pair it with a PNG or PDF export.

### gephi_export_figure
- **Method**: exports the map, builds the key, and writes both as one figure: a PDF and a PNG at 300 dpi. Colour and size come from the mappings made through these tools; `partition_column` additionally reads each group's colour back off the graph, so a reopened project or a palette Gephi chose itself still gets a correct key.
- **Params**: `{file: str, title: str, subtitle?: str, partition_column?: str, extra_channels?: list, notes?: list[str], detail_column?: str, width?: int, height?: int}`.
- **Returns**: `{success, png, pdf, pages, channels, notes, warnings?}`.
- **Notes**: `title` and `notes` are claims about the world and are never generated, the same refusal `gephi_export_legend` makes about swatches. `extra_channels` carries a channel this server does not own (a plugin's shape mapping, say) as `{channel, column, items: [{label, glyph, note?, stat?}]}` where `glyph` is one of circle, square, triangle, diamond, star, pentagon, hexagon, cross; naming a glyph rather than a plugin keeps it coupled to nothing. `detail_column` adds a second page of magnified crops, one per value; the graph-to-pixel transform is derived from the image and then CHECKED against it, and the page is dropped with a warning if under half the sampled nodes land on drawn pixels, because a misaligned crop still looks plausible.

### gephi_session_receipt
- **Method**: reports the mappings in force, the statistics run and their parameters, the layout and its settings, and the plugin and server versions.
- **Params**: `{file?: str}`: writes JSON when given a path.
- **Returns**: `{success, legend, statistics, layout, scope, versions: {server, plugin}, file?}`.
- **Notes**: for a methods section. Gephi does not record which layout ran with which settings, so without this a figure cannot be explained or reproduced later. `scope` states the limit: work done by hand in the Gephi window is not visible here.

## Import

### gephi_import_file
- **Method**: POST `/import/file`
- **Params**: `{file: str, mode?: "new_workspace"|"append", max_node_size?: float}`
- **Returns**: `{success, node_count, edge_count, import_mode, import_issues?: [{level, message}]}`
- **Notes**: Imports open in their own workspace, so no new project is needed. Auto-detects format by extension. Supports GEXF, GraphML, GML, CSV, DOT, Pajek. By default the file opens in its own workspace, as from Gephi's File > Open, so its time format and id type always fit; an empty workspace left open is removed, and one holding a graph is kept. `mode: "append"` adds the file to the current workspace, and fails when the two disagree on time format or id type; appending a node file attaches its columns to nodes whose ids already exist. An edge CSV with repeated source-target rows is merged on import (weights summed, one row's other values kept); load such rows with `gephi_add_edges` instead. Tell the user about `import_issues` that matter, such as nodes Gephi created because an edge names a node the file does not list.

### gephi_import_gexf
- **Method**: POST `/import/gexf`
- **Params**: `{file: str, mode?: "new_workspace"|"append"}`, as `gephi_import_file`

### gephi_import_graphml
- **Method**: POST `/import/graphml`
- **Params**: `{file: str, mode?: "new_workspace"|"append"}`, as `gephi_import_file`

### gephi_import_csv
- **Method**: POST `/import/csv`
- **Params**: `{file: str, mode?: "new_workspace"|"append"}`, as `gephi_import_file`

## Text Network Analysis

### gephi_text_to_network
- **Method**: builds a word co-occurrence graph from free text client-side, loads it via `/graph/nodes/add` and `/graph/edges/add`
- **Params**: `{text: str | list[str], window_size?: int (4), min_edge_weight?: float (0.0), extra_stopwords?: list[str], pos_filter?: "nouns", min_word_frequency?: int (1), merge_phrases?: bool (false), self_referential_threshold?: float (0.5), exclude_self_referential?: bool (false), context_snippets?: int (0), clear_existing?: bool (false)}`
- **Returns**: `{success, stats: {raw_word_count, kept_word_count, unique_words, words_filtered, edge_count, document_count, lemmatization, pos_filter_applied, phrases_detected, self_referential_candidates}, nodes_result, edges_result}`
- **Notes**: adds to the current workspace unless `clear_existing` is true; build in a new workspace (`gephi_new_workspace`) and rebuild there with `clear_existing: true`. Pass a list of strings, not one concatenated string, whenever the input is naturally many separate documents: the co-occurrence window resets at each list item rather than bridging between unrelated documents. Every node also carries a `document_frequency` attribute. Before trusting the result, check `stats.self_referential_candidates` (each entry: `word`, `document_frequency`, `document_ratio`, `peak_document_count`, plus `context` when `context_snippets > 0`): a word appearing in an unusually large share of documents can dominate the graph without discriminating anything, and raw frequency rank alone does not reliably catch it. See references/text-network-analysis.md for the full craft knowledge on stopword handling, window size, and reading community structure.
