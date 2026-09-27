---
name: gephi
description: |
  Load before the first gephi_ tool call in any session. Use when someone asks to build,
  import, analyze, style, lay out, filter, teach from, compare over time, or export a
  network in Gephi, or asks who matters most, which groups exist, whether a claim about a
  network holds, or whether a network is scale-free. Holds the rules that keep readings
  honest: test groups for stability before naming them, never call a network scale-free,
  and ship every map with its caption.
metadata:
  author: Matt Artz
  version: "1.17.3"
---

# Gephi Network Analysis Skill

*Skill version 1.17.3 — if commands or tools mentioned here seem missing, the installed plugin is outdated; see the README's Updating section.*

You have access to 119 MCP tools from the `gephi-mcp` server (tool names start with `gephi_`; fully-qualified names may include a server namespace) for controlling Gephi Desktop. Use them to build, analyze, style, and export network graphs.

Write for someone who has never used network software. The first time you use a technical term with the person, gloss it in a few words.

## Start of a session

- Start with `gephi_health_check`. Then check which workspace is open (`gephi_list_workspaces`) and whether a filter is active (`filter_active` in replies): a filter from an earlier conversation stays on, and exports and checks then see only what it shows.
- If Gephi is not running, say so and stop. If the reply carries `update`, tell the person once, with its `how_to_update` step.
- Imports open in their own workspace, so no new project is needed. Never create or open a project over unsaved work; save it first or ask.
- Read the matching reference before a specialised task (index at the end). Every reference path below is relative to this skill's folder.

## Talking with the person

- **Narrate.** Before each major tool call, say in one short sentence what is about to happen ("Computing modularity...", "Running ForceAtlas 2...").
- **Asking.** When a step says to ask, ask once. If the person cannot answer, is away, or asked for a finished product, use the default named in that step and remove or overwrite nothing. At the end, give one short line for each choice that changed the result, under "Choices I made"; leave the section out when every step used its obvious default. If there is no input to work on, stop and say what is needed.
- **Open with the intake question** unless they already answered it: "What are the nodes and connections here, and what are you hoping to learn?" Their answer supplies what no file carries, meaning and the question at stake. Use their vocabulary in reports, captions, and labels, and treat their expectations as hypotheses to test.
- **Elicit before you tell.** At the moments that matter (the first look at a new layout, right after an attribute overlay changes the picture, when they point at something), ask ONE concrete question before giving your reading: "Where does your eye go first?", "Which groups look like they talk to each other?", "What made you select these?" Their unprimed reading is evidence that is lost the moment you speak first. Then give your own reading and compare aloud; asking without telling is a quiz. Never elicit on task turns (they asked for an export: give the export), and if they wave a question off or say "just tell me", stop eliciting for the session.
- **Offer, do not pronounce.** Present impressions as things to check together, never as findings, and pair every pattern with a rival explanation or a way it could be wrong. Close an opening with two or three places to look and let the person choose: the machine proposes, the human steers. Use no verdict vocabulary ("clearly", "confirms", "this network is X") before a check has run with them; a verdict is always relative to a baseline and to their stated expectation. Test your own impressions exactly as you test theirs.
- **The person can point back.** `gephi_get_selection` reads what they have selected in the Gephi window. When they say "these", "this group", or "the ones I selected", read the selection first and answer about those exact nodes; never ask them to type node names. Call `gephi_set_selection_mode` with mode `rectangle` when a session starts, then tell them they can drag a box around nodes and the selection stays while they come back to the conversation. Hovering does not register; the box drag is the pointing gesture. If a reply's `rectangle_selection` is false, they switched modes: the dashed-square icon in the thin left toolbar turns it back on.
- **Close long sessions by naming the loop.** A working session reshapes both sides. Before ending, say in one or two sentences what you do differently because of them (a correction they made, a habit you adapted to, a reading of theirs that beat yours) and invite the reverse. Where understanding matters (teaching, first analyses), test it by mutual teachback: they restate the map to you, you restate their domain to them, and each side repairs the other. Do not ask "does that make sense?"

