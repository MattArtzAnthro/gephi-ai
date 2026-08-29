---
name: explore-network
description: Explore the graph already open in Gephi through intake, profiling, goal-directed analysis, styling, layout, and an overview. Use when the user has a graph loaded and wants an initial guided exploration without importing a file.
---

# Explore

Run the initial exploration on the graph in the current Gephi workspace. This
is the import-and-explore workflow without the import step: open the file in Gephi first
(File > Open, or a Data Laboratory import), then run this. No file path is
needed.

**Tell the user what you're doing at each step** — narrate briefly before each tool call.

## Steps

1. **Health check**: Call `gephi_health_check`. If it fails, tell the user to start Gephi and stop.

2. **Confirm there is a graph**: Call `gephi_get_project_info`. If there is no project or the graph is empty, say so and suggest opening a file in Gephi or using the `import-and-explore` skill with a path; stop.

3. **The intake question** (skip if they already told you): in one friendly
   question, ask what the nodes and connections are and what they hope to
   learn. Their answer sets the vocabulary for everything you present, and
   their expectations become hypotheses to test rather than assumptions.

4. **Profile**: Call `gephi_profile_graph` (one call, the full quantitative
   picture). Give a short plain-language first reading that combines their
   description with the numbers, then ask the two or three questions the
   profile raises (its `flags` are candidates: isolates, fragmentation, hub
   dominance).

5. **Let the intake + profile guide what follows** — do not run a fixed
   recipe:
   - Isolates or fragmentation: ask before removing anything (their "data
     problem" may be their finding).
   - Their stated interest picks the metric (brokers/gatekeepers ->
     betweenness; influence/reach -> degree or PageRank; roles -> the
     similarity layout).
   - If they named an attribute they expect to organize the network, test it
     against the partition baseline before coloring by it; prefer detected
     communities when their attribute fails, and say so plainly.
   - Size and density pick the layout per the layout guide's purpose table.
   - Caption clusters in their vocabulary, not in cluster numbers.

6. **Style the graph** (guided by the above):
   - Color by community: `gephi_color_by_partition` with column `"modularity_class"` and the validated palette (see skill reference)
   - Size by degree: `gephi_size_by_ranking` with column `"degree"`, min_size 3, max_size 25

7. **Layout**: Tell the user: "Running ForceAtlas 2 layout..." Call `gephi_run_layout` with algorithm `"ForceAtlas 2"`, 1000 iterations, properties `{"linLogMode": true, "scalingRatio": 100, "gravity": 1.0, "barnesHutOptimize": true}`.

8. **Report**: Summarize:
   - Graph size (nodes, edges)
   - Graph type (directed/undirected)
   - Number of communities found
   - Number of connected components
   - Average degree
   - Ready for further analysis — suggest next steps (centrality, export, etc.)
