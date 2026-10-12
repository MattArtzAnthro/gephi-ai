"""The live harnesses stay runnable between releases.

live_smoke_test.py and live_scale_test.py need a running Gephi, so they are run by hand (their
docstrings give the commands) and pytest never collects them. What can rot unseen in between is
checked here without Gephi: that they import, that their graph generators still write what the
run expects, and that every tool they call still exists under that name.
"""

import re
from pathlib import Path

import gephi_mcp
from gephi_mcp_viewer import parse_gexf

HERE = Path(__file__).parent


def test_the_smoke_graph_has_the_promised_scale(tmp_path):
    import live_smoke_test

    path = tmp_path / "smoke.gexf"
    nodes, edges = live_smoke_test.build_big_gexf(str(path))

    graph = parse_gexf(str(path), max_nodes=10**9)
    assert nodes == len(graph["nodes"]) == 1000
    assert edges == len(graph["edges"]) and edges > 3000


def test_the_scale_graph_has_the_requested_size(tmp_path):
    import live_scale_test

    path = tmp_path / "scale.gexf"
    nodes, edges = live_scale_test.gen(1000, str(path))

    graph = parse_gexf(str(path), max_nodes=10**9)
    assert nodes == len(graph["nodes"]) == 1000
    assert edges == len(graph["edges"])


def test_every_tool_a_harness_calls_still_exists():
    for harness in ("live_smoke_test.py", "live_scale_test.py"):
        called = set(re.findall(r"\bg\.(gephi_\w+)", (HERE / harness).read_text()))
        assert called, harness
        missing = sorted(name for name in called if not hasattr(gephi_mcp, name))
        assert not missing, f"{harness} calls tools that no longer exist: {missing}"
