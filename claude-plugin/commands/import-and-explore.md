---
description: Import a graph file and run an initial exploration with layout and styling
argument-hint: "<file-path>"
allowed-tools: mcp__gephi-mcp__*
---

# Import & Explore

Import a graph file into Gephi, run initial analysis, apply styling, and present an overview.

## Steps

1. **Health check**: Call `gephi_health_check` to confirm Gephi is running.

2. **Create project**: Call `gephi_create_project` to start fresh.

3. **Import file**: Call `gephi_import_file` with the path from `$ARGUMENTS`. Support GEXF, GraphML, GML, CSV, DOT, and Pajek formats.

4. **Get overview**: Call `gephi_get_project_info` and `gephi_get_graph_stats` to report the imported graph size.

5. **Initial analysis**:
   - Call `gephi_compute_degree`
   - Call `gephi_compute_modularity` with resolution 1.0
   - Call `gephi_compute_connected_components`

6. **Remove isolates** (if any): Call `gephi_remove_isolates` if the graph has isolated nodes.

7. **Style the graph**:
   - Color by community: `gephi_color_by_partition` with column `"modularity_class"` and pastel palette
   - Size by degree: `gephi_size_by_ranking` with column `"degree"`, min_size 3, max_size 25

8. **Layout**: Call `gephi_run_layout` with algorithm `"forceatlas2"`, 1000 iterations, properties `{"linLogMode": true, "scalingRatio": 100, "gravity": 1.0, "barnesHutOptimize": true}`.

9. **Report**: Summarize:
   - Graph size (nodes, edges)
   - Graph type (directed/undirected)
   - Number of communities found
   - Number of connected components
   - Average degree
   - Ready for further analysis — suggest next steps (centrality, export, etc.)
