---
name: community-detection
description: Detect, validate, visualize, and explain communities in the loaded Gephi graph using Louvain or an installed Leiden statistic. Use for community detection, modularity, cluster coloring, or resolution comparisons.
---

# Community Detection Workflow

Run a complete community detection and visualization workflow on the current Gephi graph.

Follow the `gephi` skill's rules throughout; this workflow repeats only the ones
it is most likely to break.
Read `../gephi/references/statistics-guide.md` before
interpreting modularity, and `../gephi/references/layout-guide.md`
before the layout step.

**Tell the user what you are doing at each step.** Narrate briefly before each tool call.

## Rules this workflow must keep

- **Asking.** When a step says to ask, ask once. If the person cannot answer, is away, or asked for a finished product, use the default named in that step, remove or overwrite nothing, and list each choice under "Choices I made". If there is no input to work on, stop and say what is needed.
- **Session start.** Start with `gephi_health_check`. Then check which workspace is open (`gephi_list_workspaces`) and whether a filter is active (`filter_active` in replies): a filter from an earlier conversation stays on, and exports and checks then see only what it shows.
- **Stability.** Run `gephi_community_stability` before naming, captioning, or colouring by groups, and say how stable they are.
- **Palette.** On a light background, leave `colors` unset: the plugin gives the largest group the first of eight colours validated for readability, the next largest the second, and so on, in an order that keeps the five largest groups distinguishable wherever they touch, even for colour-blind readers; past five groups, label the groups as well. On a dark background, pass the dark-surface palette. Colour must never be the only way to tell groups apart: label the largest nodes or the groups.

## Steps

1. **Session start**: Call `gephi_health_check`. If it fails, tell the user to start Gephi and stop. Call `gephi_list_workspaces` and `gephi_get_project_info`, and tell the user the node and edge counts. If `filter_active` is true, say that communities will be found in the visible nodes only.

2. **Ask which method** (skip if the request names one or the user already
   said). One question, with the trade-off stated plainly. Default: Louvain at
   resolution 1.0.

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

3. **Compute communities**:
   - Louvain: call `gephi_compute_modularity` with the requested
     resolution (default 1.0). Gephi's resolution runs *opposite* to the
     gamma convention in most papers: raising it merges communities.
   - Leiden: call `gephi_run_statistic` with `name="Leiden algorithm"` and
     `params={"algorithm": "Leiden", "qualityFunction": "Modularity",
     "resolution": <resolution>}`; the result column is what the plugin
     reports (check `gephi_get_columns` and use that name in step 5).
   Tell the user: "Running community detection..." then report the number of
   communities. Do not call the partition strong or weak from the modularity
   score: random graphs with the same degrees score 0.3 to 0.6.

   **Check that the communities hold up**: call `gephi_community_stability`
   (Louvain only; 20 runs). Tell the user in plain words how often accounts
   grouped together stay together (`mean_stability`) and how many stable cores
   there are. If `consensus_warning` appears, say the communities are loose and
   color by `stable_core` in step 5 instead of the single run.

4. **Compute degree**: Call `gephi_compute_degree`. Tell the user: "Computing degree distribution..."

5. **Color by community**: Call `gephi_color_by_partition` with the community column (`"modularity_class"` for Louvain, `stable_core` when the stability check warned, the Leiden plugin's column otherwise). Leave `colors` unset on a light background (see the palette rule); past eight groups the reply carries a `palette_note`, which the report repeats.

6. **Size by degree**: Call `gephi_size_by_ranking` with column `"degree"` and the default sizes (about one to ten on screen).

7. **Layout**: Tell the user: "Running ForceAtlas 2 layout..." Call `gephi_run_layout` with algorithm `"ForceAtlas 2"` in two passes with `sync: true`: first 1500 iterations with properties `{"linLogMode": false, "scalingRatio": 10, "strongGravityMode": true, "gravity": 0.01, "barnesHutOptimization": true}`, then 3000 iterations with `{"linLogMode": true, "scalingRatio": 0.5, "strongGravityMode": true, "gravity": 0.001, "barnesHutOptimization": true}` (see the layout guide). Leave Dissuade Hubs off.

8. **Report results**: Summarize the communities found, their sizes (`gephi_column_value_frequencies` on the community column counts members per community), and how well they held up across runs. Give the modularity score only with its context, never as a verdict. Name only communities that are stable cores. End with "Choices I made" when any default was used.
