---
description: Apply publication-ready styling and export the current graph
argument-hint: "[output-path]"
allowed-tools: mcp__gephi-mcp__*
---

# Publication-Ready Visualization & Export

Apply publication-quality styling to the current graph and export in multiple formats.

## Steps

1. **Health check**: Call `gephi_health_check` to confirm Gephi is running.

2. **Graph info**: Call `gephi_get_project_info` to confirm graph has nodes and edges.

3. **Set preview settings for clean export** (no labels):
   ```json
   {
     "node.label.show": false,
     "edge.opacity": 20,
     "edge.curved": true,
     "edge.color": "source",
     "node.opacity": 100,
     "node.border.width": 0.5,
     "arrow.size": 0
   }
   ```

4. **Export clean PNG**: Call `gephi_export_png` at 3840x2160 resolution.
   - Use the path from `$ARGUMENTS[0]` if provided, otherwise default to `~/Desktop/network.png`

5. **Enable labels and export annotated version**:
   - Call `gephi_set_preview_settings` with:
     ```json
     {
       "node.label.show": true,
       "node.label.proportinalSize": false,
       "node.label.font": "Arial 8 Plain",
       "node.label.outline.size": 3,
       "node.label.outline.opacity": 90,
       "edge.opacity": 15
     }
     ```
   - Export with `_labeled` suffix added to the filename

6. **Export SVG**: Call `gephi_export_svg` for vector editing (same base path, `.svg` extension).

7. **Report**: Tell the user the file paths of all exported files.
