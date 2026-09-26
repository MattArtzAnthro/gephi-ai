---
name: visualize-network
description: Turn the graph currently open in Gephi into a clean, legible, publication-ready map through a measured layout, visual-QA, inspection, and adjustment loop. Use for visualize, lay out, style, make this readable, or make this publication-ready.
---

# Visualize a Network

Style and lay out the live graph in place. The goal is a map where real structure
is visible, hubs are legible, edges are informative but quiet, and nothing is
accidentally invisible.

Follow the `gephi` skill's rules throughout; this workflow repeats only the ones
it is most likely to break. Read `../gephi/references/layout-guide.md` for layout
selection and its symptom-to-fix table. Read
`../gephi/references/reading-network-maps.md` for the caption and interpretation
discipline.

## Rules this workflow must keep

- **Session start.** Start with `gephi_health_check`. Then check which workspace is open (`gephi_list_workspaces`) and whether a filter is active (`filter_active` in replies): a filter from an earlier conversation stays on, and exports and checks then see only what it shows.
- **Stability.** Run `gephi_community_stability` before naming, captioning, or colouring by groups, and say how stable they are.
- **Palette.** On a light background, leave `colors` unset: the plugin gives the largest group the first of eight colours validated for readability, the next largest the second, and so on, in an order that keeps the five largest groups distinguishable wherever they touch, even for colour-blind readers; past five groups, label the groups as well. On a dark background, pass the dark-surface palette. Colour must never be the only way to tell groups apart: label the largest nodes or the groups.
  Dark-surface palette, keyed largest group first:
  `{"0":[57,135,229],"1":[201,133,0],"2":[0,131,0],"3":[213,81,129],"4":[144,133,233],"5":[230,103,103],"6":[25,158,112],"7":[217,89,38]}`
- **Edges.** On a light background, edges use `{"edge.color": "#D0D0D0", "edge.opacity": 90, "edge.thickness": 1.0, "edge.curved": false}`. Label settings change labels only; they never reset edge values.
- **Caption and legend.** Every export ships with a copy-ready caption (data, layout and settings, what size and colour encode, what the map does and does not show) and, when colour encodes groups, a legend (`gephi_export_legend`).

## Iterative Loop

1. **Health and baseline.** Call `gephi_health_check`, then
   `gephi_list_workspaces`, `gephi_get_graph_stats`, and `gephi_visual_qa`. Stop
   if Gephi is unavailable or the graph is empty. If `filter_active` is true, the
   map shows only the visible nodes; say so in the caption. Use a requested
   partition column; otherwise prefer `modularity_class`, a clearly categorical
   column, or computed communities.
2. **Data-truth gate.** Run `gephi_visual_qa` with the partition column. If its
   verdict is `none`, do not color by that attribute. Compute communities with
   `gephi_compute_modularity` and use `modularity_class`, or proceed without
   community color. Before colouring by computed communities, run
   `gephi_community_stability`; if it warns, color by `stable_core` instead.
3. **Style.** Compute degree if needed. Color by the partition with `colors`
   unset (the palette rule), size nodes by degree with the default sizes (about
   one to ten on screen; pass `cap` when a few nodes dwarf the rest, and say so in
   the caption), and set the edge values above. Draw edges in that light
   neutral, straight unless direction matters; source-colored edges are a
   deliberate choice, not a default.
4. **Layout.** Run the layout selected by the layout guide. For ForceAtlas 2, use
   synchronous execution and two passes (LinLog off to tune, then LinLog on with
   scalingRatio divided by about 20), small strong gravity, Dissuade Hubs off, and
   measured weight handling. Finish with Noverlap.
5. **Inspect.** Run `gephi_visual_qa`, export a small diagnostic PNG, and inspect
   it. Check overview separation and close-up node legibility.
6. **Adjust one variable.** Diagnose the symptom, change exactly one layout or
   preview parameter, rerun a short pass, and measure again. Repeat up to three
   times or until the QA warnings are resolved and both zoom levels read well.
7. **Label and export.** Add cluster captions only for groups that passed the
   stability check and have evidence-based names. Use `extent.suggested_export`
   for the canvas, scale up for publication, and export to the requested
   destination (default: the Desktop), with the legend from
   `gephi_export_legend` when colour encodes groups. Offer `gephi_view_graph`
   when the host supports MCP Apps.

Do not stop after the first successful layout call; success means a visually and
numerically checked result. If a layout explodes or any coordinates become
non-finite, reset with Random Layout and restart the loop.

## Boundaries

- Mutate layout and style, never nodes, edges, or attributes used as source data.
- Never color by an unverified grouping.
- Never claim scale-free or power-law structure in the caption.

## Deliverable

Return the export path, the legend path, the copy-ready caption, a short change
log naming each adjustment and why it was made, and notes about any false
grouping, missing structure, filters, or disconnected components surfaced by QA.
