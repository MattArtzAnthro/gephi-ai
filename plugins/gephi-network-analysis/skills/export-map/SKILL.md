---
name: export-map
description: Export the current Gephi map as a clean PNG, labeled PNG, and SVG after checking that it is laid out, styled, and visually valid. Use for publication-ready map export and caption handoff.
---

# Export Map

Export the map currently open in Gephi: a clean PNG, a labeled PNG, and an SVG.
This command exports; it does not lay out or style. The map has to be a map
first (laid out, sized, colored), which the `visualize-network` workflow does.

**Tell the user what you're doing at each step** — narrate briefly before each tool call so they know what's happening.

## Steps

1. **Health check**: Call `gephi_health_check`. If it fails, tell the user to start Gephi and stop.

2. **Graph info**: Call `gephi_get_project_info`. Tell the user the node/edge counts. If the graph is empty, stop and tell them.

3. **Is it a map yet?** Call `gephi_visual_qa` (with the partition column if the
   graph has one). If its `warnings` include the "looks untouched" warning, or
   `sizes.flat` is true and `colors.distinct` is 1, the graph has been loaded
   but not laid out or styled: exporting now produces the block of overlapping
   default nodes. Say that, and offer the recommended path: use `visualize-network`
   (layout, sizes, colors, with a visual check) and then export. Only continue
   without it if the user says so. If `visual_qa` returns other warnings (invisible
   sizes, near-white colors, an exploded layout), fix or flag them before exporting.

4. **Set preview settings for clean export** (no labels). Call `gephi_set_preview_settings` with:
   ```json
   {
     "node.label.show": false,
     "edge.opacity": 25,
     "edge.curved": true,
     "edge.color": "source",
     "edge.thickness": 2.0,
     "node.opacity": 100,
     "node.border.width": 0.3,
     "arrow.size": 0
   }
   ```
   Tell the user: "Setting preview to clean mode — no labels, community-colored edges."

5. **Export clean PNG**: Call `gephi_export_png` with `file` set to the user's path or `~/Desktop/network.png`, at `width: 3840, height: 2160`.
   Tell the user: "Exporting clean PNG at 4K resolution..."

6. **Enable labels and export annotated version**:
   - Call `gephi_set_preview_settings` with:
     ```json
     {
       "node.label.show": true,
       "node.label.proportinalSize": false,
       "node.label.font": "Arial 10 Plain",
       "node.label.outline.size": 4,
       "node.label.outline.opacity": 95,
       "edge.opacity": 15
     }
     ```
   - Export with `_labeled` suffix. Tell the user: "Exporting labeled version..."

7. **Export SVG**: Call `gephi_export_svg` with `file` set to the same base path with `.svg` extension.
   Tell the user: "Exporting SVG for vector editing..."

8. **Report**: List all exported file paths clearly.

## Important

- The export tools use `file` as the parameter name for the output path, not `path`
- If any export fails, report the error and continue with remaining exports
