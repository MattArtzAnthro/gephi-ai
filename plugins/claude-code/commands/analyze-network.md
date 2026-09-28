---
description: Run comprehensive structural analysis and report network properties
allowed-tools: mcp__plugin_gephi-network-analysis_gephi-ai__*, Skill(gephi-network-analysis:gephi)
---

# Comprehensive Network Analysis

Run a full structural analysis of the current graph and present a detailed report of its properties.

Read `${CLAUDE_PLUGIN_ROOT}/skills/gephi/references/statistics-guide.md`,
`${CLAUDE_PLUGIN_ROOT}/skills/gephi/references/reading-network-maps.md`, and
`${CLAUDE_PLUGIN_ROOT}/skills/gephi/references/claim-verification.md` as needed.
These references are authoritative for interpretation; do not substitute a
remembered rule of thumb.

**Tell the user what you are doing at each step.** Narrate briefly before each tool call (for example, "Computing modularity...", "Running centrality analysis...").

## Rules this command must keep

- **Asking.** When a step says to ask, ask once. If the person cannot answer, is away, or asked for a finished product, use the default named in that step and remove or overwrite nothing. At the end, give one short line for each choice that changed the result, under "Choices I made"; leave the section out when every step used its obvious default. If there is no input to work on, stop and say what is needed.
- **Session start.** Start with `gephi_health_check`. Then check which workspace is open (`gephi_list_workspaces`) and whether a filter is active (`filter_active` in replies): a filter from an earlier conversation stays on, and exports and checks then see only what it shows.
- **Ranking.** To rank nodes on a metric, call `gephi_query_nodes` with `sort_by` set to the metric, `columns` set to the few columns you need, and `limit` about 10: nodes are ordered before paging, so the first page is the top of the whole graph. Without `columns`, every attribute of every node comes back and a long listing can overflow.
- **Stability.** Run `gephi_community_stability` before naming, captioning, or colouring by groups, and say how stable they are.
- **No scale-free label.** Never call a heavy-tailed degree distribution "scale-free" or a "power law": those fits are near-indistinguishable from log-normal in practice and smuggle in a universal-law claim (Jacomy 2020; Broido and Clauset 2019). Describe hub dominance as a property of this network.

## Steps

1. **Load the gephi skill first.** Before any Gephi call, load the `gephi-network-analysis:gephi` skill. Its rules apply to every step below; this command repeats only the ones it is most likely to break.

2. **Session start**: Call `gephi_health_check`. If it fails, tell the user to start Gephi and stop. Then call `gephi_list_workspaces` and note `filter_active` in the replies. If a filter is on, say so before any number is reported, and ask whether to analyze the filtered view or the whole graph (`gephi_reset_filters` shows every node again). Default: leave the filter on, analyze what is visible, and say in the report that a filter was on.

3. **The intake question** (skip if already answered in this conversation):
   ask in one sentence what the nodes and ties are and what they want to
   learn. Use their vocabulary in the whole report, and treat their
   expectations as hypotheses the analysis will confirm or contradict.
   Default: use the graph's own column names as the vocabulary and report
   the structure without prior hypotheses.

4. **Profile first**: Call `gephi_profile_graph` (one call: size, density,
   degree distribution, components, isolates, weights, modularity,
   clustering, flags). Open the report with a plain-language first reading
   that combines their description with these numbers, and let the profile
   decide which deeper analyses are worth running rather than running
   everything.

5. **Degree distribution**: Read it from the profile (minimum, maximum, average, and whether it is heavy-tailed, meaning a few high-degree hubs, or even). Do not query every node for it. Call `gephi_compute_degree` so the `degree` column exists for ranking in step 10.

6. **Community structure**: Call `gephi_compute_modularity` with resolution 1.0, then `gephi_community_stability` to check that the communities hold up. The modularity score alone never shows strong communities.

7. **Path analysis**: Call `gephi_compute_avg_path_length` to get average path length, diameter, and radius. When the user asks about two particular nodes, `gephi_find_shortest_path` gives the path between them and how many equally short paths exist.

8. **Clustering**: Call `gephi_compute_clustering_coefficient` to measure local cohesion (how often a node's neighbours are tied to each other).

9. **Centrality**: Call `gephi_compute_betweenness` and `gephi_compute_pagerank`.

10. **Key nodes**: Rank the top nodes on `degree`, `betweenesscentrality`, and `pageranks` with the ranking rule above: one `gephi_query_nodes` call per metric, `column` and `min` set, `limit` 20 or less.

11. **Report**: Present a structured summary:

    ### Network Overview
    - Nodes, edges, density, average degree, graph type

    ### Connectivity
    - Number of components, size of giant component

    ### Community Structure
    - Number of communities, `mean_stability` in plain words, the stable cores, and the modularity score with that context

    ### Small-World Properties
    - Average path length, clustering coefficient, comparison with random network expectations

    ### Key Nodes
    - Top 5 by degree, betweenness, and PageRank

    ### Structural character
    - Describe the network's structure in this-network terms: hub dominance (a few
      nodes concentrate ties) or even degree; clustering and path length relative to
      size (small-world-*like*, stated as a comparison, not a label); fragmentation.
      No universal-law labels such as "scale-free" (see the rules above).

    ### Choices I made (only if a choice changed the result)
    - One short line per choice that changed the result.

## Reading pass (after the numbers)

Once statistics are computed and a layout exists, walk the guided reading
process from `${CLAUDE_PLUGIN_ROOT}/skills/gephi/references/reading-network-maps.md`:
state the reading rules (axes are arbitrary, only distances matter), identify
main clusters with temporary letter names, point out the structural holes and
what they imply, overlay one attribute at a time and compare its distribution to
the structure, inventory the special nodes (bridges via betweenness,
within-cluster hubs via degree, off-color outliers), and only then name clusters
in the person's own vocabulary, after the stability check. Present insights as
hypotheses or findings and say which.

Before delivering YOUR reading of a fresh map (and again after an attribute
overlay changes it), ask one concrete question first ("where does your eye go
first?" or "which groups look connected to you?"), then give your reading and
compare the two aloud. Their unprimed look is evidence your fluency would
otherwise erase; the differences between the readings are often the finding.
Skip this on task turns, and drop it for the session if they wave it off.
Default: give your reading directly.
