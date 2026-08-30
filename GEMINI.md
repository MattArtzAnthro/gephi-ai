# Gephi AI — Instructions for AI Coding Agents

This repository ships an MCP server (`gephi-ai` on PyPI) that controls a
running Gephi Desktop through a local HTTP API provided by the Gephi AI plugin
(`gephi-ai-<version>.nbm`), plus a portable skill that teaches network-analysis
practice. The server exposes 113 tools whose names start with `gephi_`
(Claude Code shows them as `mcp__gephi-mcp__gephi_*`).

When a user asks to build, analyze, lay out, style, or export a network, follow
this chain:

1. **MCP tools present** (tool names start with `gephi_`): use them. Call
   `gephi_health_check` first. It confirms that Gephi Desktop is running with
   the plugin installed, reports the plugin and server versions, and says
   whether an update is available. If it fails, tell the user to start Gephi
   (with the plugin installed from the Releases page) and stop; nothing else
   works without it.

2. **Your agent supports MCP but the server is not registered**: the user can
   add it with one command. The launcher is the same everywhere; only the
   registration syntax differs.

   ```bash
   claude mcp add gephi-mcp -- uvx gephi-ai
   codex mcp add gephi-mcp -- uvx gephi-ai
   gemini mcp add -s user gephi-mcp uvx gephi-ai
   ```

   `uvx` fetches the current `gephi-ai` release from PyPI on first run and
   caches it. Any other MCP client: point it at `uvx gephi-ai` over stdio.

3. **No MCP at all**: there is no fallback. The server talks to Gephi Desktop
   on `127.0.0.1:8080`, so it has to run on the machine where Gephi runs.
   Say so, and point the user at the README's Install section.

## The skill

`plugins/claude-code/skills/gephi/` is a self-contained skill folder (`SKILL.md` plus
`references/`): tool reference, layout guide, statistics guide, filtering,
claim verification, text networks, and how to read a network map. It is
written for any agent that reads the portable skill format. Install it by
copying the folder into your agent's skills directory (`~/.codex/skills/`,
`~/.cursor/skills/`, `~/.copilot/skills/`, or `.agents/skills/` in a project);
Claude Code users get it through the plugin, together with slash commands and
subagents that only Claude Code can run.

## Working principles, in brief

- Read before you restyle. Profile the graph (`gephi_profile_graph`) and ask
  what the nodes and ties are before choosing metrics or a layout.
- Compute before you claim. `modularity_class`, `Degree`, and centrality
  columns do not exist until their statistic has run.
- Never describe a heavy-tailed degree distribution as "scale-free" or a
  "power law"; describe hub dominance as a property of this network.
- A verified claim comes with receipts: `gephi_claim_record` re-reads the cited
  nodes and values from the live graph and returns the record.
- Every final export ships with its caption: data, layout and key settings,
  what size and color encode, and what the map does and does not license.
- Destructive tools (clear, remove, merge, filter, extract) take an undo
  snapshot; `gephi_undo` restores it. Say what a filter will remove before
  running it.

Full guidance lives in `SKILL.md` and its references; prefer them over
improvising.
