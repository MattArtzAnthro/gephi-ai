---
description: Run full community detection workflow on the current graph
argument-hint: "[resolution]"
allowed-tools: mcp__gephi-mcp__*
---

# Community Detection Workflow

Run a complete community detection and visualization workflow on the current Gephi graph.

**Tell the user what you're doing at each step** — narrate briefly before each tool call.

## Steps

1. **Health check**: Call `gephi_health_check`. If it fails, tell the user to start Gephi and stop.

2. **Graph info**: Call `gephi_get_project_info`. Tell the user the node/edge counts.

3. **Compute modularity**: Call `gephi_compute_modularity` with resolution `$ARGUMENTS[0]` (default 1.0). Tell the user: "Running community detection..." then report the modularity score and number of communities.

4. **Compute degree**: Call `gephi_compute_degree`. Tell the user: "Computing degree distribution..."

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

7. **Layout**: Tell the user: "Running ForceAtlas 2 layout..." Call `gephi_run_layout` with algorithm `"ForceAtlas 2"`, 1500 iterations, and properties `{"scalingRatio": 200, "linLogMode": true, "gravity": 1.0, "barnesHutOptimize": true}`.

8. **Report results**: Summarize the communities found, their sizes (query nodes to count per community), and the overall modularity score.
