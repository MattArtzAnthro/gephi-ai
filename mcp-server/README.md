# gephi-mcp

MCP server that bridges any [Model Context Protocol](https://modelcontextprotocol.io) client
to a running [Gephi Desktop](https://gephi.org) instance, exposing **76 tools** for graph
construction, statistics, community detection, layout, styling, filtering, and
publication-ready export.

It translates MCP tool calls into HTTP requests against the Gephi MCP plugin's local API
(`http://127.0.0.1:8080`). Each tool has a typed signature, so clients receive a precise
per-field JSON schema rather than an opaque blob.

This is the **MCP server** component of [gephi-ai](https://github.com/MattArtzAnthro/gephi-ai);
see the top-level repository for the Gephi plugin, the Claude Code plugin, and full docs.

## Install

```bash
pip install -e .
```

Installs the `gephi-mcp` command (stdio transport).

## Use

The Gephi MCP plugin must be installed and Gephi Desktop running first. Then point any MCP
client at the `gephi-mcp` command, e.g. for Claude Desktop:

```json
{ "mcpServers": { "gephi-mcp": { "command": "gephi-mcp" } } }
```

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `GEPHI_API_URL` | `http://127.0.0.1:8080` | Gephi plugin HTTP API base URL |
| `GEPHI_REQUEST_TIMEOUT` | `60.0` | Per-request timeout (seconds) |

## Development

```bash
pip install -e . pytest pytest-asyncio ruff
ruff check .
pytest -q
```

## License

Apache-2.0 — see the [repository LICENSE](https://github.com/MattArtzAnthro/gephi-ai/blob/main/LICENSE).
