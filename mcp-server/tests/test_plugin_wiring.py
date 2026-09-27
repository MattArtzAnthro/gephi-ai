"""
The Claude Code plugin names its own tools in three places: the PreToolUse hook matcher, the
agents' tool lists, and the commands' allowed-tools. Installed as a plugin, the tools are named
mcp__plugin_gephi-network-analysis_gephi-mcp__gephi_*, not mcp__gephi-mcp__gephi_* as they are
for a server registered by hand. With the hand-registered names the hook never fired and the
agents' read-only lists restricted nothing.
"""
import json
import re
from pathlib import Path

import gephi_mcp

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "claude-code"
PLUGIN_PREFIX = "mcp__plugin_gephi-network-analysis_gephi-mcp__"
BARE_PREFIX = "mcp__gephi-mcp__"


def _frontmatter(path):
    return path.read_text(encoding="utf-8").split("---", 2)[1]


def _field(path, key):
    for line in _frontmatter(path).splitlines():
        if line.startswith(f"{key}:"):
            return [t.strip() for t in line.split(":", 1)[1].split(",") if t.strip()]
    return None


def _registered():
    return {t.name for t in gephi_mcp.mcp._tool_manager.list_tools()}


def test_the_health_check_hook_matches_the_plugins_tool_names():
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    matcher = hooks["hooks"]["PreToolUse"][0]["matcher"]
    guarded = ["gephi_add_node", "gephi_add_edges", "gephi_import_file", "gephi_clear_graph",
               "gephi_run_layout"]
    for tool in guarded:
        assert re.search(matcher, PLUGIN_PREFIX + tool), f"hook misses the plugin's {tool}"
        assert re.search(matcher, BARE_PREFIX + tool), f"hook misses the hand-registered {tool}"
    for tool in ("gephi_add_node_attribute_that_does_not_exist", "gephi_health_check"):
        assert not re.search(matcher, PLUGIN_PREFIX + tool), f"hook also guards {tool}"


def test_agents_restrict_tools_with_the_key_claude_code_reads():
    for agent in sorted((PLUGIN / "agents").glob("*.md")):
        assert _field(agent, "allowed-tools") is None, f"{agent.name}: agents read tools:, not allowed-tools:"
        assert _field(agent, "tools"), f"{agent.name} declares no tools"


def test_agent_and_command_tool_lists_name_the_plugins_tools():
    registered = _registered()
    files = [(p, "tools") for p in (PLUGIN / "agents").glob("*.md")]
    files += [(p, "allowed-tools") for p in (PLUGIN / "commands").glob("*.md")]
    for path, key in files:
        for entry in _field(path, key) or []:
            if not entry.startswith("mcp__"):
                continue
            assert entry.startswith(PLUGIN_PREFIX), f"{path.name}: {entry} is not the plugin's name"
            name = entry[len(PLUGIN_PREFIX):]
            assert name == "*" or name in registered, f"{path.name}: {entry} is not a tool"
