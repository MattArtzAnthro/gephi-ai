# Gephi MCP Tool Reference

Complete catalog of all MCP tools for controlling Gephi Desktop.

## Health

### gephi_health_check
- **Method**: GET `/health`
- **Params**: None
- **Returns**: `{success, service, version, status}`
- **Usage**: Call first to verify Gephi is running

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

### gephi_export_graphml
- **Method**: POST `/export/graphml`
- **Params**: `{file: str}`

### gephi_export_csv
- **Method**: POST `/export/csv`
- **Params**: `{file: str, separator?: str (","), target?: "nodes"|"edges"|"both"}`

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
