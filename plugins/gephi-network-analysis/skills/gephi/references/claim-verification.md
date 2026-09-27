# Verifying a structural claim against the graph

Someone asserts something about a network in plain language: "these two teams
barely interact," "she is more central than he is," "the group would fall
apart without him," "these accounts form a tight cluster." Each of these is a
*checkable* claim: it maps to a measurement the graph can either support or
refute with a number. This is the general form of what `gephi_visual_qa`
already does for one specific claim (is a proposed grouping real in the
network's ties?), and the same discipline applies to any structural assertion.

The method is always the same three moves: **classify the claim, run the
matching measurement, and report confirmed, refuted, or cannot tell, with the
number.** Do not narrate a verdict before the measurement has run.

## Classify the claim, then measure

| The claim sounds like | Measure it with | The number that settles it |
|---|---|---|
| "X is more [central / connected / important] than Y" | `gephi_compare_nodes(x, y, metric)` after computing that statistic | which node's value is higher, and by how much |
| "these two groups barely interact" / "A and B are separate worlds" | `gephi_visual_qa` with `partition_column` set to the grouping | within-group edge share against the random baseline (strong, weak, or none) |
| "she is the key connector / bridge" | compute betweenness (`gephi_compute_betweenness`), then rank | where the named node sits in the betweenness ranking |
| "he is the most important / active" | compute degree or the relevant centrality, then rank | the node's rank on that metric |
| "the group survives losing him" / "removing X fragments everything" | `gephi_whatif` removing X, and separately the next comparable node (see removal tests below) | change in components, giant-component share, average path length |
| "A can only reach B through C" / "C is the link between them" | `gephi_find_shortest_path(a, b)`, then `gephi_whatif` removing C | `equally_short_paths` (above 1: other routes of the same length exist) and whether a path survives without C |
| "group A reaches group B only through C" | the group-level path below | whether any cross-group path survives without C |
| "they are only a few steps apart" / "these two are far apart" | `gephi_find_shortest_path(a, b)` | `steps` (and `length` when weights are distances), against the network's average path length |
| "the network grew / fragmented after X" | slice before and after with `gephi_time_slice`, same statistics in each (see change-over-time.md) | the per-period numbers, with the windows named |
| "these accounts form a natural cluster" | `gephi_visual_qa` with `partition_column` set to the proposed grouping | the partition verdict |

The measurement tools already exist; the work is picking the right one and
reading its number honestly. `gephi_compare_nodes` and `gephi_whatif` are the
two built for this: the first for comparing two nodes, the second for "what
would happen if" robustness claims. A plain statistic and a ranking answer most
centrality and importance claims.

## The metric has to match the word

"Central," "important," "key," and "connected" are not one metric. Pick the
one the claim actually means, and say which you used:

- **"connected / active / talked-about most"**: degree (the raw count of ties).
- **"the bridge / the connector / routes between groups"**: betweenness (how
  often a node sits on the shortest paths between others). A node can be
  high-degree but low-betweenness (popular within one cluster, bridging
  nothing) or the reverse (few ties, but the only link between two halves).
  Conflating them is the most common way a centrality claim gets mis-verified.
- **"influential / well-connected to the well-connected"**: PageRank, checked
  against eigenvector centrality. Do not rank on eigenvector centrality alone
  (see statistics-guide.md).

If the claim is vague ("she is central"), measure the two or three that could
plausibly be meant and report where the node lands on each. The claim may be
true on one and false on another, which is itself the honest answer.

## Groups the graph has no column for

A claim often names groups the data does not record: "the founders," "the
outside consultants," "the Paris office." Before measuring, write down who was
counted in each group and why. Then:

- **Find every named member before calling anyone absent.** Names in a graph are
  often spelled differently from the claim. Search on part of the name
  (`gephi_query_nodes` with `column: "label"` and `contains`), and try the
  usual variants (accents dropped, a letter added or missing, surname first).
  Say someone is not in the graph only after those searches come back empty.
- **Rerun with the borderline members moved.** Put each doubtful member in the
  other group, or leave them out, and measure again. A verdict that flips when
  one or two people move is a verdict about the grouping, not the network; say
  so.
- **Check direct ties first.** Before any path or mixing measure, look for
  edges running straight from one group to the other (`gephi_query_edges`, or a
  filter on the two groups). One direct tie refutes "A reaches B only through
  C."
- Once the groups are settled, write them to a column (`gephi_add_column`, then
  `gephi_batch_set_node_attributes`) so every later measurement uses the same
  membership.

## Removal tests: compare with the next comparable node

A removal almost always changes something, so the change alone does not show
that X matters. Also remove the next comparable node: the one just below X on
the same measure (the next-highest degree or betweenness, say), in its own
`gephi_whatif` run. The effect belongs to X only if it clearly exceeds that
comparison. When the two changes are close, report that the network depends on
nodes of that rank, not on X in particular.

## "Only through C" at the group level

To test whether group A reaches group B only through C, work on a copy so the
person's graph is never changed:

1. `gephi_duplicate_workspace` on the current workspace, and work in the copy.
2. `gephi_remove_node` on C in the copy.
3. `gephi_find_shortest_path` for several pairs, each with one node in A and one
   in B. Pick pairs from different parts of each group, not only the
   best-connected members.
4. `gephi_delete_workspace` on the copy, and confirm the original is the open
   workspace again (`gephi_list_workspaces`).

If any pair still finds a path, the claim is refuted; give the path. If none
does, the claim holds for the pairs checked; name how many were checked.

## Report confirmed, refuted, or cannot tell, with the number

Three outcomes, not two. The discipline `gephi_visual_qa` uses ("if the
verdict is none, coloring by it would mislead") applies to every claim:

- **Confirmed**: the measurement supports the claim. Give the number, not just
  the verdict: "Confirmed: her betweenness is 22,013 and his is 15, so she sits
  on far more shortest paths."
- **Refuted**: the measurement contradicts the claim. Say so plainly and give
  the number that does it: "Refuted: 34% of the two teams' ties cross between
  them, well above what separate groups would show; they interact more than the
  claim assumes."
- **Cannot tell from this data**: distinct from refuted, and the outcome most
  often skipped. The graph cannot speak to the claim when the required
  statistic has not been computed yet (compute it first, never guess); when the
  sample is too small or skewed for the number to mean anything; or when the
  claim is about something the graph does not encode (intent, cause, offline
  ties). Say which. "Cannot tell: this graph has 18 nodes, so a robustness claim
  about removing one will not generalize."

Never upgrade "cannot tell" into "refuted," and never let a confirmed
measurement on a small or skewed graph read as a strong finding: a
`gephi_whatif` diff or a single centrality comparison on a tiny or
unrepresentative network can mislead exactly the way any single sample can.
Pair a surprising verdict with a check: does the number survive on the giant
component only? Does it hold after pruning weak ties and recomputing? A claim
worth verifying is worth a second look before it travels.

## Worked shape

> Claim: "Losing the family node would fragment the whole network."
>
> 1. Classify: a robustness claim, so `gephi_whatif` removing `family`, and a
>    second run removing the node just below it in degree.
> 2. Run it: removing `family` leaves components at 1, moves the giant-component
>    share from 1.0 to 0.98 and the average path length from 4.4 to 4.6. The
>    comparison node moves them about as much.
> 3. Report: "Refuted. Removing `family` leaves the network in one component
>    (giant share 0.98, essentially intact) and lengthens the average path only
>    slightly (4.4 to 4.6), about as much as removing the next most connected
>    node. It is a well-connected node, but the network routes around its
>    absence rather than fragmenting."

The tool returned the numbers; the verdict and its honesty are the analysis.
