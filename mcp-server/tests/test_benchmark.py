"""The benchmark in bench/benchmark.py, run offline against the fake Gephi. It must refuse the
user's own Gephi (port 8080), write the documented JSON and table, record an erroring step and
carry on, and compare two runs without calling noise a change."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
from test_ledger_survives_snapshot import install_fake_gephi

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bench"))
import benchmark  # noqa: E402

SEPARATE = "http://127.0.0.1:8091"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ("GEPHI_API_URL", "GEPHI_AI_TIMING_LOG", "GEPHI_SKIP_UPDATE_CHECK"):
        monkeypatch.delenv(name, raising=False)


def fake_gephi(monkeypatch, faults=None):
    """The fake Gephi, with a layout that has already finished and no one-second polling wait."""
    real_sleep = asyncio.sleep

    async def quick(_seconds):
        await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", quick)
    return install_fake_gephi(monkeypatch, faults={
        "/layout/status": {"success": True, "running": False}, **(faults or {})})


def run(argv, tmp_path, capsys):
    code = benchmark.main([*argv, "--out", str(tmp_path / "result.json")])
    return code, capsys.readouterr()


def test_refuses_when_the_url_is_unset(monkeypatch, tmp_path, capsys):
    state = fake_gephi(monkeypatch)
    code, seen = run(["--sizes", "5"], tmp_path, capsys)
    assert code == 2 and "GEPHI_API_URL" in seen.err
    assert state["calls"] == [] and not (tmp_path / "result.json").exists()


@pytest.mark.parametrize("url", ["http://127.0.0.1:8080", "http://localhost:8080/"])
def test_refuses_port_8080(monkeypatch, tmp_path, capsys, url):
    monkeypatch.setenv("GEPHI_API_URL", url)
    state = fake_gephi(monkeypatch)
    code, seen = run(["--sizes", "5"], tmp_path, capsys)
    assert code == 2 and "8080" in seen.err and "--allow-port-8080" in seen.err
    assert state["calls"] == []


def test_the_flag_allows_port_8080(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GEPHI_API_URL", "http://127.0.0.1:8080")
    state = fake_gephi(monkeypatch)
    code, _ = run(["--sizes", "5", "--repeats", "1", "--allow-port-8080"], tmp_path, capsys)
    assert code == 0 and state["calls"]


def test_two_sizes_one_repeat_write_the_json_and_the_table(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GEPHI_API_URL", SEPARATE)
    state = fake_gephi(monkeypatch, faults={
        "/health": {"success": True, "version": "1.6.0", "gephi_version": "0.11.4"}})
    code, seen = run(["--sizes", "20,30", "--repeats", "1"], tmp_path, capsys)
    assert code == 0
    data = json.loads((tmp_path / "result.json").read_text())
    assert {"date", "server_version", "plugin_version", "gephi_version", "machine", "sizes",
            "seed", "repeats", "generator", "results"} <= set(data)
    assert data["plugin_version"] == "1.6.0" and data["gephi_version"] == "0.11.4"
    assert data["sizes"] == [20, 30] and data["repeats"] == 1
    assert {"platform", "cpu_count"} <= set(data["machine"])
    steps = data["results"]["20"]
    assert list(steps) == [name for name, _ in benchmark.STEPS]
    for entry in steps.values():
        assert len(entry["ms"]) == 1 and entry["median"] == entry["min"] == entry["max"]
    assert "| Step | 20 nodes | 30 nodes |" in seen.out
    assert "| pagerank |" in seen.out
    # The timing log sits beside the result, and the export folder is gone afterwards.
    log = tmp_path / "result.timing.jsonl"
    logged = {json.loads(line)["tool"] for line in log.read_text().splitlines()}
    assert logged >= {"gephi_generate_graph", "gephi_compute_pagerank"}
    # The benchmark's own bookkeeping (counting workspaces) is not a measured step.
    assert "gephi_list_workspaces" not in logged
    exported = [Path(c[3]["file"]) for c in state["calls"] if c[1].startswith("/export/") and "file" in c[3]]
    assert exported and not any(p.exists() or p.parent.exists() for p in exported)


def test_an_existing_timing_log_variable_is_kept(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GEPHI_API_URL", SEPARATE)
    mine = tmp_path / "mine.jsonl"
    monkeypatch.setenv("GEPHI_AI_TIMING_LOG", str(mine))
    fake_gephi(monkeypatch)
    run(["--sizes", "5", "--repeats", "1"], tmp_path, capsys)
    assert mine.exists() and not (tmp_path / "result.timing.jsonl").exists()


def test_an_erroring_step_is_recorded_and_the_run_continues(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GEPHI_API_URL", SEPARATE)
    fake_gephi(monkeypatch, faults={
        "/statistics/pagerank": {"success": False, "error": "no memory"}})
    code, seen = run(["--sizes", "5", "--repeats", "2"], tmp_path, capsys)
    assert code == 0
    steps = json.loads((tmp_path / "result.json").read_text())["results"]["5"]
    assert steps["pagerank"]["ms"] == [] and steps["pagerank"]["median"] is None
    assert [e["error"] for e in steps["pagerank"]["errors"]] == ["no memory", "no memory"]
    assert len(steps["layout"]["ms"]) == 2 and len(steps["export_png"]["ms"]) == 2
    assert "error" in seen.out


def test_a_step_in_the_skip_table_is_listed_not_run(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GEPHI_API_URL", SEPARATE)
    monkeypatch.setitem(benchmark.SKIPS, 5, {"betweenness": "too slow at this size"})
    state = fake_gephi(monkeypatch)
    _, seen = run(["--sizes", "5", "--repeats", "1"], tmp_path, capsys)
    entry = json.loads((tmp_path / "result.json").read_text())["results"]["5"]["betweenness"]
    assert entry["skipped"] == "too slow at this size" and entry["ms"] == []
    assert not [c for c in state["calls"] if c[1] == "/statistics/betweenness"]
    assert "skipped" in seen.out


def _result(medians, spread):
    """A hand-made result: one size, one step per entry, ms values around the median."""
    return {"sizes": [100], "results": {"100": {
        step: {"ms": [m - spread, m, m + spread], "median": m, "min": m - spread,
               "max": m + spread, "errors": [], "skipped": None}
        for step, m in medians.items()}}}


def test_compare_flags_only_changes_larger_than_the_spread(tmp_path, capsys):
    old, new = tmp_path / "old.json", tmp_path / "new.json"
    old.write_text(json.dumps(_result({"slower": 100, "noise": 100, "faster": 100}, 5)))
    new.write_text(json.dumps(_result({"slower": 200, "noise": 108, "faster": 40}, 5)))
    assert benchmark.main(["--compare", str(old), str(new)]) == 0
    out = capsys.readouterr().out
    row = {line.split("|")[2].strip(): line for line in out.splitlines()
           if line.startswith("| 100")}
    assert "+100" in row["slower"] and "+100.0%" in row["slower"] and "real: slower" in row["slower"]
    assert "+8" in row["noise"] and "within noise" in row["noise"]
    assert "-60" in row["faster"] and "real: faster" in row["faster"]


def test_compare_needs_at_least_two_timings_per_run(tmp_path, capsys):
    one = {"sizes": [1], "results": {"1": {"s": {"ms": [10], "median": 10, "min": 10,
                                                  "max": 10, "errors": [], "skipped": None}}}}
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps(one))
    b.write_text(json.dumps(one))
    benchmark.main(["--compare", str(a), str(b)])
    assert "not enough repeats" in capsys.readouterr().out


def _generates(state):
    return sum(1 for c in state["calls"] if c[1] == "/graph/generate")


def test_a_warm_up_pass_runs_first_and_is_neither_timed_nor_logged(monkeypatch, tmp_path, capsys):
    """The first run on a freshly started Gephi is slower (the JVM is still compiling), which made
    unrelated steps look faster in every later run; one untimed pass at the smallest size first."""
    monkeypatch.setenv("GEPHI_API_URL", SEPARATE)
    state = fake_gephi(monkeypatch)
    code, _ = run(["--sizes", "30,20", "--repeats", "1"], tmp_path, capsys)
    assert code == 0
    assert _generates(state) == 3, "a warm-up pass at the smallest size, then one per size"
    data = json.loads((tmp_path / "result.json").read_text())
    assert data["warmup"] == {"size": 20, "repeats": 1}
    assert all(len(e["ms"]) == 1 for e in data["results"]["20"].values())
    log = (tmp_path / "result.timing.jsonl").read_text().splitlines()
    assert sum(json.loads(line)["tool"] == "gephi_generate_graph" for line in log) == 2


def test_the_warm_up_can_be_switched_off(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GEPHI_API_URL", SEPARATE)
    state = fake_gephi(monkeypatch)
    code, _ = run(["--sizes", "20", "--repeats", "1", "--no-warmup"], tmp_path, capsys)
    assert code == 0 and _generates(state) == 1
    assert json.loads((tmp_path / "result.json").read_text())["warmup"] is None
