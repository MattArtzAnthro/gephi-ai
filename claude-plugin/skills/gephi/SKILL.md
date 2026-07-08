---
name: gephi
description: |
  When the user wants to analyze, visualize, or explore network graphs using Gephi,
  this skill provides workflows and best practices for the 102 Gephi MCP tools.
  Triggered when the user mentions Gephi, network analysis, graph visualization,
  community detection, social network analysis, or graph metrics.
compatibility: Requires Gephi Desktop 0.11.1+ running with the Gephi MCP Plugin (1.2.12+) installed, and the gephi-mcp MCP server connected.
metadata:
  author: Matt Artz
  version: "1.9.20"
---

# Gephi Network Analysis Skill

*Skill version 1.9.20 — if commands or tools mentioned here seem missing, the installed plugin is outdated; see the README's Updating section.*

You have access to 102 MCP tools (prefixed `mcp__gephi-mcp__`) for controlling Gephi Desktop. Use them to build, analyze, style, and export network graphs.

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
- **Never claim "scale-free" or "power law" from a heavy-tailed degree distribution** — power-law and log-normal fits are near-indistinguishable in practice, and the term smuggles in a universal-law claim (Jacomy 2020). Describe hub dominance as a characteristic of THIS network ("a few accounts concentrate most ties"), not as the signature of a law.
- **Every final export ships with its story.** When handing over a finished map, always provide copy-ready caption text: data, layout and key settings, what size and color encode, and what the map does and does not license a reader to conclude. Circulating a network image without interpretive context ("storyletting") is the field's named failure mode — see references/reading-network-maps.md.
- **The craft has citable sources; use them.** When a question goes deeper than the conversation can carry, recommend ONE matched open-access source (table in references/reading-network-maps.md). When a map is publication-bound, include the software citations in the caption offer (Gephi = Bastian et al. 2009; ForceAtlas 2 = Jacomy et al. 2014; modularity = Blondel et al. 2008; plugins per their own papers). Most users don't know their tools are citable scholarship.

## Standard Workflow

