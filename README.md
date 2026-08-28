# Gephi AI

AI-powered network analysis through [Gephi](https://gephi.org) and the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). Build, analyze, style, and export publication-ready network visualizations by talking to your AI assistant.

Built for researchers working across network science and AI.

> **Status: public beta.** APIs may change between minor versions.

## What you get

**Your AI assistant drives Gephi.** Say what you want in plain language and the assistant builds, analyzes, styles, and exports publication-ready network maps.

**It's a conversation, not a command line.** The assistant explains what it's doing, checks its own maps before showing them, and teaches you to read what you're seeing. You can point back: select nodes in the Gephi window and ask "what did I select?"

**Any data, any MCP client.** Network files import directly; spreadsheets and other data become networks conversationally. Works with Claude Code, Claude Desktop, or any MCP-compatible assistant.

<details>
<summary>Full feature list</summary>

- 109 tools covering the whole workflow: build, analyze, style, lay out, filter, and export
- One-level undo: destructive operations snapshot the workspace automatically, so `gephi_undo` brings the graph back
- Layout quality is measured, not eyeballed: the graph profile flags heavy-tailed weights and hub-and-spoke wiring before a layout runs, visual QA scores how well communities separated and frames exports around the main cloud (ignoring runaway outlier nodes), and numerically exploded layouts are caught automatically instead of exported
- Interactive network view inside the chat (pan, zoom, hover, click a node to ask about it)
- Slash commands for common jobs: `/analyze-network`, `/community-detection`, `/centrality`, `/visualize`, `/export-map`, `/import-and-explore`, `/explore`, `/verify-claim`, `/text-network`, `/teach`, `/counterfactual`
- Specialized agents that run multi-step work in their own context and hand back just the result: independent claim verification, layout iteration, structural analysis, and text-network construction
- Two extra layouts beyond Gephi's own: by role played in the network, and by community (best for reply and retweet networks)
- Reads your selection in the Gephi window, so "what did I select?" just works
- Drives any layout or metric plugin installed from the Gephi plugin portal
- Imports GEXF, GraphML, GML, CSV, DOT, and Pajek; turns spreadsheets and other files into networks conversationally

</details>

## Architecture

Three components connect your AI assistant to Gephi Desktop:

```
Claude / AI Assistant
        │
   MCP Protocol (stdio)
        │
   MCP Server (Python)          ← Translates MCP tool calls to HTTP
        │
   HTTP API (localhost:8080)
        │
   Gephi Plugin (Java)          ← Runs inside Gephi Desktop
        │
   Gephi Desktop                ← Must be running first
```

| Component | Directory | What it does |
|-----------|-----------|-------------|
| Gephi Plugin | `gephi-mcp-plugin/` | Java module that adds an HTTP API to Gephi Desktop |
| MCP Server | `mcp-server/` | Python server that exposes 109 Gephi tools via MCP |
| Claude Plugin | `claude-plugin/` | Skills, commands, agent, and hooks for Claude Code |

Install the Gephi plugin plus your AI client's connection — the Claude Code plugin bundles the MCP server, so most users install just two things. Gephi Desktop must be running before using any tools.

> **Security note:** the plugin's HTTP API binds to `127.0.0.1` only, validates the
> request `Host` header (DNS-rebinding defense), and sends no CORS headers — it is
> reachable only by local processes such as the MCP server, never by a web page.
> It is not authenticated, so do not expose port 8080 beyond localhost.

> **macOS note:** older plugin versions could wedge Gephi during sustained writes
> against a large rendered graph (calls hang; only `gephi_health_check` answers).
> Plugin 1.2.0 fixes the two causes on our side: writes now pause the renderer via
> Gephi's own viz-engine API, and a read-lock leak in the query endpoints (the main
> culprit) is closed. All lock waits are bounded, so a genuinely wedged Gephi returns
> an immediate "fully quit and reopen Gephi" error instead of hanging, and
> `gephi_health_check` exposes lock probes (`graph_lock`, `graph_lock_stats`) that
> detect the condition. If you ever see persistent "Graph is busy" errors, restart
> Gephi — and make sure you are on plugin 1.2.2 or newer.

## Setup

### Prerequisites

