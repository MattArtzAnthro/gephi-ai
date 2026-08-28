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

3. **Ask which method** (skip if `$ARGUMENTS` names one or the user already
   said). One question, with the trade-off stated plainly:

   - **Louvain** (Gephi's built-in Modularity; Blondel et al. 2008): maximizes
     modularity by greedy local moves. Fast and familiar; the default.
   - **Leiden** (Traag, Waltman, and van Eck 2019): the same objective with a
     refinement step that guarantees every community is internally connected
     and converges more reliably. Its partitions can be more uneven in size.
     Requires the CWTS Leiden plugin in Gephi; check `gephi_list_statistics`
     for `"Leiden algorithm"` before offering it as available.
   - **Stochastic block model inference** (Peixoto 2019): fits a generative
     model of the edges and selects the partition that best explains them,
     with model selection that returns a single block when the data support no
     structure. Modularity maximization has no such check and returns a
     partition for any graph, including a random one. SBM inference is not
     implemented in Gephi; if the user wants it, say so and point to graph-tool
     (`minimize_blockmodel_dl`) outside this workflow.

   Frame the choice as: modularity maximization gives a partition that
   describes how the observed edges cluster; SBM inference tests whether a
   block structure is supported at all. Cite the papers in the caption
   when the map is publication-bound.

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
