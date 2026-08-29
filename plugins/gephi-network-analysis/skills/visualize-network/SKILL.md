---
name: visualize-network
description: Turn the graph currently open in Gephi into a clean, legible, publication-ready map through a measured layout, visual-QA, inspection, and adjustment loop. Use for visualize, lay out, style, make this readable, or make this publication-ready.
---

# Visualize a Network

Style and lay out the live graph in place. The goal is a map where real structure
is visible, hubs are legible, edges are informative but quiet, and nothing is
accidentally invisible.

Read `../gephi/references/layout-guide.md` for layout selection and its
symptom-to-fix table. Read `../gephi/references/reading-network-maps.md` for the
caption and interpretation discipline.

## Iterative Loop

1. **Health and baseline.** Call `gephi_health_check`, then
   `gephi_get_graph_stats` and `gephi_visual_qa`. Stop if Gephi is unavailable or
   the graph is empty. Use a requested partition column; otherwise prefer
   `modularity_class`, a clearly categorical column, or computed communities.
2. **Data-truth gate.** Run `gephi_visual_qa` with the partition column. If its
   verdict is `none`, do not color by that attribute. Compute communities with
   `gephi_compute_modularity` and use `modularity_class`, or proceed without
   community color.
3. **Style.** Compute degree if needed. Apply the validated eight-color partition
   palette with gray beyond eight communities, size nodes by degree, and set
   preview defaults from the gephi skill. Use subdued source-colored edges for
   most networks and neutral gray for dense text networks.
4. **Layout.** Run the layout selected by the layout guide. For ForceAtlas 2, use
   synchronous execution, LinLog, size-appropriate scaling, and measured weight
   handling. Finish with Noverlap.
5. **Inspect.** Run `gephi_visual_qa`, export a small diagnostic PNG, and inspect
   it. Check overview separation and close-up node legibility.
6. **Adjust one variable.** Diagnose the symptom, change exactly one layout or
   preview parameter, rerun a short pass, and measure again. Repeat up to three
   times or until the QA warnings are resolved and both zoom levels read well.
7. **Label and export.** Add cluster captions only when they have evidence-based
   names. Use `extent.suggested_export` for the canvas, scale up for publication,
   and export to the requested destination. Offer `gephi_view_graph` when the host
   supports MCP Apps.

Do not stop after the first successful layout call; success means a visually and
numerically checked result. If a layout explodes or any coordinates become
non-finite, reset with Random Layout and restart the loop.

## Boundaries

- Mutate layout and style, never nodes, edges, or attributes used as source data.
- Never color by an unverified grouping.
- Never claim scale-free or power-law structure in the caption.
- Every final export includes copy-ready caption text: data, layout and key
  settings, size/color encodings, and what the map does and does not support.

## Deliverable

Return the export path, caption, a short change log naming each adjustment and why
it was made, and notes about any false grouping, missing structure, filters, or
disconnected components surfaced by QA.
