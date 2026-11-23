# Formal models

Machine-checked models of the parts of the MCP server where a wrong step loses a graph or
misreports what was done. They check the models, not the Python; each model names the code it
follows, and the tests listed below hold the code to it.

## Run

```bash
bash formal/check.sh        # Lean: build, no sorry, standard axioms only
bash formal/tla/check.sh    # TLA+: every row against its expected result (TRACES=1 prints counterexamples)
```

Lean 4.36.0, unpacked from the GitHub release into `~/.local/lean/` (or set `LEAN_LAKE` to
its `lake`). TLC needs Java 11 or later and `tla2tools.jar` 1.7.4 at
`~/.local/share/tla/tla2tools.jar` (or set `TLA_JAR`). Neither runs in `scripts/check.sh` or CI.

## What is modelled

| Model | Code | Proves or checks |
|---|---|---|
| `GephiModel/Endpoints.lean` | `stats_integrity.mutates_graph`, `replaces_graph` | A call that replaces the graph always counts as changing it, so the methods record is never left describing a replaced graph; a GET never does either; an unlisted path counts as a change. |
| `GephiModel/Snapshot.lean` | `gephi_mcp._new_copy_id` | The workspace taken for a duplicate's copy is never the original, never one that existed before, and is in the list just read. |
| `GephiModel/Ledger.lean` | `session_ledger.Ledger` | One legend item per channel; a change of graph starts an empty record and keeps at most 20 earlier ones; a reset channel leaves the legend. |
| `tla/Workspace.tla` | undo snapshot, `gephi_undo`, `gephi_whatif`, `gephi_compare_workspaces` | Undo removes only the snapshot's source; the record describes the workspace on screen; no change lands on a workspace other than the one on screen at the call. |
| `tla/Layout.tla` | `gephi_run_layout`, `gephi_stop_layout` | The record and a sync call's result say "stopped" exactly for a stopped layout. |
| `tla/ReadGate.tla` | `_one_at_a_time`, `_ReadGate` | No read runs while a what-if or compare has switched workspaces; the gate always reopens. |

`mcp-server/tests/test_formal_conformance.py` holds the Python prefix tuples to the Lean lists.
`mcp-server/tests/test_workspace_and_layout_guards.py` has one test per TLA+ guard; each fails
with its guard removed.

## When to run

Run both scripts after a change to: the endpoint prefix tuples in `stats_integrity.py`; the
snapshot, undo, what-if or `_read_graph` code; `gephi_run_layout` or `gephi_stop_layout`; the tool
lock or read gate; `session_ledger.py`. Change the model in the same commit as the code.

In `tla/check.sh`, a `current` row sets every guard as the server has it. A row with a guard off
must FAIL: it shows the guard is needed. A row that changes result without a reason is a
regression in the model or the code.

## Limits

- A snapshot edited while it is the workspace on screen is restored as edited
  (`UndoRestores`, expected FAIL).
- Gephi's stop answer does not name the layout it stopped. A stop answered after the next
  layout began is counted against that one (`Layout current`, 2 runs, expected FAIL). It needs
  a stop and a run sent at the same time.
- Changes made by hand in the Gephi window are outside every model.
- The numeric modules (`partition_match.py`, `community_stability.py`, `graph_diff.py`,
  `bipartite.py`) and the Java plugin are not modelled.
