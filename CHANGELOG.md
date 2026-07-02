# Changelog

Notable changes to **gephi-ai**. Versions apply together to the Gephi plugin
(`gephi-mcp-plugin/`), the MCP server (`mcp-server/`), and the Claude Code plugin
(`claude-plugin/`). Format follows [Keep a Changelog](https://keepachangelog.com).

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
