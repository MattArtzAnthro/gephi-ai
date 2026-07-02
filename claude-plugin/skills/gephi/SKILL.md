---
name: gephi
description: |
  When the user wants to analyze, visualize, or explore network graphs using Gephi,
  this skill provides workflows and best practices for the 77 Gephi MCP tools.
  Triggered when the user mentions Gephi, network analysis, graph visualization,
  community detection, social network analysis, or graph metrics.
compatibility: Requires Gephi Desktop 0.11.1+ running with the Gephi MCP Plugin v1.0.0-beta installed, and the gephi-mcp MCP server connected.
metadata:
  author: Matt Artz
  version: "1.6"
---

# Gephi Network Analysis Skill

You have access to 77 MCP tools (prefixed `mcp__gephi-mcp__`) for controlling Gephi Desktop. Use them to build, analyze, style, and export network graphs.

## Communication

**Always narrate what you're doing.** Before each major tool call, tell the user what's about to happen in a short sentence (e.g., "Computing modularity...", "Running ForceAtlas 2 layout..."). This prevents the user from wondering what's happening during long operations.

## Critical Things To Know

- **Layout algorithm name**: Use `"ForceAtlas 2"` (with space and capitals), not `"forceatlas2"`
- **Export file parameter**: Export tools use `file` as the key, not `path`
- **Run statistics before styling** — `modularity_class` and `degree` columns don't exist until you compute them
- **`node.label.proportinalSize`** — note the typo (missing 'o'). This is Gephi's actual property name.
- **Always call `project/new` before importing** — stale workspace state from prior operations can cause issues. A fresh project prevents this.
- **`edge.color: "source"` colors edges individually** — the plugin automatically colors each edge to match its source node's color and sets mode to ORIGINAL. This is safe and produces the watercolor halo effect.
- **`node.label.font` supports multi-word names** — e.g., `"Courier New 12 Bold"`. The plugin parses everything before the first digit as the font name.
- **Imported node sizes are auto-capped at 30** — GEXF files with large `viz:size` values are automatically capped during import to prevent oversized nodes from hiding edges.
- **Filters refresh the preview automatically** — `remove_isolates`, `giant_component`, `filter_by_degree` now properly refresh the preview model after modifying the graph.
- **`sync: true` in `gephi_run_layout`** — makes the call block until layout finishes. Always use this so Noverlap and Label Adjust don't start on a still-moving graph.

## Standard Workflow

