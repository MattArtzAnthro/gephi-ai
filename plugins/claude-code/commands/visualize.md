---
description: Take the current graph to a finished map: layout, sizes, colors, visual check, export (dispatches the layout-iterator agent)
argument-hint: "[partition column, e.g. modularity_class]"
allowed-tools: Agent, Task, Skill
---

# Visualize

Take the graph currently open in Gephi to a genuinely good map: real structure
visible, hubs prominent, communities unmistakable, edges informative but quiet,
nothing invisible. This lays out and styles the graph in place; for export alone,
use `/export-map`.

## Rules this command must keep

- **Stability.** Run `gephi_community_stability` before naming, captioning, or colouring by groups, and say how stable they are.
- **Caption and legend.** Every export ships with a copy-ready caption (data, layout and settings, what size and colour encode, what the map does and does not show) and, when colour encodes groups, a legend (`gephi_export_legend`).

## Steps

1. **Load the gephi skill first.** Before any Gephi call, load the `gephi-network-analysis:gephi` skill. Its rules apply to every step below; this command repeats only the ones it is most likely to break.

2. **Dispatch the layout-iterator agent.** It runs the whole run, visual check,
   inspect, and adjust loop in its own context, following
   `${CLAUDE_PLUGIN_ROOT}/skills/gephi/references/layout-guide.md`, so the dozens of
   intermediate exports and diagnoses stay out of this conversation. Pass the
   partition column from `$ARGUMENTS` (if given) so the agent colors by it, after
   checking it is topologically real and stable. If `$ARGUMENTS` is empty, the
   agent picks the grouping (`modularity_class`, else the most category-like
   column, else computes communities).

3. **Relay the result.** Show the export path, the legend path, and the caption,
   and relay any data-truth notes the agent surfaced (a fake grouping, missing
   structure, disconnected components, an active filter) and its short change log.
