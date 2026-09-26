"""
Live checks of the Claude Code plugin's wiring, through the real `claude` CLI.

test_plugin_wiring.py checks the names written in the plugin's files. Only Claude Code can say
whether it applies them: whether the hook fires, whether an agent's tool list holds, whether a
command's pre-approved tools are actually approved. Plugin tool naming has changed under this
plugin once already, and the files then looked right while nothing applied.

Opt-in, because each test starts a Claude session (Haiku; a few cents each):

    GEPHI_LIVE_PLUGIN=1 PYTHONPATH=. .venv/bin/python -m pytest -v tests/test_plugin_live.py

Run from mcp-server/. Gephi need not be running: every test points the plugin at a closed port.
The plugin under test is this working tree's plugins/claude-code, with its server started from
this working tree rather than PyPI. `--setting-sources project` keeps your own settings out, so
neither an installed copy of the plugin nor your permission rules can make a test pass.
The model is asked to make specific calls; a failure is worth reading before it is believed.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

MCP_DIR = Path(__file__).resolve().parents[1]
PLUGIN = MCP_DIR.parent / "plugins" / "claude-code"
TOOL = "mcp__plugin_gephi-network-analysis_gephi-mcp__gephi_"
HOOK_MESSAGE = "Gephi Desktop is not running or the MCP plugin is not responding"

pytestmark = pytest.mark.skipif(
    os.environ.get("GEPHI_LIVE_PLUGIN") != "1" or shutil.which("claude") is None,
    reason="live plugin checks: set GEPHI_LIVE_PLUGIN=1 with the claude CLI installed")


def _closed_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def session(tmp_path_factory):
    root = tmp_path_factory.mktemp("live-plugin")
    plugin = root / "plugin"
    shutil.copytree(PLUGIN, plugin, ignore=shutil.ignore_patterns("__pycache__"))
    launch = f"import sys; sys.path.insert(0, {str(MCP_DIR)!r}); import gephi_mcp; gephi_mcp.mcp.run()"
    (plugin / ".mcp.json").write_text(json.dumps(
        {"mcpServers": {"gephi-mcp": {"command": sys.executable, "args": ["-c", launch]}}}))
    project = root / "project"
    project.mkdir()
    env = dict(os.environ, GEPHI_API_URL=f"http://127.0.0.1:{_closed_port()}")

    def run(prompt, bypass_permissions=True):
        argv = ["claude", "-p", "--setting-sources", "project", "--model", "haiku",
                "--plugin-dir", str(plugin), "--output-format", "stream-json", "--verbose"]
        if bypass_permissions:
            argv += ["--permission-mode", "bypassPermissions"]
        out = subprocess.run(argv + [prompt], cwd=project, env=env, capture_output=True,
                             text=True, timeout=600).stdout
        return [json.loads(line) for line in out.splitlines() if line.startswith("{")]

    return run


def _calls(events):
    """(tool name, id, called from inside a subagent) for every tool call in the session."""
    return [(c["name"], c["id"], bool(e.get("parent_tool_use_id")))
            for e in events if e.get("type") == "assistant"
            for c in e["message"]["content"] if c.get("type") == "tool_use"]


def _results(events):
    return {c["tool_use_id"]: json.dumps(c.get("content"))
            for e in events if e.get("type") == "user" and isinstance(e["message"].get("content"), list)
            for c in e["message"]["content"] if c.get("type") == "tool_result"}


def _denied(events):
    return [d.get("tool_name", "") for e in events if e.get("type") == "result"
            for d in e.get("permission_denials", [])]


def test_the_hook_stops_a_graph_change_when_gephi_is_down(session):
    # The skill tells the model to check Gephi first; this test needs the call itself, so the
    # prompt rules out the health check and the skill for this one session.
    events = session("This is a test of a safety hook. Do not load any skill and do not call "
                     "gephi_health_check. Your first Gephi call must be gephi_add_node with id "
                     "'probe' (load it with ToolSearch if it is deferred), even if you expect it "
                     "to fail. Then report exactly what happened.")
    attempted = [i for name, i, _ in _calls(events) if name == TOOL + "add_node"]
    results = _results(events)
    assert attempted, "the model never tried gephi_add_node, so the hook was not exercised"
    assert any(HOOK_MESSAGE in results.get(i, "") for i in attempted), \
        "gephi_add_node ran without the plugin's health-check hook stopping it"


def test_a_read_only_agent_cannot_reach_a_restyling_tool(session):
    events = session(
        "Dispatch the gephi-network-analysis:claim-verifier agent with exactly this task: "
        "'Call gephi_health_check. Then call gephi_set_node_color for node probe with r=1, g=2, "
        "b=3, loading it with ToolSearch if needed. Report which of the two calls you could make.'")
    inside = {name for name, _, sub in _calls(events) if sub}
    assert TOOL + "health_check" in inside, \
        "the agent could not call gephi_health_check, so it has none of the plugin's tools"
    assert TOOL + "set_node_color" not in inside, \
        "the read-only claim-verifier called gephi_set_node_color"


def test_a_command_pre_approves_its_gephi_tools(session):
    events = session("/gephi-network-analysis:explore Step one: call the gephi_health_check tool "
                     "(load it with ToolSearch if needed) and report its result. Do nothing else.",
                     bypass_permissions=False)
    ran = [i for name, i, _ in _calls(events) if name == TOOL + "health_check"]
    assert ran and all(i in _results(events) for i in ran), \
        "gephi_health_check never ran under the command's own permissions"
    assert not [d for d in _denied(events) if d.startswith(TOOL)], \
        f"the command's allowed-tools did not approve: {_denied(events)}"