1. **Health check** — `gephi_health_check` (stop if Gephi isn't running)
2. **Fresh project** — call `gephi_create_project` before importing
3. **Import** — `gephi_import_file` or build with `gephi_add_nodes`/`gephi_add_edges`
4. **Statistics** — compute degree, modularity, etc.
5. **Style** — color by partition, size by ranking
6. **Layout** — `gephi_run_layout` with `"ForceAtlas 2"`, then optionally `"Noverlap"` and `"Label Adjust"`
7. **Preview** — `gephi_set_preview_settings` for export appearance
8. **Export** — `gephi_export_png` (use `file` param), `gephi_export_svg`, etc. For interactive exploration in MCP Apps hosts (claude.ai, Claude Desktop), prefer `gephi_view_graph` — it renders an interactive view inline in the conversation; use `gephi_export_png` for publication stills.

## Tool Quick Reference

### Project & Workspace
`gephi_create_project`, `gephi_open_project`, `gephi_save_project`, `gephi_get_project_info`, `gephi_new_workspace`, `gephi_list_workspaces`, `gephi_switch_workspace`, `gephi_delete_workspace`, `gephi_duplicate_workspace`, `gephi_rename_workspace`

### Graph Construction
`gephi_add_node`/`gephi_add_nodes`, `gephi_add_edge`/`gephi_add_edges`, `gephi_remove_node`/`gephi_bulk_remove_nodes`, `gephi_remove_edge`, `gephi_clear_graph`, `gephi_set_node_label`/`gephi_set_edge_label`, `gephi_set_node_position`/`gephi_batch_set_positions`, `gephi_set_edge_weight`, `gephi_query_nodes`, `gephi_get_node`, `gephi_query_edges`

### Statistics (run before styling)
- `gephi_compute_modularity` → creates `modularity_class`
- `gephi_compute_degree` → creates `degree`, `indegree`, `outdegree`
- `gephi_compute_betweenness` → creates `betweenesscentrality`, `closnesscentrality`, `eccentricity`, `harmonicclosnesscentrality` (0.11.1+)
- `gephi_compute_pagerank` → creates `pageranks`
- `gephi_compute_eigenvector` → creates `eigencentrality`
- `gephi_compute_connected_components` → creates `componentnumber`
- `gephi_compute_clustering_coefficient` → creates `clustering`
- `gephi_compute_avg_path_length` → avg path length, diameter
- `gephi_compute_hits` → creates `authority`, `hub` (lowercase column names)

### Appearance
`gephi_color_by_partition`, `gephi_color_by_ranking`, `gephi_size_by_ranking`, `gephi_set_node_color`/`gephi_set_node_size`, `gephi_set_edge_color`, `gephi_edge_thickness_by_weight`, `gephi_batch_set_node_colors`, `gephi_reset_appearance`

### Layout
`gephi_run_layout` (use `"ForceAtlas 2"`, `"Yifan Hu"`, `"Fruchterman Reingold"`, `"Circular"`, `"Random Layout"`), `gephi_stop_layout`, `gephi_get_layout_status`, `gephi_get_available_layouts`, `gephi_get_layout_properties`/`gephi_set_layout_properties`

### Filtering
`gephi_filter_by_degree`, `gephi_filter_by_edge_weight`, `gephi_remove_isolates`, `gephi_extract_ego_network`, `gephi_extract_giant_component`, `gephi_reset_filters`

### Preview & Export
`gephi_get_preview_settings`/`gephi_set_preview_settings`, `gephi_export_png`/`gephi_export_pdf`/`gephi_export_svg` (use `file` param), `gephi_export_gexf`/`gephi_export_graphml`/`gephi_export_csv`, `gephi_view_graph` (interactive in-chat view, no `file` param)

### Import
`gephi_import_file`, `gephi_import_gexf`/`gephi_import_graphml`/`gephi_import_csv`

## Styling Defaults

### Pastel Community Colors
Always override default Gephi colors with this palette for `gephi_color_by_partition`:
```json
{"0": [212,222,99], "1": [227,185,216], "2": [89,238,200], "3": [154,226,255], "4": [255,171,125], "5": [255,173,203], "6": [255,220,130], "7": [190,170,230]}
```

### Publication Export Settings
Clean (no labels):
```json
{"node.label.show": false, "edge.opacity": 25, "edge.curved": true, "edge.color": "source", "edge.thickness": 2.0, "node.opacity": 100, "node.border.width": 0.3, "arrow.size": 0}
```

Labeled:
```json
{"node.label.show": true, "node.label.proportinalSize": false, "node.label.font": "Arial 10 Plain", "node.label.outline.size": 4, "node.label.outline.opacity": 95, "edge.opacity": 15}
```

New in 0.11.1: `"node.label.avoidOverlap": true` prevents label collisions; `"node.label.overlapGridSize": 50` controls grid granularity. Both can be combined with existing label settings.

### Layout
- ForceAtlas 2 for most graphs: `{"scalingRatio": 15, "linLogMode": true, "gravity": 1.0, "sync": true}`, 1000-1500 iterations — scale `scalingRatio` up with node count (see Beautiful Graph Recipe table)
- Follow with Noverlap: `{"algorithm": "Noverlap", "iterations": 500, "properties": {"margin": 5.0}, "sync": true}`
- Follow with Label Adjust (500 iterations, sync: true) if labels are enabled
- **`barnesHutOptimize` is wrong** — the correct key is `barnesHutOptimization`

## Key Gotchas

- **macOS render deadlock — work in one pass (most important).** On macOS, Gephi's OpenGL view (the concurrent VizEngine "World Updater") and the Data Laboratory table both hold the graph's read lock almost continuously while rendering, and Gephi's own write operations block on it. A burst of API **writes against a large, actively-rendering graph can deadlock Gephi** (every write call times out; only `gephi_health_check` still answers). This is a Gephi-core limitation, not the plugin — the v1.1.x plugin hardens its own locking so a single clean pass works, but it can't fix Gephi's renderer. **Working envelope:** do **build/import → compute stats → style → layout → export** as one focused sequence, then stop. Avoid long interactive sessions that keep mutating an already-laid-out, on-screen graph. Keep graphs reasonably sized. If a write call times out, the view has deadlocked — **restart Gephi** (fully quit + reopen) to recover; there is no other recovery.
- **Filters are destructive** — they permanently remove nodes/edges. Save project first.
- **High gravity (>3) compresses nodes** into a ball. Fix: run Random Layout (1 iteration), then re-run ForceAtlas 2.
- **Workspace switching can deadlock** — same render-deadlock cause as above; if the API hangs after a workspace switch, restart Gephi.
- **`gephi_extract_giant_component` (and other writes after a layout) can deadlock Gephi** — highest-risk during heavy rendering. To contain outlier nodes that blow out the bounding box, prefer high FA2 gravity (5–8) over destructive filters.
- **Press Ctrl+Shift+H in Gephi** to center the view on the graph after API operations — the API modifies data but doesn't move the viewport camera.
- **`background.color` in preview settings is stored but Gephi's PNG exporter always writes white** — the Java plugin intercepts and composites the background color after export, but for reliable dark backgrounds use the Python post-processing workflow below.
- **For dark backgrounds, use a vibrant/saturated color palette** — the default pastel palette is designed for white. Pastels on dark backgrounds are barely visible. Use saturated colors like `[255,90,70]` (coral), `[60,150,255]` (blue), `[140,230,70]` (lime) etc.
- **`edge.opacity` 60 is the minimum for dark background compositing** — at 25% (default), edge pixels are too close to white to recover the original hue. Use 60% so compositing has enough signal.
- **Knowledge graph bounding box blowout** — KGs with extreme betweenness variance (hub-and-spoke structure) produce outlier nodes that push the Gephi bounding box far outside the main cluster. Fix: use gravity 5–8 in FA2. Post-process in Python using centroid-crop (see Crop section below) — NOT alpha-threshold bounding box, which includes outlier nodes and returns full-canvas dimensions.
- **Size by degree, not betweenness, for KGs** — betweenness variance in hub-and-spoke KGs is so extreme (e.g., 0–74k) that 95% of nodes get minimum size. Degree has lower variance and produces more proportional sizing.
- **Vivid source colors are required for white-background visibility** — "soft pastel" appearance on white comes from vivid node colors rendered at high opacity (not from literally pale colors). Pastel node colors (e.g., [227,185,216]) are near-white and disappear even at 90% opacity. Use fully saturated colors (e.g., [220,30,80], [150,30,220]) — at 100% opacity with thick edges they produce a vivid, readable graph. Reduce opacity only if the graph is dense enough that overlapping edges create unwanted solid blobs.
- **White background KG final settings that work** — `edge.opacity: 100`, `edge.thickness: 6`, `node size min 8 max 30`, vivid modularity colors, centroid-crop the export. These settings produce clearly visible colored lines on white.
- **Hand-authored GEXF must XML-escape `"` (and `'`) in attribute values** — when you generate a GEXF yourself to import, node `label`/attribute values containing a double-quote (e.g. titles like `"Un/Doing Race"` or `Sorting Things Out: …`) produce malformed XML and `gephi_import_file` fails with `java.lang.RuntimeException` SEVERE. Escape `<>&"'` in every attribute, then validate the file parses (`python3 -c "import xml.dom.minidom,sys; xml.dom.minidom.parse(sys.argv[1])" file.gexf`) before importing.
- **`gephi_query_nodes` `sort_by`/`descending` may not sort** — observed returning nodes in alphabetical id order regardless. To rank, pull the nodes and sort client-side, or read `pageranks`/`degree` from an exported GEXF/CSV.
- **Re-styling right after an export is a lock hotspot** — `gephi_color_by_partition` / `gephi_size_by_ranking` called immediately after a PNG export frequently returns `Graph is busy (renderer holds the lock); please retry`. Retry once or twice; if it persists, don't fight it — `gephi_export_gexf` and finish styling/labeling externally (see "Render externally from GEXF" below).

## Beautiful Graph Recipe

Bad-looking graphs almost always come from one of three problems: layout parameters ignored (the most common), no overlap prevention, or wrong edge/label settings. Follow this recipe for publication-quality output.

### scalingRatio by graph size

`scalingRatio` must be calibrated to node count — too high and communities fly to the canvas edges:

| Nodes | scalingRatio | barnesHutOptimization | distributedAttraction |
|-------|-------------|----------------------|----------------------|
| ≤ 50  | 10–20       | false                | false                |
| 50–300 | 30–80      | true                 | false                |
| 300–1000 | 100–150  | true                 | true                 |
| 1000+ | 200–300     | true                 | true                 |

### Phase 1 — Community layout (1000–1500 iterations)
```json
{
  "algorithm": "ForceAtlas 2",
  "iterations": 1200,
  "sync": true,
  "properties": {
    "scalingRatio": 15,
    "linLogMode": true,
    "gravity": 1.0,
    "barnesHutOptimization": false
  }
}
```
- `linLogMode: true` is the single most important setting — it makes communities pull together as tight clusters with open space between them
- `scalingRatio` default (10) is fine for small graphs; scale up with node count per the table above
- `distributedAttraction` (Dissuade Hubs) helps large graphs but pushes communities apart on small ones — avoid for < 300 nodes
- `barnesHutOptimization` is only needed for large graphs (300+); skip it for small graphs to avoid approximation artifacts
- Always use `sync: true` so Phase 2 doesn't start on a still-moving graph

### Phase 2 — Overlap prevention (200 iterations)
```json
{
  "algorithm": "ForceAtlas 2",
  "iterations": 200,
  "sync": true,
  "properties": {
    "scalingRatio": 15,
    "linLogMode": true,
    "gravity": 1.0,
    "adjustSizes": true
  }
}
```
- `adjustSizes: true` (Prevent Overlap) runs FA2 while accounting for node sizes — nodes physically push each other apart
- Keep the same `scalingRatio` as Phase 1 so community structure is preserved

### Phase 3 — Fine-grained separation
```json
{"algorithm": "Noverlap", "iterations": 300, "sync": true, "properties": {"margin": 3.0}}
```

### Phase 4 — Label positioning (only if showing labels)
```json
{"algorithm": "Label Adjust", "iterations": 300, "sync": true}
```

### Preview settings for community graphs
```json
{
  "node.label.show": false,
  "edge.color": "source",
  "edge.opacity": 20,
  "edge.curved": true,
  "edge.thickness": 1.5,
  "node.opacity": 100,
  "node.border.width": 0.5,
  "node.label.avoidOverlap": true,
  "arrow.size": 0
}
```
- `edge.color: "source"` creates the watercolor halo effect where edges fade into their source community color
- `edge.opacity: 20` keeps edges from overwhelming the community structure
- `node.label.avoidOverlap: true` (0.11.1+) prevents label collisions without needing Label Adjust

## Dark Background Workflow

Gephi's PNG exporter always writes a white background regardless of `background.color`. Use this Python post-processing recipe after `gephi_export_png`:

```python
from PIL import Image
import numpy as np

img = Image.open('export.png').convert('RGB')
arr = np.array(img, dtype=np.float32)
bg = np.array([28, 28, 46], dtype=np.float32)   # dark navy #1C1C2E

dist = 255.0 - arr
alpha = np.clip(np.max(dist, axis=2) / 255.0 * 1.8, 0, 1)
a_safe = np.maximum(alpha, 0.02)[:,:,np.newaxis]
recovered = np.clip((arr - 255.0*(1-alpha[:,:,np.newaxis])) / a_safe, 0, 255)
result = np.clip(bg + alpha[:,:,np.newaxis]*(recovered - bg), 0, 255).astype(np.uint8)
Image.fromarray(result).save('export-dark.png')
```

**Requirements for this to work well:**
- `edge.opacity` must be at least 60 (pastels at 25% produce near-white pixels; recovery fails)
- Use saturated/vibrant colors, not pastels
- Works best for unlabeled exports — labels turn invisible after compositing (white outlines → navy)

**For labeled exports**, use white background (`background.color: "#FFFFFF"`). Labels are readable on white natively.

**Crop and scale to fill canvas** — use centroid-based cropping, not alpha-threshold bounding box. Alpha-threshold fails on sparse graphs (outlier nodes at canvas edges push the bounding box to full canvas width). Centroid method finds the center of mass of visible content and crops a fixed window around it:

```python
dist = 255.0 - arr
alpha = np.clip(np.max(dist, axis=2) / 255.0 * 1.8, 0, 1)
mask = alpha > 0.12
ys, xs = np.where(mask)
cy, cx = int(ys.mean()), int(xs.mean())
half_w, half_h = 900, 700   # tune to graph density
img.crop((max(0,cx-half_w), max(0,cy-half_h),
          min(W,cx+half_w), min(H,cy+half_h))).resize((3840,2160), Image.LANCZOS).save('export-zoom.png')
```

- Adjust `half_w`/`half_h` based on how spread out the graph is (900/700 works for KGs with bounding box blowout)
- For dark background compositing, apply the compositing step first, then centroid-crop the result

## Community Labels (Post-Processing)

Gephi has no native community label feature. Use Python to overlay one label per modularity class after export.

**Workflow:**

1. Run `gephi_query_nodes` (limit covers all nodes, attributes: `["modularity_class"]`) to get x/y positions and colors per node.
2. Group by modularity class, compute centroid: `cx = mean(xs)`, `cy = mean(ys)`.
3. Map Gephi coordinates → pixels using the full coordinate bounding box:
   ```python
   px = (cx - x_min) / (x_max - x_min) * W
   py = H - (cy - y_min) / (y_max - y_min) * H   # Y axis is inverted
   ```
4. Draw text at those pixel positions using PIL, with a white outline (draw at ±2px offsets before drawing the colored label).
5. Exclude any class whose centroid is a known outlier (single node pushed far from the main cluster by FA2 repulsion — centroid will be far outside the visible region).
6. Compute the crop window from the min/max of in-frame centroid pixels + 320px margin each side, then resize to target canvas.

**Gotchas:**
- FA2 can push a single-node class (degree-1 node) to extreme coordinates (e.g. x = -233494). Always check centroids for outliers before cropping.
- Community centroids land inside the edge mass, not cleanly beside clusters (hub-and-spoke topology means all clusters overlap in the center). See "Radial leader-line labels" below for the fix.

### Render externally from GEXF (exact coords, full control)

When you need labels, distinct community colors, or any layout the overlay-on-PNG
path can't give cleanly, **don't pull coordinates with `gephi_query_nodes` and
don't use `export_csv`** (the node CSV has no x/y). Instead `gephi_export_gexf`
— it bakes `<viz:position>` plus every attribute (`modularity_class`,
`pageranks`) — then re-render the whole figure in matplotlib. This sidesteps the
white-background compositing entirely and gives full control over color (no
look-alike-palette collisions) and label placement.

Parse the viz namespace **by local tag name** (`position`/`size`/`color` are in
`gexf.net/.../viz`, not the default namespace):

```python
import xml.etree.ElementTree as ET
import numpy as np, matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import matplotlib.patheffects as pe

local = lambda t: t.split('}')[-1]
root = ET.parse('graph-positions.gexf').getroot()
pos, comm, pr = {}, {}, {}
for n in root.iter():
    if local(n.tag) != 'node': continue
    nid = n.get('id')
    for c in n:
        if local(c.tag) == 'position': pos[nid] = (float(c.get('x')), float(c.get('y')))
        elif local(c.tag) == 'attvalues':
            for av in c:
                if av.get('for') == 'modularity_class': comm[nid] = int(float(av.get('value')))
                elif av.get('for') == 'pageranks':       pr[nid]   = float(av.get('value'))
edges = [(e.get('source'), e.get('target')) for e in root.iter()
         if local(e.tag) == 'edge' and e.get('source') in pos and e.get('target') in pos]

PAL = {0:'#e74c3c',1:'#e98b1f',2:'#f1c40f',3:'#8bc34a',4:'#2ecc71',
       5:'#1abc9c',6:'#3498db',7:'#ff2e88',8:'#9b59b6',9:'#00d0e0'}  # 10 distinct hues
nodes = list(pos)
fig, ax = plt.subplots(figsize=(17,17), dpi=240)
fig.patch.set_facecolor('#0a0c1a'); ax.set_facecolor('#0a0c1a')
ax.add_collection(LineCollection([[pos[s],pos[t]] for s,t in edges],
    colors=[PAL[comm.get(s,0)] for s,_ in edges], linewidths=0.35, alpha=0.10))
pv = np.array([pr.get(n,0) for n in nodes])
ax.scatter([pos[n][0] for n in nodes], [pos[n][1] for n in nodes],
    s=18 + (pv/pv.max())*2600, c=[PAL[comm.get(n,0)] for n in nodes],
    edgecolors='none', alpha=0.95, zorder=3)
```

(Edges colored by **source** community = the watercolor halo; nodes sized by
PageRank. matplotlib renders ~7k edges fine.)

### Radial leader-line labels (fixes centroid pile-up)

Because community centroids overlap in the dense core, labels placed *at* the
centroids collide. Instead place labels on a **ring** around the graph, evenly
spaced by each centroid's angle, with a **leader line** back to a marker at the
true centroid — no overlaps, locations still exact:

```python
xs = np.array([pos[n][0] for n in nodes]); ys = np.array([pos[n][1] for n in nodes])
cx, cy = np.median(xs), np.median(ys)
R = np.percentile(np.hypot(xs-cx, ys-cy), 98)         # cloud radius (98th pct ignores outliers)
anchor = {k: (np.median([pos[n][0] for n in nodes if comm.get(n)==k]),
              np.median([pos[n][1] for n in nodes if comm.get(n)==k])) for k in PAL}
order = sorted(PAL, key=lambda k: np.arctan2(anchor[k][1]-cy, anchor[k][0]-cx))
base  = np.arctan2(anchor[order[0]][1]-cy, anchor[order[0]][0]-cx)
for i, k in enumerate(order):
    ang = base + 2*np.pi*i/len(order)                 # even spacing → guaranteed no overlap
    lx, ly = cx + R*1.32*np.cos(ang), cy + R*1.32*np.sin(ang)
    ax.plot([anchor[k][0], lx], [anchor[k][1], ly], color=PAL[k], lw=1.2, alpha=0.55, zorder=4)
    ax.scatter([anchor[k][0]], [anchor[k][1]], s=140, facecolor=PAL[k],
               edgecolor='white', lw=1.5, zorder=6)
    t = ax.text(lx, ly, NAMES[k], color='white', ha='left' if lx>=cx else 'right',
                va='center', fontsize=16, fontweight='bold', zorder=7)
    t.set_path_effects([pe.withStroke(linewidth=4.5, foreground=PAL[k]),
                        pe.withStroke(linewidth=9, foreground='#0a0c1a')])
ax.set_aspect('equal'); ax.axis('off')
plt.savefig('graph-labeled.png', facecolor='#0a0c1a', bbox_inches='tight', pad_inches=0.25)
```

`NAMES` is your `{modularity_class: "Theme"}` map — name each community from its
top-PageRank members (`gephi_query_nodes` or the exported node table).

### Troubleshooting
- **Nodes in a ball**: gravity is too high OR layout parameters weren't applied (check you're using correct key names). Fix: run Random Layout (1 iteration), then re-run Phase 1.
- **Communities not separating**: `linLogMode` is off, or `scalingRatio` is too low. Verify properties are accepted.
- **Nodes still overlapping after Phase 2**: run Noverlap with higher margin (5–8).
- **Labels colliding**: run Label Adjust, or enable `node.label.avoidOverlap: true` in preview settings.

For detailed tool parameters, see [references/tool-reference.md](references/tool-reference.md).
For layout algorithm details, see [references/layout-guide.md](references/layout-guide.md).
For statistics interpretation, see [references/statistics-guide.md](references/statistics-guide.md).
