---
description: Independently verify a plain-language claim about the current graph (confirmed / refuted / cannot tell, with the number)
argument-hint: "\"<the claim>\" [export-path.json]"
allowed-tools: Agent, Task, Skill
---

# Verify a structural claim

Check the claim in `$ARGUMENTS` against the graph currently loaded in Gephi.

## Rules this command must keep

- **Asking.** When a step says to ask, ask once. If the person cannot answer, is away, or asked for a finished product, use the default named in that step, remove or overwrite nothing, and list each choice under "Choices I made". If there is no input to work on, stop and say what is needed.

## Steps

1. **Load the gephi skill first.** Before any Gephi call, load the `gephi-network-analysis:gephi` skill. Its rules apply to every step below; this command repeats only the ones it is most likely to break.

2. **Get the claim.** If `$ARGUMENTS` is empty, ask the user what claim they want
   checked (one sentence). There is no default claim: without one, stop and say
   what is needed.

3. **Dispatch the claim-verifier agent** with the claim verbatim, and the export
   path if one was given (the agent passes it to `gephi_claim_record`, which writes
   the record as JSON for a methods appendix). The agent runs in its own context
   (so its measurement runs do not clutter this conversation) and, importantly,
   verifies **independently**: it is not invested in the claim being true. It
   follows `${CLAUDE_PLUGIN_ROOT}/skills/gephi/references/claim-verification.md` and
   returns a verdict (**confirmed / refuted / cannot tell**) with the actual number
   and an honest caveat.

4. **Relay the record plainly**: the verdict, the metric and the numbers, the
   evidence nodes by label, and whether the receipts were verified against the live
   graph. Do not soften a "refuted" or a "cannot tell". If the record says
   `verified: false`, say so and do not present the numbers as checked. If the
   agent reported an active filter, say that the verdict covers only the visible
   nodes.
