"""
Tripwires for the repository's agent-facing documents. Registration commands
and instruction files get pasted verbatim by people and by agents, so a stale
or missing one fails here instead of at a user's terminal.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

REGISTRATIONS = (
    "claude mcp add gephi-mcp -- uvx gephi-mcp",
    "codex mcp add gephi-mcp -- uvx gephi-mcp",
    "gemini mcp add -s user gephi-mcp uvx gephi-mcp",
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
    skill = REPO / "claude-plugin" / "skills" / "gephi" / "SKILL.md"
    body = skill.read_text(encoding="utf-8").split("---", 2)[2]
    stray = [ln for ln in body.splitlines()
             if "mcp__gephi-mcp__" in ln and "Claude Code shows them as" not in ln]
    assert stray == [], f"Claude-only tool prefix in skill prose: {stray[:3]}"
