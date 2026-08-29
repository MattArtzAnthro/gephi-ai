---
description: Test a hypothetical edit against the loaded graph without touching it — "what would happen if I removed this node?"
argument-hint: "<plain-language what-if question>, e.g. \"what if I removed the top 3 hubs?\""
allowed-tools: mcp__gephi-mcp__*
---

# Counterfactual test

Answer `$ARGUMENTS` by running it as a real measurement against the graph currently
loaded in Gephi, using `gephi_whatif`. It duplicates the current workspace, applies
the edit to the copy, diffs the structural profile before/after, then deletes the
copy — the real graph is never touched, so this is safe to run repeatedly.

If `$ARGUMENTS` is empty, ask what edit they want to test (one sentence is enough:
"what if we removed the top hub?", "what if these two accounts stopped talking?").

## Steps

1. **Health check**: `gephi_health_check`. If it fails, tell the user to start Gephi
   and stop.

2. **Resolve the edit.** Turn the plain-language question into `gephi_whatif`'s edit
   list (`remove_node`, `remove_nodes`, `add_edge`, `remove_edge`). If the person
   names nodes by label rather than id ("the top hub", "Alice"), resolve the id first
   — `gephi_query_nodes` for a name/rank lookup, `gephi_compute_degree` or the
   existing profile if "top hub" needs a metric to rank by. Confirm which node(s) you
   resolved to before running the edit if there's any ambiguity.

3. **Run `gephi_whatif`** with the resolved edits. Only pass `include_slow: true`
   (diffs average path length / diameter too) if the graph is roughly under 3k nodes
   — same cost gate as `gephi_profile_graph`.

4. **Report the diff**, not a verdict. `gephi_whatif` returns measurements, and the
   framing matters:
   - Lead with the numbers that changed and by how much (components, giant-component
     share, density, modularity, isolates, path length if computed).
   - This is a hypothesis test, not a conclusion — say what the delta does and does
     not support, and note the same caution that applies to any single sample: a
     counterfactual on a small or skewed graph, or a single removed node standing in
     for a whole category, can mislead.
   - Offer a rival read where one exists (e.g. "components jumped because this
     specific hub is also a cut vertex, not because hubs in general hold the network
     together — want to test a second one to check?").

5. **Remind them nothing changed.** The scratch copy is already deleted and they're
   back on their real graph — if they want to make the edit for real, point them at
   the direct tool (`gephi_remove_node`, `gephi_add_edge`, etc.), which is protected
   by `gephi_snapshot`/`gephi_undo`.
