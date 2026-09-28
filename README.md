# Gephi AI

Control [Gephi](https://gephi.org) by talking to your AI assistant. Build, analyze, style, and export publication-ready network maps through the [Model Context Protocol (MCP)](https://modelcontextprotocol.io).

Built for researchers working across network science and AI.

> **Status: public beta.** APIs may change between minor versions.

## What you get

**Your AI assistant drives Gephi.** Say what you want in plain language and the assistant builds, analyzes, styles, and exports the map.

**It is a conversation, not a command line.** The assistant explains what it is doing, checks its own maps before showing them, and teaches you to read what you see. You can point back: select nodes in Gephi and ask "what did I select?"

**Any data, any MCP client.** Network files import directly, and spreadsheets and other data become networks conversationally. Works with Claude Code, Claude Desktop, OpenAI Codex, Gemini CLI, or any MCP client.

<details>
<summary>Full feature list</summary>

- 120 tools covering the whole workflow: build, analyze, style, lay out, filter, and export
- One-level undo: destructive operations snapshot the workspace first, so `gephi_undo` brings the graph back
- Measured layout quality: the graph profile flags heavy-tailed weights and hub-and-spoke wiring before a layout runs, visual QA scores how well communities separate, and numerically exploded layouts are caught instead of exported
- Interactive network view inside the chat (pan, zoom, hover, and click a node to ask about it)
- Slash commands for common jobs: `/analyze-network`, `/community-detection`, `/centrality`, `/visualize`, `/export-map`, `/import-and-explore`, `/explore`, `/verify-claim`, `/text-network`, `/teach`, and `/counterfactual`
- Specialized agents for claim verification, layout iteration, structural analysis, and text networks
- Two extra layouts beyond Gephi's own: by role in the network, and by community
- Reads your selection in the Gephi window
- Drives any layout or metric plugin installed from the Gephi plugin portal
- Imports GEXF, GraphML, GML, CSV, DOT, and Pajek

</details>

## Install

You need [Gephi Desktop](https://gephi.org) 0.11.3 or newer and an AI assistant. Most clients also need [uv](https://docs.astral.sh/uv/getting-started/installation/), which runs the server and manages Python for you; Claude Desktop brings its own.

### 1. Add the plugin to Gephi

1. Download `gephi-ai-1.5.1.nbm` from the [Releases page](https://github.com/MattArtzAnthro/gephi-ai/releases).
2. In Gephi, open **Tools > Plugins > Downloaded > Add Plugins**, select the file, and click **Install**.
3. Restart Gephi. **Tools > Gephi AI Server** shows that the plugin is running.

### 2. Connect your assistant

Use one connection method per app. Two at once means two servers and every tool listed twice.

**Claude Code** (recommended: adds the slash commands, agents, and skills):

```bash
claude plugin marketplace add MattArtzAnthro/gephi-ai
claude plugin install gephi-network-analysis@gephi-ai
```

**Claude Desktop:** download `gephi-ai-<version>.mcpb` from the [Releases page](https://github.com/MattArtzAnthro/gephi-ai/releases) and double-click it. Claude Desktop installs Python, the server, and its dependencies itself. The first launch needs an internet connection and can take a minute. Tested with Claude Desktop 1.40609.0.

**OpenAI Codex** (adds the same workflows as skills):

```bash
codex plugin marketplace add MattArtzAnthro/gephi-ai --ref main
codex plugin add gephi-network-analysis@gephi-ai
```

Start a new Codex task after installing.

**Gemini CLI:**

```bash
gemini mcp add -s user gephi-ai uvx gephi-ai
```

**Any other MCP client:** run `uvx gephi-ai` over stdio.

<details>
<summary>Tools only, without the skills and commands</summary>

```bash
claude mcp add gephi-ai -- uvx gephi-ai
codex mcp add gephi-ai -- uvx gephi-ai
```

Claude Desktop through its config file (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "gephi-ai": {
      "command": "uvx",
      "args": ["gephi-ai"]
    }
  }
}
```

</details>

<details>
<summary>Network-analysis guidance for other agents</summary>

Copy the skill folder into your agent's skills directory:

```bash
git clone https://github.com/MattArtzAnthro/gephi-ai.git
cp -r gephi-ai/plugins/claude-code/skills/gephi ~/.codex/skills/
```

| Agent | Skills directory |
|:------|:-----------------|
| OpenAI Codex | `~/.codex/skills/` (or install the Codex plugin above) |
| Cursor | `~/.cursor/skills/` |
| GitHub Copilot / VS Code | `~/.copilot/skills/` |
| Any agent, per project | `.agents/skills/` in your repository |

The repository also carries `AGENTS.md` and `GEMINI.md`, which those agents read on their own.

</details>

### 3. Check that it works

With Gephi open, ask your assistant: **"Check if Gephi is running."** It should call `gephi_health_check` and confirm the connection, including whether your plugin and server are up to date.

## Updating

The health check tells you once per session when something is out of date.

- **Claude Code:** `claude plugin update gephi-network-analysis@gephi-ai`, then start a new session.
- **Claude Desktop bundle:** download the newest `.mcpb` from Releases and double-click it.
- **Config file or `uvx` setups:** nothing to do; `uvx` fetches the latest release when the app restarts.
- **Gephi plugin:** install the newest `.nbm` through **Tools > Plugins > Downloaded** and restart Gephi.

<details>
<summary>Upgrade notes</summary>

- **From plugin 1.2.x (one time):** the plugin was renamed to Gephi AI, so the new version installs alongside the old one and both try to use port 8080. In **Tools > Plugins > Installed**, uninstall **Gephi AI (MCP)**, restart Gephi, then install the new `.nbm`.
- **From the `gephi-mcp` package:** the server is now published as `gephi-ai`. If your config says `uvx gephi-mcp`, change it to `uvx gephi-ai` to keep getting updates.
- **From the `gephi-mcp` server name:** the setup commands and the Claude plugin now name the server `gephi-ai`, so its tools show as `mcp__gephi-ai__gephi_*` (`mcp__plugin_gephi-network-analysis_gephi-ai__gephi_*` from the plugin). A server you registered by hand as `gephi-mcp` keeps working under that name; re-register it as `gephi-ai` to match, and re-approve the tools once.
- **Cowork** keeps its own copy of plugins. Ask Cowork to update gephi-network-analysis, then fully quit and reopen the app.

</details>

## Troubleshooting

- **"Executable not found in $PATH":** the app cannot find `uvx` or `gephi-ai`. Install with `uvx` or `pipx` rather than inside a project virtual environment, or point your config at the executable's full path.
- **Every tool appears twice:** two connection methods are active. Remove one (bundle: **Settings > Extensions**; config file: delete the `gephi-ai` block, or `gephi-mcp` in an older setup).
- **"Graph is busy" keeps appearing:** fully quit and reopen Gephi.
- **Opening `http://127.0.0.1:8080` in a browser returns `403`:** this is intended. The API refuses browsers so that a web page cannot drive Gephi. `curl http://127.0.0.1:8080/health` shows whether the plugin is running.

## Security

The plugin's API listens on `127.0.0.1` only and refuses requests from browsers and from non-local host names. It has no authentication, so any program running under your account can use it. Do not expose port 8080.

## Tools (120)

| Category | Count | Examples |
|----------|-------|---------|
| Project & Workspace | 12 | `gephi_create_project`, `gephi_save_project`, `gephi_duplicate_workspace`, `gephi_snapshot`, `gephi_undo` |
| Graph Construction | 18 | `gephi_add_nodes`, `gephi_add_edges`, `gephi_query_nodes`, `gephi_get_node`, `gephi_text_to_network`, `gephi_bipartite_projection` (two-mode to one-mode) |
| Statistics & Analysis | 21 | `gephi_compute_modularity`, `gephi_run_statistic` (any installed metric), `gephi_compare_partitions` (detected groups against known ones), `gephi_find_shortest_path`, `gephi_whatif` (counterfactual), `gephi_compare_nodes`, `gephi_community_stability` (are the communities real?), `gephi_compare_workspaces` (what changed between two versions) |
| Layout | 9 | `gephi_run_layout`, `gephi_get_layout_properties`, `gephi_community_layout`, `gephi_similarity_layout`, `gephi_bipartite_layout` |
| Appearance | 11 | `gephi_color_by_partition`, `gephi_color_edges_by_partition`, `gephi_size_by_ranking`, `gephi_label_clusters` |
| Filtering | 11 | `gephi_filter_by_degree`, `gephi_extract_backbone`, `gephi_list_filters`, `gephi_apply_filter` (any filter, by name), `gephi_apply_filters` (several combined) |
| Attributes | 5 | `gephi_get_columns`, `gephi_set_node_attributes` |
| Preview & Export | 14 | `gephi_export_png`, `gephi_export_screenshot` (live canvas capture), `gephi_export_gexf`, `gephi_export` (VNA, Pajek, DL, and more), `gephi_view_graph`, `gephi_export_legend`, `gephi_export_figure` (map and key as one PDF), `gephi_session_receipt` (how the figure was made) |
| Data Laboratory | 5 | `gephi_column_value_frequencies`, `gephi_detect_duplicates`, `gephi_merge_nodes`, `gephi_create_regex_column`, `gephi_edit_column` |
| Timeline | 3 | `gephi_get_timeline`, `gephi_set_time_from_columns` (time from start and end columns), `gephi_time_slice` (one period in its own workspace) |
| Import | 4 | `gephi_import_file`, `gephi_import_gexf` |
| Health & Diagnostics | 3 | `gephi_health_check`, `gephi_visual_qa`, `gephi_profile_graph` |
| View / Camera / Perspective | 4 | `gephi_focus_view`, `gephi_set_selection_mode`, `gephi_get_perspective`, `gephi_switch_perspective` |

The full reference, layout guide, and statistics guide live in [`plugins/claude-code/skills/gephi/`](plugins/claude-code/skills/gephi/).

## How it works

```
AI assistant  →  MCP server (Python)  →  HTTP on 127.0.0.1:8080  →  Gephi plugin (Java)  →  Gephi Desktop
```

| Component | Directory |
|-----------|-----------|
| Gephi plugin | `gephi-ai-plugin/` |
| MCP server | `mcp-server/` |
| Claude Code plugin | `plugins/claude-code/` |
| Codex plugin | `plugins/gephi-network-analysis/` |
| Claude Desktop bundle | `mcpb/` |

## Development

The Gephi plugin needs JDK 17 or newer (Gephi 0.11.3's libraries are Java 17) and Maven:

```bash
cd gephi-ai-plugin
mvn clean package    # builds target/gephi-ai-<version>.nbm and copies its jar into Gephi's modules folder
```

Fully quit and reopen Gephi after every rebuild. Replacing the plugin while Gephi runs can crash it without a clear error. The build copies only the module jar; when the bundled libraries change, install the whole `.nbm` (RELEASING.md, step 3).

Every build checks the plugin before it compiles and tests it:

- **Checkstyle** runs with Gephi core's own configuration (`gephi-ai-plugin/checkstyle.xml`), and any violation fails the build.
- **`SourceRulesTest`** holds the rules that keep the plugin from freezing Gephi: graph locks released in `finally`, no loops over live graph iterators, no project changes or graph reads on the interface thread, named daemon threads, and the licence header on every file.

The MCP server is a standard Python package in `mcp-server/`, tested with `pytest`, linted with `ruff`, and type-checked with `mypy`. The release scripts are checked with `shellcheck`, and the CI workflow with `actionlint`. On a pull request, CI also runs `scripts/check-fix-tests.sh`, which warns about a `fix` commit that changes no test. The live smoke test (`mcp-server/tests/live_smoke_test.py`) drives every tool against a running Gephi; its docstring gives the command for a separate test Gephi. Release steps are in [RELEASING.md](RELEASING.md).

## Citation

> Artz, Matt. 2025. Gephi AI. Software. Zenodo. https://doi.org/10.5281/zenodo.18673386

If you adapt this project, please credit "gephi-ai (Matt Artz, 2025–2026), https://github.com/MattArtzAnthro/gephi-ai".

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Author

**Matt Artz**, [mattartz.me](https://www.mattartz.me) | [ORCID](https://orcid.org/0000-0002-3822-1429)
