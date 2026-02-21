# gephi-ai

AI-powered network analysis through [Gephi](https://gephi.org) and the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). Build, analyze, style, and export publication-ready network visualizations by talking to your AI assistant.

Built for researchers working across network science and AI.

## What You Get

**73 MCP tools** for controlling Gephi Desktop -- graph construction, community detection, centrality analysis, layout algorithms, filtering, styling, and publication-ready export.

**Claude Code plugin** with slash commands (`/analyze-network`, `/community-detection`, `/centrality`, `/visualize`, `/import-and-explore`), a specialized network analyst agent, and workflow skills that teach Claude network science best practices.

**Works with any MCP client** -- Claude Code, Claude Desktop, or any MCP-compatible assistant.

## Quickstart (Claude Code)

### Prerequisites

- [Gephi Desktop](https://gephi.org/users/download/) 0.10.1+
- Python 3.10+
- [Claude Code](https://code.claude.com)

### 1. Install the Gephi Plugin

Build the `.nbm` module and install it through Gephi's plugin manager:

```bash
cd gephi-mcp-plugin
mvn clean package
```

Then in Gephi: **Tools > Plugins > Downloaded > Add Plugins** -- select `target/gephi-mcp-1.0.0.nbm`.

Restart Gephi. The plugin starts automatically and listens on `http://127.0.0.1:8080`.

### 2. Install the MCP Server

```bash
cd mcp-server
pip install -e .
```

This installs the `gephi-mcp` command on your PATH.

### 3. Install the Claude Code Plugin

Inside Claude Code, run:

```
/plugin marketplace add MattArtzAnthro/gephi-ai
/plugin install gephi-network-analysis@gephi-ai
```

This adds the MCP server, slash commands, network analyst agent, skills, and a health-check hook.

### 4. Verify

Open Gephi, then ask Claude:

> "Check if Gephi is running"

It should call `gephi_health_check` and confirm the connection. Try a slash command:

```
/gephi-network-analysis:analyze-network
```

## Other MCP Clients

The MCP server works with any MCP-compatible client, not just Claude Code.

**Claude Desktop** -- Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gephi-mcp": {
      "command": "gephi-mcp"
    }
  }
}
```

**Claude Code (MCP only, without plugin)** -- If you just want the 73 tools without the plugin's skills and commands:

```bash
claude mcp add gephi-mcp -- gephi-mcp
```

**Other clients** -- Point your MCP client at the `gephi-mcp` command using stdio transport.

## What the Plugin Adds

The Claude Code plugin (`claude-plugin/`) goes beyond raw MCP tools:

| Component | What it does |
|-----------|-------------|
| **Slash commands** | `/analyze-network`, `/community-detection`, `/centrality`, `/visualize`, `/import-and-explore` |
| **Network analyst agent** | Specialized subagent for deep structural analysis, metric comparison, and network classification |
| **Gephi skill** | Teaches Claude network science workflows, visualization best practices, and known Gephi gotchas |
| **Health-check hook** | Automatically verifies Gephi is running before graph-modifying operations |
| **Reference guides** | Tool reference, layout guide, and statistics guide for detailed parameter help |

## Tool Categories (73 tools)

| Category | Tools | Examples |
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

## Example Workflows

### Community Detection

```
1. gephi_create_project
2. gephi_add_nodes / gephi_add_edges  (or gephi_import_file)
3. gephi_compute_modularity           (resolution: 1.0)
4. gephi_run_layout                   (ForceAtlas 2, 1000 iterations)
5. gephi_color_by_partition           (column: modularity_class)
6. gephi_size_by_ranking              (column: degree)
7. gephi_export_png                   (3840x2160 for publication)
```

### Centrality Analysis

```
1. Import or build graph
2. gephi_compute_betweenness
3. gephi_compute_pagerank
4. gephi_run_layout                   (ForceAtlas 2)
5. gephi_color_by_ranking             (column: betweenesscentrality)
6. gephi_size_by_ranking              (column: pageranks)
7. gephi_query_nodes                  (find top-ranked nodes)
```

## Architecture

```
Claude / AI Assistant
        |
   MCP Protocol (stdio)
        |
   MCP Server (Python)
        |
   HTTP API (localhost:8080)
        |
   Gephi Plugin (Java)
        |
   Gephi Desktop
```

| Component | Path | Description |
|-----------|------|-------------|
| Gephi Plugin | `gephi-mcp-plugin/` | Java NetBeans module with HTTP API server |
| MCP Server | `mcp-server/` | Python MCP server (73 tools) |
| Claude Plugin | `claude-plugin/` | Claude Code plugin (skills, commands, agent, hooks) |
| Skills | `.claude/skills/` | Standalone skill + reference guides |

## Documentation

Detailed reference guides are in `.claude/skills/gephi/`:

- **SKILL.md** -- Main skill definition with workflow patterns and best practices
- **references/tool-reference.md** -- Complete API reference for all 73 tools
- **references/layout-guide.md** -- Layout algorithm selection and parameter tuning
- **references/statistics-guide.md** -- Statistics interpretation and visualization guide

## Tech Stack

- **Gephi Plugin**: Java 11, NetBeans Platform, NanoHTTPD, Gson
- **MCP Server**: Python 3.10+, MCP SDK (FastMCP), httpx, Pydantic
- **Target**: Gephi 0.10.1, NetBeans RELEASE126

## Citation

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18673386.svg)](https://doi.org/10.5281/zenodo.18673386)

If you use this software in your academic research, please cite:

> Artz, Matt. 2025. gephi-ai. Software. Zenodo. https://doi.org/10.5281/zenodo.18673386

## Attribution

If you use or adapt this project in your work, please credit:

> Built with gephi-ai (Matt Artz, 2025) -- https://github.com/MattArtzAnthro/gephi-ai

## License

Apache License 2.0 -- see [LICENSE](LICENSE).

## Author

**Matt Artz** -- [mattartz.me](https://www.mattartz.me) | [ORCID](https://orcid.org/0000-0002-3822-1429)
