# Version notes

`gephi_health_check` reports the Gephi AI plugin version (`version`) and the MCP server
version (`server_version`). Gephi's own version is under Help > About. When behaviour
differs from the skill, check this list before anything else, and suggest updating when an
item applies.

## Gephi Desktop

- **0.11.3 or later** is required by plugin 1.5.0 and later; earlier plugins run on **0.11.1
  or later**. 0.11.1 adds the `harmonicclosnesscentrality` column (from
  `gephi_compute_betweenness`) and the label preview settings `node.label.avoidOverlap` and
  `node.label.overlapGridSize`.
- **0.11.2 and earlier, on macOS:** opening the Overview tab can freeze Gephi (force-quit to
  recover) when an accessibility tool such as Grammarly Desktop polls the app while the graph
  canvas is created. Gephi 0.11.3 fixes it: suggest updating. On an older version, quit those
  tools for the Gephi session. `graph_lock` reports ok during the freeze, because it happens
  outside the graph.
- **0.11.3** fixes one cause of ForceAtlas 2 coordinates becoming `Infinity` or `NaN` (nodes
  with zero net movement, gephi#3235). Other causes remain; the `layout_exploded` check still
  applies.

## Gephi AI Java plugin

- **1.1.x:** no protection against Gephi's renderer holding the graph lock, so writes can hang
  indefinitely. Keep each session to one build, style, layout, and export pass, and update the
  plugin.
- **1.2.0 and later:** every lock wait is bounded, so a call returns "Graph is busy" instead
  of hanging.
- **1.2.16 and earlier:** OpenOrd and Yifan Hu run with every property at zero unless each one
  is passed: OpenOrd collapses every node to one point and Yifan Hu does nothing, while both
  report success. All-zero values from `gephi_get_layout_properties` are the sign. Update, or
  pass every property explicitly.
- **Before 1.3.0:** a background colour set once for PNG export applied to every later export
  in every workspace. From 1.3.0, `gephi_export_png` reads `background.color` from the
  workspace's preview settings at export time.
- **1.3.2 and later:** a modularity run that never converges (gephi#1630) is stopped after 45
  seconds and repeated once; `reruns_after_nonconvergence` says so.
- **1.3.3 and later:** a layout setting whose name matches no property is listed in
  `unapplied_params` with a warning, instead of being dropped silently.
- **1.4.0 and later:** statistics run through Gephi's Statistics panel (with its report and a
  cancel button), layouts through the Layout panel (algorithm and exact settings), and
  colouring and sizing set the Appearance panel to the same column and values
  (`appearance_panel` in the reply says whether it was set). Columns can be named by the
  title shown in Gephi as well as by id. On earlier plugins, none of this shows in Gephi's
  panels, so do not point the viewer to them. Sorting and choosing columns in `gephi_query_nodes`, the `cap` in `gephi_size_by_ranking`, and a dry run of `gephi_remove_isolates` also need 1.4.0; on an older plugin the server refuses them rather than let the plugin ignore them.
- **1.5.0 and later:** requires Gephi 0.11.3. Colouring and sizing go through Gephi's
  Appearance API, as the panel's Apply button does: with a filter on, only the visible nodes
  or edges change (`view` and `filter_active` in the reply say so), and in a partial `colors`
  map the values left out take Gephi's default grey. A capped `gephi_size_by_ranking` is the
  exception and sizes every node. Screenshots are written straight to the file and no longer
  touch the toolbar's screenshot settings. PDFs are US Letter, landscape for a wide layout.
  `gephi_health_check` reports `gephi_version` and, when an update needs a newer Gephi, says to
  update Gephi first; `gephi_run_statistic` adds `panel_result`, the Statistics panel's line.
- **1.5.2 and later:** a second request for a statistic that is already running is refused with
  "already running" instead of starting a duplicate run. Failed requests log their stack trace in
  Gephi's own log, which is worth attaching to a bug report.
