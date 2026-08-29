# Gephi Network Analysis for Codex

This package is the Codex/OpenAI counterpart to `claude-plugin/`. It keeps the
same Gephi MCP server and network-analysis guidance while translating
Claude-only commands, custom agents, and hooks into Codex-native plugin pieces.

## What is included

- `.codex-plugin/plugin.json` — Codex plugin manifest
- `.mcp.json` — local `uvx gephi-mcp` server registration, pinned to the same
  release used by the Claude plugin
- `skills/gephi/` — the complete network-analysis skill and reference library
- focused workflow skills replacing every Claude slash command
- strengthened workflow skills replacing the four Claude custom agents

## Local architecture

Gephi AI cannot be a conventional hosted ChatGPT connector: its MCP server must
run on the same computer as Gephi Desktop so it can reach the loopback-only Gephi
API at `127.0.0.1:8080`. This package is therefore intended for Codex/local plugin
use. A public ChatGPT directory submission would require a different architecture
that does not expose or proxy the unauthenticated local Gephi API.

## Runtime prerequisites

1. Gephi Desktop 0.11.1 or newer.
2. The Gephi AI Desktop plugin 1.3.0 or newer installed and running.
3. `uv`/`uvx` available on the system path.

The plugin launches `gephi-mcp==1.17.0`. Every operational skill calls
`gephi_health_check` first and stops cleanly when Gephi is unavailable. This
replaces the Claude `PreToolUse` hook without depending on an unsupported host
lifecycle callback.

## Claude-to-Codex mapping

| Claude component | Codex equivalent |
|---|---|
| `skills/gephi` | `skills/gephi` |
| slash commands | focused workflow skills |
| `network-analyst` agent | `analyze-network` skill |
| `claim-verifier` agent | `verify-claim` skill |
| `layout-iterator` agent | `visualize-network` skill |
| `text-network-builder` agent | `build-text-network` skill |
| `PreToolUse` health hook | mandatory first step in every operational skill |

## Versioning

The Codex plugin version tracks the Claude plugin version (`1.14.0`). The MCP
server version is independently pinned at `1.17.0`, matching the source package.
