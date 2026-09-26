# Compiling a plain-language filter into a Gephi filter

Someone says "show me only the nodes with degree at least 5," "just the giant
component," "the accounts where type is bot," "brokers between the two clusters."
Each is a filter. The job is to compile the request into the right Gephi filter
via `gephi_list_filters` (discover) + `gephi_apply_filter` (apply), the same
discover-then-run shape as `gephi_list_statistics` / `gephi_run_statistic`.

## The loop

1. **Discover.** Call `gephi_list_filters`. It returns every available filter —
   built-in topology filters (Degree Range, In/Out-Degree Range, K-core, Giant
   Component, Ego Network, Neighbors, Edge Weight, Mutual Edge, Has Self-loop, …)
   **plus a per-column attribute filter for every node/edge column currently in
   the graph**, named by kind and column, e.g. "Equal: group String (Node)",
   "Range: Degree Integer (Node)", "Non-null: email String (Node)". The
   attribute set is data-dependent, so always list against the actual graph
   rather than assuming a filter name exists.
2. **Match the intent to a filter and read its `properties`.** Each entry lists
   its settable properties with types. A `Range`-typed property takes a
   `[low, high]` pair.
3. **Apply** with `gephi_apply_filter(name, params, action, column)`.

## Choosing the action — this is the important decision

- **`select` (default)** — narrows the *visible* graph non-destructively (a
  GraphView; the underlying data is untouched, `gephi_reset_filters` restores
  it). Use for exploratory "show me…" filtering and for reading counts (the
  result reports nodes/edges before and after).
- **`new_workspace`** — materializes the filtered subgraph into a fresh
  workspace. **Prefer this whenever you'll filter repeatedly on a large graph.**
  A visible-only filter leaves the hidden elements resident in memory, so a
  chain of filters can grow memory unbounded; exporting to a new workspace and
  continuing there keeps only what survived. State that you're doing this and
  why.
- **`column`** — writes filter membership into a boolean column (name it via
  `column`) instead of hiding anything. Use when you want to *mark* matches to
  color or size by them afterward, keeping the whole graph visible.

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

Run it with `dry_run=True` first: the reply counts what
would stay and what would go, and nothing changes. Each filter in a combined
call judges the whole network, so "the giant component" there means the
network's own, not the largest component of what the other filters kept;
for that, apply the filters one after another as in the worked shape below.
Take filter and property names from `gephi_list_filters`, not from this
example. Say which logic you used; "these two
teams barely interact" verified by a filter is only as good as the filter that
stood for it (see claim-verification.md).

## Worked shape

> "Keep only the well-connected core — degree 5 or more, largest component."
>
> 1. `gephi_list_filters` → find "Degree Range" (property "range",
>    type Range) and "Giant Component" (no properties).
> 2. `gephi_apply_filter("Degree Range", {"range": [5, 9999]}, "select")`
>    → nodes_before 339, nodes_after 88.
> 3. `gephi_apply_filter("Giant Component", action="select")` → nodes_after 71.
> 4. Report: "Filtered to the degree-≥5 nodes in the giant component: 71 of 339
>    nodes remain. Non-destructive — `gephi_reset_filters` brings the rest back."

The filter did the narrowing; the counts and the honest framing are the analysis.
