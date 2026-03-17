# gephi-ai

AI-powered network analysis through [Gephi](https://gephi.org) and the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). Build, analyze, style, and export publication-ready network visualizations by talking to your AI assistant.

Built for researchers working across network science and AI.

## What you get

**73 MCP tools** for controlling Gephi Desktop — graph construction, community detection, centrality analysis, layout algorithms, filtering, styling, and publication-ready export.

**Claude Code plugin** with slash commands (`/analyze-network`, `/community-detection`, `/centrality`, `/visualize`, `/import-and-explore`), a specialized network analyst agent, and workflow skills that teach Claude network science best practices.

**Works with any MCP client** — Claude Code, Claude Desktop, or any MCP-compatible assistant.

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
| MCP Server | `mcp-server/` | Python server that exposes 73 Gephi tools via MCP |
| Claude Plugin | `claude-plugin/` | Skills, commands, agent, and hooks for Claude Code |

All three must be installed. Gephi Desktop must be running before using any tools.

## Setup

### Prerequisites

- [Gephi Desktop](https://gephi.org/users/download/) 0.10.1+
- [Java JDK 11+](https://adoptium.net/) and [Maven](https://maven.apache.org/) (to build the Gephi plugin)
- [Python 3.10+](https://www.python.org/) (for the MCP server)
- [Claude Code](https://claude.ai/code) or [Claude Desktop](https://claude.ai/download) (for AI interaction)

### Step 1: Install the Gephi plugin

This adds the HTTP API server inside Gephi Desktop.

```bash
cd gephi-mcp-plugin
mvn clean package
```

Then in Gephi: **Tools → Plugins → Downloaded → Add Plugins** — select `target/nbm/gephi-mcp-1.0.0.nbm`.

Restart Gephi. The plugin starts automatically and listens on `http://127.0.0.1:8080`.

**Verify:** Open a browser to `http://127.0.0.1:8080/health` — you should see `{"success": true}`.

### Step 2: Install the MCP server

This bridges MCP clients to the Gephi HTTP API.

```bash
cd mcp-server
pip install -e .
```

This installs the `gephi-mcp` command on your PATH.

**Verify:** Run `gephi-mcp --help` to confirm it installed.

### Step 3: Connect your AI assistant

#### Claude Code (full plugin — recommended)

```bash
claude plugin install gephi-ai/gephi-network-analysis
```

This adds the MCP server, slash commands, network analyst agent, skills, and a health-check hook.

#### Claude Code (MCP tools only)

If you just want the 73 tools without skills and commands:

```bash
claude mcp add gephi-mcp -- gephi-mcp
```

#### Claude Desktop

Add to your MCP configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "gephi-mcp": {
      "command": "gephi-mcp"
    }
  }
}
```

#### Other MCP clients

Point your client at the `gephi-mcp` command using stdio transport.

### Step 4: Verify

With Gephi running, ask your assistant:

> "Check if Gephi is running"

It should call `gephi_health_check` and confirm the connection. In Claude Code, try:

```
/gephi-network-analysis:import-and-explore path/to/your/graph.gexf
```

## What the Claude Code plugin adds

The plugin (`claude-plugin/`) goes beyond raw MCP tools:

| Component | What it does |
|-----------|-------------|
| **Slash commands** | `/analyze-network`, `/community-detection`, `/centrality`, `/visualize`, `/import-and-explore` |
| **Network analyst agent** | Specialized subagent for deep structural analysis, metric comparison, and network classification |
| **Gephi skill** | Teaches Claude network science workflows, visualization best practices, and known Gephi gotchas |
| **Health-check hook** | Automatically verifies Gephi is running before graph-modifying operations |
| **Reference guides** | Tool reference, layout guide, and statistics interpretation guide |

## Tools (73)

| Category | Count | Examples |
|----------|-------|---------|
| Project & Workspace | 8 | `gephi_create_project`, `gephi_save_project` |
| Graph Construction | 17 | `gephi_add_nodes`, `gephi_add_edges`, `gephi_query_nodes` |
| Statistics | 9 | `gephi_compute_modularity`, `gephi_compute_pagerank` |
| Layout | 6 | `gephi_run_layout`, `gephi_get_layout_properties` |
| Appearance | 9 | `gephi_color_by_partition`, `gephi_size_by_ranking` |
| Filtering | 6 | `gephi_filter_by_degree`, `gephi_extract_giant_component` |
| Attributes | 5 | `gephi_get_columns`, `gephi_set_node_attributes` |
| Preview & Export | 8 | `gephi_export_png`, `gephi_export_pdf`, `gephi_export_gexf` |
| Import | 4 | `gephi_import_file`, `gephi_import_gexf` |
| Health | 1 | `gephi_health_check` |

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
- **references/tool-reference.md** — Complete API reference for all 73 tools
- **references/layout-guide.md** — Layout algorithm selection and parameter tuning
- **references/statistics-guide.md** — Statistics interpretation guide

## Tech stack

- **Gephi Plugin**: Java 11, NetBeans Platform, NanoHTTPD, Gson
- **MCP Server**: Python 3.10+, MCP SDK (FastMCP), httpx, Pydantic
- **Target**: Gephi 0.10.1, NetBeans RELEASE126

## Attribution

If you use or adapt this project in your work, please credit:

> Built with gephi-ai (Matt Artz, 2025–2026) — https://github.com/MattArtzAnthro/gephi-ai

## License

Apache License 2.0 — see [LICENSE](LICENSE).

## Author

**Matt Artz** — [mattartz.me](https://www.mattartz.me) | [ORCID](https://orcid.org/0000-0002-3822-1429)
