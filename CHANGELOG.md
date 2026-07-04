# Changelog

Notable changes to **gephi-ai**. Versions apply together to the Gephi plugin
(`gephi-mcp-plugin/`), the MCP server (`mcp-server/`), and the Claude Code plugin
(`claude-plugin/`). Format follows [Keep a Changelog](https://keepachangelog.com).

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
