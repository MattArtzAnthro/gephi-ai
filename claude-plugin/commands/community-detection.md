---
description: Run full community detection workflow on the current graph
argument-hint: "[louvain|leiden] [resolution]"
allowed-tools: mcp__gephi-mcp__*
---

# Community Detection Workflow

Run a complete community detection and visualization workflow on the current Gephi graph.

**Tell the user what you're doing at each step** — narrate briefly before each tool call.

## Steps

1. **Health check**: Call `gephi_health_check`. If it fails, tell the user to start Gephi and stop.

2. **Graph info**: Call `gephi_get_project_info`. Tell the user the node/edge counts.

3. **Ask which kind of community** (skip if `$ARGUMENTS` names an algorithm or
   the user already said). One question, two real options and one honest note:

   - **Louvain** (Gephi's built-in Modularity): a *descriptive* breakdown of how
     the observed edges cluster. Fast, familiar, communities of fairly even size.
     The default; fine for getting a discursive hold on the structure.
   - **Leiden**: also descriptive, technically better (guarantees connected
     communities, more robust to resolution), and it tends to return partitions
     that are *less* even in size, which is more faithful but can be less
     tractable (very small and very large communities are hard to use).
     Requires the CWTS Leiden plugin in Gephi; check `gephi_list_statistics`
     for `"Leiden algorithm"` before offering it as available.
   - **Statistical inference (Peixoto's stochastic block model)** posits a
     generative model and finds the partition that best explains the observed
     edges; it will *not* find communities in a random graph, where Louvain and
     Leiden always will. It is not available in Gephi. If the user wants
     communities in the sense of an underlying process rather than a
     descriptive reduction, say so plainly and point to graph-tool
     (`minimize_blockmodel_dl`) outside this workflow.

   Frame the choice as: do you want communities as the realization of an
   underlying process (inference), or as a descriptive reduction of the edge
   distribution (Louvain or Leiden)?

4. **Compute communities**:
   - Louvain: call `gephi_compute_modularity` with resolution `$ARGUMENTS`
     resolution (default 1.0). Note Gephi's resolution runs *opposite* to the
     gamma convention in most papers: raising it merges communities.
   - Leiden: call `gephi_run_statistic` with `name="Leiden algorithm"` and
     `params={"algorithm": "Leiden", "qualityFunction": "Modularity",
     "resolution": <resolution>}`; the result column is what the plugin
     reports (check `gephi_get_columns` and use that name in step 6).
   Tell the user: "Running community detection..." then report the modularity
   score and number of communities.

5. **Compute degree**: Call `gephi_compute_degree`. Tell the user: "Computing degree distribution..."

6. **Color by community**: Call `gephi_color_by_partition` with the community column (`"modularity_class"` for Louvain; the Leiden plugin's column otherwise) and the validated palette (readable on white exports, colorblind-safe):
   ```json
   {
     "column": "modularity_class",
     "colors": {
       "0": [42, 120, 214],
       "1": [27, 175, 122],
       "2": [237, 161, 0],
       "3": [0, 131, 0],
       "4": [74, 58, 167],
       "5": [227, 73, 72],
       "6": [232, 123, 164],
       "7": [235, 104, 52]
     }
   }
   ```
   With more than 8 communities, color the 8 largest and set the rest to gray [153,153,153].

7. **Size by degree**: Call `gephi_size_by_ranking` with column `"degree"`, `min_size: 3`, `max_size: 25`.

8. **Layout**: Tell the user: "Running ForceAtlas 2 layout..." Call `gephi_run_layout` with algorithm `"ForceAtlas 2"`, 1500 iterations, and properties `{"scalingRatio": 200, "linLogMode": true, "gravity": 1.0, "barnesHutOptimize": true}`.

9. **Report results**: Summarize the communities found, their sizes (query nodes to count per community), and the overall modularity score.
