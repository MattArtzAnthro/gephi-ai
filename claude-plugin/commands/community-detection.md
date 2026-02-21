---
description: Run full community detection workflow on the current graph
argument-hint: "[resolution]"
allowed-tools: mcp__gephi-mcp__*
---

# Community Detection Workflow

Run a complete community detection and visualization workflow on the current Gephi graph.

## Steps

1. **Health check**: Call `gephi_health_check` to confirm Gephi is running. Abort with a clear message if it is not.

2. **Graph info**: Call `gephi_get_project_info` to get node/edge counts. Report the graph size to the user.

3. **Compute modularity**: Call `gephi_compute_modularity` with resolution `$ARGUMENTS[0]` (default to 1.0 if no argument provided). Report the modularity score and number of communities found.

4. **Compute degree**: Call `gephi_compute_degree` to create the degree attribute for sizing.

5. **Color by community**: Call `gephi_color_by_partition` with column `"modularity_class"` and this pastel palette:
   ```json
   {
     "column": "modularity_class",
     "colors": {
       "0": [212, 222, 99],
       "1": [227, 185, 216],
       "2": [89, 238, 200],
       "3": [154, 226, 255],
       "4": [255, 171, 125],
       "5": [255, 173, 203],
       "6": [255, 220, 130],
       "7": [190, 170, 230]
     }
   }
   ```

6. **Size by degree**: Call `gephi_size_by_ranking` with column `"degree"`, `min_size: 3`, `max_size: 25`.

7. **Layout**: Call `gephi_run_layout` with algorithm `"forceatlas2"`, 1500 iterations, and properties `{"scalingRatio": 200, "linLogMode": true, "gravity": 1.0, "barnesHutOptimize": true}`.

8. **Report results**: Summarize the communities found, their sizes (query nodes to count per community), and the overall modularity score.
