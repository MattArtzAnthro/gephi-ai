---
description: Export the current map as clean and labeled PNG plus SVG
argument-hint: "[output-path]"
allowed-tools: mcp__plugin_gephi-network-analysis_gephi-mcp__*, Skill
---

# Export Map

Export the map currently open in Gephi: a clean PNG, a labeled PNG, an SVG, a
legend when colour encodes groups, and a copy-ready caption. This command
exports; it does not lay out or style. The map has to be a map first (laid out,
sized, colored), which `/visualize` or `/analyze-network` does.

Read `${CLAUDE_PLUGIN_ROOT}/skills/gephi/references/reading-network-maps.md` for
the caption discipline.

**Tell the user what you are doing at each step.** Narrate briefly before each tool call so they know what is happening.

## Rules this command must keep

- **Asking.** When a step says to ask, ask once. If the person cannot answer, is away, or asked for a finished product, use the default named in that step and remove or overwrite nothing. At the end, give one short line for each choice that changed the result, under "Choices I made"; leave the section out when every step used its obvious default. If there is no input to work on, stop and say what is needed.
- **Session start.** Start with `gephi_health_check`. Then check which workspace is open (`gephi_list_workspaces`) and whether a filter is active (`filter_active` in replies): a filter from an earlier conversation stays on, and exports and checks then see only what it shows.
- **Caption and legend.** Every export ships with a copy-ready caption (data, layout and settings, what size and colour encode, what the map does and does not show) and, when colour encodes groups, a legend (`gephi_export_legend`).
- **Edges.** On a light background, edges use `{"edge.color": "#D0D0D0", "edge.opacity": 90, "edge.thickness": 1.0, "edge.curved": false}`. Label settings change labels only; they never reset edge values.

## Steps

1. **Load the gephi skill first.** Before any Gephi call, load the `gephi-network-analysis:gephi` skill. Its rules apply to every step below; this command repeats only the ones it is most likely to break.

2. **Session start**: Call `gephi_health_check`. If it fails, tell the user to start Gephi and stop. Call `gephi_list_workspaces` and `gephi_get_project_info`. Tell the user the node and edge counts and which workspace will be exported. If the graph is empty, stop and tell them. If `filter_active` is true, say that the export will show only the visible nodes, and put that in the caption.

3. **Is it a map yet?** Call `gephi_visual_qa` (with the partition column if the
   graph has one). If its `warnings` include the "looks untouched" warning, or
   `sizes.flat` is true and `colors.distinct` is 1, the graph has been loaded
   but not laid out or styled: exporting at this point produces the block of overlapping
   default nodes. Say that, and offer the recommended path: run `/visualize`
   (layout, sizes, colors, with a visual check) and then export. Ask once
   whether to export anyway. Default: do not export an untouched graph; stop
   and say that `/visualize` comes first. If `visual_qa` returns other warnings
   (invisible sizes, near-white colors, an exploded layout), fix or flag them
   before exporting.

4. **Choose the path.** Use the path in `$ARGUMENTS`. Default: `~/Desktop/network.png`, with the other files beside it.

5. **Set preview settings for clean export** (no labels). Call `gephi_set_preview_settings` with:
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

6. **Export clean PNG**: Call `gephi_export_png` with `file` set to the chosen path, at `width: 3840, height: 2160`.
   Tell the user: "Exporting clean PNG at 4K resolution..."

7. **Enable labels and export annotated version**:
   - Call `gephi_set_preview_settings` with label settings only, so the edges keep the values from step 5:
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

8. **Export SVG**: Call `gephi_export_svg` with `file` set to the same base path with the `.svg` extension.
   Tell the user: "Exporting SVG for vector editing..."

9. **Export the legend** when colour encodes groups: call `gephi_export_legend` with `file` set to the same base path with a `_legend.svg` suffix (the legend is an SVG). It refuses when no colour or size mapping was applied through these tools in this session; then say so and name the colours in the caption instead. If the legend shows numbers rather than names, say so, and suggest writing the earned names to a column and colouring by that column.

10. **Report**: List every exported file path clearly, then give the copy-ready caption: the data, the layout and its key settings, what node size and colour encode, and what the map does and does not show (including any active filter). End with "Choices I made" only for choices that changed the result.

## Important

- The export tools use `file` as the parameter name for the output path, not `path`
- If any export fails, report the error and continue with remaining exports