1. **Health check** — `gephi_health_check` (stop if Gephi isn't running)
2. **Fresh project** — call `gephi_create_project` before importing
3. **Import** — `gephi_import_file` or build with `gephi_add_nodes`/`gephi_add_edges`
4. **Statistics** — compute degree, modularity, etc.
5. **Data-truth check** — before coloring by any claimed grouping, run `gephi_visual_qa` with `partition_column` set. If the verdict is "none", the attribute does not match the topology and coloring by it would mislead; compute real communities with `gephi_compute_modularity` instead (and say so). When building demo/synthetic networks, wire real structure: preferential attachment within communities, hub-biased bridges between them, within-group edge share above 60% — never random edges with decorative group labels.
6. **Style** — color by partition, size by ranking. With community colors applied, tint edges by their source (`edge.color` set to `source`, `edge.opacity` 30-40) so edges carry community identity without noise. Exception: dense word co-occurrence graphs (text networks) — per-source edge coloring adds a second visual dimension on top of an already-high edge count and reads as busier, not clearer; use a flat neutral gray instead (see references/text-network-analysis.md).
7. **Layout** — `gephi_run_layout` with `"ForceAtlas 2"` (linLogMode true, gravity 0), then run `gephi_visual_qa` and export a small PNG to inspect; fix every warning and adjust per references/layout-guide.md before finishing with `"Noverlap"` and `"Label Adjust"`
8. **Preview** — `gephi_set_preview_settings` for export appearance
9. **Export** — size the canvas to the layout shape using `extent.suggested_export` from `gephi_visual_qa`, then `gephi_export_png` (use `file` param), `gephi_export_svg`, etc. For interactive exploration in MCP Apps hosts (claude.ai, Claude Desktop), prefer `gephi_view_graph` — it renders an interactive view inline in the conversation (pass `caption_column` for floating cluster captions; the app offers per-node ask-Claude, ego highlighting, in-place refresh, and a time slider on dynamic graphs); use `gephi_export_png` for publication stills. When crafting a bespoke network diagram and the MCP App view is unavailable or unsuitable, build an interactive HTML/canvas artifact from `gephi_export_gexf` data (positions, colors, and sizes are baked in) instead of settling for a static PNG — reserve PNG for publication exports.

## Teaching Mode (watch-along sessions)

When a human is watching the Gephi window while you work (teaching, demos, paired
analysis), switch to narrated pacing: announce each step and what to watch for
BEFORE doing it; use `gephi_focus_view` to direct their eyes (fit graph after
import/layout, center+select a cluster before discussing it); run layouts in
200-300 iteration chunks with narration between passes instead of one long blast;
pause after each visible change and invite their observations. The /teach command
codifies the full pattern. Watching the instrument operate is the pedagogy — never
do anything the viewer can't follow.

**The person can point back.** `gephi_get_selection` reads what they have selected
in the Gephi window. Whenever they use deictic words about the canvas — "these",
"this group", "the ones I selected" — read the selection FIRST and answer about
those exact nodes; never ask them to type node names. Tell them early in a session
HOW to point: the rectangle-selection tool (dashed-square icon, thin toolbar on
the left edge of the canvas) — drag a box around nodes and it persists while they
come back to the conversation. Hover highlighting is transient and does not
register; the rectangle is the pointing gesture.

**Close long sessions by naming the loop.** A working session reshapes both
sides; say so before ending. One or two sentences on what you now do
differently because of them (a correction they made, a habit you adapted to, a
reading of theirs that beat yours), and an invitation for the reverse. Where
understanding matters (teaching, first analyses), test it by mutual teachback —
they restate the map to you, you restate their domain to them, each side
repairs the other — rather than by asking "does that make sense?"

## Opening a Network Conversation

The first turn decides the quality of everything after it. Two moves, always:

1. **Ask the intake question** (skip if they already told you): one friendly
   sentence — "what are the nodes and connections here, and what are you
   hoping to learn?" Their answer supplies what no file carries: meaning and
   the question at stake. Use their vocabulary everywhere (reports, captions,
   labels), and treat their expectations as hypotheses to test, not truths to
   assume.
2. **Run `gephi_profile_graph`** — one call, the full quantitative picture
   (size, density, degree distribution, components, isolates, weights,
   modularity, clustering, auto-raised flags). You can absorb a dozen
   simultaneous measurements better than most humans can; do it, then give a
   short plain-language first reading that marries their description with the
   numbers, and ask the 2-3 questions the profile raises.

**The first reading is provisional by design — the goal is exploration, not
conclusions.** Success is measured by what the person notices next, not by how
fast a verdict lands:

- **Elicit before you tell.** At the moments that matter — first look at a new
  layout, right after an attribute overlay changes the picture, when they
  point at something — ask ONE concrete question before giving your reading
  ("where does your eye go first?", "which groups look like they talk to each
  other?", "what made you select these?"). Their unprimed reading is evidence
  that is destroyed the instant you speak first. Then always give your own
  reading and compare aloud; asking without telling is a quiz, and quizzes are
  not conversation. Never elicit on task turns (they asked for an export, give
  the export), and if they wave a question off or say "just tell me", stop
  eliciting for the session.
- Present impressions as things to check together, never as findings ("the
  numbers hint at groups — want to see if they match anything you
  recognize?"), and pair every pattern with a rival explanation or a way it
  could be wrong.
- Close the opening with two or three places to look together and let the
  person choose — the machine proposes, the human steers.
- No verdict vocabulary ("clearly", "confirms", "this network is X") before a
  check has run WITH them; verdicts are always relative to a baseline and to
  their stated expectation.
- Symmetry: your own impressions get tested exactly like their expectations
  do. Neither side's prior gets a free pass.

**Then let both guide every downstream decision:**

- Their goal picks the metric: brokers/gatekeepers -> betweenness;
  reach/influence -> degree or PageRank; "who plays similar roles" -> the
  similarity layout; importance-by-association -> eigenvector.
- Size + density pick the layout (purpose table in the layout guide); the
  profile's hairball flag means filter weak ties or raise scalingRatio before
  wasting a render; the tree-like flag means force layouts will NOT separate
  communities — run modularity, then gephi_community_layout (and state its
  changed reading rule: disc placement is legibility, not structure).
- If they expect an attribute to organize the network, TEST it (partition
  share vs baseline) before coloring by it; when it fails, say so plainly and
  offer detected communities — the gap between their expectation and the
  structure is usually the finding.
- Isolates and fragments: ask before removing (one person's noise is another
  person's result).
- Caption clusters in their vocabulary, derived from their data, never
  "cluster 0/1/2" — but only AFTER the reading process has earned the names
  (letters first, real names last; see references/reading-network-maps.md).
- When interpreting a laid-out map, follow the guided reading process in
  references/reading-network-maps.md: layout -> clusters (letter names) ->
  structural holes (the gaps are findings too) -> THEN attribute colors
  compared against the structure -> special nodes (bridges, within-cluster
  hubs, off-color outliers) -> earned names. State the reading rules (axes
  mean nothing, only distances; reruns keep clusters, not positions).

## Plugin Ecosystem Passthrough

gephi-ai drives Gephi's plugin ecosystem, not just its built-ins (verified live):

- **Layouts:** anything installed via Tools > Plugins appears in
  `gephi_list_layouts` and runs by name (verified with Force Atlas 3D). Bundled
  in core and always available: Noverlap (overlap-removal finishing pass),
  OpenOrd (very large graphs), Label Adjust.
- **Statistics:** `gephi_list_statistics` shows every metric including plugin
  ones; `gephi_run_statistic` runs any of them by name (verified with the CWTS
  Leiden plugin — recommend it over plain modularity for large networks).
  Results land in columns; style with size/color-by-ranking or partition.
- If a user wants a capability Gephi lacks, check the plugin portal
  (gephi.org/desktop/plugins) — install in Gephi, restart it, and the new
  layouts/metrics are immediately drivable here.

## From Files to Networks (recipes)

Any data the conversation can read becomes a graph — no importer plugin needed.
With a file path (Claude Code / Cowork): `gephi_import_file` handles GEXF,
GraphML, GML, CSV, DOT, Pajek. Without a path (attachment in chat, API data,
pasted table): parse it yourself and batch `gephi_add_nodes` + `gephi_add_edges`
(chunk a few hundred per call). Shapes:

- **Edge list** (source,target[,weight] rows): add directly.
- **Adjacency matrix**: one edge per nonzero cell.
- **Bipartite two-column** (person,event): add both node sets with a `type`
  attribute, or project (edge between rows sharing a value).
- **Entity rows with attributes** (spreadsheet of people/orgs): nodes with
  attributes; edges from a relationship column, or compute attribute-similarity
  edges yourself (only link above a threshold, put similarity in weight).
- **JSON**: map objects to nodes, references between them to edges.
- **RDF/triples**: subject and object as nodes, predicate as edge label.
- **Free text** (an essay, transcript, article, or corpus, not already a
  node/edge shape): `gephi_text_to_network` builds a word co-occurrence
  graph directly — don't hand-parse prose yourself. See
  references/text-network-analysis.md before reporting any structural gap
  as a finding.

Then run the standard flow (stats -> style -> layout -> QA). This replaces what
portal users install separate importer plugins for, and it works with formats
those plugins never covered.

## Tool Quick Reference

### Project & Workspace
`gephi_create_project`, `gephi_open_project`, `gephi_save_project`, `gephi_get_project_info`, `gephi_new_workspace`, `gephi_list_workspaces`, `gephi_switch_workspace`, `gephi_delete_workspace`, `gephi_duplicate_workspace`, `gephi_rename_workspace`

### Graph Construction
`gephi_add_node`/`gephi_add_nodes`, `gephi_add_edge`/`gephi_add_edges`, `gephi_remove_node`/`gephi_bulk_remove_nodes`, `gephi_remove_edge`, `gephi_clear_graph`, `gephi_set_node_label`/`gephi_set_edge_label`, `gephi_set_node_position`/`gephi_batch_set_positions`, `gephi_set_edge_weight`, `gephi_query_nodes`, `gephi_get_node`, `gephi_query_edges`, `gephi_text_to_network` (builds a word co-occurrence graph from free text, with optional `pos_filter="nouns"`, `min_word_frequency`, `merge_phrases`, `exclude_self_referential`/`self_referential_threshold` for document-frequency-based generic-hub detection, and `context_snippets` to attach real source-text excerpts to each flagged candidate for the gray-zone cases no threshold or word list can resolve — see references/text-network-analysis.md), `gephi_extract_backbone` (disparity-filter edge pruning — a principled alternative to a flat weight cutoff, see references/text-network-analysis.md)

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

### Analysis & counterfactual
- `gephi_profile_graph` → one-call quantitative picture (size, density, degree, connectivity, modularity, clustering); run first
- `gephi_whatif(edits, include_slow=False)` → apply hypothetical edits (`remove_node`/`remove_nodes`/`add_edge`/`remove_edge`) to a throwaway workspace copy, diff the structural profile before/after, auto-clean the scratch copy; the real graph is never touched. For robustness/"what if we removed X" claims — see references/claim-verification.md
- `gephi_compare_nodes(id_a, id_b, metric)` → deterministic two-node comparison on one metric (from attributes or a built-in field); errors if the metric isn't computed yet. For "is X more central than Y" claims — see references/claim-verification.md

### Appearance
`gephi_color_by_partition`, `gephi_color_edges_by_partition` (color edges by a categorical edge column — relationship type/period/tier), `gephi_color_by_ranking`, `gephi_size_by_ranking`, `gephi_set_node_color`/`gephi_set_node_size`, `gephi_set_edge_color`, `gephi_edge_thickness_by_weight`, `gephi_batch_set_node_colors`, `gephi_reset_appearance`

### Layout
`gephi_run_layout` (use `"ForceAtlas 2"`, `"Yifan Hu"`, `"Fruchterman Reingold"`, `"Circular"`, `"Random Layout"`), `gephi_stop_layout`, `gephi_get_layout_status`, `gephi_get_available_layouts`, `gephi_get_layout_properties`/`gephi_set_layout_properties`

### View / Camera / Perspective (Desktop only)
`gephi_focus_view` (mode graph|zero|node|edge|region, select highlights nodes, zoom) — directs the human viewer's attention in the Gephi window; essential in teaching mode. `gephi_set_selection_mode` (rectangle|direct|disable) — enable box-drag selection so pointing (`gephi_get_selection`) works without the human clicking the toolbar icon; call with `rectangle` at the start of teaching mode. `gephi_get_perspective`/`gephi_switch_perspective` — list/switch the top-level tab (Overview / Data Laboratory / Preview) to bring the viewer to the view you're about to discuss.

### Filtering
`gephi_filter_by_degree`, `gephi_filter_by_edge_weight`, `gephi_remove_isolates`, `gephi_extract_ego_network`, `gephi_extract_giant_component`, `gephi_reset_filters`, `gephi_list_filters`/`gephi_apply_filter` (the general filter tools — apply ANY built-in or per-column attribute filter by name, action `select`/`new_workspace`/`column`; see references/filtering.md)

### Data Laboratory
`gephi_column_value_frequencies` (value distribution of a column), `gephi_detect_duplicates` (nodes sharing a column value), `gephi_merge_nodes` (merge duplicates into one — destructive), `gephi_create_regex_column` (boolean column flagging regex matches)

### Timeline (dynamic graphs)
`gephi_get_timeline` (read-only: is the graph dynamic, time bounds, dynamic columns, interval state) — reason over node/edge start/end values to narrate change over time. There is no programmatic time-window tool: driving Gephi's timeline from outside destabilizes its render thread; slice by time in the Gephi timeline UI directly if needed.

### Preview & Export
`gephi_get_preview_settings`/`gephi_set_preview_settings`, `gephi_export_png`/`gephi_export_pdf`/`gephi_export_svg` (use `file` param), `gephi_export_gexf`/`gephi_export_graphml`/`gephi_export_csv`, `gephi_export` (any format by name — VNA/Pajek/DL/spreadsheet/GDF/JSON, for UCINET/Pajek interchange), `gephi_view_graph` (interactive in-chat view, no `file` param)

### Import
`gephi_import_file`, `gephi_import_gexf`/`gephi_import_graphml`/`gephi_import_csv`

## Styling Defaults

### Community Colors (validated palette)
Always override default Gephi colors for `gephi_color_by_partition`. This palette is
validated for categorical use on light backgrounds (lightness band, chroma floor,
colorblind separation, contrast — the old pastel palette failed all four and was
near-invisible on white exports):
```json
{"0": [42,120,214], "1": [27,175,122], "2": [237,161,0], "3": [0,131,0], "4": [74,58,167], "5": [227,73,72], "6": [232,123,164], "7": [235,104,52]}
```
On dark backgrounds use the dark-surface variant:
```json
{"0": [57,135,229], "1": [25,158,112], "2": [201,133,0], "3": [0,131,0], "4": [144,133,233], "5": [230,103,103], "6": [213,81,129], "7": [217,89,38]}
```
More than 8 communities: color the 8 largest, set the rest to neutral gray
[153,153,153] — extra generated hues stop being distinguishable. Enable node labels
for the largest nodes; color must not be the only way to identify a community.

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
- Choosing by purpose (groups, scale, maps, circles, finishing passes): see the layout guide's "Choosing a layout" table — lead with what the person wants to see, then name the algorithm.
- ForceAtlas 2 for most graphs: `{"scalingRatio": 15, "linLogMode": true, "gravity": 0, "sync": true}`, 1000-1500 iterations — scale `scalingRatio` up with node count (see Beautiful Graph Recipe table). Gravity stays 0 on connected graphs (use 0.5-1.0 only to keep disconnected components in frame); excessive gravity packs nodes into a central blob and is the most common layout mistake. LinLog mode + gravity 0 is the reference config for making communities visible (Venturini, Jacomy, and Jensen 2021).
- **Inspect and adjust, always:** after the layout, export a small PNG, look at it, diagnose with the symptom table in references/layout-guide.md (blob = gravity too high; hairball = LinLog off or scaling too low; unreadable cluster interiors = raise scalingRatio), change ONE parameter, rerun ~300 iterations. Two or three loops usually converge — say what you saw and changed.
- Follow with Noverlap: `{"algorithm": "Noverlap", "iterations": 500, "properties": {"margin": 5.0}, "sync": true}`
- Follow with Label Adjust (500 iterations, sync: true) if labels are enabled
- **`barnesHutOptimize` is wrong** — the correct key is `barnesHutOptimization`

## Key Gotchas

- **"Graph is busy" errors and the wedge detector.** Plugin 1.2.0+ fixed the historic macOS wedge at the root (writes pause the renderer via Gephi's own viz-engine API, and a read-lock leak in the query endpoints — the main culprit — is closed), and every lock wait is bounded, so nothing hangs anymore. If a call returns "Graph is busy", retry once — a transient render pass can hold the lock briefly. If it **persists**, run `gephi_health_check` and read the verdict: `graph_lock: "busy"` or a **nonzero `graph_lock_stats.readers` while Gephi is idle means a leaked read hold — nothing will recover this; tell the user plainly that Gephi must be fully quit and reopened**, and that their graph data in an unsaved project will be lost (suggest `gephi_save_project` earlier in sessions). `queued > 0` for a long time means a writer is starving behind render load — pause mutations and let it drain. On plugin 1.1.x these protections don't exist: writes can hang indefinitely, so keep sessions to one focused build → style → layout → export pass and upgrade the plugin.
- **Preview settings do not affect Gephi's Overview canvas.** Everything set via `gephi_set_preview_settings` (including `node.label.show`) applies to exports and the Preview tab only. To see labels live in the Overview window, the user must click the black **T** toggle in the toolbar at the bottom of the graph canvas — only they can do that.
- **Label fonts render in graph-coordinate space and clamp weirdly.** A fixed point size vanishes on large layouts, and with `node.label.proportinalSize: false` Gephi clamps every label to its node's bounds (bigger fonts silently do nothing). For readable hub captions use `gephi_label_clusters` (proportional sizing + extent-scaled font handled for you); when hand-tuning, set proportional TRUE and scale the base font to the layout extent.
- **Filters are destructive** — they permanently remove nodes/edges. Save project first.
- **High gravity (>3) compresses nodes** into a ball. Fix: run Random Layout (1 iteration), then re-run ForceAtlas 2.
- **Opening the Overview tab can freeze Gephi on macOS (race, full force-quit
  to recover).** Root cause captured by thread dump: the UI thread blocks
  creating the OpenGL canvas while the macOS main thread blocks on an
  accessibility query back to the UI thread — a mutual wait outside the graph
  lock entirely (health reports graph_lock ok during it). The trigger is an
  accessibility client polling the app during canvas creation: with Grammarly
  Desktop running the freeze hit repeatedly, including on an empty workspace;
  with it quit, the same click worked. Prevention: quit accessibility-polling
  utilities (Grammarly Desktop and similar assistants) for the Gephi session.
  Graph size and click timing do not reliably matter.
- **Workspace switching can deadlock** — same render-deadlock cause as above; if the API hangs after a workspace switch, restart Gephi.
- **`gephi_extract_giant_component` (and other writes after a layout) can deadlock Gephi** — highest-risk during heavy rendering. To contain outlier nodes that blow out the bounding box, prefer high FA2 gravity (5–8) over destructive filters — as a temporary containment tactic only; revert gravity to 0 for the final layout.
- **Press Ctrl+Shift+H in Gephi** to center the view on the graph after API operations — the API modifies data but doesn't move the viewport camera.
- **`background.color` in preview settings is stored but Gephi's PNG exporter always writes white** — the Java plugin intercepts and composites the background color after export, but for reliable dark backgrounds use the Python post-processing workflow below.
- **For dark backgrounds, use the dark-surface variant of the community palette** (see Styling Defaults) — palettes tuned for white surfaces lose contrast on dark ones and vice versa.
- **`edge.opacity` 60 is the minimum for dark background compositing** — at 25% (default), edge pixels are too close to white to recover the original hue. Use 60% so compositing has enough signal.
- **Knowledge graph bounding box blowout** — KGs with extreme betweenness variance (hub-and-spoke structure) produce outlier nodes that push the Gephi bounding box far outside the main cluster. Fix: use gravity 5–8 in FA2. Post-process in Python using centroid-crop (see Crop section below) — NOT alpha-threshold bounding box, which includes outlier nodes and returns full-canvas dimensions.
- **ForceAtlas 2 can numerically explode, not just spread out** — observed once on a ~700-node/~1900-edge weighted graph with a high-weight hub, 1500 iterations: node coordinates reached `Infinity`/`NaN` (one node hit `1e37`), not just a large-but-finite bounding box. This is silent: the layout call still returns `success`. Check exported positions with `math.isfinite` before trusting a layout on a weighted graph with a strong hub. (The exact parameter combination that triggered it is unconfirmed — see the `/layout/run` request-key gotcha below, discovered afterward, which casts doubt on which properties were actually active for this run. Treat this as "FA2 can do this on some graphs," not as a specific combination to avoid.) Fix: reset with Random Layout and rerun rather than trying to nudge the exploded node back — the explosion wasn't confined to one node, it corrupted the whole layout.
- **`/layout/run`'s tuning values must be sent under the key `"properties"`, not `"params"`** — when driving the Gephi HTTP API directly (not through `gephi_run_layout`, which builds this correctly), a request with the wrong key returns `success: true` and runs the layout on its plugin defaults, silently discarding every custom value. There is no error to catch this. The tell: changing `scalingRatio`/`gravity` across a wide range and getting back nearly the same layout extent every time — a layout genuinely that insensitive to a parameter is itself the anomaly. Verify the request shape (or just use `gephi_run_layout`) before concluding a parameter doesn't matter for a given graph. The same applies to `"Noverlap"`'s `speed`/`ratio`/`margin`, which default to `0.0` — a full no-op, not a gentle setting.
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
For building and reading text networks, see [references/text-network-analysis.md](references/text-network-analysis.md).
For verifying a plain-language structural claim against the graph, see [references/claim-verification.md](references/claim-verification.md).
For compiling a plain-language filter into a Gephi filter, see [references/filtering.md](references/filtering.md).
Multiplex graphs: `gephi_add_edge`/`gephi_add_edges` accept an `edge_type` label so the same pair can hold several parallel typed edges (e.g. "cites" + "coauthor"). To compare layers, filter to one type (`gephi_apply_filter` with the "Edge Type" filter), compute modularity, repeat per type, and compare the partitions.
