---
description: Take the current graph to a finished map: layout, sizes, colors, visual check, export (dispatches the layout-iterator agent)
argument-hint: "[partition column, e.g. modularity_class]"
allowed-tools: Task
---

# Visualize

Dispatch the **layout-iterator** agent to take the graph currently open in Gephi to a
genuinely good map: real structure visible, hubs prominent, communities unmistakable,
edges informative but quiet, nothing invisible. This lays out and styles the graph in
place; for export alone, use `/export-map`.

The agent runs the whole run → visual_qa → inspect → adjust loop in its own context,
so the dozens of intermediate exports and diagnoses stay out of this conversation. It
returns the finished export, its caption, and a short change log.

Pass the partition column from `$ARGUMENTS` (if given) so the agent colors by it —
after checking it is topologically real. If `$ARGUMENTS` is empty, the agent picks the
grouping (`modularity_class`, else the most category-like column, else computes
communities). When the agent returns, show the export path and caption, and relay any
data-truth notes it surfaced (a fake grouping, missing structure, disconnected
components).
