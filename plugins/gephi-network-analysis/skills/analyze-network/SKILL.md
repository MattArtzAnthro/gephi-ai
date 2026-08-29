---
name: analyze-network
description: Run a rigorous structural analysis of the loaded Gephi graph, compare centralities, characterize communities, and report what the data does and does not support. Use for comprehensive network analysis or interpretation rather than one claim or a styling-only task.
---

# Comprehensive Network Analysis

Run a full structural analysis of the current graph and present a detailed report of its properties.

Read `../gephi/references/statistics-guide.md`,
`../gephi/references/reading-network-maps.md`, and
`../gephi/references/claim-verification.md` as needed. These references are
authoritative for interpretation; do not substitute a remembered rule of thumb.

**Tell the user what you're doing at each step** — narrate briefly before each tool call (e.g., "Computing modularity...", "Running centrality analysis...").

## Steps

1. **Health check**: Call `gephi_health_check`. If it fails, tell the user to start Gephi and stop.

2. **The intake question** (skip if already answered in this conversation):
   ask in one sentence what the nodes and ties are and what they want to
   learn. Use their vocabulary in the whole report, and treat their
   expectations as hypotheses the analysis will confirm or contradict.

3. **Profile first**: Call `gephi_profile_graph` (one call — size, density,
   degree distribution, components, isolates, weights, modularity,
   clustering, flags). Open the report with a plain-language first reading
   that combines their description with these numbers, and let the profile
   decide which deeper analyses are worth running rather than running
   everything.

4. **Degree distribution**: Call `gephi_compute_degree`. Query nodes to understand the degree distribution — report min, max, average, and whether it is heavy-tailed (a few high-degree hubs) or even. Do NOT label it "scale-free" or "power-law": those fits are near-indistinguishable from log-normal in practice and smuggle in a universal-law claim (Jacomy 2020). Describe hub dominance as a property of this network, not a law.

5. **Community structure**: Call `gephi_compute_modularity` with resolution 1.0. Report the modularity score and number of communities.

6. **Path analysis**: Call `gephi_compute_avg_path_length` to get average path length, diameter, and radius.

7. **Clustering**: Call `gephi_compute_clustering_coefficient` to measure local cohesion.

8. **Centrality**: Call `gephi_compute_betweenness` and `gephi_compute_pagerank`.

9. **Report**: Present a structured summary:

   ### Network Overview
   - Nodes, edges, density, average degree, graph type

   ### Connectivity
   - Number of components, size of giant component

   ### Community Structure
   - Modularity score, number of communities, interpretation

   ### Small-World Properties
   - Average path length, clustering coefficient, comparison with random network expectations

   ### Key Nodes
   - Top 5 by degree, betweenness, and PageRank

   ### Structural character
   - Describe the network's structure in this-network terms: hub dominance (a few
     nodes concentrate ties) vs. even degree; clustering + path length relative to
     size (small-world-*like*, stated as a comparison, not a label); fragmentation.
     Do NOT slap on universal-law labels ("scale-free") — see step 4.

## Reading pass (after the numbers)

Once statistics are computed and a layout exists, walk the guided reading
process from `../gephi/references/reading-network-maps.md`: state the reading rules
(axes are arbitrary, only distances matter), identify main clusters with
temporary letter names, point out the structural holes and what they imply,
overlay one attribute at a time and compare its distribution to the structure,
inventory the special nodes (bridges via betweenness, within-cluster hubs via
degree, off-color outliers), and only then name clusters in the person's own
vocabulary. Present insights as hypotheses or findings and say which.

Before delivering YOUR reading of a fresh map (and again after an attribute
overlay changes it), ask one concrete question first — "where does your eye go
first?" or "which groups look connected to you?" — then give your reading and
compare the two aloud. Their unprimed look is evidence your fluency would
otherwise erase; the differences between the readings are often the finding.
Skip this on task turns, and drop it for the session if they wave it off.

## Boundaries

- Interpret; do not recolor, relayout, filter destructively, or edit the graph.
- Compare metrics rather than interpreting one in isolation.
- Treat every structural assertion as a claim to check, and pair patterns with
  a rival explanation when the graph cannot distinguish causes.
- Never call a heavy-tailed network scale-free or claim a power law.
