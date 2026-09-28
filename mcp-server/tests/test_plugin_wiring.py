"""
The Claude Code plugin names its own tools in three places: the PreToolUse hook matcher, the
agents' tool lists, and the commands' allowed-tools. Installed as a plugin, the tools are named
mcp__plugin_gephi-network-analysis_gephi-ai__gephi_*, not mcp__gephi-ai__gephi_* as they are
for a server registered by hand. With the hand-registered names the hook never fired and the
agents' read-only lists restricted nothing.
"""
import json
import re
from pathlib import Path

import gephi_mcp

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "claude-code"
PLUGIN_PREFIX = "mcp__plugin_gephi-network-analysis_gephi-ai__"
BARE_PREFIX = "mcp__gephi-ai__"


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
        assert re.search(matcher, "mcp__gephi-mcp__" + tool), f"hook misses the pre-1.20 server name {tool}"
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


def test_commands_grant_only_the_skill_they_load():
    # The plugin directory holds a bare Skill grant for review: it pre-approves every skill.
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    skills = {f"{manifest['name']}:{p.parent.name}" for p in (PLUGIN / "skills").glob("*/SKILL.md")}
    for command in sorted((PLUGIN / "commands").glob("*.md")):
        grants = [t for t in _field(command, "allowed-tools") or [] if t.startswith("Skill")]
        assert grants, f"{command.name} grants no skill, but tells the model to load one"
        for grant in grants:
            name = re.fullmatch(r"Skill\((.+)\)", grant)
            assert name, f"{command.name}: '{grant}' pre-approves every skill; name the one it loads"
            assert name.group(1) in skills, f"{command.name}: {name.group(1)} is not this plugin's skill"


def test_no_command_pre_approves_a_shell():
    for command in sorted((PLUGIN / "commands").glob("*.md")):
        grants = _field(command, "allowed-tools") or []
        assert not [t for t in grants if t.split("(")[0] == "Bash"], f"{command.name} pre-approves Bash"


def test_the_plugin_ships_a_square_icon():
    icon = PLUGIN / ".claude-plugin" / "icon.svg"
    view_box = re.search(r'viewBox="0 0 (\d+) (\d+)"', icon.read_text(encoding="utf-8"))
    assert view_box and view_box.group(1) == view_box.group(2), "the icon is not square"
    assert int(view_box.group(1)) >= 128, "the directory wants an icon of at least 128px"


def test_the_hook_command_survives_a_plugin_path_with_spaces():
    # Cowork installs plugins under "Application Support"; an unquoted path splits there.
    hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    for entry in hooks["hooks"]["PreToolUse"]:
        for hook in entry["hooks"]:
            assert hook["command"].startswith('"${CLAUDE_PLUGIN_ROOT}/'), hook["command"]


def test_the_plugin_shows_as_gephi_ai():
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["displayName"] == "Gephi AI"
