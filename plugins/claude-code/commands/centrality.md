---
description: Run centrality analysis and identify the most important nodes
allowed-tools: mcp__plugin_gephi-network-analysis_gephi-mcp__*, Skill
---

# Centrality Analysis Workflow

Run comprehensive centrality analysis to identify the most important and influential nodes in the graph.

Read `${CLAUDE_PLUGIN_ROOT}/skills/gephi/references/statistics-guide.md` before
interpreting scores, and `${CLAUDE_PLUGIN_ROOT}/skills/gephi/references/layout-guide.md`
before the layout step.

**Tell the user what you are doing at each step.** Narrate briefly before each tool call.

## Rules this command must keep

- **Session start.** Start with `gephi_health_check`. Then check which workspace is open (`gephi_list_workspaces`) and whether a filter is active (`filter_active` in replies): a filter from an earlier conversation stays on, and exports and checks then see only what it shows.
- **Ranking.** To rank nodes on a metric, call `gephi_query_nodes` with `column` set to the metric and `min` set to a cutoff, with `limit` 20 or less, and raise or lower the cutoff until about ten nodes match (`matches` gives the total). A large `limit` returns every column of every node and can overflow.
- **No scale-free label.** Never call a heavy-tailed degree distribution "scale-free" or a "power law": those fits are near-indistinguishable from log-normal in practice and smuggle in a universal-law claim (Jacomy 2020; Broido and Clauset 2019). Describe hub dominance as a property of this network.
- **Eigenvector caveat.** Gephi's eigenvector centrality can rank nodes differently from a standard calculation. Never rank on it alone: compare it with PageRank, and report a node as an authority only when the two agree.

## Steps

1. **Load the gephi skill first.** Before any Gephi call, load the `gephi-network-analysis:gephi` skill. Its rules apply to every step below; this command repeats only the ones it is most likely to break.

2. **Session start**: Call `gephi_health_check`. If it fails, tell the user to start Gephi and stop. Call `gephi_list_workspaces` and `gephi_get_project_info` for node and edge counts and graph type. If `filter_active` is true, say that the scores will describe only the visible nodes.

3. **Compute all centrality metrics**:
   - Call `gephi_compute_degree` for degree (number of ties)
   - Call `gephi_compute_betweenness` for betweenness centrality (how often a node sits on the shortest path between others), closeness, and eccentricity
   - Call `gephi_compute_pagerank` for PageRank (importance passed on by important neighbours)
   - Call `gephi_compute_eigenvector` for eigenvector centrality (ties to well-tied nodes)

4. **Rank the top nodes** with the ranking rule, one metric at a time:
   - `gephi_query_nodes` with `column: "degree"`, a `min` cutoff, and `limit: 20`: top 10 by degree (hubs)
   - the same with `column: "betweenesscentrality"`: top 10 by betweenness (bridges)
   - the same with `column: "pageranks"`: top 10 by PageRank (importance)
   - the same with `column: "eigencentrality"`, read only beside PageRank (see the eigenvector caveat)
   - Nodes that appear in several top-10 lists are the key actors.

5. **Visualize by betweenness**: Call `gephi_color_by_ranking` with:
   - column: `"betweenesscentrality"`
   - Light blue to dark red gradient: `r_min: 200, g_min: 220, b_min: 255, r_max: 180, g_max: 0, b_max: 0`

6. **Size by PageRank**: Call `gephi_size_by_ranking` with column `"pageranks"` and the default sizes (about one to ten on screen).

7. **Layout**: Tell the user: "Running ForceAtlas 2 layout..." Call `gephi_run_layout` with algorithm `"ForceAtlas 2"` in two passes with `sync: true`: first 1500 iterations with properties `{"linLogMode": false, "scalingRatio": 10, "strongGravityMode": true, "gravity": 0.01, "barnesHutOptimization": true}`, then 3000 iterations with `{"linLogMode": true, "scalingRatio": 0.5, "strongGravityMode": true, "gravity": 0.001, "barnesHutOptimization": true}` (see the layout guide). Leave Dissuade Hubs off.

8. **Measure vulnerabilities**: For the top two or three bridges, call `gephi_whatif` with `[{"op": "remove_node", "id": "<id>"}]`, one node per call. It works on a scratch copy and never changes the real graph. Report the change in components and giant-component share for each. Also remove the next-ranked comparable node: the effect belongs to the bridge only if it clearly exceeds that comparison.

9. **Report**: Present a ranked table of key nodes with their centrality scores. Highlight:
   - **Hubs**: High degree nodes
   - **Bridges**: High betweenness, low degree (connecting different communities)
   - **Authorities**: High PageRank, with eigenvector centrality agreeing
   - **Vulnerabilities**: Nodes whose removal fragments the network, with the `gephi_whatif` numbers from step 8
