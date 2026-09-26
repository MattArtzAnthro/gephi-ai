---
name: export-map
description: Export the current Gephi map as a clean PNG, labeled PNG, and SVG after checking that it is laid out, styled, and visually valid. Use for publication-ready map export and caption handoff.
---

# Export Map

Export the map currently open in Gephi: a clean PNG, a labeled PNG, an SVG, a
legend when colour encodes groups, and a copy-ready caption. This workflow
exports; it does not lay out or style. The map has to be a map first (laid out,
sized, colored), which the `visualize-network` workflow does.

Follow the `gephi` skill's rules throughout; this workflow repeats only the ones
it is most likely to break.
Read `../gephi/references/reading-network-maps.md` for
the caption discipline.

**Tell the user what you are doing at each step.** Narrate briefly before each tool call so they know what is happening.

## Rules this workflow must keep

- **Asking.** When a step says to ask, ask once. If the person cannot answer, is away, or asked for a finished product, use the default named in that step, remove or overwrite nothing, and list each choice under "Choices I made". If there is no input to work on, stop and say what is needed.
- **Session start.** Start with `gephi_health_check`. Then check which workspace is open (`gephi_list_workspaces`) and whether a filter is active (`filter_active` in replies): a filter from an earlier conversation stays on, and exports and checks then see only what it shows.
- **Caption and legend.** Every export ships with a copy-ready caption (data, layout and settings, what size and colour encode, what the map does and does not show) and, when colour encodes groups, a legend (`gephi_export_legend`).
- **Edges.** On a light background, edges use `{"edge.color": "#D0D0D0", "edge.opacity": 90, "edge.thickness": 1.0, "edge.curved": false}`. Label settings change labels only; they never reset edge values.

## Steps

1. **Session start**: Call `gephi_health_check`. If it fails, tell the user to start Gephi and stop. Call `gephi_list_workspaces` and `gephi_get_project_info`. Tell the user the node and edge counts and which workspace will be exported. If the graph is empty, stop and tell them. If `filter_active` is true, say that the export will show only the visible nodes, and put that in the caption.

2. **Is it a map yet?** Call `gephi_visual_qa` (with the partition column if the
   graph has one). If its `warnings` include the "looks untouched" warning, or
   `sizes.flat` is true and `colors.distinct` is 1, the graph has been loaded
   but not laid out or styled: exporting at this point produces the block of overlapping
   default nodes. Say that, and offer the recommended path: use `visualize-network`
   (layout, sizes, colors, with a visual check) and then export. Ask once
   whether to export anyway. Default: do not export an untouched graph; stop
   and say that `visualize-network` comes first. If `visual_qa` returns other warnings
   (invisible sizes, near-white colors, an exploded layout), fix or flag them
   before exporting.

3. **Choose the path.** Use the path given in the request. Default: `~/Desktop/network.png`, with the other files beside it. Name the path under "Choices I made" when it is the default.

4. **Set preview settings for clean export** (no labels). Call `gephi_set_preview_settings` with:
   ```json
   {
     "node.label.show": false,
     "edge.opacity": 90,
     "edge.curved": false,
     "edge.color": "#D0D0D0",
     "edge.thickness": 1.0,
     "node.opacity": 100,
     "node.border.width": 0.3,
     "arrow.size": 0
   }
   ```
   Tell the user: "Setting preview to clean mode: no labels, light gray edges."

5. **Export clean PNG**: Call `gephi_export_png` with `file` set to the chosen path, at `width: 3840, height: 2160`.
   Tell the user: "Exporting clean PNG at 4K resolution..."

6. **Enable labels and export annotated version**:
   - Call `gephi_set_preview_settings` with label settings only, so the edges keep the values from step 4:
     ```json
     {
       "node.label.show": true,
       "node.label.proportinalSize": false,
       "node.label.font": "Arial 10 Plain",
       "node.label.outline.size": 4,
       "node.label.outline.opacity": 95
     }
     ```
   - Export with a `_labeled` suffix. Tell the user: "Exporting labeled version..."

7. **Export SVG**: Call `gephi_export_svg` with `file` set to the same base path with the `.svg` extension.
   Tell the user: "Exporting SVG for vector editing..."

8. **Export the legend** when colour encodes groups: call `gephi_export_legend` with `file` set to the same base path with a `_legend.svg` suffix (the legend is an SVG). It refuses when no colour or size mapping was applied through these tools in this session; then say so and name the colours in the caption instead. If the legend shows numbers rather than names, say so, and suggest writing the earned names to a column and colouring by that column.

9. **Report**: List every exported file path clearly, then give the copy-ready caption: the data, the layout and its key settings, what node size and colour encode, and what the map does and does not show (including any active filter). End with "Choices I made" when any default was used.

## Important

- The export tools use `file` as the parameter name for the output path, not `path`
- If any export fails, report the error and continue with remaining exports
