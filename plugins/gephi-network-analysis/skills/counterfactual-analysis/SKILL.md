---
name: counterfactual-analysis
description: Test a hypothetical edit against the loaded Gephi graph without changing the real workspace. Use for what-if questions such as removing hubs, adding ties, deleting ties, or comparing structural resilience.
---

# Counterfactual test

Answer the user's what-if question by running it as a real measurement against the graph currently
loaded in Gephi, using `gephi_whatif`. It duplicates the current workspace, applies
the edit to the copy, compares the structural profile before and after, then deletes
the copy. The real graph is never touched, so this is safe to run repeatedly.

Follow the `gephi` skill's rules throughout; this workflow repeats only the ones
it is most likely to break.
Read `../gephi/references/claim-verification.md` for
removal tests and their comparison node.

## Rules this workflow must keep

- **Asking.** When a step says to ask, ask once. If the person cannot answer, is away, or asked for a finished product, use the default named in that step and remove or overwrite nothing. At the end, give one short line for each choice that changed the result, under "Choices I made"; leave the section out when every step used its obvious default. If there is no input to work on, stop and say what is needed.
- **Session start.** Start with `gephi_health_check`. Then check which workspace is open (`gephi_list_workspaces`) and whether a filter is active (`filter_active` in replies): a filter from an earlier conversation stays on, and exports and checks then see only what it shows.
- **Ranking.** To rank nodes on a metric, call `gephi_query_nodes` with `sort_by` set to the metric, `columns` set to the few columns you need, and `limit` about 10: nodes are ordered before paging, so the first page is the top of the whole graph. Without `columns`, every attribute of every node comes back and a long listing can overflow.

## Steps

1. **Session start**: `gephi_health_check`. If it fails, tell the user to start Gephi
   and stop. Call `gephi_list_workspaces`; if `filter_active` is true, say the test
   runs on the visible nodes only.

2. **Get the question.** If the request does not specify an edit, ask what edit they want to test
   (one sentence is enough: "what if we removed the top hub?", "what if these two
   accounts stopped talking?"). Default: remove the single highest-degree node.

3. **Resolve the edit.** Turn the plain-language question into `gephi_whatif`'s edit
   list (`{"op": "remove_node", "id": ...}`, `remove_nodes`, `add_edge`,
   `remove_edge`). If the person names nodes by label rather than id ("the top
   hub", "Alice"), resolve the id first: `gephi_query_nodes` with `column` and
   `value` or `contains` for a name, or with the ranking rule for "top hub"
   (`gephi_compute_degree` first if the `degree` column is missing). If the name
   matches more than one node, ask which one. Default: the match with the highest
   degree, named in the report.

4. **Run `gephi_whatif`** with the resolved edits. Only pass `include_slow: true`
   (which also compares average path length and diameter) if the graph is roughly
   under 3,000 nodes, the same cost gate as `gephi_profile_graph`.

5. **Report the difference**, not a verdict. `gephi_whatif` returns measurements, and
   the framing matters:
   - Lead with the numbers that changed and by how much (components, giant-component
     share, density, modularity, isolates, path length if computed).
   - This is a hypothesis test, not a conclusion. Say what the change does and does
     not support, and note the caution that applies to any single sample: a
     counterfactual on a small or skewed graph, or a single removed node standing in
     for a whole category, can mislead.
   - Offer a rival reading where one exists (for example, "components jumped because
     this specific hub is also a cut vertex, not because hubs in general hold the
     network together. Should I test a second one to check?").
   - Add "Choices I made" only for choices that changed the result.

6. **Remind them nothing changed.** The scratch copy is already deleted and they are
   back on their real graph. If they want to make the edit for real, point them at
   the direct tool (`gephi_remove_node`, `gephi_add_edge`, and so on), which
   `gephi_snapshot` and `gephi_undo` protect.
