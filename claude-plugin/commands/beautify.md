---
description: Iterate on the current graph's visual design until it is publication-ready
argument-hint: "[partition column, e.g. modularity_class]"
allowed-tools: mcp__gephi-mcp__*, Read, Bash
---

# Beautify Workflow

Take the graph currently open in Gephi and iterate on its visual design until it is
genuinely good: real structure visible, hubs prominent, communities unmistakable,
edges informative but quiet, nothing invisible. Follow the loop below; it encodes the
lessons in the gephi skill and references/layout-guide.md.

**Tell the user what you're doing at each step** — narrate briefly, and after each
inspection say what you saw and what you're changing.

## The loop

1. **Baseline.** `gephi_get_graph_stats`, then `gephi_visual_qa` (pass the partition
   column from $ARGUMENTS if given, else try `modularity_class`, else the most
   category-like node column). Export a baseline PNG and look at it (Read the file).

2. **Data-truth gate.** If the partition verdict is "none", STOP styling by that
   column: tell the user the grouping does not match the topology, and either run
   `gephi_compute_modularity` (resolution 1.0) and use `modularity_class`, or ask
   whether to proceed without community coloring. Never color by a fake grouping.

3. **Style.**
   - `gephi_color_by_partition` with the validated palette from the skill (8 colors;
     gray extras beyond 8).
   - `gephi_size_by_ranking` on degree (or a better ranking if one exists), min 10-12,
     max 55-70 depending on node count.
   - `gephi_set_preview_settings`: `edge.opacity` 30, `edge.thickness` 1.5,
     `edge.color` "source", `arrow.size` 0, `node.border.width` 1,
     `node.label.show` false (labels only if they carry meaning and the graph is
     small enough to read them).

4. **Layout.** ForceAtlas 2, `linLogMode` true, `gravity` 0 (0.5 only if components
   drift), `scalingRatio` 2-10 by size, sync true, 800-1500 iterations. Then Noverlap
   (margin 4-6).

5. **Inspect and adjust.** `gephi_visual_qa` again, export a small PNG, Read it, and
   diagnose with the symptom table in references/layout-guide.md. Fix every QA
   warning; change ONE layout parameter per rerun. Repeat up to 3 times or until both
   zoom levels read well (distinct regions in overview, distinguishable nodes within).

6. **Cluster captions (optional).** If the communities have meaningful names, offer
   `gephi_label_clusters` with a names map — one outlined caption per region, hub-anchored,
   reversible with `restore: true`.

7. **Final export.** Use `extent.suggested_export` from the last QA for the canvas
   dimensions (scale up ~2400 on the long side for publication). Export PNG where the
   user asked (default: their Desktop). In MCP Apps hosts also offer
   `gephi_view_graph` for the interactive version.

8. **Report.** Before/after summary: what the baseline looked like, what changed and
   why, and anything about the data itself the QA surfaced (fake groupings, missing
   structure, disconnected components).