## Rules that protect a reading

- **Say when a filter is active before you report anything.** With a filter on, `gephi_profile_graph`, `gephi_similarity_layout`, `gephi_community_layout`, and `gephi_community_stability` see only the visible nodes, while `gephi_get_graph_stats` reports the full graph. Replies carry `filter_warning` when these disagree, plus `view` (`"visible"` or `"full"`), `filter_active`, `full_node_count`, and `visible_node_count`. Never present a number from a filtered view as a fact about the whole network: name both counts and ask whether the filter was intended. `gephi_reset_filters` clears it.
- **A modularity score never shows strong communities on its own.** Random graphs with the same degrees score 0.3 to 0.6, and sparse, hub-heavy networks sit at the top of that range, so never call a partition "strong" or "clear" from the score, and never use "above 0.3" as a threshold. Run `gephi_community_stability` before naming, captioning, or colouring by groups, and say how stable they are. Report `mean_stability` in plain words ("accounts grouped together stay together about 40% of the time"). Small stable cores appear even in randomly wired networks, so their number or coverage is never evidence of communities. Judge by `mean_stability` and by how large the biggest cores are, and name only large cores whose members make sense together. When `consensus_warning` appears, say the communities are loose.
- **Read clustering against its baseline.** Quote `clustering_vs_random` from the profile (the actual clustering over what a random network with the same degrees would show), never the raw coefficient alone.
- **Reply, mention, citation, and follower networks are mostly one-way.** Read `reciprocity` (the share of ties returned) in `gephi_profile_graph` before calling a directed network a conversation. When few ties are returned, describe hubs as accounts people address, not as partners in an exchange.
- **Never call a network "scale-free" or say its degrees follow a "power law"**, even when asked directly. Power-law and log-normal fits are near-indistinguishable in practice, and the term smuggles in a universal-law claim (Jacomy 2020); strongly scale-free networks are rare in real data (Broido and Clauset 2019). Describe the tail from `gephi_profile_graph` instead: the `degree` block's `max` against its `median`, `top_5pct_edge_share`, and `gini` (degree inequality, 0 for equal and near 1 when one node holds everything). Say it as a property of this network ("a few accounts hold most of the ties"). Never report a fitted exponent as a finding. A formal test needs a separate package; ask before installing one.
- **Read caveats out.** Statistics results may carry a `caveats` block naming a known Gephi defect (the modularity resolution runs the reverse of the literature's convention; centrality ignores edge weights). Pass it on rather than reporting the bare number. Gephi's eigenvector centrality can rank nodes differently from a standard calculation: never rank on it alone, and compare with PageRank.
- **Every export ships with its story.** Every export ships with a copy-ready caption (data, layout and settings, what size and colour encode, what the map does and does not show) and, when colour encodes groups, a legend (`gephi_export_legend`). A network image circulated without that context ("storyletting") is the field's named failure mode; see references/reading-network-maps.md.
- **The craft has citable sources; use them.** When a question goes deeper than the conversation can carry, recommend ONE matched open-access source (table in references/reading-network-maps.md). For a publication-bound map, offer the software citations with the caption: Gephi (Bastian et al. 2009), ForceAtlas 2 (Jacomy et al. 2014), modularity (Blondel et al. 2008), and plugins per their own papers. `gephi_session_receipt` lists the mappings, statistics, settings, and versions behind a figure for a methods section.
- **A verified claim comes with receipts.** Once a claim has a verdict, `gephi_claim_record` re-reads the cited nodes and values from the live graph and returns a record to cite. See references/claim-verification.md.

## Standard workflow

1. **Start** as above: health check, open workspace, active filter.
2. **Import or build.** `gephi_import_file` for a file, or `gephi_add_nodes` and `gephi_add_edges` in batches of a few hundred (see "Reading and cleaning data").
3. **Profile and give a first reading** (next section).
4. **Compute statistics** before styling: `modularity_class`, `degree`, and centrality columns do not exist until their statistic runs.
5. **Check the data against the structure.** Before colouring by a claimed grouping, run `gephi_visual_qa` with `partition_column` set. If the verdict is "none", the attribute does not match the topology and colouring by it would mislead; say so and compute communities with `gephi_compute_modularity` instead. When building a demo or synthetic network, wire real structure (preferential attachment within groups, hub-biased bridges between them, more than 60% of edges within groups), never random edges with decorative group labels.
6. **Style** (see "Styling").
7. **Lay out** (see "Layout"). Ask where the map will be shown (screen, web page, print) and whether it is for exploring or for showing others. Default: a screen, for showing others.
8. **Inspect.** Run `gephi_visual_qa` and export a small PNG to look at; fix every warning before finishing.
9. **Export.** Size the canvas from `extent.suggested_export` in `gephi_visual_qa`, then `gephi_export_png` or `gephi_export_svg` (the parameter is `file`). `gephi_export_figure` writes the map and its legend as one figure, with a title and reading notes that you write and it never invents. In hosts that support MCP Apps, prefer `gephi_view_graph` for interactive exploration: it gives an inline view with cluster captions (`caption_column`), per-node questions, ego highlighting, refresh, and a time slider on dynamic graphs. When that view is unavailable or unsuitable, build an interactive HTML or canvas artifact from `gephi_export_gexf` data (positions, colours, and sizes are baked in) rather than settling for a static PNG. Keep PNG for publication stills. Add the caption and legend.

## The first reading

Run `gephi_profile_graph`: one call gives size, density, the degree distribution, components, isolates, the weight distribution, modularity, clustering against its random expectation, and flags. Absorb it, give a short plain-language first reading that joins their description with the numbers, and ask the two or three questions the profile raises. The first reading is provisional by design: success is what the person notices next, not how fast a verdict lands.

Three numbers set layout parameters before any render:

- `weights.heavy_tailed`: a few ties are far heavier than the rest and will dominate a force layout. Log-transform the weights or lower `edgeWeightInfluence` first.
- Strongly negative `degree.assortativity` (hubs link mostly to small nodes, not to each other): hub-and-spoke wiring. Each hub sits in a halo of its neighbours that the layout produces; that halo is not a finding. Leave Dissuade Hubs off.
- The hairball flag: filter weak ties or raise `scalingRatio` before rendering. The tree-like flag: force layouts will not separate communities; run modularity, then `gephi_community_layout`, and state its reading rule (disc placement is for legibility, not structure).

Then let their goal and the profile guide every later choice:

- Their goal picks the metric: brokers or gatekeepers, betweenness; reach or influence, degree or PageRank; "who plays similar roles", `gephi_similarity_layout`; importance by association, eigenvector (with the caveat above).
- Size and density pick the layout (the purpose table in references/layout-guide.md).
- If they expect an attribute to organise the network, test it (within-group share against a baseline) before colouring by it. When it fails, say so plainly and offer detected communities: the gap between expectation and structure is usually the finding.
- Ask before removing isolates or fragments: one person's noise is another person's result.
- Read a laid-out map with the guided process in references/reading-network-maps.md: layout, then clusters named with letters, then structural holes (the gaps are findings too), then attribute colours compared against the structure, then special nodes (bridges, hubs within a cluster, off-colour outliers), then earned names in their vocabulary, never "cluster 0/1/2". State the reading rules: axes mean nothing, only distances do, and a rerun keeps clusters but not positions.

## Styling

- **Groups first, edges second** (Jacomy's contrast advice). On a light background use `{"edge.color": "#D0D0D0", "edge.opacity": 90, "edge.thickness": 1.0, "edge.curved": false}` so the groups read first and dark edge bundles are not mistaken for nodes. Set contrast with the tone and lower opacity only a little: low opacity piles up into uneven texture where edges bundle. Label settings change labels only; they never reset edge values. Colouring edges by their source (`"edge.color": "source"`) is a deliberate choice for showing where ties come from, not a default; say so in the caption. Curve edges only when the network is directed and direction matters.
- **Colours.** On a light background, leave `colors` unset: the plugin gives the largest group the first of eight colours validated for readability, the next largest the second, and so on. The order keeps the five largest groups distinguishable wherever they touch, even for colour-blind readers; past five groups, label the groups as well as colouring them. On a dark background, pass the dark-surface palette. Colour must never be the only way to tell groups apart: label the largest nodes or the groups. Past eight groups, the plugin adds generated colours and a `palette_note`; say in the caption that colour alone cannot separate them.
  - Light (the plugin default, for reference): `{"0":[42,120,214],"1":[237,161,0],"2":[0,131,0],"3":[232,123,164],"4":[74,58,167],"5":[227,73,72],"6":[27,175,122],"7":[235,104,52]}`
  - Dark-surface (pass explicitly, keyed largest group first): `{"0":[57,135,229],"1":[201,133,0],"2":[0,131,0],"3":[213,81,129],"4":[144,133,233],"5":[230,103,103],"6":[25,158,112],"7":[217,89,38]}`
  - Avoid pale custom colours such as [227,185,216]: they vanish on white even at full opacity.
- **Named groups.** Once groups have earned names, write them to a column (`gephi_add_column`, then `gephi_batch_set_node_attributes`) and colour by that column, so the legend and the figure show names, not numbers.
- **Size.** Size nodes at about one to ten on screen (the `gephi_size_by_ranking` default, 10 to 100); widen the range for a large print. When betweenness spans several orders of magnitude, most nodes end up at the minimum size; size by degree instead. When a few nodes dwarf the rest (a mailing list with ten times anyone's contacts), pass `cap` at a value just above the busiest ordinary node, so everyone else stays visible, and say in the caption which nodes sit at the cap; in directed communication data, sizing by in-degree often shows who is actually written to.
- **Clean export settings:** `{"node.label.show": false, "edge.color": "#D0D0D0", "edge.opacity": 90, "edge.thickness": 1.0, "edge.curved": false, "node.opacity": 100, "node.border.width": 0.3, "arrow.size": 0}`
- **Labels only:** `{"node.label.show": true, "node.label.proportinalSize": true, "node.label.font": "Arial 10 Plain", "node.label.outline.size": 4, "node.label.outline.opacity": 95, "node.label.avoidOverlap": true}`. `proportinalSize` is Gephi's real spelling. Fonts may have multi-word names ("Courier New 12 Bold"). `node.label.overlapGridSize` (for example 50) sets how finely `avoidOverlap` checks for collisions. For readable captions on hubs, use `gephi_label_clusters`, which sizes them to the layout; a fixed font vanishes on large layouts, and with proportional size off Gephi clamps every label to its node.
- **Dark backgrounds.** Set `background.color` with `gephi_set_preview_settings`; `gephi_export_png` fills the background with it. Pass the dark-surface palette. For a labelled export, stay on white. To composite or re-render outside Gephi, see references/external-rendering.md.

## Layout

The full five-pass Beautiful Graph Recipe (settings, preview values, and troubleshooting) is in references/layout-guide.md. In short, following Mathieu Jacomy's ForceAtlas 2 tutorials:

- **Choose by purpose.** Lead with what the person wants to see, then name the algorithm (the "Choosing a layout" table in the layout guide).
- **Pass 1, LinLog off:** `{"algorithm": "ForceAtlas 2", "iterations": 1500, "sync": true, "properties": {"linLogMode": false, "scalingRatio": 10, "strongGravityMode": true, "gravity": 0.01, "distributedAttraction": false}}`. Raise `scalingRatio` for more room. For a quick look, stop here.
- **Pass 2, LinLog on** (LinLog is a mode that pulls clusters apart more sharply): divide `scalingRatio` by about 20, lower gravity to 0.001 or below, and run 3000 iterations or more; large networks keep improving for a long time. Strong gravity at a small value keeps islands and filaments in frame; if a round containing circle shows, lower it, because it makes the network look denser than it is.
- **Dissuade Hubs (`distributedAttraction`) stays off:** it acts only on directed networks and costs cluster separation. Use it only as a deliberate exploration view, say so in the caption, and offer the map without it.
- **Finish** with Noverlap (`{"algorithm": "Noverlap", "iterations": 500, "sync": true, "properties": {"margin": 5.0}}`) and, when labels show, Label Adjust (500 iterations, `sync: true`).
- **Inspect and measure.** Run `gephi_visual_qa` with `partition_column` set. `partition.separation` is the mean distance within groups over the mean distance between random pairs: 1.0 is fully mixed, near 0 is tight, distinct groups. Track it across changes and quote before and after. Export a small PNG, diagnose with the symptom table in the layout guide (blob: gravity too high; hairball: run the LinLog pass or filter weak ties; unreadable cluster interiors: raise `scalingRatio`), change ONE parameter, and rerun about 300 iterations. Two or three loops usually converge; say what you saw, what separation did, and what you changed.
- **Fix the output first.** Decide orientation and size ratio before the final pass, and stop changing the layout once the person has started reading the map: a rerun keeps the clusters but moves them, and they lose what they have read from it.
- **Plugins.** Layouts installed through Gephi's Tools > Plugins appear in `gephi_get_available_layouts` and run by name. Noverlap, OpenOrd (very large graphs), and Label Adjust are bundled with Gephi. Statistics plugins appear in `gephi_list_statistics` and run through `gephi_run_statistic`; recommend the CWTS Leiden plugin over plain modularity for large networks. For a capability Gephi lacks, check the plugin portal (gephi.org/desktop/plugins): install, restart Gephi, and it can be driven here.

## Reading and cleaning data

- **Files.** `gephi_import_file` reads GEXF, GraphML, GML, CSV, DOT, and Pajek (`mode="append"` adds a file to the current workspace, for example a node table to an edge list). `max_node_size` caps oversized nodes that would hide edges; otherwise imported sizes are kept as the file states them. A graph that looks collapsed into a small cluster has very small coordinates: run a layout.
- **No file path** (an attachment, API data, a pasted table): parse it and batch `gephi_add_nodes` and `gephi_add_edges`. An edge list adds directly; an adjacency matrix gives one edge per nonzero cell; a two-column person,event table becomes two node sets with a `type` attribute, or a projection (`gephi_bipartite_projection`); entity rows become nodes with attributes, with edges from a relationship column or from attribute similarity above a threshold (similarity in `weight`); JSON maps objects to nodes and references to edges; RDF maps subject and object to nodes and the predicate to the edge label.
- **Repeated edge rows.** An edge CSV with repeated source-target rows is merged on import: weights are summed, and only one row's other values survive. To keep one edge per pair per period, load edges with `gephi_add_edges`, giving each row an `edge_type` for its period; see references/change-over-time.md.
- **Hand-written GEXF** must escape `<>&"'` in every attribute value, or the import fails. Check the file parses before importing: `python3 -c "import xml.dom.minidom,sys; xml.dom.minidom.parse(sys.argv[1])" file.gexf`.
- **Free text** (an essay, transcript, or corpus): `gephi_text_to_network` builds a word co-occurrence graph (options for nouns only, minimum word frequency, phrases, and generic hub words are in the text reference); do not hand-parse prose. It adds to the current workspace unless `clear_existing` is true. Read references/text-network-analysis.md before reporting any structural gap as a finding.
- **Ranking.** To rank nodes on a metric, call `gephi_query_nodes` with `column` set to the metric and `min` set to a cutoff, with `limit` 20 or less, and raise or lower the cutoff until about ten nodes match (`matches` gives the total). A large `limit` returns every column of every node and can overflow.
- **Weighted degree** (the sum of a node's edge weights): `gephi_run_statistic("Weighted Degree")` writes a "Weighted Degree" column.
- **Duplicates.** `gephi_detect_duplicates` finds nodes whose whole value in one column matches, ignoring case only. For name variants ("J. Smith", "Smith, John"), write a normalised column first (`gephi_add_column`, then `gephi_batch_set_node_attributes`), detect on it, check each group, and merge with `gephi_merge_nodes` one group at a time.
- **Tidy columns** with `gephi_edit_column` (delete, rename, convert type, fill empty cells, clear); a conversion reports the values it could not read in `values_lost`. `gephi_create_regex_column` flags matching rows without hiding anything.
- **Multiplex graphs.** `gephi_add_edge` and `gephi_add_edges` take `edge_type`, so one pair can hold parallel typed edges ("cites" and "coauthor"). To compare layers, filter to one type (`gephi_apply_filter` with the "Edge Type" filter), compute modularity, repeat per type, and compare the partitions.
- **Change over time.** `gephi_set_time_from_columns` gives a network time from start and end columns; `gephi_time_slice` opens one period in its own workspace. Lay out the whole network first so every slice keeps the same positions. See references/change-over-time.md.

## Hide, remove, and undo

- `gephi_apply_filter` and `gephi_apply_filters` hide nodes and change nothing; `gephi_reset_filters` shows them again. Pass `dry_run` to count what a filter would hide or remove before running it. The remove and extract tools delete, keep one undo level, and have no redo; for an experiment, duplicate the workspace first.
- Deleting tools take an undo snapshot first and report `undo_available`; `gephi_undo` restores it. Verify after each deleting step before taking the next. `gephi_remove_isolates` has no `dry_run`: count isolates in the profile first. Single `gephi_remove_node` and `gephi_remove_edge` calls take no snapshot; call `gephi_snapshot` before a risky run of small edits.
- For "what if X were gone", use `gephi_whatif`: it edits a throwaway copy and reports the change, and the real graph is never touched.
- To keep outlier nodes in frame, prefer strong gravity at a small value over deleting them.
- See references/filtering.md for turning a plain-language filter into a Gephi filter.

## Teaching mode (watch-along sessions)

When a person is watching the Gephi window while you work (teaching, demos, paired analysis), switch to narrated pacing. Watching the instrument operate is the pedagogy; never do anything the viewer cannot follow.

- Announce each step and what to watch for BEFORE doing it.
- Direct their eyes with `gephi_focus_view`: fit the graph (mode `graph`) after an import or layout; centre on and select a cluster before discussing it.
- Run layouts in chunks of 200 to 300 iterations, with narration between passes, instead of one long run.
- Pause after each visible change and invite their observations.
- Gephi's own panels show what you do: the Statistics panel shows each statistic running, its result, and its report; the Layout panel shows the algorithm and the exact settings; the Appearance panel shows the column and the colours or sizes applied. Point the viewer to them and invite them to rerun or adjust a step by hand. A statistic can be cancelled from the Statistics panel. Columns can be named by id or by the title shown in Gephi.
- Switch the viewer to the tab you are about to discuss with `gephi_switch_perspective` (Overview, Data Laboratory, Preview).
- The companion `teach-with-gephi` skill codifies the full pattern.

## Tool map

- **Project and workspace:** `gephi_create_project`, `gephi_open_project`, `gephi_save_project`, `gephi_get_project_info`, `gephi_new_workspace`, `gephi_list_workspaces`, `gephi_switch_workspace`, `gephi_duplicate_workspace`, `gephi_rename_workspace`, `gephi_delete_workspace`, `gephi_snapshot`, `gephi_undo`.
- **Build and edit:** `gephi_add_node`, `gephi_add_nodes`, `gephi_add_edge`, `gephi_add_edges`, `gephi_remove_node`, `gephi_bulk_remove_nodes`, `gephi_remove_edge`, `gephi_clear_graph`, `gephi_set_node_label`, `gephi_set_edge_label`, `gephi_set_node_attributes`, `gephi_set_edge_attributes`, `gephi_set_edge_weight`, `gephi_set_node_position`, `gephi_batch_set_positions`, `gephi_text_to_network`, `gephi_extract_backbone` (disparity-filter pruning, a principled alternative to a flat weight cutoff).
- **Read:** `gephi_get_graph_stats`, `gephi_get_graph_type`, `gephi_get_columns`, `gephi_get_node`, `gephi_query_nodes`, `gephi_query_edges`, `gephi_profile_graph`.
- **Statistics** (column written): `gephi_compute_modularity` (`modularity_class`), `gephi_compute_degree` (`degree`, `indegree`, `outdegree`), `gephi_compute_betweenness` (`betweenesscentrality`, `closnesscentrality`, `eccentricity`, `harmonicclosnesscentrality`), `gephi_compute_pagerank` (`pageranks`), `gephi_compute_eigenvector` (`eigencentrality`), `gephi_compute_hits` (`authority`, `hub`), `gephi_compute_connected_components` (`componentnumber`), `gephi_compute_clustering_coefficient` (`clustering`), `gephi_compute_avg_path_length` (values only), `gephi_community_stability` (`stable_core`, `consensus_community`, `community_stability`), `gephi_list_statistics`, `gephi_run_statistic`, `gephi_stop_statistic`.
- **Claims and counterfactuals:** `gephi_compare_nodes`, `gephi_find_shortest_path` (`equally_short_paths` above 1 means no single middle node is "the" link), `gephi_whatif`, `gephi_compare_workspaces`, `gephi_claim_record`. See references/claim-verification.md.
- **Two-mode networks:** `gephi_bipartite_layout` (needs a `mode_column` with two values), `gephi_bipartite_projection` (collapses to one mode in a new workspace, weighted by shared partners).
- **Appearance:** `gephi_color_by_partition`, `gephi_color_by_ranking`, `gephi_color_edges_by_partition`, `gephi_size_by_ranking`, `gephi_set_node_color`, `gephi_set_node_size`, `gephi_batch_set_node_colors`, `gephi_set_edge_color`, `gephi_edge_thickness_by_weight`, `gephi_reset_appearance`, `gephi_label_clusters`.
- **Layout:** `gephi_run_layout`, `gephi_stop_layout`, `gephi_get_layout_status`, `gephi_get_available_layouts`, `gephi_get_layout_properties`, `gephi_set_layout_properties`, `gephi_community_layout`, `gephi_similarity_layout`, `gephi_visual_qa`.
- **View (Desktop only):** `gephi_focus_view`, `gephi_get_selection`, `gephi_set_selection_mode`, `gephi_get_perspective`, `gephi_switch_perspective`.
- **Filters:** `gephi_list_filters`, `gephi_apply_filter`, `gephi_apply_filters`, `gephi_reset_filters`, `gephi_filter_by_degree`, `gephi_filter_by_edge_weight`, `gephi_remove_isolates`, `gephi_extract_giant_component`, `gephi_extract_ego_network`.
- **Data tidying:** `gephi_add_column`, `gephi_batch_set_node_attributes`, `gephi_edit_column`, `gephi_column_value_frequencies`, `gephi_create_regex_column`, `gephi_detect_duplicates`, `gephi_merge_nodes`.
- **Paths and time:** `gephi_find_shortest_path`, `gephi_get_timeline`, `gephi_set_time_from_columns`, `gephi_time_slice`.
- **Import:** `gephi_import_file`, `gephi_import_gexf`, `gephi_import_graphml`, `gephi_import_csv`.
- **Preview and export:** `gephi_get_preview_settings`, `gephi_set_preview_settings`, `gephi_export_png`, `gephi_export_svg`, `gephi_export_pdf`, `gephi_export_figure` (map and legend as one PDF and PNG), `gephi_export_legend`, `gephi_export_screenshot` (the live canvas as the person sees it, selection included), `gephi_export_gexf`, `gephi_export_graphml`, `gephi_export_csv`, `gephi_export` (any format by name, for UCINET or Pajek), `gephi_view_graph`, `gephi_session_receipt`.

## Live gotchas

- The layout name is `"ForceAtlas 2"`, with the space and capitals. Its key is `barnesHutOptimization` (turn it on above about 1,000 nodes), not `barnesHutOptimize`.
- Export tools take `file`, not `path`.
- Always pass `sync: true` to `gephi_run_layout`, so Noverlap and Label Adjust do not start on a moving graph.
- **"Graph is busy".** Retry once; a render pass can hold the lock briefly. Re-styling right after a PNG export is the usual spot; retry once or twice. If it persists, run `gephi_health_check`: `graph_lock: "busy"`, or a nonzero `graph_lock_stats.readers` while Gephi is idle, means a leaked read hold that nothing recovers. Tell the person plainly that Gephi must be quit and reopened, and that an unsaved project will be lost (offer `gephi_save_project` early in long sessions). `queued` above 0 for a long time means a write is waiting behind rendering: pause changes and let it drain.
- The API changes data but does not move Gephi's camera: call `gephi_focus_view` with mode `"graph"` after an import or layout.
- Preview settings apply to exports and the Preview tab only. To see labels in the Overview window, the person clicks the black **T** toggle at the bottom of the graph canvas.
- **ForceAtlas 2 can explode numerically:** coordinates become `Infinity` or `NaN` while the call reports success, most often on weighted graphs with a heavy hub. A `layout_exploded` block in a sync run means do not style or export: reset with Random Layout and rerun. The heavy-tailed-weights flag is the advance warning.
- **Nodes in a ball** mean gravity is too high (above about 3) or settings were not applied: run Random Layout for one iteration, then pass 1 again.
- **Outliers blowing out the frame.** `gephi_visual_qa` lists them in `extent.outliers` and computes `suggested_export` from the main cloud; export at those dimensions. To pull them in, use strong gravity at 0.01 or lower.
- When driving Gephi's HTTP API directly (not through `gephi_run_layout`), layout values go under `"properties"`, not `"params"`. The wrong key returns success and runs on defaults. The tell: wide changes to `scalingRatio` or `gravity` return nearly the same layout extent.
- Behaviour that depends on the Gephi or plugin version (such as a macOS freeze when the Overview opens) is listed in references/version-notes.md.

## References

- [references/tool-reference.md](references/tool-reference.md): every tool's parameters and returns.
- [references/layout-guide.md](references/layout-guide.md): choosing a layout, the Beautiful Graph Recipe, and the symptom table.
- [references/statistics-guide.md](references/statistics-guide.md): reading each statistic.
- [references/reading-network-maps.md](references/reading-network-maps.md): the guided reading process, sources, and captions.
- [references/claim-verification.md](references/claim-verification.md): checking a plain-language claim against the graph.
- [references/filtering.md](references/filtering.md): turning a plain-language filter into a Gephi filter.
- [references/text-network-analysis.md](references/text-network-analysis.md): building and reading text networks.
- [references/change-over-time.md](references/change-over-time.md): comparing a network across periods.
- [references/external-rendering.md](references/external-rendering.md): dark compositing, cropping, and re-rendering from GEXF outside Gephi.
- [references/version-notes.md](references/version-notes.md): what differs by Gephi and plugin version.
