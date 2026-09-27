---
name: import-and-explore
description: Import a GEXF, GraphML, GML, CSV, DOT, or Pajek file into its own Gephi workspace, profile it, style it, lay it out, and present an initial evidence-aware exploration.
---

# Import & Explore

Import a graph file into Gephi, run initial analysis, apply styling, and present an overview.

Follow the `gephi` skill's rules throughout; this workflow repeats only the ones
it is most likely to break.
Read `../gephi/references/layout-guide.md` before the
layout step and `../gephi/references/change-over-time.md`
when the data has time columns.

**Tell the user what you are doing at each step.** Narrate briefly before each tool call.

## Rules this workflow must keep

- **Asking.** When a step says to ask, ask once. If the person cannot answer, is away, or asked for a finished product, use the default named in that step and remove or overwrite nothing. At the end, give one short line for each choice that changed the result, under "Choices I made"; leave the section out when every step used its obvious default. If there is no input to work on, stop and say what is needed.
- **Importing.** Imports open in their own workspace, so no new project is needed. Never create or open a project over unsaved work; save it first or ask.
- **Stability.** Run `gephi_community_stability` before naming, captioning, or colouring by groups, and say how stable they are.
- **Filtering.** `gephi_apply_filter` and `gephi_apply_filters` hide nodes and change nothing; `gephi_reset_filters` shows them again. Pass `dry_run` to count what a filter would hide or remove before running it. The remove and extract tools delete, keep one undo level, and have no redo; for an experiment, duplicate the workspace first.

## Steps

1. **Health check**: Call `gephi_health_check`. If it fails, tell the user to start Gephi and stop. If the request holds no file path, ask for one; there is no default, so stop until a path is given.

2. **Import file**: Call `gephi_import_file` with the path supplied in the request. It opens the file in a new workspace, so the work already open stays as it was. Supported formats: GEXF, GraphML, GML, CSV, DOT, and Pajek.

3. **The intake question** (skip if they already told you): in one friendly
   question, ask what the nodes and connections are and what they hope to
   learn. Their answer sets the vocabulary for everything you present, and
   their expectations become hypotheses to test rather than assumptions.
   Default: use the file's own column names as the vocabulary and explore
   without prior hypotheses.

4. **Profile**: Call `gephi_profile_graph` (one call, the full quantitative
   picture). Give a short plain-language first reading that combines their
   description with the numbers, then ask the two or three questions the
   profile raises (its `flags` are candidates: isolates, fragmentation, hub
   dominance). Default: keep every node and continue with the whole graph.

5. **Let the intake and profile guide what follows.** Do not run a fixed
   recipe:
   - Time data (`gephi_get_timeline` shows `graph_is_dynamic`) or a date
     column: offer to compare periods (see the change-over-time reference).
     Default: explore the whole period at once.
   - Isolates or fragmentation: ask before removing anything (their "data
     problem" may be their finding). Default: keep them and report how many
     there are.
   - Their stated interest picks the metric (brokers or gatekeepers ->
     betweenness; influence or reach -> degree or PageRank; roles -> the
     similarity layout).
   - If they named an attribute they expect to organize the network, test it
     against the partition baseline before coloring by it; prefer detected
     communities when their attribute fails, and say so plainly.
   - Size and density pick the layout per the layout guide's purpose table.
   - Caption clusters in their vocabulary, not in cluster numbers.

6. **Style the graph** (guided by the above):
   - Communities: `gephi_compute_modularity` (resolution 1.0), then `gephi_community_stability`, and say how stable the groups are.
   - Color by community: `gephi_color_by_partition` with column `"modularity_class"` (or `stable_core` when the stability check warned), leaving `colors` unset so the plugin applies its validated palette, largest group first.
   - Size by degree: `gephi_size_by_ranking` with column `"degree"` and the default sizes (about one to ten on screen).

7. **Layout**: Tell the user: "Running ForceAtlas 2 layout..." Call `gephi_run_layout` with algorithm `"ForceAtlas 2"` in two passes with `sync: true`: first 1500 iterations with properties `{"linLogMode": false, "scalingRatio": 10, "strongGravityMode": true, "gravity": 0.01, "barnesHutOptimization": true}`, then 3000 iterations with `{"linLogMode": true, "scalingRatio": 0.5, "strongGravityMode": true, "gravity": 0.001, "barnesHutOptimization": true}` (see the layout guide). Leave Dissuade Hubs off.

8. **Report**: Summarize:
   - Graph size (nodes, edges)
   - Graph type (directed or undirected)
   - Number of communities found, and how stable they are
   - Number of connected components
   - Average degree
   - Choices I made, one short line per choice that changed the result (leave out if none)
   - Ready for further analysis: suggest next steps (centrality, export, and so on)
