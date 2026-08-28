---
description: Independently verify a plain-language claim about the current graph (confirmed / refuted / can't-tell, with the number)
argument-hint: "\"<the claim>\" [export-path.json]"
allowed-tools: Task
---

# Verify a structural claim

Dispatch the **claim-verifier** agent to check the claim in `$ARGUMENTS` against the
graph currently loaded in Gephi.

The agent runs in its own context (so its measurement runs don't clutter this
conversation) and, importantly, verifies **independently** — it is not invested in
the claim being true. It returns a verdict: **confirmed / refuted / can't-tell**,
with the actual number and an honest caveat.

Pass the claim verbatim, and the export path if one was given (the agent passes it
to `gephi_claim_record`, which writes the record as JSON for a methods appendix). If
`$ARGUMENTS` is empty, ask the user what claim they want checked (one sentence), then
dispatch.

When the agent returns, relay the record plainly: the verdict, the metric and the
numbers, the evidence nodes by label, and whether the receipts were verified against
the live graph. Don't soften a "refuted" or a "can't-tell." If the record says
`verified: false`, say so and do not present the numbers as checked.
