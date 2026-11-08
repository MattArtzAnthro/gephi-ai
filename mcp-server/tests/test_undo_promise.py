"""The server instructions say which tools take an undo snapshot. That sentence is read from the
source here, so it cannot drift from the tools again: every tool it says snapshots must call a
snapshot helper, and every tool it says does not must not."""
import inspect
import re
from pathlib import Path

import gephi_mcp

REPO = Path(__file__).resolve().parents[2]
SNAPSHOT_HELPERS = ("_auto_snapshot(", "_snapshot_then(", "_snapshot_current(")


def _rule_eight():
    text = " ".join(gephi_mcp._INSTRUCTIONS.split())
    match = re.search(r"8\. (.*?) 9\. ", text)
    assert match, "rule 8 of the server instructions is missing"
    return match.group(1)


def _sentences(rule):
    return [s for s in re.split(r"(?<=\.) ", rule) if s]


def _names(sentence):
    return re.findall(r"\bgephi_[a-z_]+", sentence)


def _takes_snapshot(tool):
    source = inspect.getsource(getattr(gephi_mcp, tool))
    return any(helper in source for helper in SNAPSHOT_HELPERS)


def _split():
    promised = [s for s in _sentences(_rule_eight()) if "take an undo snapshot" in s]
    denied = [s for s in _sentences(_rule_eight()) if " do not:" in s or s.startswith("These do not")]
    assert len(promised) == 1 and len(denied) == 1, "rule 8 must say who snapshots and who does not"
    return _names(promised[0]), _names(denied[0])


def test_every_tool_the_instructions_say_snapshots_calls_a_snapshot_helper():
    promised, _ = _split()
    promised = [n for n in promised if n != "gephi_undo"]
    assert len(promised) >= 4
    for tool in promised:
        assert _takes_snapshot(tool), f"{tool} is promised an undo snapshot but takes none"


def test_every_tool_the_instructions_say_does_not_snapshot_takes_none():
    _, denied = _split()
    assert {"gephi_remove_node", "gephi_remove_edge", "gephi_apply_filter",
            "gephi_apply_filters"} <= set(denied)
    for tool in denied:
        if tool == "gephi_snapshot":
            continue
        assert not _takes_snapshot(tool), f"{tool} is said to take no snapshot but does"


def test_the_instructions_tell_the_agent_to_snapshot_first_for_the_tools_without_one():
    sentence = next(s for s in _sentences(_rule_eight()) if "gephi_snapshot" in s)
    assert "first" in sentence


def test_the_blanket_promise_is_gone_from_every_copy():
    old = "(clear, remove, merge, filter, extract) take an"
    for path in ("CLAUDE.md", "AGENTS.md", "GEMINI.md", "README.md",
                 "plugins/claude-code/skills/gephi/SKILL.md",
                 "plugins/gephi-network-analysis/skills/gephi/SKILL.md"):
        assert old not in " ".join((REPO / path).read_text(encoding="utf-8").split()), path


def test_each_copy_names_the_tools_that_take_no_snapshot():
    for path in ("CLAUDE.md", "AGENTS.md", "GEMINI.md",
                 "plugins/claude-code/skills/gephi/SKILL.md",
                 "plugins/gephi-network-analysis/skills/gephi/SKILL.md"):
        text = " ".join((REPO / path).read_text(encoding="utf-8").split())
        for tool in ("gephi_remove_node", "gephi_remove_edge", 'action="column"'):
            assert tool in text, f"{path} does not mention {tool} as taking no snapshot"