- [Gephi Desktop](https://gephi.org/users/download/) 0.11.1+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (runs the MCP server; one-line install, manages Python for you)
- [Claude Code](https://claude.ai/code) or [Claude Desktop](https://claude.ai/download) (for AI interaction)

### Step 1: Install the Gephi plugin

This adds the HTTP API server inside Gephi Desktop. No build tools needed — download the pre-built plugin:

1. Download `gephi-mcp-1.2.17.nbm` from the [Releases page](https://github.com/MattArtzAnthro/gephi-ai/releases) (also available at the root of this repository).
2. In Gephi: **Tools → Plugins → Downloaded → Add Plugins** — select the `.nbm` file, then click **Install**.
3. Restart Gephi. The plugin starts automatically and listens on `http://127.0.0.1:8080`.

**Verify:** Open a browser to `http://127.0.0.1:8080/health` — you should see `{"success": true}`.

### Step 2: Connect your AI assistant

#### Claude Desktop (fastest start)

Download `gephi-ai-<version>.mcpb` from the [Releases page](https://github.com/MattArtzAnthro/gephi-ai/releases) and double-click it — Claude Desktop installs the server with all dependencies bundled. No terminal, no config file. (Requires Python 3.10+ on your system, which modern macOS provides.)

> Use ONE connection method per app. If you previously added `gephi-mcp` to `claude_desktop_config.json` by hand, remove that entry before installing the bundle — otherwise Claude Desktop runs two copies of the server and every tool appears twice.

<details>
<summary>Alternative: Claude Desktop via config file</summary>

Add to your MCP configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "gephi-mcp": {
      "command": "uvx",
      "args": ["gephi-mcp"]
    }
  }
}
```

</details>

#### Claude Code (most capable)

```bash
claude plugin marketplace add MattArtzAnthro/gephi-ai
claude plugin install gephi-network-analysis@gephi-ai
```

(Or run the same two commands as `/plugin marketplace add …` and `/plugin install …` inside a Claude Code session.)

The plugin bundles and runs the MCP server itself (via uv), and adds the slash commands, the network analyst agent, and the skills that teach Claude network science best practices. If you use Claude Code, this is the recommended setup.

<details>
<summary>Claude Code with MCP tools only (no skills or commands)</summary>

```bash
claude mcp add gephi-mcp -- uvx gephi-mcp
```

</details>

#### OpenAI Codex CLI, Gemini CLI, and other MCP clients

The server is model-agnostic: a stdio MCP server with one launcher that works everywhere. Register it once:

```bash
codex mcp add gephi-mcp -- uvx gephi-mcp
gemini mcp add -s user gephi-mcp uvx gephi-mcp
```

(Claude Code without the plugin: `claude mcp add gephi-mcp -- uvx gephi-mcp`.)

These agents get all 109 tools. To give them the network-analysis guidance as well, copy the skill folder into your agent's skills directory:

```bash
git clone https://github.com/MattArtzAnthro/gephi-ai.git
cp -r gephi-ai/claude-plugin/skills/gephi ~/.codex/skills/
```

| Agent | Skills directory |
|:------|:-----------------|
| Claude Code | install the plugin (skill, commands, and agents together) |
| OpenAI Codex CLI | `~/.codex/skills/` |
| Cursor | `~/.cursor/skills/` |
| GitHub Copilot / VS Code | `~/.copilot/skills/` |
| Shared project-level | `.agents/skills/` in your repository |

The slash commands and subagents are Claude Code constructs; other agents get the skill and the tools. The repository also carries `AGENTS.md` and `GEMINI.md`, which those agents read on their own.

Any other MCP client: point it at `uvx gephi-mcp` using stdio transport. `uvx` fetches the
[`gephi-mcp` package from PyPI](https://pypi.org/project/gephi-mcp/) on first run and
caches it. For a persistent named command, `pipx install gephi-mcp` also works.

<details>
<summary>Troubleshooting: "Executable not found in $PATH"</summary>

Avoid installing with pip inside a project virtual environment. Inside an
activated `.venv` the `gephi-mcp` command only exists on that venv's `PATH`, and MCP
clients launch servers outside your shell — the server fails with "Executable not
found in $PATH" even though `which gephi-mcp` succeeds. Use `uvx`/`pipx`, or point
your MCP config at the venv executable's absolute path.

</details>

### Step 3: Verify

First confirm the MCP server actually connected. In Claude Code, run `/mcp` — `gephi-mcp` should be listed as **connected**. (In Claude Desktop, check that the tools appear in the tools menu.) If it shows a failure like "Executable not found in $PATH", the launcher (`uv`/`uvx` or `gephi-mcp`) isn't on the global `PATH` — see the notes in Step 2.

Then, with Gephi running, ask your assistant:

> "Check if Gephi is running"

It should call `gephi_health_check` and confirm the connection. In Claude Code, try:

```
/gephi-network-analysis:import-and-explore path/to/your/graph.gexf
```

## Updating

gephi-ai improves often, so keep it current. Most fixes and new tools arrive through
updates. The health check tells you once per session when your install is behind the
latest release and shows the matching update step, but that notice only appears on
recent versions, so if you installed a while ago (or an older command like `/teach`
is missing), run the update below once to catch up. Updating is safe to do anytime.

- **Claude Code:** `claude plugin update gephi-network-analysis@gephi-ai`, then start a new session.
- **If `/mcp` shows `Failed to reconnect to plugin:gephi-network-analysis:gephi-mcp: -32000`** on server 1.11.0 or older, that is the MCP SDK 2.0 break (issue #5); updating to 1.12.0 or newer is the fix, no pin needed.
- **Claude Desktop (one-click bundle):** download the newest `.mcpb` from Releases and double-click it again.
- **Claude Desktop (config file):** nothing to do — the `uvx` entry fetches the latest release each time you fully quit and reopen Claude Desktop.
- **Switching connection methods:** remove the old one first (bundle: uninstall in Settings > Extensions; config file: delete the `gephi-mcp` block). Two methods at once means two servers and duplicated tools.
- **Cowork:** Cowork keeps its own copy of plugins, separate from Claude Code — updating one does not update the other. If Cowork's commands look older than this README (for example, no `/teach`), ask Cowork itself to update the gephi-network-analysis plugin, then fully quit and reopen the app.
- **Gephi plugin:** install the newest `.nbm` from Releases via Tools > Plugins > Downloaded and restart Gephi.

`gephi_health_check` reports both the Gephi plugin version and the MCP server version, and says whether they are up to date, so you can see at a glance what you are running.

## What the Claude Code plugin adds

The plugin (`claude-plugin/`) goes beyond raw MCP tools:

| Component | What it does |
|-----------|-------------|
| **Slash commands** | `/analyze-network`, `/community-detection`, `/centrality`, `/visualize`, `/export-map`, `/import-and-explore`, `/explore`, `/verify-claim`, `/text-network`, `/teach`, `/counterfactual` |
| **Agents** | Subagents that run multi-step work in their own context and return just the result: `network-analyst` (structural interpretation), `claim-verifier` (independently checks one claim — confirmed / refuted / can't-tell, with the number), `layout-iterator` (runs the `/visualize` loop to a publication-ready map), `text-network-builder` (turns free text into a word co-occurrence network) |
| **Gephi skill** | Teaches Claude network science workflows, visualization best practices, and known Gephi gotchas |
| **Health-check hook** | Automatically verifies Gephi is running before graph-modifying operations |
| **Reference guides** | Tool reference, layout guide, and statistics interpretation guide |

## Tools (109)

| Category | Count | Examples |
|----------|-------|---------|
| Project & Workspace | 12 | `gephi_create_project`, `gephi_save_project`, `gephi_duplicate_workspace`, `gephi_snapshot`, `gephi_undo` |
| Graph Construction | 17 | `gephi_add_nodes`, `gephi_add_edges`, `gephi_query_nodes`, `gephi_get_node`, `gephi_text_to_network` |
| Statistics & Analysis | 15 | `gephi_compute_modularity`, `gephi_run_statistic` (any installed metric), `gephi_whatif` (counterfactual), `gephi_compare_nodes` |
| Layout | 8 | `gephi_run_layout`, `gephi_get_layout_properties`, `gephi_community_layout`, `gephi_similarity_layout` |
| Appearance | 11 | `gephi_color_by_partition`, `gephi_color_edges_by_partition`, `gephi_size_by_ranking`, `gephi_label_clusters` |
| Filtering | 10 | `gephi_filter_by_degree`, `gephi_extract_backbone`, `gephi_list_filters`, `gephi_apply_filter` (any filter, by name) |
| Attributes | 5 | `gephi_get_columns`, `gephi_set_node_attributes` |
| Preview & Export | 11 | `gephi_export_png`, `gephi_export_screenshot` (live selection-aware canvas capture), `gephi_export_gexf`, `gephi_export` (VNA/Pajek/DL/…), `gephi_view_graph` |
| Data Laboratory | 4 | `gephi_column_value_frequencies`, `gephi_detect_duplicates`, `gephi_merge_nodes`, `gephi_create_regex_column` |
| Timeline | 1 | `gephi_get_timeline` (dynamic-graph state, read-only) |
| Import | 4 | `gephi_import_file`, `gephi_import_gexf` |
| Health & Diagnostics | 3 | `gephi_health_check`, `gephi_visual_qa`, `gephi_profile_graph` |
| View / Camera / Perspective | 4 | `gephi_focus_view`, `gephi_set_selection_mode`, `gephi_get_perspective`, `gephi_switch_perspective` |

## Example workflows

### Community detection

```
1. gephi_create_project
2. gephi_import_file                  (your GEXF, GraphML, or CSV)
3. gephi_compute_degree
4. gephi_compute_modularity           (resolution: 1.0)
5. gephi_color_by_partition           (column: modularity_class)
6. gephi_size_by_ranking              (column: degree)
7. gephi_run_layout                   (ForceAtlas 2, 1000 iterations)
8. gephi_export_png                   (3840x2160 for publication)
```

### Centrality analysis

```
1. Import or build graph
2. gephi_compute_betweenness
3. gephi_compute_pagerank
4. gephi_run_layout                   (ForceAtlas 2)
5. gephi_color_by_ranking             (column: betweenesscentrality)
6. gephi_size_by_ranking              (column: pageranks)
7. gephi_query_nodes                  (find top-ranked nodes)
```

## Documentation

Reference guides are in `claude-plugin/skills/gephi/`:

- **SKILL.md** — Workflow patterns, best practices, and critical gotchas
- **references/tool-reference.md** — Complete API reference for all 109 tools
- **references/layout-guide.md** — Layout algorithm selection and parameter tuning
- **references/statistics-guide.md** — Statistics interpretation guide

## Tech stack

- **Gephi Plugin**: Java 11, NetBeans Platform, NanoHTTPD, Gson
- **MCP Server**: Python 3.10+, MCP Python SDK 2.x (`MCPServer`, 2026-07-28 protocol with the 2025-era handshake still served), httpx, Pydantic, defusedxml; vendored sigma.js + graphology for the in-chat viewer
- **Target**: Gephi 0.11.1, NetBeans RELEASE290

## Development

Building the Gephi plugin from source requires JDK 11+ and Maven:

```bash
cd gephi-mcp-plugin
mvn clean package    # output: target/gephi-mcp-<version>.nbm, auto-deployed to Gephi's modules dir
```

**Fully quit and reopen Gephi after every rebuild, even mid-session.** Gephi lazily
loads plugin classes on first use; overwriting the jar file on disk while Gephi is
still running an earlier build corrupts the classloader's view of any class not yet
loaded, and the resulting crash (a raw dropped connection, no error message) can be
hard to trace back to the real cause.

The MCP server is a standard Python package under `mcp-server/` (`pytest` for tests,
`ruff` for linting).

## Attribution

If you use or adapt this project in your work, please credit:

> Built with gephi-ai (Matt Artz, 2025–2026) — https://github.com/MattArtzAnthro/gephi-ai

## Citation

If you use this toolkit in your academic research, please cite:

> Artz, Matt. 2025. Gephi AI. Software. Zenodo. https://doi.org/10.5281/zenodo.18673386

## License

Apache License 2.0 — see [LICENSE](LICENSE).

## Author

**Matt Artz** — [mattartz.me](https://www.mattartz.me) | [ORCID](https://orcid.org/0000-0002-3822-1429)
