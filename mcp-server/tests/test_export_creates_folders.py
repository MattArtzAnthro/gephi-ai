"""Saving into a folder that does not exist yet.

Every tool that writes a file used to fail with "No such file or directory" when the folder
was new, whether Gephi wrote the file (exports, project save) or this server did (legend,
receipt). The server now creates the folder first, for absolute paths only: a relative path
would resolve against Gephi's working directory, not this server's, so guessing would create
the folder in the wrong place.
"""

import json

import pytest

import gephi_mcp


class Recorder:
    def __init__(self):
        self.calls = []

    async def __call__(self, method, endpoint, params=None, json_data=None, timeout=None):
        self.calls.append({"endpoint": endpoint, "json": json_data})
        return {"success": True}


@pytest.fixture
def rec(monkeypatch):
    r = Recorder()
    monkeypatch.setattr(gephi_mcp.gephi, "request", r)
    gephi_mcp.LEDGER.reset()
    return r


GEPHI_WRITTEN = [
    ("gephi_export_png", {}, "map.png"),
    ("gephi_export_pdf", {}, "map.pdf"),
    ("gephi_export_svg", {}, "map.svg"),
    ("gephi_export_gexf", {}, "graph.gexf"),
    ("gephi_export_graphml", {}, "graph.graphml"),
    ("gephi_export_csv", {}, "nodes.csv"),
    ("gephi_export", {"format": "pajek"}, "graph.net"),
    ("gephi_export_screenshot", {}, "screen.png"),
    ("gephi_save_project", {}, "project.gephi"),
]


@pytest.mark.parametrize("tool,extra,name", GEPHI_WRITTEN)
async def test_gephi_written_files_get_their_folder_created(rec, tmp_path, tool, extra, name):
    target = tmp_path / "new" / "deeper" / name

    result = json.loads(await getattr(gephi_mcp, tool)(file=str(target), **extra))

    assert result["success"] is True
    assert target.parent.is_dir()
    assert rec.calls[-1]["json"]["file"] == str(target)


async def test_receipt_is_written_into_a_new_folder(rec, tmp_path):
    target = tmp_path / "methods" / "receipt.json"

    result = json.loads(await gephi_mcp.gephi_session_receipt(file=str(target)))

    assert result["success"] is True
    assert json.loads(target.read_text())["success"] is True


async def test_legend_is_written_into_a_new_folder(rec, tmp_path):
    await gephi_mcp.gephi_color_by_partition(column="Modularity Class")
    target = tmp_path / "figures" / "legend.svg"

    result = json.loads(await gephi_mcp.gephi_export_legend(file=str(target)))

    assert result["success"] is True
    assert target.read_text().startswith("<")


async def test_a_folder_that_cannot_be_created_is_reported_before_gephi_is_asked(rec, tmp_path):
    blocker = tmp_path / "taken"
    blocker.write_text("a file where the folder would go")

    result = json.loads(await gephi_mcp.gephi_export_png(file=str(blocker / "map.png")))

    assert result["success"] is False
    assert "folder" in result["error"]
    assert rec.calls == []


async def test_relative_paths_are_passed_through_untouched(rec, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    await gephi_mcp.gephi_export_png(file="out/map.png")

    assert not (tmp_path / "out").exists()
    assert rec.calls[-1]["json"]["file"] == "out/map.png"
