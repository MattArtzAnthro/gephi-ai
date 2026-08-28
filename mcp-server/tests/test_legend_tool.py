"""The ledger wired into the styling tools, and the legend tool that draws on it.

The legend can only describe mappings that came through these tools. Styling done by hand in the
Gephi window is invisible here, so the tool refuses to draw a legend it cannot stand behind rather
than emitting a confident and wrong one, which would be worse than no legend at all.
"""

import json
import textwrap

import pytest

import gephi_mcp


class Recorder:
    def __init__(self):
        self.calls = []
        self.responses = []

    async def __call__(self, method, endpoint, params=None, json_data=None, timeout=None):
        self.calls.append({"method": method, "endpoint": endpoint, "json": json_data})
        if self.responses:
            return self.responses.pop(0)
        return {"success": True}

    def endpoints(self):
        return [c["endpoint"] for c in self.calls]


@pytest.fixture
def rec(monkeypatch, tmp_path):
    r = Recorder()
    monkeypatch.setattr(gephi_mcp.gephi, "request", r)
    gephi_mcp.LEDGER.reset()
    return r


def coloured_gexf(assignments):
    """A Gephi-shaped export where each node carries a partition value and a colour."""
    nodes = "\n".join(
        f'<node id="{n}" label="{n}"><attvalues><attvalue for="0" value="{group}"/></attvalues>'
        f'<viz:color r="{r}" g="{g}" b="{b}"/></node>'
        for n, (group, (r, g, b)) in assignments.items())
    return textwrap.dedent("""\
        <?xml version="1.0" encoding="UTF-8"?>
        <gexf xmlns="http://gexf.net/1.3" xmlns:viz="http://gexf.net/1.3/viz" version="1.3">
        <graph defaultedgetype="undirected">
        <attributes class="node"><attribute id="0" title="Modularity Class" type="integer"/></attributes>
        <nodes>%s</nodes><edges/></graph></gexf>
        """) % nodes


# ── The styling tools feed the ledger ──

async def test_colouring_by_a_partition_is_recorded(rec):
    await gephi_mcp.gephi_color_by_partition(column="Modularity Class")

    assert gephi_mcp.LEDGER.legend_items() == [
        {"channel": "node colour", "column": "Modularity Class"}]


async def test_sizing_by_a_ranking_records_its_range(rec):
    await gephi_mcp.gephi_size_by_ranking(column="Degree", min_size=8, max_size=44)

    item = gephi_mcp.LEDGER.legend_items()[0]
    assert item["channel"] == "node size"
    assert item["range"] == [8, 44]


async def test_a_layout_is_recorded_for_the_methods_note(rec):
    await gephi_mcp.gephi_run_layout(algorithm="ForceAtlas2", iterations=300)

    assert gephi_mcp.LEDGER.receipt()["layout"]["algorithm"] == "ForceAtlas2"


async def test_a_statistic_is_recorded_with_the_settings_it_ran_under(rec):
    rec.responses = [{"success": True, "modularity": 0.4}]

    await gephi_mcp.gephi_compute_modularity(resolution=1.5)

    assert gephi_mcp.LEDGER.receipt()["statistics"] == [
        {"metric": "modularity", "params": {"resolution": 1.5}}]


async def test_a_failed_styling_call_is_not_recorded(rec):
    """The ledger describes the map. A call Gephi refused changed nothing."""
    rec.responses = [{"success": False, "error": "no such column"}]

    await gephi_mcp.gephi_color_by_partition(column="Nonexistent")

    assert gephi_mcp.LEDGER.legend_items() == []


# The ledger reset lives inside the real client, so these are written as a pure predicate plus
# one test that drives the genuine client. Patching gephi.request away would test a seam that is
# never deployed.

@pytest.mark.parametrize("method,endpoint", [
    ("POST", "/graph/clear"),
    ("POST", "/workspace/new"),
    ("DELETE", "/workspace/delete"),
    ("POST", "/project/open"),
    ("POST", "/import/gexf"),
])
def test_these_calls_replace_the_graph_the_record_describes(method, endpoint):
    from stats_integrity import replaces_graph

    assert replaces_graph(method, endpoint) is True


@pytest.mark.parametrize("method,endpoint", [
    ("POST", "/graph/node/add"),
    ("POST", "/appearance/node/color"),
    ("POST", "/statistics/modularity"),
    ("POST", "/layout/run"),
    ("GET", "/graph/stats"),
])
def test_these_calls_leave_the_styling_record_meaningful(method, endpoint):
    """Adding a node does not invalidate a colour mapping. Only a different graph does."""
    from stats_integrity import replaces_graph

    assert replaces_graph(method, endpoint) is False


