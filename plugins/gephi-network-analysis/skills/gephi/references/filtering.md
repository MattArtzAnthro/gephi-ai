# Compiling a plain-language filter into a Gephi filter

Someone says "show me only the nodes with degree at least 5," "just the giant
component," "the accounts where type is bot," "brokers between the two
clusters." Each is a filter. The job is to compile the request into the right
Gephi filter with `gephi_list_filters` (discover) and `gephi_apply_filter`
(apply), the same discover-then-run shape as `gephi_list_statistics` and
`gephi_run_statistic`.

`gephi_apply_filter` and `gephi_apply_filters` hide nodes and change nothing; `gephi_reset_filters` shows them again. Pass `dry_run` to count what a filter would hide or remove before running it. The remove and extract tools delete, keep one undo level, and have no redo; for an experiment, duplicate the workspace first.

## The loop

1. **Discover.** Call `gephi_list_filters`. It returns every available filter:
   built-in topology filters (Degree Range, In/Out-Degree Range, K-core, Giant
   Component, Ego Network, Neighbors, Edge Weight, Mutual Edge, Has Self-loop,
   and more) **plus a per-column attribute filter for every node and edge column
   currently in the graph**, named by kind and column, for example "Equal: group
   String (Node)", "Range: Degree Integer (Node)", "Non-null: email String
   (Node)". The attribute set depends on the data, so always list against the
   actual graph rather than assuming a filter name exists.
2. **Match the intent to a filter and read its `properties`.** Each entry lists
   its settable properties with types. A `Range`-typed property takes a
   `[low, high]` pair.
3. **Count first.** `gephi_apply_filter(name, params, dry_run=True)` reports
   what would stay and what would go, and changes nothing. Tell the person what
   the filter will hide.
4. **Apply** with `gephi_apply_filter(name, params, action, column)`.

## Choosing the action: this is the important decision

- **`select` (default)** narrows the *visible* graph without changing the data
  (Gephi keeps the full graph underneath, and `gephi_reset_filters` shows it
  again). Use it for exploratory "show me" filtering and for reading counts
  (the reply reports nodes and edges before and after).
- **`new_workspace`** copies the filtered subgraph into a fresh workspace.
  **Prefer this whenever you will filter repeatedly on a large graph.** A
  visible-only filter leaves the hidden elements in memory, so a chain of
  filters can grow memory without limit; exporting to a new workspace and
  continuing there keeps only what survived. Say that you are doing this and
  why.
- **`column`** writes filter membership into a true/false column (name it with
  `column`) instead of hiding anything. Use it to *mark* matches for colouring
  or sizing afterwards while the whole graph stays visible.

## A select filter stays on

A `select` filter is saved with the workspace. It stays on after the analysis
moves on, and into the next conversation that opens the same Gephi session.
While it is on, exports, `gephi_visual_qa`, `gephi_profile_graph`, and other
checks read only the visible graph, so a map or a number can silently describe
a subset. Replies carry `filter_active` when a filter is on. At the start of a
session, and before any export or final check, look for it; call
`gephi_reset_filters` when the whole graph is meant, or say in the caption
which filter was applied.

## Filters that delete

`gephi_filter_by_degree` and `gephi_filter_by_edge_weight` do not hide: they
delete the nodes or edges outside the range. Both take `dry_run=True` to count
first, and a real run takes an undo snapshot automatically, so `gephi_undo`
restores the graph as it was (one level, no redo). `gephi_reset_filters` does
not bring deleted elements back. For a filter that leaves the data intact, use
`gephi_apply_filter` with `select` or `new_workspace`.

## AND / OR / NOT

`gephi_apply_filters` combines several filters in one call: `combine="all"`
keeps what every filter keeps (AND), `combine="any"` what at least one keeps
(OR), and `"exclude": true` on a filter keeps the opposite of what it would
keep alone (NOT). "Country is Peru or Chile":

```
gephi_apply_filters(filters=[
    {"name": "Equal: Country String (Node)", "params": {"pattern": "Peru"}},
    {"name": "Equal: Country String (Node)", "params": {"pattern": "Chile"}}], combine="any")
```

Run it with `dry_run=True` first: the reply counts what would stay and what
would go, and nothing changes. Each filter in a combined call judges the whole
network, so "the giant component" there means the network's own, not the
largest component of what the other filters kept; for that, apply the filters
one after another as in the worked shape below. Take filter and property names
from `gephi_list_filters`, not from this example. Say which logic you used:
"these two teams barely interact" verified by a filter is only as good as the
filter that stood for it (see claim-verification.md).

## Worked shape

> "Keep only the well-connected core: degree 5 or more, largest component."
>
> 1. `gephi_list_filters` finds "Degree Range" (property "range", type Range)
>    and "Giant Component" (no properties).
> 2. `gephi_apply_filter("Degree Range", {"range": [5, 9999]}, dry_run=True)`
>    counts 88 of 339 nodes kept; the person agrees.
> 3. `gephi_apply_filter("Degree Range", {"range": [5, 9999]}, "select")`:
>    nodes_before 339, nodes_after 88.
> 4. `gephi_apply_filter("Giant Component", action="select")`: nodes_after 71.
> 5. Report: "Filtered to the nodes of degree 5 or more in the giant component:
>    71 of 339 nodes remain. Nothing was deleted; `gephi_reset_filters` brings
>    the rest back. The filter stays on until it is reset, so exports show
>    only these 71."

The filter did the narrowing; the counts and the honest framing are the
analysis.
