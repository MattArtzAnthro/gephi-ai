"""
Tripwires for the repository's agent-facing documents. Registration commands
and instruction files get pasted verbatim by people and by agents, so a stale
or missing one fails here instead of at a user's terminal.
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# The server NAME is `gephi-ai` (it sets the tool prefix `mcp__gephi-ai__` and every
# allowlist that matches it; it was `gephi-mcp` before 1.20.0), and the PACKAGE the launcher
# resolves is also `gephi-ai`. Both are pinned here.
REGISTRATIONS = (
    "claude mcp add gephi-ai -- uvx gephi-ai",
    "codex mcp add gephi-ai -- uvx gephi-ai",
    "gemini mcp add -s user gephi-ai uvx gephi-ai",
)


def _read(name):
    return (REPO / name).read_text(encoding="utf-8")


def test_instruction_files_exist_for_the_three_agent_ecosystems():
    for name in ("CLAUDE.md", "AGENTS.md", "GEMINI.md"):
        assert (REPO / name).is_file(), f"{name} missing at the repository root"


def test_agents_and_gemini_instructions_are_identical():
    assert _read("AGENTS.md") == _read("GEMINI.md"), "AGENTS.md and GEMINI.md drifted apart"


def test_instruction_files_carry_the_registration_commands():
    for name in ("CLAUDE.md", "AGENTS.md", "GEMINI.md"):
        text = _read(name)
        for cmd in REGISTRATIONS:
            assert cmd in text, f"{name} lacks: {cmd}"


def test_readme_carries_the_registration_commands_and_skill_directories():
    text = _read("README.md")
    for cmd in REGISTRATIONS:
        assert cmd in text, f"README.md lacks: {cmd}"
    for d in ("~/.codex/skills/", "~/.cursor/skills/", "~/.copilot/skills/"):
        assert d in text, f"README.md lacks the skills directory {d}"


def test_skill_prose_does_not_hardcode_the_claude_tool_prefix():
    """Other agents see the tools as gephi_*; the Claude Code prefix belongs in
    allowed-tools frontmatter and hooks, not in the guidance the model reads."""
    skill = REPO / "plugins" / "claude-code" / "skills" / "gephi" / "SKILL.md"
    body = skill.read_text(encoding="utf-8").split("---", 2)[2]
    stray = [ln for ln in body.splitlines()
             if "mcp__gephi-ai__" in ln and "Claude Code shows them as" not in ln]
    assert stray == [], f"Claude-only tool prefix in skill prose: {stray[:3]}"


# ── Documentation parity: the docs must describe the tools that actually exist ──

def _registered_tools():
    import gephi_mcp
    return {t.name for t in gephi_mcp.mcp._tool_manager.list_tools()}


def test_every_registered_tool_is_documented_in_the_tool_reference():
    """A tool absent from the reference does not exist to the agent that would use it.

    This repo's primary reader is a coding agent, so an undocumented tool is not a cosmetic gap:
    it is a capability nobody can find. Counts in prose rot quietly; this fails loudly instead.
    """
    reference = _read("plugins/claude-code/skills/gephi/references/tool-reference.md")

    undocumented = sorted(t for t in _registered_tools() if t not in reference)

    assert not undocumented, f"registered but absent from the tool reference: {undocumented}"


def test_the_readme_category_counts_add_up_to_the_number_of_tools():
    """The heading count and the per-category counts are two claims that must agree with reality.

    A hand-maintained table drifts the moment a tool is added, and the drift is invisible because
    both numbers still look plausible on their own.
    """
    readme = _read("README.md")
    section = readme.split("## Tools (")[1]
    heading_count = int(section.split(")")[0])
    rows = re.findall(r"^\| [^|]+\| (\d+) \|", section, re.MULTILINE)

    assert sum(int(n) for n in rows) == heading_count, (
        f"category counts sum to {sum(int(n) for n in rows)} but the heading says {heading_count}")
    assert heading_count == len(_registered_tools()), (
        f"README says {heading_count} tools; {len(_registered_tools())} are registered")


def test_every_surface_that_states_a_tool_count_states_the_same_one():
    """A stale tool count is a claim about capability that a reader acts on.

    The count lives on nine surfaces. It drifted once already: plugin.json said
    106 while the other eight said 112, because the release sweep covered seven
    files and nobody had counted the ones outside it. This test derives the truth
    from the registrations and holds every surface to it, so the next surface that
    lags fails here rather than misinforming an agent about what it can do.
    """

    source = (REPO / "mcp-server" / "gephi_mcp.py").read_text(encoding="utf-8")
    actual = source.count("@_tool(name=")
    assert actual > 0, "could not count @_tool registrations"

    surfaces = {
        "README.md": _read("README.md"),
        "CLAUDE.md": _read("CLAUDE.md"),
        "AGENTS.md": _read("AGENTS.md"),
        "GEMINI.md": _read("GEMINI.md"),
        "mcp-server/README.md": _read("mcp-server/README.md"),
        "mcpb/manifest.json": _read("mcpb/manifest.json"),
        "plugins/claude-code/skills/gephi/SKILL.md": _read("plugins/claude-code/skills/gephi/SKILL.md"),
        "plugins/claude-code/.claude-plugin/plugin.json": _read(
            "plugins/claude-code/.claude-plugin/plugin.json"
        ),
    }

    pattern = re.compile(r"\b(\d{2,4})\s+(?:MCP\s+)?tools\b")
    checked = 0
    for name, text in surfaces.items():
        for found in pattern.findall(text):
            checked += 1
            assert int(found) == actual, (
                f"{name} claims {found} tools; the server registers {actual}"
            )
    assert checked >= len(surfaces), (
        f"only found {checked} tool-count claims across {len(surfaces)} surfaces; "
        "a surface stopped stating its count and would now drift unnoticed"
    )


def test_no_skill_or_reference_names_a_tool_that_does_not_exist():
    """The direction that is easy to skip, and where the bug was.

    A tool-count tripwire and a "documented every registered tool" check both look like
    coverage, and both are blind to the reverse: prose naming a tool that was never
    registered. That is worse than an undocumented tool, because it sends the assistant
    after something that cannot answer. `gephi_list_layouts` sat in the skill and the
    layout guide through several releases; the real tool is `gephi_get_available_layouts`.
    """
    server = (REPO / "mcp-server" / "gephi_mcp.py").read_text(encoding="utf-8")
    registered = set(re.findall(r'@_tool\(name="(gephi_[a-z0-9_]+)"', server))
    assert registered, "found no @_tool registrations to compare against"
    # Reply fields that share the prefix. Each must really be a field, not a misremembered tool.
    reply_fields = {"gephi_version"}
    java = "\n".join(p.read_text(encoding="utf-8")
                     for p in (REPO / "gephi-ai-plugin" / "src" / "main" / "java").rglob("*.java"))
    assert all(f'"{f}"' in java for f in reply_fields), "a listed reply field is not in the plugin"
    registered |= reply_fields

    surfaces = list((REPO / "plugins" / "claude-code").rglob("*.md"))
    assert surfaces, "found no Claude plugin markdown to check"

    problems = {}
    for path in surfaces:
        named = set(re.findall(r"\bgephi_[a-z0-9_]+", path.read_text(encoding="utf-8")))
        unknown = named - registered
        if unknown:
            problems[str(path.relative_to(REPO))] = sorted(unknown)
    assert not problems, f"prose names tools that do not exist: {problems}"


def test_bundle_uses_the_uv_runtime():
    manifest = json.loads(_read("mcpb/manifest.json"))
    assert manifest["manifest_version"] == "0.4"
    assert manifest["server"]["type"] == "uv"
    assert manifest["server"]["entry_point"] == "src/server.py"
    # Claude Desktop starts the server with exactly this command.
    assert manifest["server"]["mcp_config"] == {
        "command": "uv",
        "args": ["run", "--directory", "${__dirname}", manifest["server"]["entry_point"]],
    }
    assert (REPO / "mcpb" / manifest["server"]["entry_point"]).is_file()
    assert not (REPO / "mcpb" / "server").exists(), "the bundle must not vendor libraries"


def test_bundle_pins_the_same_server_version_as_the_plugins():
    manifest = json.loads(_read("mcpb/manifest.json"))
    pin = re.search(r'"gephi-ai==([^"]+)"', _read("mcpb/pyproject.toml")).group(1)
    plugin_pin = json.loads(_read("plugins/claude-code/.mcp.json"))[
        "mcpServers"]["gephi-ai"]["args"][1].split("==")[1]
    assert manifest["version"] == pin == plugin_pin


def test_readme_does_not_claim_macos_ships_python_310():
    assert "modern macOS provides" not in _read("README.md")


# ── Tool descriptions and the skill give the same defaults ──
# A session that never loads the skill still reads the tool descriptions, so a default stated
# differently in the two is a default that depends on whether the skill happened to load.

def _tool_doc(name):
    import gephi_mcp
    return next(t.description for t in gephi_mcp.mcp._tool_manager.list_tools() if t.name == name)


def test_node_sizes_default_to_a_one_to_ten_ratio():
    import inspect

    import gephi_mcp
    params = inspect.signature(gephi_mcp.gephi_size_by_ranking).parameters
    assert params["max_size"].default == 10 * params["min_size"].default


def test_export_png_recommends_the_skills_edge_default():
    doc = _tool_doc("gephi_export_png")
    assert '"edge.color": "#D0D0D0"' in doc and '"edge.opacity": 90' in doc
    assert '"edge.opacity": 25' not in doc


def test_color_by_partition_leaves_the_palette_to_the_plugin():
    doc = _tool_doc("gephi_color_by_partition")
    assert "gray" not in doc.lower() and "grey" not in doc.lower()
    assert "largest group" in doc


def test_the_skill_explains_the_plugins_already_running_refusal():
    """The plugin refuses a second run of a statistic with "already running"; both skill copies
    must tell the model what that means, or it retries in a loop behind the graph lock."""
    java = (REPO / "gephi-ai-plugin/src/main/java/org/gephi/plugins/mcp/service/"
            "GephiControlService.java").read_text(encoding="utf-8")
    assert "is already running; wait for it to finish" in java
    for copy in ("claude-code", "gephi-network-analysis"):
        skill = (REPO / "plugins" / copy / "skills" / "gephi" / "SKILL.md").read_text(encoding="utf-8")
        assert '"already running"' in skill and "gephi_stop_statistic" in skill, copy
