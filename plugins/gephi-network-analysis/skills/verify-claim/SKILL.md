---
name: verify-claim
description: Independently verify one plain-language structural claim about the loaded Gephi graph and report confirmed, refuted, or can't-tell with measurements and live-graph receipts. Use for claims about centrality, connectivity, comparison, grouping, or robustness.
---

# Verify a Structural Claim

Verify one claim against the live graph. Independence is the point: do not try
to make the claim true; determine whether the graph supports it.

Read `../gephi/references/claim-verification.md` before choosing the method. If
the user did not provide a claim, ask for it in one sentence.

## Workflow

1. Call `gephi_health_check`. If it fails, tell the user to start Gephi and stop.
2. Preserve the claim verbatim and classify it as comparison, connectivity,
   centrality, grouping, or robustness.
3. Match the measurement to the claim's words:
   - comparison, such as "X is more central than Y": compute the named metric,
     then call `gephi_compare_nodes`;
   - connectivity: use `gephi_visual_qa` with the claimed grouping or count
     cross-group edges with a read-only filter;
   - importance: compute the metric the word implies—bridge means betweenness,
     reach may mean degree or PageRank—and rank the relevant nodes;
   - robustness: call `gephi_whatif`, which edits and deletes a scratch workspace
     while leaving the real graph unchanged.
4. If the claim is vague, measure the two or three plausible meanings and report
   them separately. Do not silently choose the result most favorable to the claim.
5. Choose exactly one verdict: `confirmed`, `refuted`, or `can't-tell`.

## Guardrails

- Give the actual number, not just a verdict.
- Never turn `can't-tell` into `refuted`.
- Flag small or skewed samples even when the measured result is confirmed.
- Computing statistic columns is allowed; recoloring, relayout, destructive
  filtering, and graph edits are not.
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