async def test_the_real_client_empties_the_ledger_when_the_graph_is_replaced(monkeypatch):
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {"success": True}

    class FakeAsyncClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def request(self, **kwargs): return FakeResponse()

    monkeypatch.setattr(gephi_mcp.httpx, "AsyncClient", FakeAsyncClient)
    gephi_mcp.LEDGER.reset()
    gephi_mcp.LEDGER.record("color_by_partition", column="Modularity Class")

    await gephi_mcp.gephi.request("POST", "/graph/node/add")
    assert gephi_mcp.LEDGER.legend_items(), "an ordinary edit must not discard the record"

    await gephi_mcp.gephi.request("POST", "/graph/clear")
    assert gephi_mcp.LEDGER.legend_items() == []


# ── The legend tool ──

async def test_the_legend_refuses_when_nothing_was_mapped_through_these_tools(rec, tmp_path):
    """Silence is the honest answer. A guessed legend is worse than none."""
    out = json.loads(await gephi_mcp.gephi_export_legend(file=str(tmp_path / "legend.svg")))

    assert out["success"] is False
    assert "by hand" in out["error"].lower()
    assert rec.endpoints() == [], "it must not touch the graph before refusing"


async def test_the_legend_takes_its_swatch_colours_from_the_live_graph(rec, tmp_path):
    """Gephi assigns the palette when none is given, so the colours must be read, not assumed."""
    await gephi_mcp.gephi_color_by_partition(column="Modularity Class")
    rec.responses = [{"success": True, "content": coloured_gexf({
        "a": ("1", (78, 121, 167)),
        "b": ("1", (78, 121, 167)),
        "c": ("2", (225, 87, 89)),
    })}]

    path = tmp_path / "legend.svg"
    out = json.loads(await gephi_mcp.gephi_export_legend(file=str(path)))

    svg = path.read_text()
    assert out["success"] is True
    assert "Modularity Class" in svg
    assert "#4e79a7" in svg and "#e15759" in svg, "swatches must match the graph's actual colours"


async def test_the_legend_names_every_group_it_found(rec, tmp_path):
    await gephi_mcp.gephi_color_by_partition(column="Modularity Class")
    rec.responses = [{"success": True, "content": coloured_gexf({
        "a": ("1", (78, 121, 167)),
        "c": ("2", (225, 87, 89)),
    })}]

    path = tmp_path / "legend.svg"
    await gephi_mcp.gephi_export_legend(file=str(path))

    svg = path.read_text()
    assert ">1<" in svg and ">2<" in svg


async def test_a_size_mapping_needs_no_graph_read(rec, tmp_path):
    """The range was given to the tool, so nothing has to be looked up to describe it."""
    await gephi_mcp.gephi_size_by_ranking(column="Degree", min_size=8, max_size=44)

    path = tmp_path / "legend.svg"
    out = json.loads(await gephi_mcp.gephi_export_legend(file=str(path)))

    assert out["success"] is True
    assert "/export/gexf" not in rec.endpoints()
    assert "Degree" in path.read_text()


# ── The receipt ──

async def test_the_receipt_reports_the_layout_and_statistics_that_produced_the_figure(rec):
    rec.responses = [{"success": True}, {"success": True, "modularity": 0.4}]
    await gephi_mcp.gephi_run_layout(algorithm="ForceAtlas2", iterations=300)
    await gephi_mcp.gephi_compute_modularity(resolution=1.5)

    out = json.loads(await gephi_mcp.gephi_session_receipt())

    assert out["layout"]["algorithm"] == "ForceAtlas2"
    assert out["statistics"][0]["metric"] == "modularity"
    assert out["versions"]["server"]


async def test_the_receipt_states_its_own_limits(rec):
    out = json.loads(await gephi_mcp.gephi_session_receipt())

    assert "by hand" in out["scope"].lower()


async def test_the_receipt_can_be_written_to_a_file(rec, tmp_path):
    await gephi_mcp.gephi_run_layout(algorithm="ForceAtlas2", iterations=300)
    path = tmp_path / "methods.json"

    await gephi_mcp.gephi_session_receipt(file=str(path))

    assert json.loads(path.read_text())["layout"]["algorithm"] == "ForceAtlas2"
