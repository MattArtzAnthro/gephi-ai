# Verifying a structural claim against the graph

Someone asserts something about a network in plain language — "these two teams
barely interact," "she's more central than he is," "the group would fall apart
without him," "these accounts form a tight cluster." Each of these is a
*checkable* claim: it maps to a measurement the graph can either support or
refute with a number. This is the general form of what `gephi_visual_qa`
already does for one specific claim (is a proposed grouping topologically
real?) — the same discipline applies to any structural assertion.

The method is always the same three moves: **classify the claim → run the
matching measurement → report confirmed / refuted / can't-tell, with the
number.** Do not narrate a verdict before the measurement has run.

## Classify the claim, then measure

| The claim sounds like… | Measure it with | The number that settles it |
|---|---|---|
| "X is more [central / connected / important] than Y" | `gephi_compare_nodes(x, y, metric)` after computing that statistic | which node's value is higher, and by how much |
| "these two groups barely interact" / "A and B are separate worlds" | `gephi_visual_qa` with `partition_column` set to the grouping | within-group edge share vs. the mixed-baseline (strong / weak / none) |
| "she's the key connector / bridge" | compute betweenness (`gephi_compute_betweenness`), then rank | where the named node sits in the betweenness ranking |
| "he's the most important / active" | compute degree or the relevant centrality, then rank | the node's rank on that metric |
| "the group survives losing him" / "removing X fragments everything" | `gephi_whatif` removing X | delta in components, giant-component share, avg path length |
| "these accounts form a natural cluster" | `gephi_visual_qa` with `partition_column` = the proposed grouping | the partition truth-test verdict |

The measurement tools already exist; the work is picking the right one and
reading its number honestly. `gephi_compare_nodes` and `gephi_whatif` are the
two purpose-built for this — the first for two-entity comparisons, the second
for "what would happen if…" robustness claims — but a plain statistic + rank
answers most centrality/importance claims.

## The metric has to match the word

"Central," "important," "key," and "connected" are not one metric. Pick the
one the claim actually means, and say which you used:

- **"connected / active / talked-about most"** → degree (raw tie count).
- **"the bridge / the connector / routes between groups"** → betweenness
  (sits on shortest paths between others). A node can be high-degree but
  low-betweenness (popular within one cluster, bridges nothing) or the reverse
  (few ties, but the only link between two halves). Conflating them is the most
  common way a centrality claim gets mis-verified.
- **"influential / well-connected to the well-connected"** → eigenvector or
  PageRank.

If the claim is vague ("she's central"), measure the two or three that could
plausibly be meant and report where the node lands on each — the claim may be
true on one and false on another, which is itself the honest answer.

## Report confirmed, refuted, or can't-tell — with the number

Three outcomes, not two. The discipline `gephi_visual_qa` uses ("if the
verdict is none, coloring by it would mislead") generalizes:

- **Confirmed** — the measurement supports the claim. Give the number, not just
  the verdict: "confirmed — her betweenness is 22,013 vs. his 15, so she does
  sit on far more shortest paths."
- **Refuted** — the measurement contradicts the claim. Say so plainly and give
  the number that does it: "refuted — the two teams share 34% of their edges
  cross-group, well above what separate groups would show; they interact more
  than the claim assumes."
- **Can't tell from this data** — distinct from refuted, and the one most often
  skipped. The graph can't speak to the claim when: the required statistic
  isn't computed yet (compute it first, don't guess); the sample is too small
  or skewed for the number to mean anything; the claim is about something the
  graph doesn't encode (intent, causation, offline ties). Say which. "Can't
  tell — this graph has 18 nodes; a robustness claim about removing one won't
  generalize."

Never upgrade "can't tell" into "refuted," and never let a confirmed
measurement on a small or skewed graph read as a strong finding — a
`gephi_whatif` diff or a single centrality comparison on a tiny or unrepresentative
network can mislead exactly the way any single sample can. Pair a surprising
verdict with a check: does the number survive on the giant component only? does
it hold if you recompute after pruning weak ties? A claim worth verifying is
worth a second look before it travels.

## Worked shape

> Claim: "Losing the family node would fragment the whole network."
>
> 1. Classify → robustness claim → `gephi_whatif` removing `family`.
> 2. Run it: components 1 → 1, giant-component share 1.0 → 0.98, avg path
>    length 4.4 → 4.6.
> 3. Report: "Refuted — removing `family` leaves the network in one component
>    (giant share 0.98, essentially intact) and lengthens the average path only
>    slightly (4.4 → 4.6). It's a well-connected node, but the network routes
>    around its absence rather than fragmenting."

The tool returned the numbers; the verdict and its honesty are the analysis.
