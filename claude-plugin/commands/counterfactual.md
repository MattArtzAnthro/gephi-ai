---
description: Alias of /whatif — test a hypothetical edit against the loaded graph without touching it (counterfactual graph surgery)
argument-hint: "<plain-language what-if question>, e.g. \"what if these two communities merged?\""
allowed-tools: mcp__gephi-mcp__*
---

# Counterfactual test (alias of /whatif)

Same command as `/whatif`, kept under this name because "counterfactual" is the
vocabulary used in the paper for this capability. Follow the exact procedure in
`commands/whatif.md`: health check, resolve `$ARGUMENTS` into an edit for
`gephi_whatif`, run it against a scratch copy of the graph, then report the diff as
a hypothesis test, not a verdict — never as a conclusion, always with the caution
that a single counterfactual edit can mislead the same way any single sample can.
