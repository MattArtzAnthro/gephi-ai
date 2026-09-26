---
name: verify-claim
description: Independently verify one plain-language structural claim about the loaded Gephi graph and report confirmed, refuted, or cannot tell with measurements and live-graph receipts. Use for claims about centrality, connectivity, comparison, grouping, or robustness.
---

# Verify a Structural Claim

Verify one claim against the live graph. Independence is the point: do not try
to make the claim true; determine whether the graph supports it.

Follow the `gephi` skill's rules throughout; this workflow repeats only the ones
it is most likely to break. Read `../gephi/references/claim-verification.md`
before choosing the method.

## Rules this workflow must keep

- **Asking.** When a step says to ask, ask once. If the person cannot answer, is away, or asked for a finished product, use the default named in that step, remove or overwrite nothing, and list each choice under "Choices I made". If there is no input to work on, stop and say what is needed.
- **Session start.** Start with `gephi_health_check`. Then check which workspace is open (`gephi_list_workspaces`) and whether a filter is active (`filter_active` in replies): a filter from an earlier conversation stays on, and exports and checks then see only what it shows.
- **Ranking.** To rank nodes on a metric, call `gephi_query_nodes` with `column` set to the metric and `min` set to a cutoff, with `limit` 20 or less, and raise or lower the cutoff until about ten nodes match (`matches` gives the total). A large `limit` returns every column of every node and can overflow.
- **Stability.** Run `gephi_community_stability` before naming, captioning, or colouring by groups, and say how stable they are.

## Workflow

1. Call `gephi_health_check`. If it fails, tell the user to start Gephi and stop.
   Call `gephi_list_workspaces`; if `filter_active` is true, the verdict covers
   only the visible nodes, and the caveat says so.
2. If the user did not provide a claim, ask for it in one sentence. There is no
   default claim: without one, stop and say what is needed.
3. Preserve the claim verbatim and classify it as comparison, connectivity,
   centrality, grouping, robustness, paths, or change over time.
4. Match the measurement to the claim's words:
   - comparison, such as "X is more central than Y": compute the named metric,
     then call `gephi_compare_nodes`;
   - connectivity: use `gephi_visual_qa` with the claimed grouping, or count
     cross-group edges with `gephi_query_edges`;
   - importance: compute the metric the word implies (bridge means betweenness,
     reach may mean degree or PageRank) and rank the relevant nodes with the
     ranking rule. Gephi's eigenvector centrality can rank nodes differently from
     a standard calculation, so never rest a verdict on it alone; compare it with
     PageRank;
   - grouping, such as "these accounts form a tight cluster": compute
     modularity, then `gephi_community_stability`; a group that does not stay
     together across runs is not a tight cluster;
   - robustness: call `gephi_whatif`, which edits and deletes a scratch workspace
     while leaving the real graph unchanged. Also remove the next comparable node,
     and credit the effect to X only if it clearly exceeds that comparison;
   - paths, such as "A reaches B only through C": call `gephi_find_shortest_path`;
     one direct tie refutes "only through C"; `equally_short_paths` above 1 means
     C is not the only route, and `gephi_whatif` removing C shows whether any path
     survives;
   - change over time: slice each period with `gephi_time_slice`, run the same
     statistic in each, switch back to the original workspace, and name the
     windows in the verdict;
   - counts under several conditions: `gephi_apply_filters` with `dry_run: true`
     counts without hiding anything.
5. If the claim is vague, measure the two or three plausible meanings and report
   them separately. Do not silently choose the result most favorable to the claim.
6. Choose exactly one verdict: `confirmed`, `refuted`, or `cant_tell`.

## Guardrails

- Give the actual number, not just a verdict.
- Never turn `cant_tell` into `refuted`.
- Flag small or skewed samples even when the measured result is confirmed.
- Computing statistic columns is allowed; recoloring, relayout, filtering, and
  graph edits are not. Use `gephi_apply_filters` only with `dry_run: true`.
- Never assert scale-free or power-law structure from a heavy tail.

## Verified Record

Call `gephi_claim_record` with the verbatim claim, classification, verdict,
metric or node column, every supporting node ID, the values read for those nodes,
other numeric evidence, the caveat, and an export path when requested. The tool
re-reads the live graph and checks the receipts.

If the result says `verified: false`, remeasure and call it again. Do not present
unverified numbers as checked.

Return the structured record, its caption, and one clear sentence stating the
verdict, metric, evidence, and caveat. Keep working notes out of the handoff.
