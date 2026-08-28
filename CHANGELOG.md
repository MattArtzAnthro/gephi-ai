# Changelog

Notable changes to **gephi-ai**. Versions apply together to the Gephi plugin
(`gephi-mcp-plugin/`), the MCP server (`mcp-server/`), and the Claude Code plugin
(`claude-plugin/`). Format follows [Keep a Changelog](https://keepachangelog.com).

## MCP server 1.14.0 / claude-plugin 1.11.2

### Changed
- **The in-chat graph view (MCP App) now looks like a Gephi map.** Four defects
  made the old view read as a set of solid blobs: Gephi node sizes were drawn as
  raw pixel radii, so each community collapsed into one disc; edges were
  full-opacity straight gray lines; cluster captions never rendered because the
  caption column was passed by id while the exported attributes are keyed by
  title; and the chrome was generic white with no legend. Now: sizes are
  rescaled to the view (square root, keeping the ranking); edges follow the
  preview settings the person set in Gephi (opacity, curved, colored by source
  or mixed), which `gephi_view_graph` reads and passes along; the caption
  column is resolved by id or title; and the view has a legend column (color,
  group name, count; click to highlight a group), search by label, hover
  highlighting of a node's neighborhood, zoom controls, fullscreen, and the
  host's theme (dark mode and its fonts through the host style variables).
  Default node labels stay off unless Gephi's label setting is on; highlights
  label only the top-degree nodes so a group does not become a wall of text.
- **The view and Gephi Desktop now point at the same thing.** A node's panel
  has "Show in Gephi" (`gephi_focus_view` centers Gephi's camera on it and
  highlights it), and the app keeps the model informed of what the person is
  looking at (the graph, the grouping, a highlighted group, a selected node)
  through `ui/update-model-context`, so "why is this cluster here?" needs no
  re-explanation.

### Fixed
- Translucent edge and node colors were composited additively (blue rendered as
  cyan, orange as yellow); colors are now premultiplied for sigma's blending.

## MCP server 1.13.1 / claude-plugin 1.11.1

### Fixed
- **`gephi_claim_record` no longer advertises itself as read-only.** It never
  changes the graph, but its `export` parameter writes a file, and
  `readOnlyHint` promises a host that nothing in the environment changes, so a
  host honoring the hint could have skipped confirmation on a file write. It
  now carries the same annotation as the export tools: neither read-only nor
  destructive. Caught by a post-commit review of 1.13.0.

## MCP server 1.13.0 / claude-plugin 1.11.0

### Added
- **`gephi_claim_record`: every verified claim now comes with receipts checked
  against the graph.** `/verify-claim` used to return a paragraph: the verdict,
  a number, a caveat. Anyone asked to "show me" had nothing to show. The
  claim-verifier agent now hands the server the claim, the metric, the verdict,
  the node ids it cited, and the numbers it cited; the server re-reads those
  nodes from Gephi, confirms they exist and that the cited values match the
  live ones, and returns a structured record with the evidence nodes by label,
  a one-sentence caption for a figure or methods appendix, and an optional JSON
  export (`/verify-claim "<claim>" path.json`). A record whose numbers do not
  match the graph is marked `verified: false` and says so; the verdict is never
  altered by the tool. This is the structured form every host gets as text;
  a clickable evidence view can render the same record later.

### Changed
- **Three tool descriptions rewritten so their first sentence works as a search
  key.** Hosts that load tools on demand (Claude Code) match on the opening
  sentence; `gephi_export_screenshot` opened with a 180-character sentence,
  and `gephi_query_nodes` / `gephi_query_edges` said only "with pagination"
  without saying what the tools are for. Ships with the next server release.

## claude-plugin 1.10.1

### Changed
- **`/visualize` is now the map-making command, and `/beautify` is gone.** In
  1.10.0 `/visualize` had become an alias of `/export-map`, which left the
  most natural word for "turn this graph into a map" pointing at export alone.
  It now does what the name says: it dispatches the layout-iterator agent to
  lay out, size, color, check, and export the graph in place, which is what
  `/beautify` did. `/export-map` remains the
  export-only command. `/beautify` has no alias; the name lasted one release
  and its job now has the better name.

## MCP server 1.12.0 / claude-plugin 1.10.0

### Fixed
- **Every fresh install had been failing since the MCP Python SDK 2.0 release**
  (issue #5). `pyproject.toml` allowed `mcp>=1.0.0` while the server imported
  `mcp.server.fastmcp`, which SDK 2.x removed, so `uvx --from gephi-mcp==1.11.0`
  resolved the newest SDK and died on the first import with
  `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`; Claude Code
  reported it as `Failed to reconnect ... -32000`. Existing installs with a
  cached 1.x SDK kept working, which is why it went unnoticed for a month.

### Changed
- **Migrated to MCP Python SDK 2.x** (`mcp>=2.1,<3`): `FastMCP` is now
  `MCPServer`, and `CallToolResult` takes `structured_content` / `is_error`
  (Python field names only; the wire format is unchanged). The SDK serves both
  the 2026-07-28 protocol and the 2025-era `initialize` handshake that Claude
  Code and Claude Desktop send today; the release was verified over stdio with a
  raw 2025-06-18 handshake, with the SDK's own client, and with the live smoke
  test against Gephi 1.2.17 (126/126 tools pass). The `ui://gephi/graph-view`
  MCP App resource and its tool metadata carry over unchanged.
- **Every tool now carries annotations** (`readOnlyHint`, `destructiveHint`,
  `idempotentHint`, `openWorldHint`), classified by effect on the Gephi
  workspace: 24 read-only tools, 18 destructive ones (each already
  auto-snapshots for `gephi_undo`), the rest add or restyle without removing.
  Hosts that honor annotations can skip confirmation for reads and ask before
  `gephi_clear_graph`. Tools register through one helper so a new tool cannot
  ship unclassified.
- **`tools/list` and `resources/list` advertise a one-hour public cache hint.**
  105 tool schemas are about 77k characters; a host that honors the hint stops
  re-fetching them every session.
- **Server startup no longer pays for nltk.** `text_network` imported nltk and
  probed three corpora at module import, which every server process paid
  (about 1.4 s) before a single tool could run. The probe now runs on first
  use of lemmatization and is memoized; `import text_network` went from 1.4 s
  to 0.02 s. `LEMMATIZATION_AVAILABLE` still reads the same from outside.
- **`gephi_visual_qa` flags a graph that has been loaded but never laid out or
  styled** ("looks untouched": every node the same size and color). Exporting
  such a graph gives the block of overlapping default nodes rather than a map.

### Added (claude-plugin)
- **`/explore`**: the `/import-and-explore` flow for a graph that is already
  open in Gephi. It takes no file path; open the file in Gephi first and run
  the command on the current workspace.
- **`/export-map`**, the new name of `/visualize`. The command exports; laying
  out and styling live in `/beautify` and `/analyze-network`, and the old name
  suggested otherwise. It now checks `gephi_visual_qa` first and, on an
  untouched graph, offers `/beautify` before exporting. `/visualize` remains as
  an alias for one release.
- **`/community-detection` asks which method to run before running it**:
  modularity optimization with Louvain (Gephi's built-in) or Leiden (through
  the CWTS Leiden plugin, via `gephi_run_statistic`), or stochastic block
  model inference. The last is not implemented in Gephi, so the command says
  so and names graph-tool as the route instead of substituting a different
  method silently.

## Java plugin 1.2.17 / claude-plugin 1.9.32

### Fixed
- **Layouts ran on zeros instead of Gephi's defaults — OpenOrd collapsed the
  graph, Yifan Hu did nothing at all.** `findLayout()` returned
  `builder.buildLayout()` directly, and nothing in the plugin ever called
  `resetPropertiesValues()` — the method where Gephi actually installs a
  layout's defaults, which the desktop UI invokes when you select a layout in
  the panel. Every property the caller did not explicitly pass was therefore
  left at its Java zero-value. Measured on a 40-node graph: a bare
  `gephi_run_layout("OpenOrd")` put **all 40 nodes at (0, 0)**, because
  `Layout Size` was `0` and the output coordinate space had zero span; a bare
  `gephi_run_layout("yifanhu")` was a **complete no-op**, returning node
  positions byte-identical to before the run because `optimalDistance`,
  `initialStepSize`, and `stepRatio` were all `0`. Both reported
  `success: true`, so the only symptom was a silently wrong picture. ForceAtlas 2
  was never affected — its builder self-initializes, which is why the workhorse
  layout looked fine and the bug survived this long; the documented "large graph"
  workflow (Yifan Hu pre-pass, then FA2) had been quietly degrading to FA2-alone.
  `findLayout()` now attaches the graph model and calls `resetPropertiesValues()`
  before returning, in separate try blocks so a missing graph model cannot skip
  the reset. The graph model goes on first because size-dependent defaults read
  it (FA2 picks scalingRatio 2.0 vs 10.0 off the node count). Callers now only
  pass the properties they actually want to change.
- `gephi_get_layout_properties` consequently reported an un-reset instance's
  zero-values as though they were current settings or defaults, and — because
  every call built a fresh layout — never reflected a value set on a previous
  call. It now reports real defaults.

### Added
- `LayoutDefaultsTest` (3 tests, 48 total) pins the premise directly against the
  real Gephi layout classes: OpenOrd and Yifan Hu genuinely arrive on zeros,
  `resetPropertiesValues()` genuinely clears them, and ForceAtlas 2 genuinely
  self-initializes. Asserting the *before* state means that if a future Gephi
  release starts self-initializing these layouts, the test fails loudly rather
  than the fix quietly becoming redundant. Adds `layout-plugin` as a test-scoped
  dependency (at runtime these classes come from the host Gephi install).

### Changed
- **Skill: corrected the modularity resolution direction, which was backwards.**
  `statistics-guide.md` claimed resolution < 1.0 gives fewer, larger communities
  and > 1.0 gives more, smaller ones. It is the opposite. Verified on a graph
  built with 8 tight groups paired into 4: resolution 0.3 yielded **8**
  communities, resolution 1.5 yielded **4**. Gephi implements the
  Lambiotte-Delvenne-Barahona resolution, where raising the value *merges*
  communities — the reverse of the gamma convention in much of the modularity
  literature, which is the likely source of the error. Noted inline so it does
  not get "corrected" back.
- **Skill: OpenOrd is now documented.** It had appeared only as a name in a
  selection table with no parameter guidance at all. Adds exact property keys,
  the five-stage annealing schedule, a starting config, and the reproducibility
  caveat (output depends on seed, iteration count, *and* thread count; repeated
  runs with a fixed seed and one thread still diverged, so do not promise
  determinism). Property names are display names — `"Edge Cut"`, `"Layout Size"`,
  `"Liquid (%)"` — because OpenOrd exposes no dotted canonical names, so a
  camelCased `edgeCut` matches nothing and is silently discarded by
  `applyLayoutProperties`. Yifan Hu's camelCase keys do resolve, via the middle
  segment of `YifanHu.optimalDistance.name`.
- Skill: Yifan Hu gains `relativeStrength`, `initialStepSize`,
  `convergenceThreshold`, and `adaptiveCooling`.

## Java plugin 1.2.16 / mcp-server 1.11.0

### Added
- **`gephi_export_screenshot` (tool #105): selection-aware live canvas export.**
  `gephi_export_png` renders through Gephi's Preview pipeline, which works off
  the graph's stored data and has no concept of a live selection at all, so a
  box-drag selection could only be faked by recoloring nodes (the rest of the
  map stayed at full strength instead of dimming, visibly different from what
  the analyst actually sees on screen). This tool captures the LIVE Overview
  canvas instead, using Gephi's own built-in screenshot feature
  (`org.gephi.visualization.api.ScreenshotController`, the same backend behind
  the toolbar snapshot button) — selection highlighting, hover state, and
  current camera framing all show up exactly as rendered. `takeScreenshot()`
  is asynchronous (queued against the render engine via a `LongTaskExecutor`),
  so the Java side polls a dedicated fresh temp directory for the resulting
  file rather than assuming completion on return, then waits for the file
  size to stabilize before moving it to the requested path. Takes a `scale`
  multiplier rather than literal width/height, Gephi's screenshot API has no
  pixel-dimension control, only a scale factor on the current canvas size.
  Tradeoff documented in the tool's own docstring: this is the interactive
  Overview renderer, not the publication-quality Preview renderer, so output
  is visually rougher (no edge bundling, plainer typography) than
  `gephi_export_png`, use each tool for what it's for. `visualization-api`
  was already a compile dependency, no new Maven dependency needed. Tool
  count now 105 (README/SKILL.md/tool-reference.md/manifest swept).

### Fixed
- **`gephi_export_screenshot` actually worked only after two live-testing rounds
  surfaced real bugs, both root-caused against the real Gephi log/bytecode,
  not guessed:**
  - **`ScreenshotController` lookup was wrong.** The initial implementation did
    `Lookup.getDefault().lookup(ScreenshotController.class)`, which always
    returned null (`"Screenshot controller not available"`) —
    `ScreenshotController` is not independently registered in the global
    Lookup at all. It's only reachable via
    `VisualizationController.getScreenshotController()`, the same
    `VisualizationController` singleton `gephi_get_selection`/`gephi_focus_view`
    already use. Confirmed via `javap` on Gephi's own
    `org-gephi-visualization-api.jar`.
  - **Any write could crash the HTTP connection with zero response, unrelated
    to this feature.** `lockWrite()` only caught `InterruptedException`, so a
    `NoClassDefFoundError` (triggered live by rebuilding the plugin jar while
    Gephi was still running the previous build — a lazily-loaded class,
    `RenderPause`, failed to read from the now-different jar bytes on disk)
    skipped every `catch(Exception)` up the call chain and killed the NanoHTTPD
    connection thread outright (`curl`: "empty reply from server"). `lockWrite`
    now catches `Throwable` and converts it into a normal JSON error response,
    matching the pattern every other helper in this file already follows.
    Root-caused from Gephi's own `messages.log`, not symptom-guessed.
- **`gephi_focus_view`'s `select` response lied about what actually got
  selected.** It echoed back `select.size()` (the request) instead of the
  verified applied count — `selectNodes()` queues its effect onto the render
  engine asynchronously, so an immediate read (including the response field
  itself) could race ahead of it, and IDs that didn't resolve to a real node
  were silently counted as selected anyway. `focusView` now polls
  `getSelectedNodes()` (bounded, 1s) and reports the real, settled count.
  Live-testing this also surfaced a genuine Gephi-side limitation, not
  something in our plugin: `select`'s "custom selection" engine mode does not
  interoperate cleanly with `gephi_get_selection`'s read path (Gephi's own
  `setCustomSelection()` never clears the `rectangleSelection` flag
  `setRectangleSelection()` sets, confirmed via bytecode). Rather than paper
  over an engine-level inconsistency with more guessed code, both tools'
  docstrings now say plainly: `select` is for visual highlighting only, not
  for setting up a selection to read back later — only a real box-drag
  selection is guaranteed readable via `gephi_get_selection`.

## claude-plugin 1.9.31

### Changed
- **Dropped `/whatif`, kept `/counterfactual`.** Having two command names for the
  identical procedure (introduced in 1.9.30) was more confusing than helpful in
  practice. `/counterfactual` is now the single, self-contained command for
  testing a hypothetical edit against the loaded graph; `gephi_whatif` remains
  the underlying MCP tool name and is unchanged.

## claude-plugin 1.9.30

### Added
- **`/whatif` and `/counterfactual` slash commands.** The `gephi_whatif` tool
  (counterfactual graph surgery on a throwaway workspace copy) previously had no
  direct entry point beyond the claim-verifier agent's robustness checks. Both
  commands resolve a plain-language what-if question into an edit, run it, and
  report the diff as a hypothesis to check, never a verdict — matching the
  tool's own "measurements, not conclusions" framing. `/counterfactual` is kept
  as a separate name (the paper's vocabulary for this capability) but delegates
  to the same procedure as `/whatif`; no new MCP tool, mcp-server/nbm unchanged.

## mcp-server 1.10.0 / claude-plugin 1.9.29

### Added
- **Profile and QA enrichment: layout quality is measured, not eyeballed.** Six
  one-pass statistics folded into existing tools (no new tools; every number
  ships with a decision rule):
  - `gephi_profile_graph`: degree **Gini** (inequality) and **assortativity**
    (negative = hub-and-spoke; a strong negative raises a
    "enable distributedAttraction" flag), a **weight distribution** block when
    weights carry signal (`heavy_tailed` raises a "log-transform weights or
    lower edgeWeightInfluence" flag — the advance warning for FA2 numeric
    explosions on weighted graphs), and `clustering_expected_random` +
    `clustering_vs_random` — the configuration-model expectation for this exact
    degree sequence, so "highly clustered" is always relative to a baseline.
  - `gephi_visual_qa`: `partition.separation` — mean intra-community pair
    distance over mean random pair distance (1.0 = fully mixed, near 0 = tight
    clusters), the objective form of "did the communities separate," measured
    on the current layout for any partition (previously only reported by
    `gephi_community_layout`); `extent.outliers` + `extent.robust` — runaway
    nodes far outside the main cloud are detected (median center, 5x the
    90th-percentile radius) and `suggested_export` now frames the main cloud,
    ending the hub-and-spoke bounding-box blowout that forced Python
    centroid-cropping; non-finite positions are warned about and excluded from
    extent math.
  - `gephi_run_layout` (sync runs): a finite-positions check after every
    layout — a numerically exploded layout (non-finite or absurd coordinates,
    which Gephi reports as `success`) now returns a `layout_exploded` block
    with affected nodes and the fix instead of passing silently.

### Fixed
- **`gephi_profile_graph` never detected weighted graphs.** `parse_gexf` stores
  GEXF edge weight under `size`, but the profile read a nonexistent `weight`
  key, so `weighted` was always `false` and weight-based guidance never fired.

## mcp-server 1.9.24 / claude-plugin 1.9.28

### Added
- **One-level undo: `gephi_snapshot` + `gephi_undo` (104 tools).** Destructive tools
  (`clear_graph`, `merge_nodes`, `bulk_remove_nodes`, the filter/extract family, and
  `text_to_network` with `clear_existing`) now automatically save the workspace to a
  rolling `[undo] …` snapshot before running, and report `undo_available` in their
  result. `gephi_undo` restores the graph — nodes, edges, attributes, positions,
  appearance — exactly as it was; `gephi_snapshot` saves an undo point explicitly
  (e.g. before a sequence of per-node edits, which aren't auto-snapshotted). One
  snapshot exists at a time (taking a new one replaces the old, so memory stays
  bounded at ~2x the graph) and there is no redo. Implemented workspace-copy style
  (duplicate → rename → switch back), entirely on the Python side — no Gephi plugin
  change. Automatic snapshots are skipped above `GEPHI_SNAPSHOT_MAX_NODES`
  (default 200000) and can be disabled with `GEPHI_AUTO_SNAPSHOT=0`; a failed
  snapshot never blocks the operation itself.

## mcp-server 1.9.23 / claude-plugin 1.9.27

### Changed
- **`gephi_health_check` now shows both versions and an explicit freshness signal.**
  It reports `server_version` (the MCP server) alongside `version` (the Gephi plugin),
  plus `up_to_date: true` when the install is current or the `update` nag when it is
  behind. Previously it showed only the Gephi plugin version, which could read as
  current while the server (where the tools and the update check live) was stale.

## mcp-server 1.9.22 / claude-plugin 1.9.26

### Changed
- **`gephi_open_project` now warns that it discards the current project.** Opening a
  `.gephi` closes the current project first (needed for the load to work), which drops
  any unsaved changes in it without prompting — unlike Gephi's own File > Open. The
  docstring now says so explicitly, so the assistant offers to save (or confirm) before
  opening another file.

## mcp-server 1.9.21 / claude-plugin 1.9.25

### Added
- **Update check in `gephi_health_check`.** Once per session, health check compares
  the installed server/plugin and the Gephi `.nbm` against the latest release and, if
  behind, returns an `update` field with a surface-specific "how to update" line — so
  a stale install (the kind that silently hid `/teach` and newer tools) announces
  itself instead of failing mysteriously. Reads one canonical `latest.json` from the
  repo; fail-silent with a 2s timeout and cached per session, opt-out via
  `GEPHI_SKIP_UPDATE_CHECK=1`. Because the Claude plugin pins the server version, a
  behind-server signal also catches a stale plugin.

## mcp-server 1.9.20 / claude-plugin 1.9.24

### Fixed
- **Slow statistics no longer time out on large graphs.** `gephi_compute_betweenness`
  and `gephi_compute_avg_path_length` are all-pairs shortest paths (O(n·m)) and run
  past the default 60s request timeout on big graphs — a scale test found betweenness
  timing out at 10k nodes (it completed in ~77s, the client just gave up first). These
  tools plus `gephi_run_statistic` now use an extended timeout (`GEPHI_SLOW_TIMEOUT`,
  default 600s). The graph never wedged; only the client was cutting off early.

### Added
- **`tests/live_scale_test.py`** — a scale/perf harness running the core pipeline at
  1k / 5k / 10k with per-op timing, and **`tests/test_edge_cases.py`** — 26 headless
  unit tests for empty/directed/self-loop/parallel-edge/unicode/malformed/scale inputs.
  Live smoke harness gained integrity probes (import, save-open round-trip, GEXF
  round-trip, duplicate-workspace undo) and directed/empty edge-case scenarios.

## Java plugin 1.2.15 / mcp-server 1.9.19 / claude-plugin 1.9.23

### Fixed
- **Opening a `.gephi` project now actually loads the graph.** `gephi_open_project`
  reported success but landed in an empty workspace whenever a project was already
  open — the graphstore never deserialized, so a saved graph appeared lost (it was
  not; the file was intact). Root cause: the open did not close the current project
  first, so the load landed in a broken half-state. It now closes the current
  project before loading (as Gephi's own File > Open does) and returns the loaded
  `node_count`/`edge_count`, so an empty result is reported rather than silent.

### Changed
- Docstrings steer reversible experiments away from save/reopen round-trips:
  `gephi_duplicate_workspace` a copy and run the destructive step on the copy so
  "undo" is an instant workspace switch (no disk), or snapshot with
  `gephi_export_gexf` + `gephi_import_file`, which round-trips reliably. Noted on
  `gephi_open_project` and `gephi_filter_by_degree` (whose removals are permanent).

## Java plugin 1.2.14 / mcp-server 1.9.18 / claude-plugin 1.9.22

Makes the "point at the graph and the agent reads it" coupling work without setup.

### Changed
- **Box-drag selection is enabled automatically** at the start of a session. The
  human can drag a selection box around nodes right away and `gephi_get_selection`
  reads exactly those nodes, with no need to first pick the rectangle tool from the
  toolbar. Fires once and never overrides a mode the human later chooses.
- **`gephi_get_selection` reads through Gephi's public API**
  (`VisualizationController.getModel().getSelectedNodes()`) instead of reflecting
  into the internal render engine, so it is robust across Gephi builds rather than
  tied to one engine version.
- The selection reply now reports canvas state — `rectangle_selection`,
  `selection_enabled`, and `zoom` — so an empty selection can be explained (for
  example, the human switched mouse modes) rather than returned silently.

## Java plugin 1.2.13 / mcp-server 1.9.17 / claude-plugin 1.9.21

Two correctness fixes found by a full 102-tool live smoke test at 1000-node scale
(both invisible on small graphs). New reusable harness: `mcp-server/tests/live_smoke_test.py`.

### Fixed
- **Partition column resolved by id OR title.** `visual_qa`, `label_clusters`, and
  `community_layout` matched a partition column by its **title** while
  `color_by_partition` / `color_edges_by_partition` / `color_by_ranking` matched by
  its **id**. Gephi's modularity column is id `modularity_class` / title
  `Modularity Class`, so the canonical `modularity_class` made `visual_qa` report a
  real, strong community partition as "none" — silently misfiring the data-truth
  gate that `/beautify`, `/analyze-network`, and the layout-iterator agent depend
  on. `parse_gexf` now exposes an id/title/normalized alias map and a
  `resolve_column_key` helper; the three tools accept whichever name you pass.
  (mcp-server 1.9.17; 3 regression tests added.)
- **`set_layout_properties` no longer starts a layout.** It used to submit the
  layout to the executor as a side effect, so the natural `set_layout_properties`
  → `run_layout` sequence failed with "Layout already running." It is now
  configure-only and stages its config for the next `run_layout` of that algorithm;
  `run_layout(properties={...})` remains the one-step configure-and-run path.
  (Java plugin 1.2.13.)

## claude-plugin 1.9.20

Claude-plugin release (MCP server code unchanged). Adds specialized agents so
multi-step work runs in its own context and returns just the result, repairs a
drift in the existing analyst agent, and corrects the bundled server pin so the
plugin runs the full 102-tool server.

### Added — Agents
- **`claim-verifier`** — independently checks one plain-language structural claim
  ("she's more central than he is," "these two teams barely interact," "the org
  survives losing him") and reports **confirmed / refuted / can't-tell** with the
  actual number. Read-only; its value is independence — a fresh agent isn't rooting
  for the claim. New **`/verify-claim`** command dispatches it.
- **`layout-iterator`** — runs the whole run → visual_qa → inspect → adjust loop to
  a publication-ready map in its own context, returning the export, caption, and a
  change log. **`/beautify`** now dispatches it instead of inlining the loop.
- **`text-network-builder`** — turns free text (transcripts, field notes, survey
  answers) into a word co-occurrence network, inspecting the vocabulary and
  rebuilding with better stopwords/POS/frequency settings before layout. New
  **`/text-network`** command dispatches it.

### Changed
- **`network-analyst`** agent rewritten to be thin and defer to the gephi skill's
  reference docs rather than re-encoding analytical judgment; scoped to read-leaning
  tools (it interprets, it does not restyle) and given hard guardrails.
- All new agents and the analyst embed the same non-negotiables the skill teaches:
  never assert "scale-free"/"power-law," never read a metric in isolation, keep a
  first reading provisional, verify a claimed grouping before trusting it.

### Fixed
- **Scale-free drift** in the `/analyze-network` command: the degree-distribution
  and classification steps told the model to label distributions "scale-free /
  power-law," contradicting the skill (Jacomy 2020). Both now describe hub
  dominance as a property of *this* network and forbid the universal-law label.
- **Bundled server pin** in `.mcp.json` corrected from `gephi-mcp==1.9.1` (86
  tools) to `==1.9.16` (102 tools). The pin had lagged since the Groups C–G
  release, so the plugin was running a server that predated the filter, what-if,
  compare-nodes, edge-appearance, and text-network tools its commands and agents
  call.
- **Statistics reference** (`references/statistics-guide.md`) no longer equates a
  power-law degree distribution with a "scale-free network" — the one spot in the
  skill's own reference docs that still asserted the label the skill forbids.

## Java plugin 1.2.12 / mcp-server 1.9.16 / claude-plugin 1.9.19

Groups C–G of the integration-candidates build-out, in one plugin release —
completing the roadmap. Tool count 93 → 102. Every new API verified via `javap`
against the real Gephi module jars before building; graph-model cores TDD'd
against an in-memory `GraphModel`, runtime paths live-validated (which caught
several real issues unit tests couldn't — see Fixed and Known limitations).

### Added — Filters (Group C)
- **`gephi_list_filters`** / **`gephi_apply_filter`** — the general filter tools,
  the discover-then-apply shape of `list_statistics`/`run_statistic`.
  `list_filters` enumerates every built-in topology filter **plus a per-column
  attribute filter** for each column in the graph (static `FilterBuilder`s +
  `CategoryBuilder.getBuilders`), each with its settable properties.
  `apply_filter(name, params, action)` sets properties (a Range property takes a
  `[low, high]` pair) and applies with `action`: `select` (non-destructive
  visible filter), `new_workspace` (materialize the subgraph — the memory-safe
  path for repeated filtering), or `column` (write membership to a boolean
  column). Stack `select` calls for AND. New `references/filtering.md`.

### Added — Data Laboratory (Group D)
- **`gephi_column_value_frequencies`**, **`gephi_detect_duplicates`** — value
  distribution and duplicate-group detection over a column. Implemented as pure
  `GraphModel` cores (no datalab controller needed), so they're unit-tested
  against an in-memory model.
- **`gephi_merge_nodes`** (merge duplicates into one; destructive) and
  **`gephi_create_regex_column`** (boolean column flagging regex matches) via
  the datalab controllers.

### Added — Edge appearance + export (Group E)
- **`gephi_color_edges_by_partition`** — the edge twin of
  `gephi_color_by_partition` (color edges by relationship type / period / tier).
- **`gephi_export(file, format)`** — general export-by-format via
  `ExportController.getExporter(name)`: VNA, Pajek, DL, spreadsheet, GDF, JSON
  (UCINET/Pajek interchange, spreadsheets for non-technical readers). (`gml` is
  import-only in this Gephi build — no exporter — found by live validation.)

### Changed — Multigraph fix (Group F)
- **`gephi_add_edge`/`gephi_add_edges` accept an `edge_type` label.** Previously
  a node pair could hold only one edge (`newEdge(..., directed ? 1 : 0, ...)`
  hardcoded the type). Now a named `edge_type` creates the edge under
  GraphStore's native typed-parallel-edge mechanism (`GraphModel.addEdgeType`),
  with the duplicate check scoped to that type — so A→B can carry a "cites" edge
  AND a "coauthor" edge, while a second same-type edge is still a duplicate.
  Enables multiplex/multilayer graphs; compare layers by filtering to one edge
  type and computing modularity per layer. **Behavior with no `edge_type` is
  unchanged** (regression-tested).

### Added — Timeline (Group G)
- **`gephi_get_timeline`** — the graph's dynamic/timeline state: `is_dynamic`,
  time bounds, the `dynamic_columns` the timeline recognizes, interval state.
  Read-only; live-validated (correctly reports a dynamic import as dynamic with
  the right bounds). Reason over node/edge start/end values to narrate change
  over time.

### Known limitations (found by live validation, documented not shipped)
- **No programmatic time-window tool.** A `set_time_window` was built and then
  **removed** — driving Gephi's timeline from outside destabilizes its render
  thread in this plugin's synchronous-EDT architecture, two different ways:
  (1) the real data-level slice (`createView` + `setTimeInterval` +
  `setVisibleView`) *deadlocks* — `setVisibleView` forces a synchronous EDT
  render that wedges Gephi (the render/lock hazard the 1.2.0 write hardening
  was built for); (2) even the "safe" UI path (`TimelineController.setInterval`
  / `setEnabled`) works once, then further timeline calls time out on a
  saturated EDT. Normal writes are unaffected. Because Gephi's own shutdown runs on the EDT, a wedged timeline op also
  makes the app impossible to quit normally (Force Quit only) — so the write
  path was removed from the plugin entirely (endpoint + service method), not
  just the Python tool. `get_timeline` (read-only) ships; time-slicing is left
  to the Gephi timeline UI. Reviving a write path needs the ops wrapped in the
  viz-engine render-pause and off the EDT.
- **`gephi_apply_filter` `select`-action count is stale.** The response's
  `nodes_after`/`edges_after` read the visible graph before the filter model
  propagates in the same call, so they can report the pre-filter count even
  though the graph *is* filtered (verified: a Degree Range `[5,∞]` select shows
  `nodes_after: 339` but the exported visible graph is 64 nodes). Use
  `action="new_workspace"` or export the visible graph for an exact post-filter
  count.
- **`gephi_apply_filter` `new_workspace` doesn't materialize for property-based
  filters.** It works for parameterless topology filters (Giant Component →
  334-node workspace) but silently no-ops for filters whose property was set
  (Degree Range) — the `select` action filters those correctly, so use `select`
  (+ export the visible graph) for parameterized filters until this is fixed.

### Spike resolved — Timeline dynamic-import bug
- Reproduced live on Gephi 0.11.x: a programmatically imported dynamic GEXF **is**
  recognized at the graph-model level (`isDynamic` true, correct time bounds) —
  the feared 0.9.2-era "not recognized until save+reopen" bug does **not** block
  the data model. `TimelineController.getDynamicGraphColumns()` returns empty for
  a graph whose dynamics are node/edge *existence* (start/end) rather than
  time-varying *attribute* columns — which is correct, not the bug. (Programmatic
  data-level slicing is separately blocked by the renderer deadlock noted above.)

### Fixed
- **Range filters** (`gephi_apply_filter` with a `[low, high]` on Degree
  Range / Attribute Range) threw "Lower and upper must be the same class" —
  `org.gephi.filters.api.Range` requires both bounds to be the same `Number`
  subclass, but JSON parsing gave `Double`s that didn't match the filter's
  integer expectation. Now both bounds are coerced to the same class (Integer
  when whole, Double otherwise). Caught by live validation.
- **`gephi_merge_nodes`** threw an NPE ("columns is null") — the datalab
  controller's `mergeNodes` reads `columns.length`, so `null` fails; now passes
  empty `Column[]`/strategy arrays (reassign edges, keep the survivor's
  values). Caught by live validation.
- Health endpoint reported a stale hardcoded `version` ("1.2.5"); now tracks
  the release.

### Findings
- The candidates doc's premise that attribute filters would need bespoke wiring
  is avoided: they're reachable generically via `CategoryBuilder`, so one
  `apply_filter` covers the whole ecosystem including per-column attribute
  filters — no per-filter code.

### Tests
- New Python tool→endpoint tests (filters, data lab, edge color, export,
  get_timeline).
- 8 new Java in-memory-`GraphModel` tests: Data Lab cores (frequencies,
  duplicates incl. case-sensitivity) and the typed-parallel-edge fix (untyped
  duplicate still blocked — regression; different types coexist; same type
  blocked; batch honors per-edge type). Java suite 31 → 39, Python 137 passing.
  Tool-count guard 93 → 102.

## Java plugin 1.2.6 / mcp-server 1.9.13 / claude-plugin 1.9.16

Group B of the integration-candidates build-out — two small Desktop-controller
features. Tool count 90 → 93. Java-side (needs the rebuilt plugin + a Gephi
restart); all three tools live-validated against a running Gephi.

### Added
- **`gephi_set_selection_mode(mode)`** — sets the canvas mouse-selection mode
  (`rectangle` / `direct` / `disable`) via `VisualizationController`. Fixes a
  documented friction: the pointing feature (`gephi_get_selection`) needed the
  human to first click the toolbar's dashed-square icon; calling this with
  `rectangle` at the start of a teaching session makes box-select work
  immediately.
- **`gephi_get_perspective`** / **`gephi_switch_perspective(name)`** — list the
  top-level tabs (Overview / Data Laboratory / Preview) and switch between them
  via `PerspectiveController` (switch runs on the EDT). Brings the human's view
  to the right tab before discussing it.

### Findings
- The candidates doc's premise that `ToolController.select(Tool)` could
  pre-select the rectangle-selection gesture is **refuted**: the actual `Tool`
  SPI implementations (EdgePencil, NodePencil, Brush, Painter, Sizer,
  ShortestPath, HeatMap, Edit, NodesDragger) contain no selection tool — the
  gesture is the visualization engine's selection manager. The right mechanism
  is `VisualizationController.setRectangleSelection()`, a one-line extension of
  the controller `focusView` already uses. `ToolController` is dropped from the
  plan (its tools are manual editors with no LLM-workflow value). Verified via
  `javap` on the real Gephi module jars before building — caught before a
  wasted build.

### Tests
- 4 new Python tool→endpoint tests (selection mode default + override,
  perspective get, perspective switch). Java side is runtime-only (no
  in-memory-model core to unit-test) so it's covered by compile-against-the-real-API
  + live validation. Tool-count guard 90 → 93.

## mcp-server 1.9.12 / claude-plugin 1.9.15

First increment of the integration-candidates build-out (Group A): Python-only
orchestration that composes already-shipped tools, no Gephi plugin change. Tool
count 88 → 90.

### Added
- **`gephi_whatif(edits, include_slow=False)`** — counterfactual graph surgery.
  Duplicates the current workspace, applies hypothetical edits (`remove_node`,
  `remove_nodes`, `add_edge`, `remove_edge`) to the throwaway copy, diffs the
  structural profile before/after, and always cleans up the scratch copy — the
  real graph is never touched. Cleanup is id-correlated (survives the index
  shifts a workspace delete causes) and runs even if an edit fails. Returns
  `{diff: [{metric, before, after, delta}], cleanup}` for nodes, edges,
  density, degree, components, isolates, modularity, communities, clustering
  (+ path length/diameter when `include_slow`). For "what would removing this
  node do to path length and community structure?" scenario-testing.
- **`gephi_compare_nodes(id_a, id_b, metric)`** — deterministic two-node
  comparison on one metric (from a node's attributes or a built-in field).
  Returns which node is higher and by how much; errors clearly if the metric
  column isn't computed yet. The checkable answer to "is X more central than Y".
- **`references/claim-verification.md`** — skill reference generalizing the
  `gephi_visual_qa` partition-truth-test into a general workflow: classify a
  plain-language structural claim → run the matching measurement → report
  confirmed / refuted / **can't-tell**, with the number. Covers comparison,
  connectivity, centrality, and robustness claims, and the discipline of
  matching the metric to the word ("bridge" = betweenness, not degree).

### Changed
- The metric-panel computation is extracted from `gephi_profile_graph` into a
  shared internal `_compute_profile` helper, now used by both it and
  `gephi_whatif` — no metric logic duplicated.

### Tests
- 8 new tests (`gephi_whatif` orchestration incl. id-correlated cleanup and
  cleanup-on-edit-failure via a stateful workspace fake; `gephi_compare_nodes`
  attribute/field/tie/missing-metric paths). Suite 110 → 118 passing; tool-count
  guard updated 88 → 90.

## mcp-server 1.9.11 / claude-plugin 1.9.14

Follow-up to the self-referential-hub work below, prompted by a fair
challenge: hand-curating a stopword list (like the one used to clean up a
generic-word mega-cluster on a test corpus) solves one dataset and overfits
the next — a word that's generic scaffolding in one corpus could be exactly
the topic in another. Tested whether a structural graph metric could replace
the manual judgment call; confirmed on real data that graph-level metrics
can't, but a text-level one (peak per-document count) carries real signal,
and along the way found that one specific word had been excluded too
bluntly on that test corpus.

### Added
- **`context_snippets`** on `build_cooccurrence_graph`/`gephi_text_to_network`
  (default 0, off) — attaches short excerpts of original surrounding text to
  each `self_referential_candidates` entry, so the ~40-50% document-frequency
  gray zone (where genuinely generic words and genuinely topical hub words
  are statistically indistinguishable) can be resolved by reading real
  sentences instead of hand-grepping source text or guessing from a word list
  tuned on a different corpus. Excerpts are drawn from each word's
  *highest-count* documents first, not just the first documents it happens to
  appear in — needed to catch a word that's concentrated as a genuine
  sub-topic in a handful of documents (see Findings).
- **`peak_document_count`** on every `self_referential_candidates` entry — the
  word's single highest per-document occurrence count. On the real corpus
  that motivated this, truly generic words peaked at 12-16 in their heaviest
  document, while every genuinely topical word tested peaked at 30-175 — a
  real, consistent (if imperfect) discriminator, reported as evidence to
  weigh alongside the excerpts, not an automatic cutoff.
- 5 new tests for `context_snippets` and `peak_document_count` (110 total, up
  from 105).

### Findings
- Tested two structural alternatives to a manual stopword list — post-
  backbone degree and edge-weight concentration (a Herfindahl-style measure
  of whether a word's connections concentrate on a few strong partners or
  spread thin) — on the real corpus that motivated this. Neither separates
  generic scaffolding from a genuine topic hub: a word correctly excluded as
  generic scaffolding and a word worth keeping as a real topic landed in the
  same range on both metrics. Graph-level co-occurrence structure alone can't
  be trusted to auto-classify this gray zone.
- Caught a real mistake by re-checking with the fixed `context_snippets`
  ordering: reading two arbitrary example sentences for one word made it
  look like pure filler, supporting its earlier full exclusion from the test
  graph. But its single highest-count document used that word well over a
  hundred times and turned out to be a genuine document specifically about
  that word's own subject. The earlier blanket exclusion (documented below)
  discarded that real sub-topic along with the actual scaffolding use
  elsewhere in the corpus; there was no way to catch this without checking
  where a word was concentrated, not just where it was scattered.

## mcp-server 1.9.10 / claude-plugin 1.9.13

Direct result of reflecting honestly on a real full-text rebuild: a manual
top-frequency stopword check missed a word present in 254 of 255 documents,
because raw frequency rank can't distinguish "real topic" from "corpus-wide
scaffolding." Fixed the tool, not just the one instance.

### Added
- **`document_frequency` on every node**, and **`stats.self_referential_
  candidates`** on `build_cooccurrence_graph`/`gephi_text_to_network` — flags
  any word appearing in at least `self_referential_threshold` (default 0.5)
  of documents as a candidate self-referential/generic hub, computed
  automatically rather than requiring a manual frequency-ranking eyeball
  check (which is exactly what missed a 99%-of-documents word on a real
  corpus).
- **`exclude_self_referential`** — actually drops flagged words from the
  graph before windowing (same gap-closing treatment as `pos_filter`/
  `min_word_frequency`), rather than only reporting them. Default off
  (reporting a methodological choice like dropping half a corpus's
  vocabulary should be deliberate, not silent).
- Documented a deeper, structural finding this surfaced: on a large multi-
  document full-text corpus, a high `min_word_frequency` floor **on its
  own** can select FOR generic words, not against them — a word needs
  sustained presence across many documents to reach a high total count. On
  a real 255-article corpus this meant half the vocabulary surviving a
  frequency floor was flagged as present in most documents; modularity was
  0.47 and communities read as generic scaffolding ("Time & Temporal
  Narrative," "Everyday Speech & Quotation"). Turning on
  `exclude_self_referential` and lowering the frequency floor (no longer
  needing double duty as a generic-word filter) raised modularity to 0.60
  and produced sharply topical communities instead ("Chinese Family Firms &
  Capitalism," "Ethics, Codes & Professional Networks").
- 8 new tests for document-frequency tracking and the exclusion filter (105
  total, up from 97).

## mcp-server 1.9.9 / claude-plugin 1.9.12

### Added
- **`merge_phrases` on `gephi_text_to_network`/`build_cooccurrence_graph`** —
  detects cohesive two-word phrases ("machine learning") and merges them
  into a single node instead of leaving them as two separately co-occurring
  unigrams. A candidate pair must clear two independent tests: a
  content-bearing POS pattern (adjective+noun or noun+noun) and pointwise
  mutual information above a threshold — POS pattern alone still passes
  grammatically-adjacent-but-unrelated pairs; PMI alone would merge two
  merely-frequent unrelated words. New `extract_phrases` function exposed
  separately for inspecting candidates before enabling the merge. Default
  off (pure unigrams, unchanged prior behavior).
- Fixed a real bug this surfaced immediately on real data: a merged phrase
  could hide a stopworded word from the stopword filter (two words
  individually stopworded as a corpus's own self-referential subject name,
  but slipping through as a merged phrase) — phrase candidates are now
  dropped if either half is a stopword before merging.
- 13 new tests covering phrase detection, the PMI/POS-pattern gates, the
  stopword-leak fix, and end-to-end integration with
  `build_cooccurrence_graph` (97 total, up from 84).

## [1.9.11] (Claude Code plugin only)

### Fixed
- **Corrected 1.9.10's "crowded core = resolution problem" claim.** Root
  cause was actually a request-building bug in this session's own manual
  testing: raw HTTP calls to `/layout/run` were sent with the tuning values
  under a `"params"` key instead of the correct `"properties"` key. The
  endpoint accepted this silently (`success: true`) and ran every layout on
  plugin defaults regardless of what was "set" — which is why five very
  different `scalingRatio`/`gravity` combinations plus a `"Noverlap"` pass
  all produced nearly the same layout extent. Fixing the key and re-running
  the *exact same* first parameter values that had appeared to do nothing
  produced an immediately, clearly better-separated layout. The 2x-crop
  "fix" from 1.9.10 worked around the symptom without addressing the real
  cause and is no longer the recommended approach.
- Softened the ForceAtlas 2 numerical-explosion gotcha (SKILL.md) to not
  attribute it to a specific parameter combination, since that combination
  was set via the same broken request pattern and its actual active
  properties at the time are now unconfirmed.

### Added
- Documented the `"params"` vs `"properties"` request-key bug and the
  `"Noverlap"` zero-default trap directly, with the diagnostic tell (a
  layout that seems insensitive to a parameter across a wide range is
  itself the anomaly, not a property of the graph).

## [1.9.9] (Claude Code plugin only)

Craft knowledge from actually applying 1.9.8's new capabilities
(`min_word_frequency`, `gephi_extract_backbone`) to a real hairball complaint,
plus two more research-report triages (text preprocessing, visual layout,
cluster-naming methodology).

### Added
- **Alpha calibration warning on `gephi_extract_backbone`**: the disparity-
  filter literature's common alpha (0.05-0.1) is calibrated for networks with
  far more skewed per-node weight distributions than word co-occurrence
  produces; used naively it can collapse a graph almost entirely (observed:
  1292 edges to 8). Sweep alpha and check connectivity at each value instead
  of trusting the literature default.
- **Neutral gray edge color as the styling default for text networks**,
  documented as an exception to the general skill's per-source edge-coloring
  default — cross-referenced in both SKILL.md and the text-network reference.
- **Reframed decluttering guidance**: `min_word_frequency` +
  `gephi_extract_backbone` (actually pruning the graph) are now documented as
  the real fix for a hairball; `edge.rescale-weight` (visual-only) is
  reframed as a fast first look, not a fix — learned by watching the rescale
  trick fail to resolve a real density complaint that frequency-floor +
  backbone extraction then did resolve.
- **Cluster-label placement**: documented that a cluster's highest-degree
  node can be geometrically buried by its own same-color neighbors in a
  dense core, causing a correctly-set label to render invisibly (confirmed
  present via the API, absent from the exported pixels). Neither "Label
  Adjust" nor enlarging the buried node reliably fixes this (the latter just
  buries a different neighbor); repositioning the caption to a same-cluster
  node nearer the cluster's visual edge does.
- **Centrality-weighted label candidates**: pick cluster-naming candidates
  from degree *and* betweenness together, not degree alone — a cluster's
  most-repeated word and its most structurally-load-bearing word are
  frequently different words.
- Extended the "considered, deliberately not built" list: similarity-mapping
  (VOS/MDS) layouts, automated LLM-based cluster labeling, WebGL/LoD
  rendering for custom viewers — noted as real techniques that don't fit
  this tool's scope, with reasoning, rather than left unaddressed.

## [1.9.8] (MCP server + Claude Code plugin)

Triaged two computational-linguistics research reports on text-network-
analysis best practice against the current tool and implemented what was
genuinely a gap; documented the rest as deliberate scope decisions rather
than silently skipping them. Also fixed a real community-naming mistake
this triage surfaced.

### Added
- **`pos_filter="nouns"` on `gephi_text_to_network`/`build_cooccurrence_graph`**
  — restricts the graph to noun tokens before windowing (Rule, Cointet, and
  Bearman 2015: nouns carry a discourse's topical structure; verbs/
  adjectives add texture but also noise for topic mapping). Falls back to no
  filtering, disclosed via `stats.pos_filter_applied`, if the POS tagger
  isn't installed.
- **`min_word_frequency` on the same tool** — drops words below a corpus-
  wide occurrence count before windowing, a node-level floor distinct from
  the existing edge-level `min_edge_weight`. Standard practice for Zipfian
  text where most unique words occur once or twice and only add long-tail
  clutter.
- **`gephi_extract_backbone`** (new tool) — prunes a graph to its
  statistically significant backbone using the disparity filter (Serrano,
  Boguna, and Vespignani 2009): edge significance is judged per node,
  relative to how that node's own weight is split across its neighbors,
  rather than against one global cutoff every edge must clear. Works on any
  weighted graph, not just text networks. A more principled alternative to
  `min_edge_weight`'s flat threshold and to the previous session's
  `edge.rescale-weight` visual-only decluttering trick (which is still
  documented and still useful as a non-destructive first look).
- Skill reference (`text-network-analysis.md`) sections for all of the
  above, plus a documented "considered and deliberately not built" list
  (virtual edges via embeddings for short/sparse texts, multi-word/compound-
  noun extraction, syntactic dependency networks as an alternative edge-
  construction paradigm, discourse-state classification, distinctiveness
  centrality) with the reasoning for each, and a caveat that stripping
  negation words ("not"/"no"/"never") trades away sentiment/polarity
  information that co-occurrence graphs can't represent anyway.

### Fixed
- **A real community-naming mistake, caught by spot-checking against source
  titles**: a modularity class on a real test corpus had been named "Design,
  Ethics & Advertising" from its top-3 highest-degree words, implying one
  coherent topic. Reading the actual titles behind those words showed at
  least four unrelated articles (design pedagogy, advertising history,
  interdisciplinary collaboration, organizational innovation) that all
  happened to use "liminality" as a theoretical frame — a shared-vocabulary
  cluster, not a shared-topic one. Renamed to "Liminality Across Contexts"
  and added a new skill-doc section on the general failure mode: naming a
  cluster from top words alone can mistake a reused theoretical term for a
  real subject, catchable by reading source documents behind 2-3 of a
  class's top words (not just the highest) before finalizing a name.

## [1.9.7] (Claude Code plugin only)

Craft knowledge from a live, real-corpus text-network session (10 years of
academic article titles, 255 documents).

### Added
- **Weight-based edge rescaling for decluttering dense co-occurrence
  graphs**: `edge.rescale-weight` with a wide min/max range and low base
  opacity renders weak, single-occurrence edges as nearly invisible and
  real repeated co-occurrences as bold, surfacing a graph's backbone
  structure without deleting any data. Documented in
  `references/text-network-analysis.md`.
- **Betweenness caveat**: a high-betweenness, low-degree word can be a
  citation/bibliographic artifact (author names, cities, publishers embedded
  in book-review titles) rather than a genuine bridge concept — check the
  source text before reporting one as a finding.
- **ForceAtlas 2 numerical explosion gotcha**: a specific parameter
  combination (high gravity + high edge-weight-influence + many iterations
  on a weighted graph with a high-weight hub) drove node coordinates to
  non-finite values silently (the layout call still reports success).
  Documented with the fix in SKILL.md's known-issues section.

## [1.9.6] (MCP server + Claude Code plugin only)

### Fixed
- **`gephi_text_to_network` / `build_cooccurrence_graph` no longer bridges
  co-occurrence windows across document boundaries.** The function accepted
  only one string, so a caller with many natural documents (article titles,
  survey responses) had to concatenate them first — and the sliding window
  would then silently connect the last word of one document to the first
  words of the next, for every boundary in the corpus. `text` now also
  accepts a list of strings; the window resets at each item. A single string
  still works exactly as before. `stats.document_count` reports how many
  units were actually processed.
- Removed a stray InfraNodus citation from `gephi_text_to_network`'s
  docstring (the tool's own design intentionally doesn't reference it).

### Added
- Skill reference guidance on checking for a self-referential hub before
  styling by degree/frequency: a corpus that is *about* one subject (a
  journal's own name in its own article titles) will surface that subject as
  the dominant node without it reflecting any real structure — add it to
  `extra_stopwords` and rebuild rather than reporting it as a finding.

## [1.9.5] (MCP server + Claude Code plugin only)

### Added
- **`gephi_text_to_network`** — builds a word co-occurrence graph from free
  text (lemmatized, stopwords removed, proximity-weighted sliding window)
  and loads it directly into Gephi via the existing node/edge tools. No new
  Java endpoints needed. New `text_network.py` module carries the pure
  conversion logic, covered by its own unit tests independent of any MCP or
  Gephi connection.
- Lemmatization via NLTK's WordNet lemmatizer with POS tagging (not
  stemming — the output words become visible node labels, so a stemmer's
  mangled fragments would be visible in the graph). Degrades gracefully to
  lowercasing only if NLTK's corpus data isn't installed locally; the tool's
  returned stats disclose which mode actually ran.
- New skill reference `references/text-network-analysis.md`: when a
  structural gap is meaningful versus a sampling artifact, window-size
  tradeoffs, reading betweenness centrality as bridge concepts on a text
  network, and the lemmatizer's known limitations.

### Changed
- Added `nltk>=3.8` to `mcp-server`'s dependencies.

## [1.9.4] (Claude Code plugin only)

The reading craft deepened from Jacomy's wider corpus (the 2021 dissertation,
the 2015 visual network analysis working paper, Unblackboxing Gephi, and the
epistemic clashes article).

### Added
- **New reading rules:** what distance means in one sentence (nodes are close
  when they are close to the other close nodes in common); proximity works
  one way only (connected pairs tend to be close, close pairs are rarely
  connected); stars are not clusters (a hub's audience is not a community);
  structural holes are density gradients, not absences.
- **New reading-process steps:** watch for stretchings (extended structures
  the layout shows but modularity misses — never let a modularity score be
  the last word), and offer complementary views rather than one exhaustive
  image.
- **Anti-storyletting rule:** every final export ships with copy-ready
  caption text (data, layout and settings, encodings, what the map does and
  does not license) so no image circulates without its story.
- **Heavy-tail honesty:** never claim "scale-free" from a heavy-tailed degree
  distribution; describe hub dominance as a property of this network, not a
  law.
- **Layout guide: interpretation regimes** — small networks are read
  diagrammatically, large ones topologically; judge layouts by the right
  regime's standards.
- **The craft's sources, cited and recommended.** A matched-source table
  (mostly open access) for when a question goes deeper than the conversation
  can carry; /teach closes by offering one thread to pull; and
  publication-bound maps get proper software citations in their caption
  (Gephi, ForceAtlas 2, modularity, and plugins per their own papers) — the
  tools people use are citable scholarship, and the assistant now says so.

## [1.9.3] (Claude Code plugin only)

### Added
- **Elicit before you tell.** At the moments that shape interpretation (first
  look at a new layout, after an attribute overlay, when the person points at
  something), the assistant asks one concrete question — "where does your eye
  go first?" — before giving its own reading, then compares the two aloud.
  The person's unprimed look is evidence that the assistant's fluency would
  otherwise erase. Never on task turns, never withholding (asking without
  telling is a quiz), and dropped for the session at the first wave-off.
- **Teaching sessions close with mutual teachback.** Understanding is
  demonstrated by teaching back, not by nodding along: /teach now ends with
  the person restating the map (checked against the reading rules) and the
  assistant restating their domain (checked by them), each side repairing the
  other. Sessions also close by naming how the exchange changed each side —
  what the assistant now does differently because of the person, and the
  invitation to reflect the other way.

## [1.9.2] (Claude Code plugin only)

### Fixed
- **Fresh `claude plugin install` now connects.** The plugin's MCP config
  launched the server from a path relative to the plugin directory, which only
  exists on development installs; normal installs copy just the plugin subtree
  into a cache, the path resolved to nothing, and the server silently failed
  to connect. The config now runs the published server from PyPI
  (`uvx --from gephi-mcp==1.9.1 gephi-mcp`), which works from any install
  location. Requires [uv](https://docs.astral.sh/uv/), same as before.

## [1.9.1]

Pointing, made legible: what the person selects in the Gephi window becomes
something the conversation can read.

### Added
- **`gephi_get_selection`** (86 tools now, Java plugin 1.2.5): reads the
  human's current selection in the Gephi window — drag a rectangle selection
  around nodes, walk back to the conversation, and "what did I select?"
  resolves to the exact nodes without anyone typing node names. Returns the
  persistent selection (capped at 200, with the true count) plus a secondary
  journal of node clicks (a passive listener that never interferes with
  Gephi's own tools; only populated in selection modes that persist).
- **Skill: teaching mode teaches pointing back.** When the person uses
  deictic words about the canvas ("these", "this group"), the selection is
  read first; sessions open by showing the rectangle-selection tool as the
  way to ask about nodes.

*(1.9.0 was published to PyPI with click-journal-only wording before the live
test showed hover highlighting never persists; 1.9.1 is the corrected,
verified release.)*

## [1.8.0]

Continued lessons from real reply-network data: force layouts cannot separate
communities in tree-like networks, so the fix ships as a layout of its own.

### Added
- **`gephi_community_layout`** (85 tools now): one radial fan per detected
  community, packed as discs — hub at center, members ringed by graph distance,
  branch angles sized by subtree. For tree-like networks (replies, retweets,
  mentions, seeded citations) whose star-shaped communities interleave under
  ForceAtlas 2 no matter how long it runs. Reports a separation score
  (mean intra-community pair distance over mean random pair distance; 1.0 =
  fully mixed) before and after, and carries its changed reading rule in the
  result: disc placement is arranged for legibility and means nothing.
- **Profile detects tree-like networks.** `gephi_profile_graph` flags graphs
  with barely more ties than nodes and points to `gephi_community_layout`
  before force-layout iterations get wasted (measured on a real reply
  network: 4,000 LinLog iterations improved separation only 0.88 to 0.84;
  the community layout reached 0.10).
- **Layout guide: tree-like section** — why force layouts fail structurally,
  the separation score as the judge (below ~0.5 captions work, above it use a
  legend), the changed reading rules, and labels-are-a-budget (hub-only
  labels, collision-thinned for exports).

### Fixed
- **Java plugin 1.2.4:** `/preview/settings` now unwraps a body mistakenly
  nested under a `"settings"` key instead of silently storing the nested map
  as a junk preview property named `settings`, and the property fallback
  skips non-scalar values. The documented body shape (flat
  `{property: value}`) is unchanged.

## [1.7.3]

Lessons from the first large real-world dataset (a 40k-tweet, 12k-user
mention network), each failure converted to a fix:

### Added
- **Profile detects dandelions.** `gephi_profile_graph` flags leaf-majority
  networks (most nodes with a single tie) and prescribes the readable-map
  recipe: filter to the degree >= 2 skeleton, keep the full graph for
  statistics.
- **Layout guide: real-world harvest section** — fragmentation and
  leaf-majority as expected shapes (not errors), skeleton mapping, the
  Contraction-until-QA-clean extent fix, arrowhead removal for directed hub
  maps, legend-instead-of-captions when communities interpenetrate, and the
  rgb() color-string note for external re-renders.

### Fixed
- **Gephi plugin 1.2.3:** preview settings now apply even when the workspace's
  preview property registry was never initialized (putValue fallback) — this
  made `arrow.size`, `edge.thickness`, and friends silently no-op on fresh
  workspaces (the "Set 0 preview properties" warning caught it live).

## [1.7.2]

### Added
- Claude plugin only. New skill reference **"Reading a Network Map"** — a
  guided interpretation process adapted from Mathieu Jacomy's visual network
  analysis teaching (MDO lecture 2026; Jacomy & Grandjean, "Translating
  Networks", DH 2019): reading rules stated up front (axes mean nothing, only
  distances; reruns keep clusters, not positions; boundaries are debatable,
  clusters are not), temporary letter-naming before earned names, structural
  holes treated as findings, attribute colors overlaid only AFTER structure is
  identified so agreement and disagreement both become discoveries, and a
  special-nodes inventory mapping visual situations to the metrics that find
  them (bridges -> betweenness, within-cluster hubs -> degree, off-color
  outliers -> attribute vs. position). Wired into /analyze-network (a reading
  pass after the numbers) and /teach (the rules taught explicitly, with the
  randomize-and-relayout demonstration). Honest limitation noted: very dense
  networks are better served by matrices, which gephi-ai does not render.

## [1.7.1]

### Changed
- **The first reading is provisional by design.** The opening-move guidance
  (skill and `gephi_profile_graph` docstring) now enforces an exploration-first
  stance: impressions are presented as things to check together, every pattern
  is paired with a rival explanation, the opening closes with places to look
  rather than a plan, verdict language waits until a check has run with the
  person, and the model's own impressions are tested exactly like the user's
  expectations. The profile informs the conversation; it does not conclude it.

## [1.7.0]

### Added
- **The opening move: `gephi_profile_graph` (tool #84) + intake-first guidance.**
  One call profiles the whole graph (size, density, degree distribution,
  components, isolates, weight signal, modularity, clustering coefficient,
  auto-raised flags for fragmentation, hub dominance, and likely hairballs) —
  one approval prompt instead of six, and a quantitative picture a language
  model reads at a glance. The skill and the /import-and-explore and
  /analyze-network commands now open every network conversation the same way:
  ask what the nodes and ties are and what the person wants to learn, run the
  profile, give a plain-language first reading, and let BOTH guide every
  downstream decision — their goal picks the metrics, size and density pick
  the layout, their expected groupings get tested against the partition
  baseline before being used for color, isolates are asked about rather than
  silently removed, and clusters are captioned in their vocabulary.
- The skill now carries a version stamp, so an outdated installed plugin is
  visible in conversation (see the README's new Updating section).

## [1.6.0]

### Added
- **`gephi_similarity_layout` (tool #83) — an embedding-based layout, a category
  nothing in the Gephi ecosystem offers.** Nodes are placed by structural role
  (spectral eigenmaps of the normalized Laplacian, projected to 2D), so people
  who occupy similar positions in the network sit together even when not
  directly connected. Computed entirely in the Python layer and delivered
  through the existing positions endpoint, so it works in desktop Gephi today
  and will work headless unchanged. Base install covers it with numpy + scipy
  (new dependencies); UMAP or t-SNE projections are used automatically when
  those packages happen to be present, never required. The tool states its own
  reading rule (proximity = similar role, not connection) and the layout guide
  gains the matching purpose row.

## [1.5.3]

### Changed
- Claude plugin only (server and Gephi plugin unchanged). The layout guide now
  opens with a purpose-first selection table ("show me the groups" -> ForceAtlas
  2; huge networks -> OpenOrd then FA2; overlapping nodes -> Noverlap; maps,
  circles, bipartite layers -> the matching portal plugins), written in plain
  language so explanations work for non-technical users. README install flow
  reorganized around the same goal: one-click Claude Desktop bundle first,
  build-from-source moved to a Development section.

## [1.5.2]

### Added
- **Plugin-ecosystem passthrough completed.** Gephi plugin 1.2.2 adds
  `/statistics/available` and `/statistics/run` (run any statistic by name);
  new tools `gephi_list_statistics` and `gephi_run_statistic` (82 tools total).
  Layout passthrough already worked and is now verified and documented: install
  any portal plugin and drive it by name (verified live with Force Atlas 3D and
  the CWTS Leiden Algorithm plugin).
- **From Files to Networks recipes** in the skill and `gephi_import_file`
  docstring: spreadsheets, CSV, JSON, RDF, adjacency matrices, bipartite and
  similarity data all become graphs conversationally via batched
  add-nodes/add-edges — no importer plugin required.
- Skill section on the plugin ecosystem (Noverlap/OpenOrd/Label Adjust are
  bundled in core; Leiden recommended for large networks).

## [1.5.1]

### Added
- **Gephi plugin 1.2.1 — leak-hardening + ergonomics.**
  - Every live NodeIterable/EdgeIterable iteration in the plugin now runs over a
    `toArray()` snapshot, closing the *exception-path* variant of the read-hold
    leak fixed in 1.2.0 (an exception mid-iteration leaked the same way an early
    break did). The iteration rule is codified next to the lock helpers.
  - `size_by_ranking` / `color_by_ranking` by a degree column now auto-compute
    the degree statistic instead of failing with "Column not found" on a cold
    graph; missing-column errors name the fix.
  - `export_gexf` without a file path (or with `inline: true`) returns the GEXF
    document in the response — no file round-trip.
- `gephi_run_layout` guidance and the layout guide now give size-banded starting
  `scalingRatio` values (under ~1k nodes start 1-2; 1k-10k start 2-4; above 10k
  start 4-8) — starting high over-spreads into specks.
- Skill: the "Graph is busy" gotcha now tells Claude exactly how to act on the
  wedge detectors (`graph_lock`, `graph_lock_stats.readers`, `queued`), including
  saying plainly when only a Gephi restart will recover.
- `parse_gexf` in the viewer package accepts a GEXF document string as well as a
  file path.

## [1.5.0]

### Added
- **Gephi plugin 1.2.0 — the "protect the teaching mode" build.** Three defenses
  against the macOS renderer wedge plus camera control:
  - **Writes pause the renderer.** The viz engine's own `pauseUpdating()` /
    `resumeUpdating()` (reference-counted, reflective, no-op when headless) now
    brackets every write section, removing the read-lock pressure that caused the
    chronic deadlock while Claude mutates the graph under a live view.
  - **Nothing hangs anymore.** Read-lock acquisition is now timed (like writes have
    been), and UI-thread calls use a bounded wait — a wedged Gephi returns an
    immediate "Gephi is wedged; fully quit and reopen it" error instead of hanging
    until the client times out. `/health` gains a `graph_lock` probe ("ok"/"busy")
    as a cheap wedge detector.
  - **`gephi_focus_view` (tool #80).** Camera and attention control for the Gephi
    window: fit the graph, center on a node/edge/region, visually select nodes, set
    zoom — so Claude can direct the human viewer's eyes while it works. The missing
    piece for watch-along sessions.
- **`/teach` command + Teaching Mode skill section**: narrated pacing, chunked
  layouts, camera direction before discussion, observation pauses — codifying
  watch-Gephi-operate as a first-class use.
- `/health` also reports `graph_lock_stats` (live reader count, write-locked flag,
  queue length from the underlying lock) — a nonzero reader count while Gephi is
  idle means a leaked read hold, the precursor of a wedge.

### Fixed
- **A long-standing wedge source found and killed.** `get_nodes` / `get_edges` with
  a `limit` smaller than the graph (the defaults!) broke out of a live auto-locked
  graphstore iterator, permanently leaking a read hold on a dying request thread.
  One queued write later, every graph operation blocked forever while `/health`
  kept answering — the exact "healthy but hung" wedge seen in real sessions on
  macOS. The bug predates 1.0; query endpoints now iterate a `toArray()` snapshot,
  with a JUnit regression guard encoding the iterator contract.
- `gephi_focus_view` mode `edge` now finds directed edges (the lookup was missing
  the edge-type argument used at creation).

## [1.4.0]

### Added
- **One-click Claude Desktop install (`gephi-ai-<version>.mcpb`).** An MCP Bundle
  containing the server and every dependency — download from Releases, double-click,
  done. No terminal, no uv, no config file. Built reproducibly by
  `scripts/build-mcpb.sh` from the published PyPI artifact; runs on the system
  `python3` (3.10+). The uvx/JSON-config path remains for users who prefer it.
- **The viewer is now a two-way instrument.** Three interactive capabilities in the
  MCP App (all verified end to end against a scripted host):
  - **Click-driven exploration**: clicking a node offers "Highlight connections"
    (client-side ego highlight that dims the rest of the graph) and **"Ask Claude"**,
    which sends a question about that node into the conversation via the MCP Apps
    `ui/message` request — the visualization talks back.
  - **Refresh from Gephi**: a toolbar button re-fetches the graph through an
    app-initiated `tools/call` of `gephi_view_graph`, preserving caption settings —
    change the graph in Gephi or by asking Claude, then update the view in place.
  - **Cluster captions done properly**: `gephi_view_graph` gains `caption_column` and
    `caption_names`; the app computes size-weighted community centroids and floats
    toggleable map-style captions in an overlay — no blanked labels, no hub anchors
    (that remains `gephi_label_clusters` for PNG exports).
  - **Time slider for dynamic GEXF**: the parser now reads `start`/`end` attributes
    and `<spells>`; dynamic graphs get a scrubber that filters nodes and edges by
    spell containment. Numeric and date times supported.

## [1.3.6]

### Added
- **`gephi_visual_qa` detects over-spread layouts** — previously QA could pass a
  render whose nodes were specks in whitespace.
  When the largest node is under 1% of the layout extent's long side it now warns,
  with the fix spelled out (lower scalingRatio or raise sizes). The layout guide's
  symptom table gained the matching row, plus a composition tip (short final
  higher-gravity pass to round a straggly layout into the frame).

### Changed
- **Skill gotchas now cover the two label traps**: preview settings never affect
  Gephi's Overview canvas (the user's T toggle does), and label fonts render in
  graph-coordinate space with proportional-off clamping labels to node bounds.
- **Viewer module documents its GEXF spec coverage**, including what is consciously
  unsupported (per-edge type overrides, viz:shape, nested nodes, dynamic graphs).

## [1.3.5]

### Fixed
- **GEXF spec conformance in the parser** (checked against gephi/gexf). Attribute
  `<default>` values now apply to nodes lacking an explicit `attvalue` — previously
  such nodes were silently excluded from `gephi_visual_qa` partition math, which
  could skew or flip the grouping verdict on spec-compliant files. `viz:color`
  alpha is now preserved as `rgba()` instead of being dropped.

## [1.3.4]

### Fixed
- **Cluster captions render at true map-caption size.** Discovery from iterating on a
  live graph: with proportional label size OFF, Gephi clamps every label to its node's
  bounds, so caption fonts silently stopped growing. The recipe is the opposite of the
  intuitive one — proportional size ON, letting the hub's node size amplify the caption
  (with the pleasant cartographic side effect that bigger communities get bigger
  captions). `gephi_label_clusters` now uses that recipe with an extent-scaled base
  font.

## [1.3.3]

### Changed
- **`gephi_label_clusters` polish from design review.** New `caption_scale` parameter
  (multiplies the auto-computed caption size; 1.5-2 gives louder, map-style captions)
  and `prefer: "size"` to anchor captions on the visually largest node when degree
  and rendered size disagree. Repeat runs no longer overwrite `label_backup` with
  blanked labels, so restore always recovers the true originals, and hub captions
  resolve from the backup on re-runs.

## [1.3.2]

### Fixed
- **Cluster captions are now legibly sized on any graph.** Gephi renders preview label
  fonts in graph-coordinate space, so a fixed point size vanishes on large layouts (a
  36pt caption is ~4px on an 18,000-unit extent). `gephi_label_clusters` now computes
  the caption font from the layout extent (~extent/64, floor 14) with a matching
  outline, and reports the chosen size as `caption_font`.

## [1.3.1]

### Added
- **`gephi_label_clusters` (tool #79) — cluster captions the VNA way.** Gephi has no
  native cluster-label feature; the visual network analysis practice is to label only
  each region's most salient node. The tool blanks all labels, names each cluster's
  top-degree hub (hubs sit near their region's center of gravity, so captions land on
  the regions), and switches preview to outlined labels. Every original label is
  backed up to a `label_backup` attribute and `restore: true` reverses the whole
  operation.

## [1.3.0]

### Added
- **`gephi_visual_qa` (tool #78) — visual-design diagnostics.** One call returns node
  size range, distinct color count with near-white detection, layout extent with
  export dimensions matched to the graph's shape, and, given a partition column, the
  within-group edge share versus the random baseline with a strong/weak/none verdict.
  The "none" verdict catches decorative groupings whose edges are actually wired at
  random — coloring by those misleads, and testing showed exactly that
  failure. Warnings are actionable instructions, so any host (including skill-less
  ones like Claude Desktop and Cowork) can inspect and fix its own renders.
- **`/beautify` command** — runs the full inspect-and-adjust loop on the open graph:
  baseline QA, data-truth gate, validated styling, VNA layout, up to three diagnose
  and adjust rounds, and a shape-matched final export.

### Changed
- **Skill workflow gains a data-truth step**: verify claimed groupings against
  topology before coloring by them, and wire real structure (not decorative labels)
  when generating demo networks. Community-colored graphs now tint edges by source
  at 30-40 opacity; export canvases match the layout extent.
- **`gephi_size_by_ranking` defaults raised to min 10, max 60** (5 rendered as
  invisible specks), and **`gephi_set_preview_settings` now warns when some property
  names did not match** instead of silently reporting success.

## [1.2.4]

### Changed
- **Readable renders by default.** The pastel community palette failed a formal
  palette validation on every check (too light for white exports, three colors
  reading as gray, colorblind separation below floor, contrast 1.3-2:1) — real-world
  result: exports where no node was visible at all. Replaced in the skill with a
  validated 8-color palette (plus a dark-surface variant and an over-8-categories
  rule), and the essentials now travel in tool docstrings so skill-less hosts
  (Claude Desktop, Cowork) get them too: `gephi_color_by_partition` recommends the
  validated palette, `gephi_size_by_ranking` warns that unsized nodes render as
  invisible specks, and `gephi_export_png` carries the pre-export checklist
  (size, color, preview settings, then look at the result).

## [1.2.3]

### Changed
- **Layout guidance rebuilt on the visual network analysis literature** (prompted by
  Mathieu Jacomy's review noting too-strong gravity and suboptimal micro/macro
  balance). The layout guide, skill, and `gephi_run_layout` docstring now teach the
  VNA reference configuration for ForceAtlas 2 — LinLog mode on, **gravity 0** on
  connected graphs (gravity only exists to keep disconnected components in frame;
  excess packs the graph into a central blob) — plus an explicit inspect-and-adjust
  loop with a symptom table (blob, hairball, smeared clusters, unreadable cluster
  interiors) and micro/macro balancing via `scalingRatio`, grounded in Venturini,
  Jacomy, and Jensen (2021) and Noack's LinLog results. Previous guidance recommended
  gravity 1.0-2.0, which caused exactly the over-compacted layouts reviewers saw.
  Also corrects `barnesHutOptimize` to the real key `barnesHutOptimization` in the
  layout guide.

## [1.2.2]

### Changed
- **`gephi_view_graph` teaches its own fallback.** Not every chat surface renders MCP
  Apps (Claude Desktop chat does; Cowork, for example, does not). The tool's docstring
  and result summary now instruct the model directly: if no visual appeared, build an
  interactive visualization from the result's `structuredContent` using the host's
  native surface (widget, canvas, artifact) instead of falling back to a static PNG,
  which chat clients render small. Node positions, colors, and sizes are already in
  the payload, so the fallback needs no recomputation.

## [1.2.1]

### Fixed
- **`gephi_view_graph` now actually renders in Claude and Claude Desktop.** v1.2.0
  returned the viewer as an embedded HTML resource in the tool result, a pattern those
  hosts do not render (they fell back to text, and models reached for `gephi_export_png`
  instead). The viewer now implements the formal MCP Apps extension (spec 2026-01-26):
  the app page is a declared resource at `ui://gephi/graph-view` with mimeType
  `text/html;profile=mcp-app`, the tool advertises it via `_meta.ui.resourceUri`, and
  the page performs the `ui/initialize` handshake, receiving graph data through
  `ui/notifications/tool-result`. Data now travels in the result's `structuredContent`
  instead of a ~300KB HTML blob per call, which also keeps tool results small for
  non-app hosts (they get a one-line text summary; use `gephi_export_png` there).
  No new dependencies: the handshake is hand-rolled, sigma.js and graphology remain
  vendored, and the server side is plain FastMCP `meta`/resource declarations.

## [1.2.0]

### Added
- **`gephi_view_graph` MCP App viewer (tool #77).** Returns the current graph as a
  self-contained interactive sigma.js visualization in an embedded `ui://` HTML
  resource. MCP Apps hosts (claude.ai, Claude Desktop) render it inline in the
  conversation: pan/zoom, hover labels, click a node for its attributes. Graphs over
  `max_nodes` (default 1500) are trimmed to the highest-degree nodes, and the tool
  says so. sigma.js and graphology are vendored (MIT) so the view needs no network.
  GEXF parsing uses `defusedxml` (new dependency) rather than the XXE-prone stdlib
  parser.
- **Public beta status called out in the README.**

### Changed
- **The Claude Code plugin is now self-contained.** Its bundled MCP config launches the
  server with `uv run --directory ${CLAUDE_PLUGIN_ROOT}/../mcp-server gephi-mcp`, so
  installing the plugin is the whole setup — no separate `pip`/`pipx` step, and no
  dependence on a `gephi-mcp` command being on the global `PATH` (the failure behind #4).
  `uv` is the one prerequisite; `mcp-server/uv.lock` is committed so every install
  resolves identical dependency versions.
- **`gephi-mcp` is published to PyPI.** Non-plugin MCP clients (Claude Desktop, `claude
  mcp add`, anything stdio) now use `uvx gephi-mcp` — fetched and cached on first run —
  or `pipx install gephi-mcp`. The README install docs are rewritten around this and
  PyPI classifiers were added to the package metadata.

### Fixed
- **`pip install -e .` installs dependencies again** (#1, #3). The `dependencies` array in
  `mcp-server/pyproject.toml` sat below the `[project.urls]` table header, so TOML parsed it
  as `project.urls.dependencies` and the package declared no dependencies at all — installs
  either failed metadata validation or installed without `mcp`/`httpx`/`pydantic`. Moved it
  into the `[project]` table where it belongs.

### Changed
- **Install docs overhauled** (#4 and feedback from Mathieu Jacomy). The README now points
  users at the pre-built `.nbm` (Releases page / repo root) instead of requiring JDK + Maven
  to build the Gephi plugin from source (build-from-source is retained as a collapsible
  alternative, with the artifact path corrected to `gephi-mcp-plugin/target/`). The MCP
  server install now recommends `pipx` so the `gephi-mcp` command lands on the global `PATH`
  where MCP clients can find it, documents the venv-`PATH` pitfall, and verification now
  says to confirm the server is *connected* via `/mcp` rather than `which gephi-mcp`. The
  Claude Code plugin install command is corrected to
  `claude plugin install gephi-network-analysis@gephi-ai` (#2).

## [1.1.3]

A security, correctness, robustness, and test pass over the 1.0.0 baseline. Versions
1.1.1–1.1.2 were incremental build markers during the same effort (the `/health`
endpoint reports the version so you can confirm which jar Gephi loaded).

### Security
- **Removed wildcard CORS** (`Access-Control-Allow-Origin: *`) from the plugin's HTTP
  API. It served no purpose for the local (non-browser) MCP client and was pure
  cross-origin attack surface.
- **Added a `Host`-header guard** that rejects any non-loopback host — a defense against
  DNS-rebinding attacks from a malicious web page. Requests with no `Host` (raw local
  clients) are still allowed.

### Fixed
- **macOS render deadlock (mitigated).** External graph *writes* could deadlock Gephi's
  concurrent OpenGL VizEngine, which holds the graph read lock almost continuously while
  rendering. Writes now acquire the write lock with a non-deadlocking **timed `tryLock`
  poll** (reflected from Gephi's `GraphLockImpl.writeLock`) instead of the blocking
  `writeLock()`, and `resetFilters` wraps Gephi's internal `setVisibleView` in that lock
  so it re-enters rather than queuing. A single focused **build → analyze → style → layout
  → export** pass is now reliable with the live view open. The residual limit under
  sustained heavy rendering is Gephi-core (see the macOS note in the README and SKILL).
- **Batch tools drop nothing.** `gephi_add_nodes` / `gephi_add_edges` now apply per-item
  `attributes` (and edges honor `directed` + `label`), which were previously silently dropped.
- **Edge directedness.** Single `gephi_add_edge` now honors `directed` — undirected edges
  were always created directed.
- **`gephi_add_column` lock ordering.** It now takes the graph write lock, fixing a
  deadlock against the attribute-setters under concurrent requests.
- **Ranking with negative values.** `color_by_ranking` / `size_by_ranking` handle
  all-negative columns correctly (the min/max seed was `Double.MIN_VALUE`, the smallest
  *positive* double).
- **Layout name matching.** Names match case- and space-insensitively, so documented short
  names like `forceatlas2` resolve to `ForceAtlas 2`.
- **CSV export.** Fields are quoted per RFC 4180 (separators / quotes / newlines no longer
  corrupt columns) and written as UTF-8.
- **Health-check hook** now actually blocks the tool (exit 2) when Gephi is unreachable,
  instead of printing a message and proceeding.
- **MCP package installs again** — added `mcp-server/README.md` so `pip install` no longer
  fails metadata generation on a missing readme.

### Changed
- **Typed MCP tools.** All 76 tools expose typed, per-field parameters, so clients receive
  a precise JSON schema per tool instead of an opaque `params` object.
- **Lifecycle hardening.** Daemon HTTP listener thread + a watchdog on shutdown so the
  plugin can never block Gephi's quit.
- **Configurable.** `GEPHI_API_URL` and `GEPHI_REQUEST_TIMEOUT` are read from the environment.

### Added
- **51 automated tests** — 30 JUnit (Host-header guard, pure helpers, in-memory graph
  integration via a standalone `GraphModel`, and the write-lock reflection linchpin) +
  19 pytest (tool→HTTP mapping, sync-layout polling, all-76-registered regression guard) +
  2 hook tests.
- **CI** (`.github/workflows/ci.yml`) runs both suites + ruff on every push and PR.
- Complete docs: tool reference for all 76 tools, README security + macOS notes, SKILL
  working-envelope gotcha.

## [1.0.0]
- Initial release: Gephi plugin HTTP API, MCP server, and Claude Code plugin
  (commands, network-analyst agent, skill, health-check hook).
