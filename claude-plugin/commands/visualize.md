---
description: Apply publication-ready styling and export the current graph
argument-hint: "[output-path]"
allowed-tools: mcp__gephi-mcp__*
---

# Publication-Ready Visualization & Export

Apply publication-quality styling to the current graph and export in multiple formats.

**Tell the user what you're doing at each step** — narrate briefly before each tool call so they know what's happening.

## Steps

1. **Health check**: Call `gephi_health_check`. If it fails, tell the user to start Gephi and stop.

2. **Graph info**: Call `gephi_get_project_info`. Tell the user the node/edge counts. If the graph is empty, stop and tell them.

3. **Set preview settings for clean export** (no labels). Call `gephi_set_preview_settings` with:
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

4. **Export clean PNG**: Call `gephi_export_png` with `file` set to the user's path or `~/Desktop/network.png`, at `width: 3840, height: 2160`.
   Tell the user: "Exporting clean PNG at 4K resolution..."

5. **Enable labels and export annotated version**:
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

6. **Export SVG**: Call `gephi_export_svg` with `file` set to the same base path with `.svg` extension.
   Tell the user: "Exporting SVG for vector editing..."

7. **Report**: List all exported file paths clearly.

## Important

- The export tools use `file` as the parameter name for the output path, not `path`
- If any export fails, report the error and continue with remaining exports
