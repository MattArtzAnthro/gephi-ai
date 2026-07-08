---
description: Independently verify a plain-language claim about the current graph (confirmed / refuted / can't-tell, with the number)
argument-hint: "\"<the claim>\", e.g. \"she is more central than he is\""
allowed-tools: Task
---

# Verify a structural claim

Dispatch the **claim-verifier** agent to check the claim in `$ARGUMENTS` against the
graph currently loaded in Gephi.

The agent runs in its own context (so its measurement runs don't clutter this
conversation) and, importantly, verifies **independently** — it is not invested in
the claim being true. It returns a verdict: **confirmed / refuted / can't-tell**,
with the actual number and an honest caveat.

Pass the claim verbatim. If `$ARGUMENTS` is empty, ask the user what claim they want
checked (one sentence), then dispatch. When the agent returns, relay its verdict and
the number plainly — don't soften a "refuted" or a "can't-tell."
